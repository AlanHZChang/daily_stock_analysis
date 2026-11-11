# -*- coding: utf-8 -*-
"""Tests for name_to_code_resolver.

Covers:
- Local mapping (STOCK_NAME_MAP reverse)
- Code format boundary (_is_code_like, _normalize_code)
- Pinyin match (when pypinyin available)
- AkShare fallback (mocked)
- Fuzzy match (difflib)
- Ambiguous names return None
- Stock dataclass / resolver_name_to_code_list / US_stock_code_match / extend_AkShare
"""

import threading
import time
from typing import Optional
from unittest.mock import patch

import pandas as pd
import pytest

from src.data.stock_mapping import STOCK_NAME_MAP
from src.services import name_to_code_resolver as ntc
from src.services.name_to_code_resolver import (
    Stock,
    resolve_name_to_code,
    resolver_name_to_code_list,
    US_stock_code_match,
    _is_code_like,
    _normalize_code,
    _build_reverse_map_no_duplicates,
)


@pytest.fixture()
def clean_db(request):
    """Isolate the global stockDB/caches; the AkShare fetch is mocked offline
    by default. Parametrize with ``indirect=True`` to inject a fake map."""
    fake_map = getattr(request, "param", None)
    with patch.object(ntc, "_get_akshare_name_to_code", return_value=fake_map):
        yield
    # 恢復用歸一後的本地映射（與模塊初值同構，見 _normalize_stock_name）
    ntc.stockDB.clear()
    ntc.stockDB.update(
        {c: ntc._normalize_stock_name(n) for c, n in STOCK_NAME_MAP.items()}
    )
    ntc._names_cache[:] = [None, None, None]
    ntc._pinyin_cache[:] = [None, None]
    ntc._akshare_merged = None
    ntc._akshare_cache = None
    ntc._akshare_failure_cache = None
    ntc._akshare_inflight = None
    ntc.stockAliases.clear()


# ---------------------------------------------------------------------------
# _is_code_like
# ---------------------------------------------------------------------------

class TestIsCodeLike:
    def test_a_share_5_digits(self):
        assert _is_code_like("60051") is True
        assert _is_code_like("600519") is True

    def test_a_share_6_digits(self):
        assert _is_code_like("300750") is True

    def test_bse_with_exchange_hint(self):
        assert _is_code_like("920493.BJ") is True
        assert _is_code_like("BJ920493") is True

    def test_bj_exchange_hint_rejects_non_bse_code(self):
        assert _is_code_like("600519.BJ") is False
        assert _is_code_like("BJ600519") is False

    def test_hk_5_digits(self):
        assert _is_code_like("00700") is True

    def test_us_stock_letters(self):
        assert _is_code_like("AAPL") is True
        assert _is_code_like("TSLA") is True
        assert _is_code_like("BRK.B") is True

    def test_rejects_non_code(self):
        assert _is_code_like("贵州茅台") is False
        assert _is_code_like("1234") is False  # too short
        assert _is_code_like("1234567") is False  # too long
        assert _is_code_like("") is False
        assert _is_code_like("   ") is False


# ---------------------------------------------------------------------------
# _normalize_code
# ---------------------------------------------------------------------------

class TestNormalizeCode:
    def test_preserves_valid_a_share(self):
        assert _normalize_code("600519") == "600519"
        assert _normalize_code("  600519  ") == "600519"

    def test_strips_suffix(self):
        assert _normalize_code("600519.SH") == "600519"
        assert _normalize_code("000001.SZ") == "000001"
        assert _normalize_code("920493.BJ") == "920493"

    def test_strips_bse_prefix(self):
        assert _normalize_code("BJ920493") == "920493"

    def test_bj_exchange_hint_rejects_non_bse_code(self):
        assert _normalize_code("600519.BJ") is None
        assert _normalize_code("BJ600519") is None

    def test_preserves_us_stock(self):
        assert _normalize_code("AAPL") == "AAPL"
        assert _normalize_code("brk.b") == "BRK.B"

    def test_returns_none_for_invalid(self):
        assert _normalize_code("") is None
        assert _normalize_code("1234") is None
        assert _normalize_code("贵州茅台") is None


# ---------------------------------------------------------------------------
# _build_reverse_map_no_duplicates
# ---------------------------------------------------------------------------

class TestBuildReverseMapNoDuplicates:
    def test_excludes_ambiguous_names(self):
        # "阿里巴巴" maps to both BABA and 09988
        code_to_name = {"BABA": "阿里巴巴", "09988": "阿里巴巴", "600519": "贵州茅台"}
        result = _build_reverse_map_no_duplicates(code_to_name)
        assert "阿里巴巴" not in result
        assert result.get("贵州茅台") == "600519"

    def test_includes_unique_names(self):
        code_to_name = {"600519": "贵州茅台", "00700": "腾讯控股"}
        result = _build_reverse_map_no_duplicates(code_to_name)
        assert result["贵州茅台"] == "600519"
        assert result["腾讯控股"] == "00700"


# ---------------------------------------------------------------------------
# resolve_name_to_code
# ---------------------------------------------------------------------------

class TestResolveNameToCode:
    def test_code_like_input_returned_normalized(self):
        assert resolve_name_to_code("600519") == "600519"
        assert resolve_name_to_code("600519.SH") == "600519"
        assert resolve_name_to_code("920493.BJ") == "920493"
        assert resolve_name_to_code("  AAPL  ") == "AAPL"

    def test_local_map_exact_match(self):
        assert resolve_name_to_code("贵州茅台") == "600519"
        assert resolve_name_to_code("腾讯控股") == "00700"

    @patch("src.services.name_to_code_resolver._get_akshare_name_to_code")
    def test_local_hit_does_not_trigger_akshare(self, mock_akshare):
        # 本地表精確命中必須零網絡：既有調用方（API/Bot/導入）保持
        # 離線低延遲契約，不被 AkShare 冷啟動等待拖住。
        assert resolve_name_to_code("贵州茅台") == "600519"
        assert resolve_name_to_code("腾讯控股") == "00700"
        mock_akshare.assert_not_called()

    @patch("src.services.name_to_code_resolver._get_akshare_name_to_code")
    def test_local_hit_wins_over_akshare_same_name(self, mock_akshare):
        # 兼容性契約：本地表唯一命中的名字直接返回本地代碼，不做跨市場
        # 合併判定（中國移動：本地僅港股 00941，AkShare 有同名 A 股 600941）。
        # 完整跨市場候選由 resolver_name_to_code_list 提供。
        mock_akshare.return_value = {"中国移动": "600941"}
        assert resolve_name_to_code("中国移动") == "00941"
        mock_akshare.assert_not_called()

    def test_returns_none_for_empty_or_invalid_input(self):
        assert resolve_name_to_code("") is None
        assert resolve_name_to_code("   ") is None
        assert resolve_name_to_code(None) is None  # type: ignore

    def test_ambiguous_name_returns_none(self):
        # "阿里巴巴" maps to both BABA and 09988 in STOCK_NAME_MAP
        assert resolve_name_to_code("阿里巴巴") is None

    @patch("src.services.name_to_code_resolver._get_akshare_name_to_code")
    def test_akshare_fallback_when_not_in_local(self, mock_akshare):
        mock_akshare.return_value = {"平安银行": "000001"}
        # 000001 is in local map as 平安銀行, so we use a name that's only in akshare
        # Actually local has 000001 -> 平安銀行. So "平安銀行" would hit local first.
        # Use a name not in STOCK_NAME_MAP - e.g. some A-share only in AkShare
        mock_akshare.return_value = {"浦发银行": "600000"}
        result = resolve_name_to_code("浦发银行")
        assert result == "600000"
        mock_akshare.assert_called()

    @patch("src.services.name_to_code_resolver._get_akshare_name_to_code")
    def test_fuzzy_match_fallback(self, mock_akshare):
        mock_akshare.return_value = {"贵州茅台": "600519"}
        # Typo: 貴州茅苔 -> should fuzzy match 貴州茅臺
        result = resolve_name_to_code("贵州茅苔")
        assert result == "600519"

    @patch("src.services.name_to_code_resolver._get_akshare_name_to_code")
    def test_returns_none_when_no_match(self, mock_akshare):
        mock_akshare.return_value = {}
        result = resolve_name_to_code("不存在的股票名称xyz")
        assert result is None

    @patch("src.services.name_to_code_resolver._get_akshare_name_to_code")
    def test_skips_akshare_for_non_cjk_garbage_input(self, mock_akshare):
        result = resolve_name_to_code("aaaaaaa")
        assert result is None
        mock_akshare.assert_not_called()

    @pytest.mark.parametrize("clean_db", [{"三一重能": "688349"}], indirect=True)
    def test_akshare_exact_fallback_beats_fuzzy_for_non_local_name(self, clean_db):
        # 本地未收錄的 CJK 名稱：AkShare 精確命中（第 4 步）優先於模糊
        # 匹配（第 5 步），"三一重能" 不會被誤配到相近的 三一重工。
        assert resolve_name_to_code("三一重能") == "688349"


# ---------------------------------------------------------------------------
# Stock dataclass
# ---------------------------------------------------------------------------

class TestStock:
    def test_fields(self):
        s = Stock(code="600519", name="贵州茅台", market="a")
        assert (s.code, s.name, s.market) == ("600519", "贵州茅台", "a")

    def test_value_equality(self):
        assert Stock("600519", "贵州茅台", "a") == Stock("600519", "贵州茅台", "a")
        assert Stock("600519", "贵州茅台", "a") != Stock("00700", "腾讯控股", "hk")


# ---------------------------------------------------------------------------
# resolver_name_to_code_list
# ---------------------------------------------------------------------------

class TestResolverNameToCodeList:
    @pytest.mark.usefixtures("clean_db")
    def test_exact_match(self):
        assert resolver_name_to_code_list("贵州茅台") == [Stock("600519", "贵州茅台", "a")]

    @pytest.mark.usefixtures("clean_db")
    def test_exact_match_cross_market_sorted(self):
        # 阿里巴巴 in STOCK_NAME_MAP: BABA (us) + 09988 (hk) → hk before us
        assert resolver_name_to_code_list("阿里巴巴") == [
            Stock("09988", "阿里巴巴", "hk"),
            Stock("BABA", "阿里巴巴", "us"),
        ]

    @pytest.mark.usefixtures("clean_db")
    def test_substring_match(self):
        assert resolver_name_to_code_list("茅台") == [Stock("600519", "贵州茅台", "a")]

    @pytest.mark.usefixtures("clean_db")
    def test_pinyin_substring_match(self):
        # Non-CJK input: resolved locally via pinyin, without AkShare fetch
        assert resolver_name_to_code_list("maotai") == [Stock("600519", "贵州茅台", "a")]

    @pytest.mark.usefixtures("clean_db")
    def test_cjk_fragment_skips_pinyin_layer(self):
        # 迴歸：CJK 片段不得走拼音子串層。"平果"拼音 pingguo 與蘋果全名
        # 拼音完全相撞，預修復會經策略 3 誤命中蘋果；CJK 片段的拼音粒度
        # 失控（實義字+助詞轉拼音後可與不相干全名碰撞，如"阿里的"→
        # "alide" ⊂ "zhongdalide" 中大力德），僅 ASCII 拼音輸入走該層。
        assert resolver_name_to_code_list("平果") == []

    @pytest.mark.usefixtures("clean_db")
    def test_fuzzy_typo_match(self):
        assert resolver_name_to_code_list("贵州茅苔") == [Stock("600519", "贵州茅台", "a")]

    @pytest.mark.usefixtures("clean_db")
    def test_no_match_returns_empty(self):
        assert resolver_name_to_code_list("你好世界") == []

    @pytest.mark.usefixtures("clean_db")
    def test_invalid_input_returns_empty(self):
        assert resolver_name_to_code_list("") == []
        assert resolver_name_to_code_list(None) == []  # type: ignore
        assert resolver_name_to_code_list("茅") == []  # single char is never a name

    @pytest.mark.parametrize("clean_db", [{"浦发银行": "600000"}], indirect=True)
    def test_akshare_extension_visible_after_retry(self, clean_db):
        # Exact match against the AkShare-extended database
        assert resolver_name_to_code_list("浦发银行") == [Stock("600000", "浦发银行", "a")]


    @pytest.mark.parametrize("clean_db", [{"阿里巴巴": "600000"}], indirect=True)
    def test_local_exact_hit_still_merges_akshare_same_name_a_share(self, clean_db):
        # 本地已有同名港股/美股時，AkShare 中的同名 A 股也必須被併入。
        ntc.stockDB.clear()
        ntc.stockDB.update({"09988": "阿里巴巴", "BABA": "阿里巴巴"})
        ntc._names_cache[:] = [None, None, None]
        ntc._pinyin_cache[:] = [None, None]
        ntc._akshare_merged = None
        ntc.stockAliases.clear()
        assert resolver_name_to_code_list("阿里巴巴") == [
            Stock("600000", "阿里巴巴", "a"),
            Stock("09988", "阿里巴巴", "hk"),
            Stock("BABA", "阿里巴巴", "us"),
        ]

    @pytest.mark.parametrize("clean_db", [{"阿里巴巴": "600000"}], indirect=True)
    def test_local_single_candidate_gets_a_share_candidate_after_akshare_merge(self, clean_db):
        # 本地只有單一市場記錄時，AkShare 補齊同名 A 股後候選變完整。
        ntc.stockDB.clear()
        ntc.stockDB.update({"09988": "阿里巴巴"})
        ntc._names_cache[:] = [None, None, None]
        ntc._pinyin_cache[:] = [None, None]
        ntc._akshare_merged = None
        ntc.stockAliases.clear()
        assert resolver_name_to_code_list("阿里巴巴") == [
            Stock("600000", "阿里巴巴", "a"),
            Stock("09988", "阿里巴巴", "hk"),
        ]

class TestCompactLookupInputs:
    """查詢側同源壓平：帶內嵌空格的"源形態"輸入（如自 AkShare 數據複製的
    "五 糧 液"）與常規無空格拼寫同樣可解析——入庫壓平後查詢入口若只做
    首尾 strip，源形態輸入會在精確/子串/模糊全部層級落空。"""

    @pytest.mark.parametrize("clean_db", [{"五 粮 液": "000858"}], indirect=True)
    def test_spaced_input_resolves_via_list(self, clean_db):
        ntc.extend_AkShare()
        assert resolver_name_to_code_list("五 粮 液") == [
            Stock("000858", "五粮液", "a")
        ]

    @pytest.mark.parametrize("clean_db", [{"五 粮 液": "000858"}], indirect=True)
    def test_spaced_input_is_known_name(self, clean_db):
        ntc.extend_AkShare()
        assert ntc.is_known_stock_name("五 粮 液") is True

    def test_spaced_input_resolves_legacy(self):
        # 本地映射已有無空格拼寫：legacy 入口對帶空格輸入同樣命中
        assert resolve_name_to_code("五 粮 液") == "000858"


# ---------------------------------------------------------------------------
# US_stock_code_match
# ---------------------------------------------------------------------------

class TestUSStockCodeMatch:
    def test_known_ticker(self):
        assert US_stock_code_match("AAPL") == [Stock("AAPL", "苹果", "us")]
        assert US_stock_code_match("aapl") == [Stock("AAPL", "苹果", "us")]

    def test_unknown_word_returns_empty(self):
        assert US_stock_code_match("HELLO") == []  # ordinary English word
        assert US_stock_code_match("TOOLONGTICKER") == []
        assert US_stock_code_match("贵州茅台") == []


# ---------------------------------------------------------------------------
# extend_AkShare
# ---------------------------------------------------------------------------

class TestExtendAkShare:
    @pytest.mark.parametrize("clean_db", [{"浦发银行": "600000"}], indirect=True)
    def test_merges_new_entries_idempotently(self, clean_db):
        assert ntc.extend_AkShare() is True
        assert ntc.stockDB["600000"] == "浦发银行"
        # Same cached map object is not merged twice
        assert ntc.extend_AkShare() is False

    @pytest.mark.parametrize("clean_db", [{"贵州茅台": "600519"}], indirect=True)
    def test_no_new_entries_returns_false(self, clean_db):
        # All entries already in the local database
        assert ntc.extend_AkShare() is False

    @pytest.mark.usefixtures("clean_db")
    def test_fetch_failure_returns_false(self):
        assert ntc.extend_AkShare() is False


    @pytest.mark.parametrize("clean_db", [{"新名称": "600000"}], indirect=True)
    def test_rename_existing_code_updates_canonical_name_and_keeps_alias(self, clean_db):
        ntc.stockDB.clear()
        ntc.stockDB.update({"600000": "旧名称"})
        ntc._names_cache[:] = [None, None, None]
        ntc._pinyin_cache[:] = [None, None]
        ntc._akshare_merged = None
        ntc.stockAliases.clear()
        assert ntc.extend_AkShare() is True
        assert ntc.stockDB["600000"] == "新名称"
        assert ntc.stockAliases["600000"] == {"旧名称"}
        # 新名稱作為當前官方名稱可解析
        assert resolver_name_to_code_list("新名称") == [Stock("600000", "新名称", "a")]
        # 舊名稱作為別名仍然可解析，且展示當前官方名稱
        assert resolver_name_to_code_list("旧名称") == [Stock("600000", "新名称", "a")]


class TestCompactStockNameMerge:
    """AkShare 名稱內嵌空白壓平：stockDB 只存無空格拼寫。

    帶空格名稱（"五 糧 液"）與本地無空格拼寫（"五粮液"）語義相同：
    壓平後比較相等 → 不觸發假性改名/別名；全名精確匹配對常規輸入可見。
    """

    @pytest.mark.parametrize("clean_db", [{"五 粮 液": "600000"}], indirect=True)
    def test_spaced_akshare_name_compacted(self, clean_db):
        # 600000 不在本地映射：新條目以壓平拼寫寫入（000858 本地已有、
        # 壓平後相等屬"無變更"路徑，見下一條用例）
        assert ntc.extend_AkShare() is True
        assert ntc.stockDB["600000"] == "五粮液"

    @pytest.mark.parametrize("clean_db", [{"五 粮 液": "000858"}], indirect=True)
    def test_spaced_name_vs_local_no_spurious_alias(self, clean_db):
        # 本地已有無空格拼寫：壓平後相等，不得製造假性別名/假性改名
        ntc.stockDB.clear()
        ntc.stockDB.update({"000858": "五粮液"})
        ntc._names_cache[:] = [None, None, None]
        ntc._akshare_merged = None
        ntc.stockAliases.clear()
        assert ntc.extend_AkShare() is False
        assert ntc.stockDB["000858"] == "五粮液"
        assert "000858" not in ntc.stockAliases

    @pytest.mark.parametrize("clean_db", [{"五 粮 液": "000858"}], indirect=True)
    def test_spaced_name_exact_match_after_merge(self, clean_db):
        # 壓平後的規範名對常規無空格輸入整名可見（含 Step 3 精確匹配口徑）
        ntc.extend_AkShare()
        assert ntc.is_known_stock_name("五粮液") is True
        assert resolver_name_to_code_list("五粮液") == [Stock("000858", "五粮液", "a")]

    @pytest.mark.parametrize(
        "clean_db", [{"   ": "600000", "万  科Ａ": "000002"}], indirect=True
    )
    def test_whitespace_only_name_skipped(self, clean_db):
        # 壓平後為空的名稱條目跳過，不寫入空串；"萬  科Ａ" 歸一後為
        # "萬科A"（NFKC 寬度歸一 + 去空白）
        assert ntc.extend_AkShare() is True
        assert ntc.stockDB["000002"] == "万科A"
        assert "600000" not in ntc.stockDB or ntc.stockDB["600000"] != ""


class TestStockNameWidthNormalization:
    """庫名寬度歸一（_normalize_stock_name = NFKC + 去空白）：源數據的
    全角拼寫（AkShare "京東方Ａ"、磁盤緩存歷史數據）與 NFKC 歸一後的
    用戶輸入（"京東方A"）必須同源同變換——否則全名精確匹配落空，且會被
    更短的庫內名誤切（"京东"）。"""

    @pytest.mark.parametrize("clean_db", [{"京东方Ａ": "000725"}], indirect=True)
    def test_akshare_fullwidth_name_normalized_on_merge(self, clean_db):
        # 合併入口歸一：全角Ａ名稱以半角拼寫寫入 stockDB
        assert ntc.extend_AkShare() is True
        assert ntc.stockDB["000725"] == "京东方A"

    @pytest.mark.parametrize("clean_db", [{"京东方Ａ": "000725"}], indirect=True)
    def test_fullwidth_and_halfwidth_queries_both_resolve(self, clean_db):
        ntc.extend_AkShare()
        # 查詢入口同源歸一：全角/半角輸入皆可解析，展示名統一為歸一拼寫
        assert ntc.resolver_name_to_code_list("京东方A") == [
            Stock("000725", "京东方A", "a")
        ]
        assert ntc.resolver_name_to_code_list("京东方Ａ") == [
            Stock("000725", "京东方A", "a")
        ]
        assert ntc.is_known_stock_name("京东方Ａ") is True

    @pytest.mark.parametrize("clean_db", [{"京东方A": "000725"}], indirect=True)
    def test_legacy_fullwidth_input_resolves(self, clean_db):
        # legacy 入口查詢歸一（生產緩存側名稱經 _build_name_map_from_df
        # 已歸一，mock 按生產形態給出半角鍵）
        assert ntc.resolve_name_to_code("京东方Ａ") == "000725"

    def test_local_name_indexes_normalized(self):
        # 構建器內部歸一：全角拼寫輸入的索引鍵為半角
        unique, ambiguous = ntc._build_local_name_indexes({"000725": "京东方Ａ"})
        assert unique == {"京东方A": "000725"}
        assert ambiguous == set()

    @pytest.mark.usefixtures("real_akshare_path")
    def test_disk_cache_names_normalized_on_load(self):
        # 磁盤緩存裡的歷史未歸一名稱：加載即歸一（零網絡，落盤時間戳新鮮）
        import json
        import time as time_mod

        ntc._akshare_disk_checked = False
        ntc._AKSHARE_DISK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ntc._AKSHARE_DISK_CACHE_PATH.write_text(
            json.dumps(
                {"ts": time_mod.time(), "map": {"京东方Ａ": "000725"}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        assert ntc._get_akshare_name_to_code() == {"京东方A": "000725"}

# ---------------------------------------------------------------------------
# AkShare 單飛併發：真實 _get_akshare_name_to_code + _fetch_akshare_df 假拉取
# ---------------------------------------------------------------------------


class _FakeAkShareFetch:
    """確定性的 _fetch_akshare_df 替身。

    每次調用先置位 fetch_started（證明拉取已在後臺線程開始），再阻塞在
    release_fetch 上——測試據此精確控制拉取窗口，不依賴 sleep 計時。
    """

    def __init__(self, fail: bool = False, rows: Optional[dict] = None):
        self.fetch_started = threading.Event()
        self.release_fetch = threading.Event()
        self.fail = fail
        self.rows = rows or {"code": ["600000"], "name": ["浦发银行"]}
        self.calls = 0

    def fetch(self):
        self.calls += 1
        self.fetch_started.set()
        # 30s 兜底：用例邏輯正確時總會在收尾前 set，防自身缺陷掛死線程
        self.release_fetch.wait(timeout=30)
        if self.fail:
            raise RuntimeError("simulated akshare failure")
        return pd.DataFrame(self.rows)


@pytest.fixture()
def real_akshare_path(monkeypatch, tmp_path):
    """復位 AkShare 拉取相關全局態，走真實 _get_akshare_name_to_code 路徑。

    磁盤緩存指向臨時路徑：既隔離倉庫 data/cache 下的真實文件，也讓
    落盤/懶加載用例可以安全讀寫。
    """
    saved = (
        ntc._akshare_cache,
        ntc._akshare_failure_cache,
        ntc._akshare_merged,
        ntc._akshare_inflight,
        ntc._akshare_disk_checked,
    )
    ntc._akshare_cache = None
    ntc._akshare_failure_cache = None
    ntc._akshare_merged = None
    ntc._akshare_inflight = None
    ntc._akshare_disk_checked = False
    monkeypatch.setattr(ntc, "_AKSHARE_DISK_CACHE_PATH", tmp_path / "akshare_name_map.json")
    yield monkeypatch
    # 等待在途刷新收尾（正常用例在 finally 裡已 release，這裡毫秒級通過），
    # 避免遲到的 worker 把緩存寫進下一個用例
    deadline = time.time() + 5
    while ntc._akshare_inflight is not None and time.time() < deadline:
        time.sleep(0.05)
    ntc._akshare_cache, ntc._akshare_failure_cache, ntc._akshare_merged = saved[:3]
    ntc._akshare_inflight, ntc._akshare_disk_checked = saved[3:]
    ntc.stockDB.clear()
    ntc.stockDB.update(
        {c: ntc._normalize_stock_name(n) for c, n in STOCK_NAME_MAP.items()}
    )
    ntc._names_cache[:] = [None, None, None]
    ntc._pinyin_cache[:] = [None, None]
    ntc.stockAliases.clear()


def _run_resolver_in_thread(query: str):
    """在 daemon 線程裡執行解析，捕獲返回值/異常。"""
    outcome = {}

    def _worker():
        try:
            outcome["value"] = ntc.resolver_name_to_code_list(query)
        except BaseException as exc:  # noqa: BLE001 - 線程異常兜底
            outcome["error"] = exc

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t, outcome


def _wait_until(condition, timeout: float = 5.0) -> bool:
    """有界輪詢等待條件成立（後臺刷新收尾是確定性事件，僅耗時不定）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


class TestAkShareSingleFlightConcurrency:
    @pytest.mark.usefixtures("real_akshare_path")
    def test_waiter_resolves_after_inflight_fetch_completes(self, monkeypatch):
        fake = _FakeAkShareFetch()
        monkeypatch.setattr(ntc, "_fetch_akshare_df", fake.fetch)

        t1, r1 = _run_resolver_in_thread("浦发银行")
        t2 = None
        try:
            assert fake.fetch_started.wait(timeout=5)
            t2, r2 = _run_resolver_in_thread("浦发银行")
            # 舊實現（非阻塞放棄）在此窗口內立即返回空結果；新實現持續等待
            t2.join(timeout=2)
            # 釋放前兩個線程必須仍在等待（而非已帶空結果返回）——漏解 bug 的核心
            assert t1.is_alive() and t2.is_alive()
        finally:
            fake.release_fetch.set()
            t1.join(timeout=10)
            if t2 is not None:
                t2.join(timeout=10)
        assert not t1.is_alive() and not t2.is_alive()
        # 等待者命中在途拉取的結果（本 bug 的核心斷言），且全進程只拉取一次
        assert r1.get("value") == [Stock("600000", "浦发银行", "a")]
        assert r2.get("value") == [Stock("600000", "浦发银行", "a")]
        assert fake.calls == 1

    @pytest.mark.usefixtures("real_akshare_path")
    def test_waiter_returns_empty_after_inflight_failure_and_no_refetch(self, monkeypatch):
        fake = _FakeAkShareFetch(fail=True)
        monkeypatch.setattr(ntc, "_fetch_akshare_df", fake.fetch)

        t1, r1 = _run_resolver_in_thread("浦发银行")
        t2 = None
        try:
            assert fake.fetch_started.wait(timeout=5)
            t2, r2 = _run_resolver_in_thread("浦发银行")
            t2.join(timeout=2)
        finally:
            fake.release_fetch.set()
            t1.join(timeout=10)
            if t2 is not None:
                t2.join(timeout=10)
        assert not t1.is_alive() and not t2.is_alive()
        # 在途拉取失敗：等待者醒來命中失敗退避（而非重試風暴），本地空庫返回 []
        assert r1.get("value") == []
        assert r2.get("value") == []
        assert fake.calls == 1
        assert ntc._akshare_failure_cache is not None

    @pytest.mark.usefixtures("real_akshare_path")
    def test_cold_waiters_degrade_after_timeout_but_fetch_lands(self, monkeypatch):
        # worker 違約（超清賬餘量仍未 resolve）時的兜底路徑：等待者按死線
        # 自行降級，後臺拉取不受影響仍單次完成落地
        monkeypatch.setattr(ntc, "_AKSHARE_WAIT_COLD_START", 0.2)
        fake = _FakeAkShareFetch()
        monkeypatch.setattr(ntc, "_fetch_akshare_df", fake.fetch)

        t1, r1 = _run_resolver_in_thread("浦发银行")
        t2 = None
        try:
            assert fake.fetch_started.wait(timeout=5)
            t2, r2 = _run_resolver_in_thread("浦发银行")
            # 拉取持續掛起時，所有冷啟動等待者（含觸發拉取的那一個）都必須
            # 在超時上界內自行返回，而非無限等待
            t1.join(timeout=10)
            t2.join(timeout=10)
            # 必須在放行抓取前確認兩個等待者均已降級；僅等待 t2 不能
            # 保證 t1 已返回，否則 finally 放行後 t1 可能拿到成功結果。
            assert not t1.is_alive() and not t2.is_alive()
            assert r1.get("value") == []
            assert r2.get("value") == []
        finally:
            fake.release_fetch.set()
            t1.join(timeout=10)
            if t2 is not None:
                t2.join(timeout=10)
        assert not t1.is_alive() and not t2.is_alive()
        # 後臺拉取不受等待者超時影響，仍單次完成
        assert fake.calls == 1
        assert _wait_until(
            lambda: ntc._akshare_cache is not None
            and ntc._akshare_cache[1] == {"浦发银行": "600000"}
        )
        # 拉取落地後，後續請求立即命中新緩存
        assert ntc.resolver_name_to_code_list("浦发银行") == [Stock("600000", "浦发银行", "a")]

    @pytest.mark.usefixtures("real_akshare_path")
    def test_slow_persist_does_not_delay_waiter_wakeup(self, monkeypatch):
        # 喚醒在落盤之前：慢磁盤不得拖住等待者拿結果（緩存已就緒、
        # 等待者卻超時漏解曾是真實迴歸）
        fake = _FakeAkShareFetch()
        monkeypatch.setattr(ntc, "_fetch_akshare_df", fake.fetch)
        release_persist = threading.Event()
        monkeypatch.setattr(
            ntc, "_persist_akshare_map", lambda map_: release_persist.wait(timeout=30)
        )

        t1, r1 = _run_resolver_in_thread("浦发银行")
        try:
            assert fake.fetch_started.wait(timeout=5)
            fake.release_fetch.set()
            # 拉取完成即喚醒並返回，不等落盤
            t1.join(timeout=5)
            assert not t1.is_alive()
            assert r1.get("value") == [Stock("600000", "浦发银行", "a")]
            assert not release_persist.is_set()  # 落盤仍掛著，等待者已返回
        finally:
            release_persist.set()
            t1.join(timeout=10)

    @pytest.mark.usefixtures("real_akshare_path")
    def test_base_exception_still_clears_inflight_and_arms_backoff(self, monkeypatch):
        # finally 兜底：BaseException（如 KeyboardInterrupt/SystemExit）逃逸
        # 時也必須清在途句柄、武裝退避並喚醒等待者，不留死句柄
        class _Bomb(BaseException):
            pass

        def bomb():
            raise _Bomb

        # 接管 excepthook：既靜音 worker 死亡時的未處理異常輸出，又給出
        # "worker 已帶著 _Bomb 死亡"的確定性信號（不依賴全局線程狀態，
        # 避免被其他用例洩漏的後臺刷新線程干擾）
        hook_calls: list = []
        monkeypatch.setattr(threading, "excepthook", lambda args: hook_calls.append(args))
        monkeypatch.setattr(ntc, "_fetch_akshare_df", bomb)
        t1, r1 = _run_resolver_in_thread("浦发银行")
        t1.join(timeout=10)
        assert not t1.is_alive()
        assert _wait_until(lambda: hook_calls)  # worker 已觸發 excepthook
        assert r1.get("value") == []  # 等待者被 finally 喚醒後拿到 None
        assert ntc._akshare_inflight is None  # 無死句柄
        assert ntc._akshare_failure_cache is not None  # 退避已武裝
        assert ntc._get_akshare_name_to_code() is None  # 退避窗口內不再觸網


# ---------------------------------------------------------------------------
# Stale-while-revalidate：TTL 過期必須立即返回舊值（零等待），刷新在後臺
# 完成；網絡故障的退避窗口內舊值繼續服務（可用性），僅冷啟動才退化。
# ---------------------------------------------------------------------------


class TestAkShareStaleWhileRevalidate:
    @pytest.mark.usefixtures("real_akshare_path")
    def test_stale_served_immediately_while_refresh_inflight(self, monkeypatch):
        # 先用立即返回的假拉取把緩存填充為 v1
        primed = {"浦发银行": "600000"}

        def fetch_v1():
            return pd.DataFrame({"code": ["600000"], "name": ["浦发银行"]})

        monkeypatch.setattr(ntc, "_fetch_akshare_df", fetch_v1)
        assert ntc._get_akshare_name_to_code() == primed
        # 強制過期：時間戳撥回 TTL 之前
        ntc._akshare_cache = (time.time() - ntc._AKSHARE_CACHE_TTL - 10, primed)

        # 換成阻塞版拉取（v2：600000 改名為 新名稱銀行）
        fake = _FakeAkShareFetch(rows={"code": ["600000"], "name": ["新名称银行"]})
        monkeypatch.setattr(ntc, "_fetch_akshare_df", fake.fetch)

        started = time.monotonic()
        result = ntc._get_akshare_name_to_code()
        elapsed = time.monotonic() - started
        try:
            # 核心斷言：stale 值立即返回，沒有等待在途拉取
            assert result == primed
            assert elapsed < 2
            # 後臺刷新確實已發起且尚未完成（fake 仍被掛起）
            assert fake.fetch_started.wait(timeout=5)
            assert not fake.release_fetch.is_set()
        finally:
            fake.release_fetch.set()
        # 刷新收尾後新緩存可見，且全進程只拉取一次
        v2 = {"新名称银行": "600000"}
        assert _wait_until(lambda: ntc._akshare_cache is not None and ntc._akshare_cache[1] == v2)
        assert fake.calls == 1
        assert ntc._get_akshare_name_to_code() == v2

    @pytest.mark.usefixtures("real_akshare_path")
    def test_backoff_window_serves_stale_during_outage(self, monkeypatch):
        # 預熱緩存 v1 並強制過期
        primed = {"浦发银行": "600000"}

        def fetch_ok():
            return pd.DataFrame({"code": ["600000"], "name": ["浦发银行"]})

        monkeypatch.setattr(ntc, "_fetch_akshare_df", fetch_ok)
        assert ntc._get_akshare_name_to_code() == primed
        ntc._akshare_cache = (time.time() - ntc._AKSHARE_CACHE_TTL - 10, primed)

        # 換成立即失敗的拉取：第一次 stale 調用會發起後臺刷新並失敗
        calls = {"n": 0}

        def fetch_fail():
            calls["n"] += 1
            raise RuntimeError("simulated outage")

        monkeypatch.setattr(ntc, "_fetch_akshare_df", fetch_fail)
        assert ntc._get_akshare_name_to_code() == primed  # 故障期間舊值仍可用
        assert _wait_until(lambda: ntc._akshare_failure_cache is not None)
        # 退避窗口內再次調用：繼續服務 stale，且不再發起新的拉取
        assert ntc._get_akshare_name_to_code() == primed
        assert calls["n"] == 1


# ---------------------------------------------------------------------------
# 磁盤緩存：成功拉取後原子落盤；重啟（全局態復位）後懶加載，零網絡。
# ---------------------------------------------------------------------------


class TestAkShareDiskCache:
    @pytest.mark.usefixtures("real_akshare_path")
    def test_persist_and_reload_without_network(self, monkeypatch):
        def fetch_ok():
            return pd.DataFrame({"code": ["600000"], "name": ["浦发银行"]})

        monkeypatch.setattr(ntc, "_fetch_akshare_df", fetch_ok)
        assert ntc._get_akshare_name_to_code() == {"浦发银行": "600000"}
        assert _wait_until(lambda: ntc._AKSHARE_DISK_CACHE_PATH.is_file())

        # 模擬重啟：內存態全部復位，磁盤保留
        ntc._akshare_cache = None
        ntc._akshare_failure_cache = None
        ntc._akshare_disk_checked = False

        never = _FakeAkShareFetch()
        monkeypatch.setattr(ntc, "_fetch_akshare_df", never.fetch)
        # 懶加載直接命中（落盤時間戳新鮮），全程零網絡
        assert ntc._get_akshare_name_to_code() == {"浦发银行": "600000"}
        assert never.calls == 0

    @pytest.mark.usefixtures("real_akshare_path")
    def test_corrupt_disk_cache_ignored(self, monkeypatch):
        ntc._AKSHARE_DISK_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        ntc._AKSHARE_DISK_CACHE_PATH.write_text("not-a-json{", encoding="utf-8")

        calls = {"n": 0}

        def fetch_ok():
            calls["n"] += 1
            return pd.DataFrame({"code": ["600000"], "name": ["浦发银行"]})

        monkeypatch.setattr(ntc, "_fetch_akshare_df", fetch_ok)
        # 損壞的磁盤緩存被忽略，正常走冷啟動拉取
        assert ntc._get_akshare_name_to_code() == {"浦发银行": "600000"}
        assert calls["n"] == 1


# ---------------------------------------------------------------------------
# 預熱：冪等——併發/重複調用共享同一在途句柄，只觸發一次網絡拉取。
# ---------------------------------------------------------------------------


class TestWarmupIdempotent:
    @pytest.mark.usefixtures("real_akshare_path")
    def test_double_warmup_shares_single_fetch(self, monkeypatch):
        fake = _FakeAkShareFetch()
        monkeypatch.setattr(ntc, "_fetch_akshare_df", fake.fetch)

        ntc.warmup_akshare_cache()
        assert fake.fetch_started.wait(timeout=5)  # 在途句柄已登記
        ntc.warmup_akshare_cache()  # 第二次：共享 Future，不再拉取
        fake.release_fetch.set()

        assert _wait_until(
            lambda: ntc._akshare_cache is not None
            and ntc._akshare_cache[1] == {"浦发银行": "600000"}
        )
        assert fake.calls == 1


# ---------------------------------------------------------------------------
# 掛起（非失敗）場景：子進程超時包裝以 TimeoutError 拋出後，必須走
# 常規失敗路徑武裝退避，而非無限持有單飛鎖。
# ---------------------------------------------------------------------------


class TestAkShareHangBackoff:
    @pytest.mark.usefixtures("real_akshare_path")
    def test_timeout_error_arms_failure_backoff(self, monkeypatch):
        calls = []

        def hang():
            calls.append(1)
            # 與 _akshare_call_with_timeout 超時拋出的異常同型
            raise TimeoutError("stock_info_a_code_name 调用超过 25s，已放弃等待")

        monkeypatch.setattr(ntc, "_fetch_akshare_df", hang)
        assert ntc._get_akshare_name_to_code() is None
        assert ntc._akshare_failure_cache is not None  # 退避已武裝
        # 退避窗口內再次解析：命中失敗緩存快路徑，不再觸網
        assert ntc._get_akshare_name_to_code() is None
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# _fetch_akshare_df 接線：必須經子進程超時包裝調用 worker（掛起封頂）。
# ---------------------------------------------------------------------------


class TestFetchAkshareDfWiring:
    def test_delegates_to_subprocess_timeout_wrapper(self, monkeypatch):
        import data_provider.akshare_fetcher as af

        captured = {}

        def fake_wrapper(func, *args, **kwargs):
            captured["func"] = func
            captured["timeout"] = kwargs.get("timeout")
            captured["call_name"] = kwargs.get("call_name")
            return pd.DataFrame({"code": ["600000"], "name": ["浦发银行"]})

        monkeypatch.setattr(af, "_akshare_call_with_timeout", fake_wrapper)
        df = ntc._fetch_akshare_df()
        assert captured["func"] is ntc._akshare_stock_info_worker
        assert captured["timeout"] == ntc._AKSHARE_FETCH_TIMEOUT
        assert captured["call_name"] == "stock_info_a_code_name"
        assert list(df["name"]) == ["浦发银行"]

