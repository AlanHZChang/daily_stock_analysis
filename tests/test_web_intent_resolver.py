# -*- coding: utf-8 -*-
"""web_intent_resolver 核心解析器單測。

純 Python 層離線測試（不依賴 agent.py / SSE / 真實網絡）：
  - 規則分類：stock_analysis / sector_analysis / portfolio_analysis /
    quote_lookup / general_chat 的判定矩陣與置信度路徑常量；追問走
    上下文繼承（繼承上輪執行類意圖）；
  - 意圖邊界矩陣：三判別測試（個性化/深度/對象）的易混淆對照用例
    （每對 query 只差一兩個字、意圖完全不同），與 web_intent_types
    模塊 docstring 的對照表互為基線；
  - 裸數字代碼提升（6 位 + 首碼白名單 + 非量詞後綴 + 查庫四重閘門）；
  - 歧義確認與市場消歧（ambiguous_stock_name / pending_action 形狀）；
  - wrong code（stock_unresolved）與低置信（low_confidence）確認短路；
  - LLM 兜底（stub adapter）：置信度上限、幻覺代碼拒收、候選消歧、
    壞輸出回退、followup 偽標籤繼承/降級；
  - 確認消費：序號/名稱/裸代碼/拒絕/新話題/模糊回應的完整生命週期；
  - 會話簿記：recent_stocks 頭插去重截斷、pending_actions 替換式收斂、
    last_intent、ConversationSession 形態（.context dict）兼容；

AkShare 擴展 mock 為最小全量 A 股數據（與 test_web_intent_tokenizer 同
約定），保證離線確定性；LLM 由 _StubLLMAdapter 可編程返回，不觸網絡。
"""

import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Optional
from unittest.mock import patch

import pytest

from src.agent.llm_adapter import LLMResponse
from src.agent.web_intent_resolver import (
    LAST_INTENT_KEY,
    LAST_RESOLUTIONS_KEY,
    LLM_CONFIDENCE_CAP,
    MAX_RECENT_STOCKS,
    PENDING_ACTIONS_KEY,
    RECENT_STOCKS_KEY,
    Stock,
    TAG_STOCK_NAME,
    WebIntent,
    WebIntentResolution,
    WebIntentResolver,
    _consume_confirmations,
    _dedup_stocks,
    _disambiguate_by_market,
    _finalize_confirmation,
    _merge_llm_result,
    _normalize_pending_groups,
    _parse_llm_payload,
    _preprocess_text,
    _identify_stock_codes,
    _session_context,
    _split_sub_messages,
    apply_outcome,
    apply_pending,
    apply_resolution_to_session,
    clear_pending_actions,
)
from src.agent.web_intent_types import Market

# 與 test_web_intent_tokenizer 相同的最小全量 A 股 mock：確定、離線
_MOCK_AKSHARE_A_SHARES = {
    "酒鬼酒": "000799",
    "三花智控": "002050",
}


@pytest.fixture(autouse=True)
def _mock_akshare_extension():
    with patch(
        "src.services.name_to_code_resolver._get_akshare_name_to_code",
        return_value=_MOCK_AKSHARE_A_SHARES,
    ):
        yield


@pytest.fixture(autouse=True)
def _restore_resolver_state():
    """快照/還原 name_to_code_resolver 模塊級可變狀態，用例間互不洩漏。"""
    from src.services import name_to_code_resolver as resolver_mod

    db = dict(resolver_mod.stockDB)
    aliases = {code: set(names) for code, names in resolver_mod.stockAliases.items()}
    merged = resolver_mod._akshare_merged
    yield
    resolver_mod.stockDB.clear()
    resolver_mod.stockDB.update(db)
    resolver_mod.stockAliases.clear()
    resolver_mod.stockAliases.update(aliases)
    resolver_mod._akshare_merged = merged
    # stockDB 原地增刪，按對象身份緩存的名稱/拼音列表可能已陳舊，強制重建
    resolver_mod._names_cache[:] = [None, None, None]
    resolver_mod._pinyin_cache[:] = [None, None]


# =========================================================================
# 測試輔助
# =========================================================================


@dataclass
class _FakeSession:
    """ConversationSession 形態替身：bookkeeping 走 .context dict。"""

    context: Dict[str, Any] = field(default_factory=dict)


class _StubLLMAdapter:
    """可編程 LLM stub：記錄調用、按腳本返回/拋錯，不觸網絡。"""

    def __init__(
        self,
        content: Optional[str] = None,
        provider: str = "stub",
        exc: Optional[Exception] = None,
    ) -> None:
        self.content = content
        self.provider = provider
        self.exc = exc
        self.calls: List[Dict[str, Any]] = []

    def call_text(self, messages, **kwargs) -> LLMResponse:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if self.exc is not None:
            raise self.exc
        return LLMResponse(content=self.content, provider=self.provider)


def _resolver(llm: Any = None) -> WebIntentResolver:
    return WebIntentResolver(llm_adapter=llm)


def _pending_ali() -> Dict[str, Any]:
    """標準阿里巴巴歧義 pending 動作（跨市場雙候選）。"""
    return {
        "action": "confirm_stock",
        "intent": "stock_analysis",
        "name": "阿里巴巴",
        "candidates": [
            {"code": "HK09988", "name": "阿里巴巴", "market": "hk"},
            {"code": "BABA", "name": "阿里巴巴", "market": "us"},
        ],
        "original_request": "分析阿里巴巴",
    }


def _flat(two_dim):
    """二維任務列表（外層=子消息任務組）→ 一維任務列表（斷言可讀形態）。"""
    return [t for group in two_dim for t in group]


def _codes(resolution: WebIntentResolution) -> List[str]:
    return [s.code for s in resolution.stocks]


def _candidate_codes(resolution: WebIntentResolution) -> List[str]:
    return [c.code for c in resolution.candidates]


def _sub_texts(text: str) -> List[str]:
    """_split_sub_messages 二維 tokens → 子消息文本列表（斷言可讀形態）。"""
    return ["".join(t.text for t in sub) for sub in _split_sub_messages(text)]


# =========================================================================
# 空輸入
# =========================================================================


class TestEmptyInput:
    def test_empty_string(self):
        r = _resolver().resolve_first("")
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.source == "rule"
        assert r.stocks == []
        assert not r.needs_confirmation

    def test_whitespace_only(self):
        r = _resolver().resolve_first("   \n\t ")
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_none_input(self):
        r = _resolver().resolve_first(None)  # type: ignore[arg-type]
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_punct_only(self):
        r = _resolver().resolve_first("！！！？？")
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.confidence == 0.5


# =========================================================================
# 規則分類 — stock_analysis
# =========================================================================


class TestRuleStockAnalysis:
    def test_explicit_a_code(self):
        r = _resolver().resolve_first("分析600519")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.source == "rule"
        assert r.confidence == 0.9
        assert _codes(r) == ["600519"]

    def test_bare_a_code(self):
        r = _resolver().resolve_first("600519")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]

    def test_exchange_suffixed_code(self):
        r = _resolver().resolve_first("600519.SH 怎么样")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]

    def test_hk_prefixed_code(self):
        r = _resolver().resolve_first("HK00700怎么样")
        assert _codes(r) == ["HK00700"]
        assert r.confidence == 0.9

    def test_us_ticker(self):
        r = _resolver().resolve_first("分析AAPL")
        assert _codes(r) == ["AAPL"]

    def test_full_name_with_request(self):
        r = _resolver().resolve_first("分析贵州茅台")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.confidence == 0.85
        assert _codes(r) == ["600519"]

    def test_bare_abbreviation_name(self):
        # 裸個股指稱的默認歸屬是股票分析（T2/T3：無數據詞即觀點類任務）
        r = _resolver().resolve_first("茅台")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.confidence == 0.8
        assert _codes(r) == ["600519"]

    def test_comparison_two_codes(self):
        r = _resolver().resolve_first("对比000858和300750")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["000858", "300750"]
        assert r.primary_stock_code == ""  # 多股比較不鎖定單一 scope

    def test_institutional_holdings_is_research(self):
        # 無第一人稱領屬的"持倉"是研究維度（機構/北向持倉），不是組合語境
        r = _resolver().resolve_first("分析茅台的持仓")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]

    def test_mock_akshare_name_resolvable(self):
        r = _resolver().resolve_first("分析酒鬼酒")
        assert _codes(r) == ["000799"]

    def test_function_words_do_not_block_entity(self):
        # 高頻功能詞（你/覺得，filler extend 池）作 DFS 全覆蓋片段：
        # 實體前的口語前綴不阻斷實體提取
        r = _resolver().resolve_first("你觉得茅台怎么样")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]

    def test_no_confirmation_at_high_confidence(self):
        r = _resolver().resolve_first("分析600519")
        assert not r.needs_confirmation
        assert r.pending_action is None


# =========================================================================
# 規則分類 — portfolio_analysis / quote_lookup / sector_analysis / 閒聊
# =========================================================================


class TestRulePortfolioAnalysis:
    @pytest.mark.parametrize("text", [
        "我的持仓怎么样",
        "帮我看看自选股",
        "加仓还是减仓",
        "我的仓位如何",
    ])
    def test_portfolio_inputs(self, text):
        # T1 個性化：無個股指稱時持倉/自選股詞即整體組合語境
        r = _resolver().resolve_first(text)
        assert r.intent == WebIntent.PORTFOLIO_ANALYSIS
        assert r.confidence == 0.85
        assert r.stocks == []

    def test_portfolio_action_with_entity(self):
        # 3a：持倉操作詞 + 個股 = 組合語境下的個股評估（依賴成本/倉位）
        r = _resolver().resolve_first("我的茅台还该拿着吗")
        assert r.intent == WebIntent.PORTFOLIO_ANALYSIS
        assert _codes(r) == ["600519"]
        assert not r.needs_confirmation

    def test_portfolio_subject_with_possessive(self):
        # 3b：持倉主題 + 第一人稱領屬 + 無強分析詞 → 組合語境
        r = _resolver().resolve_first("我的茅台仓位重不重")
        assert r.intent == WebIntent.PORTFOLIO_ANALYSIS
        assert _codes(r) == ["600519"]

    def test_possessive_with_research_subject_is_stock(self):
        # 3b 反例：句中有"我"但答案對所有用戶相同 → 股票分析
        r = _resolver().resolve_first("我的茅台基本面怎么样")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]


class TestRuleQuoteLookup:
    def test_broad_market_default_quote(self):
        # 泛市場裸詞默認報數（T2）：大盤不可能是股票，對象無歧義
        r = _resolver().resolve_first("今天大盘怎么样")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.confidence == 0.85

    def test_market_keyword_sets_sector_slot(self):
        # 市場詞的市場範圍由 sectors 槽承載（"港股行情"→["港股"]）
        r = _resolver().resolve_first("港股行情")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.sectors == ["港股"]

    def test_index_keyword(self):
        r = _resolver().resolve_first("上证指数怎么样")
        assert r.intent == WebIntent.QUOTE_LOOKUP

    def test_digit_index_keyword(self):
        # 含數字指數詞（滬深300）：數字段受 Step 3 保護區放行
        r = _resolver().resolve_first("沪深300怎么样")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.confidence == 0.85

    def test_entity_with_quote_word(self):
        # 個股路徑 T2：數據詞（多少錢）+ 無強分析詞 → 行情查詢
        r = _resolver().resolve_first("茅台多少钱")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(r) == ["600519"]
        assert r.confidence == 0.85

    def test_now_adverb_between_entity_and_quote(self):
        # "現在"（extend，⊂"出現在"）經 DFS 全覆蓋（茅臺+現在）完成實體
        # 提取：實體與數據詞之間的口語詞不阻斷識別，超串場景不被盲撕
        r = _resolver().resolve_first("茅台现在多少钱")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(r) == ["600519"]

    def test_market_word_with_entity_is_research(self):
        r = _resolver().resolve_first("A股600519怎么样")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]


class TestRuleSectorAnalysis:
    def test_sector_combo_opinion(self):
        # "行業名+泛稱"相鄰組合消除對象歧義 → 高置信板塊分析
        r = _resolver().resolve_first("白酒板块怎么看")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.stocks == []

    def test_market_opinion_upgrades_to_sector(self):
        # 泛市場 + 觀點/結構判斷（T2 強分析詞）→ 市場結構分析歸板塊意圖
        r = _resolver().resolve_first("大盘怎么看")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85

    def test_bare_sector_name_exact_pool_high_confidence(self):
        # 精確命中行業名詞池（半導體）＝行業 vs 個股雙解已消 → 0.85 直達；
        # 行業兼股票名（機器人，sector_n_stock）雙解未消 → 0.5 交 LLM 裁定
        r = _resolver().resolve_first("半导体怎么样")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        r2 = _resolver().resolve_first("机器人怎么样")
        assert r2.intent == WebIntent.SECTOR_ANALYSIS
        assert r2.confidence == 0.5


class TestRuleGeneralChat:
    def test_greeting(self):
        r = _resolver().resolve_first("你好")
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.confidence == 0.5
        assert not r.needs_confirmation  # 閒聊非執行類，無需確認

    def test_weather(self):
        r = _resolver().resolve_first("今天天气不错")
        assert r.intent == WebIntent.GENERAL_CHAT


# =========================================================================
# 裸數字代碼提升 — 四重閘門
# =========================================================================


class TestNumericCodePromotion:
    def test_promotion_with_request(self):
        r = _resolver().resolve_first("分析300750")
        assert _codes(r) == ["300750"]
        assert r.confidence == 0.9

    def test_promotion_bare(self):
        r = _resolver().resolve_first("300750怎么样")
        assert _codes(r) == ["300750"]

    def test_amount_not_promoted(self):
        # 量詞後綴：金額語義，絕不當代碼
        r = _resolver().resolve_first("我有300750元")
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.stocks == []

    def test_index_point_not_promoted(self):
        r = _resolver().resolve_first("上证3300点怎么样")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.stocks == []

    def test_year_not_promoted(self):
        r = _resolver().resolve_first("2024年怎么样")
        assert r.stocks == []

    def test_non_whitelisted_first_digit_not_promoted(self):
        # 首碼白名單（0/3/6/4/8/92）：999999 形態非法不提升
        r = _resolver().resolve_first("分析999999")
        assert r.stocks == []
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_not_in_db_not_promoted(self):
        # 白名單通過但查庫未命中（本地庫無此 A 股）：不虛構實體
        r = _resolver().resolve_first("分析360001")
        assert r.stocks == []

    def test_five_digit_not_promoted(self):
        # 5 位裸數字與日期/價格共形，不提升（交 LLM/確認兜底）
        r = _resolver().resolve_first("分析00700")
        assert r.stocks == []
        assert r.candidates == []


# =========================================================================
# 歧義確認與市場消歧
# =========================================================================


class TestAmbiguityConfirmation:
    def test_cross_market_name_needs_confirmation(self):
        r = _resolver().resolve_first("阿里巴巴")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.needs_confirmation
        assert r.reason == "ambiguous_stock_name"
        assert set(_candidate_codes(r)) == {"HK09988", "BABA"}
        assert r.stocks == []  # 未消解前不攜帶確定實體

    def test_pending_action_shape(self):
        r = _resolver().resolve_first("分析阿里巴巴")
        pa = r.pending_action
        assert pa is not None
        assert pa["action"] == "confirm_stock"
        assert pa["original_request"] == "分析阿里巴巴"
        # groups 是唯一權威結構（無頂層 name/candidates 投影）
        assert "name" not in pa and "candidates" not in pa
        assert len(pa["groups"]) == 1
        g = pa["groups"][0]
        assert g["name"] == "阿里巴巴"
        assert {c["code"] for c in g["candidates"]} == {"HK09988", "BABA"}
        for c in g["candidates"]:
            assert set(c.keys()) == {"code", "name", "market"}

    def test_market_word_disambiguates(self):
        # 市場詞收窄：消解行為落在 stocks（市場範圍由 sectors 槽承載）
        r = _resolver().resolve_first("港股阿里巴巴")
        assert not r.needs_confirmation
        assert _codes(r) == ["HK09988"]

    def test_us_market_word_disambiguates(self):
        r = _resolver().resolve_first("美股阿里巴巴")
        assert _codes(r) == ["BABA"]

    def test_dual_listing_a_hk(self):
        r = _resolver().resolve_first("分析中芯国际")
        assert r.needs_confirmation
        assert set(_candidate_codes(r)) == {"688981", "HK00981"}

    def test_confirmed_plus_ambiguous_mix(self):
        # 確定實體與歧義並存：stocks 帶確定項，歧義仍觸發確認
        r = _resolver().resolve_first("分析600519和阿里巴巴")
        assert _codes(r) == ["600519"]
        assert r.needs_confirmation
        assert set(_candidate_codes(r)) == {"HK09988", "BABA"}


# =========================================================================
# wrong code / 存疑代碼 / 低置信確認
# =========================================================================


class TestWrongCodeConfirmation:
    def test_invalid_suffixed_code(self):
        # 6 位 A 股形態掛 .HK 後綴：標註市場與形態矛盾 → wrong_hk_code
        r = _resolver().resolve_first("分析600519.HK")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.needs_confirmation
        assert r.reason == "stock_unresolved"
        assert r.unresolved_names == ["600519.HK"]
        assert r.confidence == 0.9

    def test_invalid_exchange_prefix(self):
        # SH + 999999：首碼白名單不過 → wrong_a_code
        r = _resolver().resolve_first("分析SH999999")
        assert r.needs_confirmation
        assert r.reason == "stock_unresolved"

    def test_wrong_code_pending_action_has_no_candidates(self):
        r = _resolver().resolve_first("分析SH999999")
        pa = r.pending_action
        assert pa["action"] == "confirm_stock"
        assert pa["groups"] == []


class TestLowConfidenceConfirmation:
    def test_unknown_us_ticker_without_llm(self):
        # 庫外美股 ticker → unknown_us_code：非全量庫無法判定合法與否，
        # 不做確認——未驗證代碼透傳執行端實查（rule 直達，無 LLM）
        r = _resolver().resolve_first("分析ZZZZ")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.confidence == 0.8
        assert r.unverified_codes == ["ZZZZ"]
        assert not r.needs_confirmation

    def test_sector_only_without_llm(self):
        # 行業名兼股票全名（機器人）：意圖歸屬無法由規則裁定 → 確認
        r = _resolver().resolve_first("分析机器人")
        assert r.needs_confirmation
        assert r.reason == "low_confidence"
        assert r.confidence < 0.6

    def test_general_chat_not_confirmed(self):
        # 閒聊雖低置信但非執行類，直接放行不確認
        r = _resolver().resolve_first("你好")
        assert not r.needs_confirmation


# =========================================================================
# LLM 兜底
# =========================================================================


def _llm_json(intent: str, confidence: float = 0.9, **extra) -> str:
    import json
    return json.dumps({"intent": intent, "confidence": confidence, **extra}, ensure_ascii=False)


class TestLLMFallback:
    def test_confidence_capped(self):
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.99))
        r = _resolver(stub).resolve_first("聊聊电影")
        assert r.source == "llm"
        assert r.confidence == LLM_CONFIDENCE_CAP

    def test_valid_stock_code_injected(self):
        stub = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.8, stock_code="600519"))
        r = _resolver(stub).resolve_first("帮我看看那只白酒股")
        assert r.source == "llm"
        assert _codes(r) == ["600519"]

    def test_hallucinated_code_rejected(self):
        # LLM 給出庫外代碼：拒收注入、轉 stock_unresolved 確認
        stub = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.9, stock_code="888888"))
        r = _resolver(stub).resolve_first("随便看看")
        assert r.source == "llm"
        assert r.stocks == []
        assert r.unresolved_names == ["888888"]
        assert r.needs_confirmation
        assert r.reason == "stock_unresolved"

    def test_llm_disambiguates_candidates(self):
        # candidates 與 LLM 觸發無關："阿里巴巴" tag 全識別 + 0.8 → 規則
        # 直達轉用戶確認，大模型零調用（歧義出口是確認，不是猜選）
        stub = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.9, stock_code="HK09988"))
        r = _resolver(stub).resolve_first("阿里巴巴")
        assert stub.calls == []
        assert r.source == "rule"
        assert set(_candidate_codes(r)) == {"HK09988", "BABA"}
        assert r.needs_confirmation
        assert r.reason == "ambiguous_stock_name"

    def test_rule_entities_preserved(self):
        # 規則已解析的硬實體不因 LLM 未提及而丟失
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        r = _resolver(stub).resolve_first("600519")
        assert _codes(r) == ["600519"]

    def test_high_confidence_exempt_from_side_triggers(self):
        # 主體已高置信時附帶存疑不觸發 LLM 複核："順便"切分後主任務
        # （報價）規則直達且置信度不被壓低；附帶是獨立的第二任務，
        # 其存疑透傳由該任務自身承接
        stub = _StubLLMAdapter(content='{"intent": "quote_lookup", "confidence": 0.9}')
        rs = WebIntentResolver(llm_adapter=stub).resolve("茅台多少钱顺便看下SOFI")
        # 主任務高置信直達（stub 僅被附帶子消息調用一次）；附帶被 LLM
        # 改判 quote 獨立成任務（不折疊，LLM cap 0.75）
        assert len(stub.calls) == 1
        tasks = _flat(rs)
        assert len(tasks) == 2
        assert tasks[0].source == "rule" and tasks[0].confidence == 0.85
        assert tasks[0].intent == WebIntent.QUOTE_LOOKUP
        assert _codes(tasks[0]) == ["600519"]
        assert tasks[1].source == "llm" and tasks[1].confidence == 0.75
        assert tasks[1].unverified_codes == ["SOFI"]

    def test_unknown_code_as_subject_passes_through(self):
        # 存疑代碼主體（有意圖詞"分析"）：hk/us 無法判定合法與否，
        # 規則直達放行（不確認不 LLM），unverified 透傳執行端
        stub = _StubLLMAdapter(content='{"intent": "quote_lookup", "confidence": 0.9}')
        r = WebIntentResolver(llm_adapter=stub).resolve_first("分析下SOFI")
        assert len(stub.calls) == 0
        assert r.source == "rule"
        assert r.unverified_codes == ["SOFI"]
        assert not r.needs_confirmation

    def test_llm_failed_low_confidence_chat_not_released(self):
        # 證據狀態守恆：複核被觸發即證明規則不可靠，複核失敗後證據
        # 未變——llm_failed 的低置信閒聊候選不放行，轉澄清確認
        # （詞池外板塊"哈嘍板塊"整段 DFS 陪葬時，LLM 是唯一識別路徑）
        stub = _StubLLMAdapter(exc=RuntimeError("timeout"))
        rs = WebIntentResolver(llm_adapter=stub).resolve("然后再分析一下哈喽板块")
        r = _flat(rs)[0]
        assert r.source == "llm_failed"
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.confidence == 0.5
        assert r.needs_confirmation is True
        assert r.reason == "low_confidence"

    def test_llm_failed_confident_chat_still_released(self):
        # 高置信閒聊（複核因其他條件觸發但閒聊判定可靠）不受影響
        stub = _StubLLMAdapter(exc=RuntimeError("timeout"))
        rs = WebIntentResolver(llm_adapter=stub).resolve("你好呀")
        assert _flat(rs)[0].intent == WebIntent.GENERAL_CHAT
        assert _flat(rs)[0].needs_confirmation is False

    def test_llm_failed_keeps_rule_result_and_confidence(self):
        # llm_failed 與 rule 的區分：兜底已觸發但失敗——意圖/置信度/
        # stocks 與規則判定同源（"你好"規則閒聊 0.5），僅 source 標記
        # 路徑；同消息未配 LLM 時為純 rule
        stub = _StubLLMAdapter(exc=RuntimeError("timeout"))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("你好")
        assert r.source == "llm_failed"
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.confidence == 0.5
        r2 = _resolver().resolve_first("你好")
        assert r2.source == "rule"
        assert (r2.intent, r2.confidence) == (r.intent, r.confidence)

    def test_bad_json_falls_back_to_rules(self):
        stub = _StubLLMAdapter(content="我觉得是股票研究")
        r = _resolver(stub).resolve_first("你好")
        assert r.source == "llm_failed"
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_invalid_intent_falls_back(self):
        stub = _StubLLMAdapter(content=_llm_json("unknown_intent", 0.9))
        r = _resolver(stub).resolve_first("你好")
        assert r.source == "llm_failed"

    def test_exception_falls_back(self):
        stub = _StubLLMAdapter(exc=RuntimeError("boom"))
        r = _resolver(stub).resolve_first("你好")
        assert r.source == "llm_failed"

    def test_error_provider_falls_back(self):
        stub = _StubLLMAdapter(content="...", provider="error")
        r = _resolver(stub).resolve_first("你好")
        assert r.source == "llm_failed"

    def test_followup_without_context_downgraded(self):
        # LLM 返回 followup 偽標籤但上輪是閒聊：無產物可追問，降級閒聊
        stub = _StubLLMAdapter(content=_llm_json("followup", 0.9))
        session = {LAST_INTENT_KEY: "general_chat"}
        r = _resolver(stub).resolve_first("继续", session_context=session)
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_followup_with_context_inherits_intent(self):
        # 規則無信號（"再展開講講"無 followup 詞）→ LLM 判 followup 且
        # 上輪為執行類意圖 → 偽標籤轉為繼承上輪意圖（不是獨立意圖）
        stub = _StubLLMAdapter(content=_llm_json("followup", 0.9))
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver(stub).resolve_first("再展开讲讲", session_context=session)
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.source == "llm"

    def test_prompt_carries_context(self):
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        session = {
            RECENT_STOCKS_KEY: ["600519"],
            LAST_INTENT_KEY: "stock_analysis",
        }
        _resolver(stub).resolve_first("聊聊", session_context=session)
        assert len(stub.calls) == 1
        user_body = stub.calls[0]["messages"][1]["content"]
        assert "聊聊" in user_body
        assert "600519" in user_body
        assert "stock_analysis" in user_body
        # 低溫度確定性輸出 + 有界超時
        assert stub.calls[0]["kwargs"]["temperature"] == 0.0

    def test_prompt_carries_chain_subject_for_fragment(self):
        # 多任務消息的子消息片段觸發兜底時，prompt 攜帶鏈式主體
        # current_stock（同消息前序片段已確定的標的，查庫派生三元組）：
        # 片段自身無標的（"和市盈率"），LLM 憑 current_stock 判回執行類
        # 意圖並回代碼，合併後報價訴求不降級閒聊
        # 無主體意圖片段（"和市盈率"）默認主體為"它"走繼承，
        # 鏈式主體在場（HK00700）→ 判定可靠 → 零調用直達
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_code="HK00700"))
        rs = _resolver(stub).resolve("看下HK00700股价，和市盈率", {})
        assert stub.calls == [], "继承产物主体在场，免复核直达"
        frag = _flat(rs)[1]
        assert frag.source == "context"
        assert frag.intent == WebIntent.QUOTE_LOOKUP
        assert frag.primary_stock_code == "HK00700"
        # blob 變體（視野殘缺）仍復核：prompt 攜帶鏈式主體 current_stock
        stub2 = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_code="HK00700"))
        rs2 = _resolver(stub2).resolve("看下HK00700股价，和市盈率哈哈", {})
        assert len(stub2.calls) == 1, "视野残缺强制复核"
        user_body = stub2.calls[0]["messages"][1]["content"]
        assert '"current_stock": {"code": "HK00700"' in user_body
        assert _codes(_flat(rs2)[1]) == ["HK00700"],             "复核合并后市盈率诉求指向链式主体，不降级闲聊"

    def test_high_confidence_rule_skips_llm(self):
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        _resolver(stub).resolve_first("分析600519")
        assert stub.calls == []

    def test_low_confidence_rule_invokes_llm(self):
        # 行業兼股票名（雙解未消，無 combo）：對象歧義 → 低置信交 LLM 裁定
        stub = _StubLLMAdapter(content=_llm_json("sector_analysis", 0.9))
        r = _resolver(stub).resolve_first("机器人怎么样")
        assert len(stub.calls) == 1
        assert r.source == "llm"
        assert r.intent == WebIntent.SECTOR_ANALYSIS

    def test_sector_combo_high_confidence_skips_llm(self):
        # "行業名+板塊"相鄰組合消除對象歧義 → 規則直接高置信，不打擾 LLM
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        r = _resolver(stub).resolve_first("半导体板块怎么样")
        assert stub.calls == []
        assert r.source == "rule"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85

    def test_bare_unknown_code_skips_llm(self):
        # 裸存疑代碼：tag 全識別（unknown_us_code 也是識別產物）+ 0.8 →
        # 免複核直達，unverified 透傳執行端實查（與"分析下SOFI"同構）
        stub = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.8, stock_code="AAPL"))
        r = _resolver(stub).resolve_first("ZZZZ")
        assert stub.calls == []
        assert r.source == "rule"
        assert r.unverified_codes == ["ZZZZ"]
        assert not r.needs_confirmation


# =========================================================================
# 確認消費 — pending confirm_stock 的響應解析
# =========================================================================


def _ali_session() -> Dict[str, Any]:
    return {
        PENDING_ACTIONS_KEY: [_pending_ali()],
        LAST_INTENT_KEY: "stock_analysis",
        RECENT_STOCKS_KEY: [],
    }


class TestConfirmationConsumption:
    @staticmethod
    def _pending_pingan() -> Dict[str, Any]:
        # "平安"歧義：平安銀行 / 中國平安 雙候選（同市場，全名可區分）
        return {
            "action": "confirm_stock",
            "intent": "stock_analysis",
            "name": "平安",
            "candidates": [
                {"code": "000001", "name": "平安银行", "market": "a"},
                {"code": "601318", "name": "中国平安", "market": "a"},
            ],
            "original_request": "分析平安",
        }

    def test_market_word_us_choice(self):
        # 聚合項輸入：市場詞把 hk/us 雙候選收窄到唯一
        r = _resolver().resolve_first("美股", _ali_session())
        assert r.source == "confirmation"
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["BABA"]
        assert r.confidence == 0.9

    def test_intent_inherited_from_pending(self):
        # 確認消費繼承 pending 記錄的原意圖：行情查詢的歧義消解後仍是查詢
        session = _ali_session()
        session[PENDING_ACTIONS_KEY][0]["intent"] = "quote_lookup"
        r = _resolver().resolve_first("港股", session)
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(r) == ["HK09988"]

    def test_pending_without_intent_falls_back(self):
        # 形狀防禦：pending 缺 intent 字段 → 回退 stock_analysis
        session = _ali_session()
        del session[PENDING_ACTIONS_KEY][0]["intent"]
        r = _resolver().resolve_first("港股", session)
        assert r.intent == WebIntent.STOCK_ANALYSIS

    def test_pending_bogus_intent_falls_back(self):
        session = _ali_session()
        session[PENDING_ACTIONS_KEY][0]["intent"] = "bogus_intent"
        r = _resolver().resolve_first("港股", session)
        assert r.intent == WebIntent.STOCK_ANALYSIS

    def test_name_plus_market_reply_picks_market(self):
        # 複述組名 + 聚合項（"阿里巴巴港股"）：市場詞先於名稱子串裁決，
        # 名稱子串命中全部同組候選時不構成證據
        r = _resolver().resolve_first("阿里巴巴港股", _ali_session())
        assert r.source == "confirmation"
        assert _codes(r) == ["HK09988"]

    def test_full_name_exact_choice(self):
        # 同市場多候選無市場聚合項：候選全名全等命中
        r = _resolver().resolve_first("平安银行", self._pending_pingan_session())
        assert r.source == "confirmation"
        assert _codes(r) == ["000001"]

    def test_ambiguous_name_substring_not_consumed(self):
        # 歧義名本身（"平安"）命中全部候選 = 不消解：絕不取第一個，
        # 整輪按新消息解析（用戶必須給出聚合項）
        r = _resolver().resolve_first("平安", self._pending_pingan_session())
        assert r.source == "rule"

    @staticmethod
    def _pending_pingan_session() -> Dict[str, Any]:
        return {PENDING_ACTIONS_KEY: [TestConfirmationConsumption._pending_pingan()]}

    def test_bare_digit_code_choice(self):
        # 裸 5 位數字按 HK 口徑規範（09988 → HK09988）命中候選
        r = _resolver().resolve_first("09988", _ali_session())
        assert r.source == "confirmation"
        assert _codes(r) == ["HK09988"]

    def test_named_code_choice(self):
        # 顯式代碼形態解析為確定實體且在候選內 → 消費
        r = _resolver().resolve_first("HK09988", _ali_session())
        assert r.source == "confirmation"
        assert _codes(r) == ["HK09988"]

    def test_declined(self):
        r = _resolver().resolve_first("不用了", _ali_session())
        assert r.source == "confirmation"
        assert r.intent == WebIntent.GENERAL_CHAT
        assert not r.needs_confirmation

    @pytest.mark.parametrize("text", ["算了", "取消", "不需要", "算了，不用了"])
    def test_decline_variants(self, text):
        r = _resolver().resolve_first(text, _ali_session())
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.source == "confirmation"

    def test_new_topic_drops_pending(self):
        # 確定實體不在候選中 → 新話題：正常解析（pending 由 apply 收斂）
        r = _resolver().resolve_first("分析600519", _ali_session())
        assert r.source == "rule"
        assert _codes(r) == ["600519"]

    @pytest.mark.parametrize("text", ["1", "2", "5", "第一个", "二"])
    def test_numeric_reply_not_consumed(self, text):
        # 純序號/中文序數不是合法消歧輸入：零消解按新消息解析
        # （裸數字代碼形態除外，見 bare_digit_code_choice）
        r = _resolver().resolve_first(text, _ali_session())
        assert r.source == "rule"
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_vague_reply_not_consumed(self):
        r = _resolver().resolve_first("嗯嗯", _ali_session())
        assert r.source == "rule"
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_malformed_pending_ignored(self):
        session = {PENDING_ACTIONS_KEY: [{"action": "confirm_stock"}]}
        r = _resolver().resolve_first("港股", session_context=session)
        assert r.source == "rule"  # 無候選可確認，直接正常解析

    def test_pending_non_list_shape_ignored(self):
        session = {PENDING_ACTIONS_KEY: "not-a-list"}
        r = _resolver().resolve_first("分析600519", session_context=session)
        assert _codes(r) == ["600519"]

    def test_market_word_hk_choice(self):
        r = _resolver().resolve_first("港股", _ali_session())
        assert r.source == "confirmation"
        assert _codes(r) == ["HK09988"]


# =========================================================================
# 會話簿記 — recent_stocks / pending_actions / last_intent
# =========================================================================


class TestSessionBookkeeping:
    def test_write_via_update_context_when_available(self):
        # ConversationSession 形態（帶 update_context 簿記入口）優先走它，
        # 不繞過宿主直接改 dict（可能帶持久化/髒標記鉤子）
        class _Session:
            def __init__(self) -> None:
                self.context: Dict[str, Any] = {}
                self.writes: List[Any] = []

            def update_context(self, key: str, value: Any) -> None:
                self.writes.append((key, value))
                self.context[key] = value

        session = _Session()
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("600519", "贵州茅台", "a")]))
        written_keys = [k for k, _v in session.writes]
        # 組合入口 = apply_pending（消費即結算）→ apply_outcome（recent/last/投影）
        assert written_keys == [PENDING_ACTIONS_KEY, RECENT_STOCKS_KEY, LAST_INTENT_KEY,
                                LAST_RESOLUTIONS_KEY]
        assert session.context[LAST_INTENT_KEY] == "stock_analysis"

    def test_recent_stocks_head_insert(self):
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("600519", "贵州茅台", "a")]))
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("000858", "五粮液", "a")]))
        assert session[RECENT_STOCKS_KEY] == ["000858", "600519"]

    def test_recent_stocks_dedup_moves_to_head(self):
        session = {RECENT_STOCKS_KEY: ["600519", "000858"]}
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("600519", "贵州茅台", "a")]))
        assert session[RECENT_STOCKS_KEY] == ["600519", "000858"]

    def test_recent_stocks_truncated(self):
        session = {RECENT_STOCKS_KEY: [f"60000{i}" for i in range(MAX_RECENT_STOCKS)]}
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("300750", "宁德时代", "a")]))
        recent = session[RECENT_STOCKS_KEY]
        assert recent[0] == "300750"
        assert len(recent) == MAX_RECENT_STOCKS

    def test_candidates_not_written_to_recent(self):
        # 未確認的歧義候選不汙染繼承上下文
        session: Dict[str, Any] = {}
        r = _resolver().resolve_first("阿里巴巴")
        apply_resolution_to_session(session, r)
        assert session[RECENT_STOCKS_KEY] == []

    def test_confirmation_writes_pending(self):
        session: Dict[str, Any] = {}
        r = _resolver().resolve_first("分析阿里巴巴")
        apply_resolution_to_session(session, r)
        pending = session[PENDING_ACTIONS_KEY]
        assert len(pending) == 1
        assert pending[0]["action"] == "confirm_stock"

    def test_stale_pending_cleared_by_apply(self):
        # 生命週期收斂：舊 pending 存在，本輪無確認產出 → apply 後清空
        session = _ali_session()
        r = _resolver().resolve_first("分析600519", session_context=session)
        apply_resolution_to_session(session, r)
        assert session[PENDING_ACTIONS_KEY] == []

    def test_consumed_round_clears_pending(self):
        session = _ali_session()
        r = _resolver().resolve_first("港股", session_context=session)
        apply_resolution_to_session(session, r)
        assert session[PENDING_ACTIONS_KEY] == []
        assert session[RECENT_STOCKS_KEY] == ["HK09988"]
        assert session[LAST_INTENT_KEY] == "stock_analysis"

    def test_apply_writes_pending_from_non_first_task(self):
        # 多意圖消息的歧義短路組結構全程保留：兄弟任務（茅臺 quote）隨
        # 確認任務一起返回並寫入 last_resolutions（即跨輪暫存器）；apply
        # 寫入確認任務的 pending，消費結算後兄弟任務經 ③ 拼接恢復——
        # 確認循環不斷裂、請求不丟
        tasks = _resolver().resolve("查一下茅台股价，然后分析阿里巴巴")
        flat = _flat(tasks)
        confirming = next(t for t in flat if t.needs_confirmation)
        sibling = next(t for t in flat if not t.needs_confirmation)
        assert sibling.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(sibling) == ["600519"]
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, tasks)
        assert session[PENDING_ACTIONS_KEY] == [confirming.pending_action]
        # 用戶下一輪聚合項回覆被正確消費，兄弟任務隨 ③ 拼接恢復
        after = _resolver().resolve("港股", session)
        # ③ 拼接保 last_resolution 子消息序：兄弟（quote 茅臺）在前
        assert [(t.intent, _codes(t)) for t in _flat(after)] == [
            (WebIntent.QUOTE_LOOKUP, ["600519"]),
            (WebIntent.STOCK_ANALYSIS, ["HK09988"]),
        ]

    def test_apply_pending_scans_all_positions(self):
        # apply_pending 掃描全部任務，不假設 _flat(tasks)[0]——防禦
        # resolve 之外的列表構造方（SSE 集成層）
        plain = WebIntentResolution(WebIntent.QUOTE_LOOKUP, 0.9,
                                    stocks=[Stock("600519", "贵州茅台", "a")])
        confirming = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.85, needs_confirmation=True,
            pending_action={"action": "confirm_stock", "groups": []},
        )
        session: Dict[str, Any] = {}
        apply_pending(session, [plain, confirming])
        assert session[PENDING_ACTIONS_KEY] == [confirming.pending_action]

    def test_short_circuit_round_skips_outcome(self):
        # 時機拆分：短路輪整鏈未執行——recent_stocks / last_intent 不得
        # 記錄未執行的任務（茅臺 quote 未跑、意圖未跑）
        session = {RECENT_STOCKS_KEY: ["000858"], LAST_INTENT_KEY: "quote_lookup"}
        tasks = _resolver().resolve("查一下茅台股价，然后分析阿里巴巴")
        apply_resolution_to_session(session, tasks)
        assert session[PENDING_ACTIONS_KEY]  # pending 正常寫入
        assert session[RECENT_STOCKS_KEY] == ["000858"]  # 未執行的茅臺不入列
        assert session[LAST_INTENT_KEY] == "quote_lookup"  # 保持上一執行輪

    def test_apply_pending_and_outcome_split_entries(self):
        # 拆分入口各自獨立可用：apply_pending 只動 pending，
        # apply_outcome 只動 recent/last
        session: Dict[str, Any] = {}
        apply_pending(session, WebIntentResolution(WebIntent.GENERAL_CHAT, 0.9))
        assert session[PENDING_ACTIONS_KEY] == []
        assert RECENT_STOCKS_KEY not in session
        assert LAST_INTENT_KEY not in session
        apply_outcome(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("600519", "贵州茅台", "a")]))
        assert session[RECENT_STOCKS_KEY] == ["600519"]
        assert session[LAST_INTENT_KEY] == "stock_analysis"

    def test_last_intent_recorded(self):
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.PORTFOLIO_ANALYSIS, 0.85))
        assert session[LAST_INTENT_KEY] == "portfolio_analysis"

    def test_last_resolutions_recorded(self):
        # 持續性會話保留上一輪（已執行）任務列表投影：下一輪 resolve 的
        # context 可讀取，含意圖/標的/板塊/來源子消息
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, [
            WebIntentResolution(
                WebIntent.STOCK_ANALYSIS, 0.85,
                stocks=[Stock("600519", "贵州茅台", "a")],
                source_request="分析贵州茅台"),
            WebIntentResolution(
                WebIntent.SECTOR_ANALYSIS, 0.85, sectors=["白酒"]),
        ])
        recorded = [t for g in session[LAST_RESOLUTIONS_KEY] for t in g]
        assert [t["intent"] for t in recorded] == ["stock_analysis", "sector_analysis"]
        assert recorded[0]["stocks"] == [{"code": "600519", "name": "贵州茅台", "market": "a"}]
        assert recorded[0]["source_request"] == "分析贵州茅台"
        assert recorded[1]["sectors"] == ["白酒"]

    def test_short_circuit_round_writes_last_resolutions(self):
        # 短路輪也寫 last_resolutions（第五步確認消費的數據源：上輪歧義
        # 任務的 pending_action 必須跨輪可見）；last_intent 仍只記執行輪
        session: Dict[str, Any] = {}
        tasks = _resolver().resolve("查一下茅台股价，然后分析阿里巴巴")
        apply_resolution_to_session(session, tasks)
        recorded = [t for g in session[LAST_RESOLUTIONS_KEY] for t in g]
        # 組結構保留：兄弟任務與確認任務都在（last_resolution 即暫存器）
        assert [t["intent"] for t in recorded] == ["quote_lookup", "stock_analysis"]
        assert recorded[1]["needs_confirmation"] is True
        assert recorded[1]["pending_action"]["groups"][0]["name"] == "阿里巴巴"
        # last_intent 仍只記執行輪：短路輪不寫（鍵缺失或保持舊值）
        assert session.get(LAST_INTENT_KEY) != "quote_lookup"

    def test_conversation_session_object(self):
        # ConversationSession 形態（.context dict）同樣可寫
        session = _FakeSession()
        apply_resolution_to_session(session, WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[Stock("600519", "贵州茅台", "a")]))
        assert session.context[RECENT_STOCKS_KEY] == ["600519"]

    def test_none_session_noop(self):
        apply_resolution_to_session(None, WebIntentResolution(WebIntent.GENERAL_CHAT, 0.5))

    def test_clear_pending_actions(self):
        session = _ali_session()
        clear_pending_actions(session)
        assert session[PENDING_ACTIONS_KEY] == []

    def test_clear_pending_actions_on_object(self):
        session = _FakeSession(context=_ali_session())
        clear_pending_actions(session)
        assert session.context[PENDING_ACTIONS_KEY] == []


# =========================================================================
# 上下文繼承 — inherited_stock_code / 追問繼承（上下文繼承機制）
# =========================================================================


class TestContextInheritance:
    def test_recent_stock_inherited(self):
        session = {RECENT_STOCKS_KEY: ["600519"]}
        r = _resolver().resolve_first("你好", session_context=session)
        assert r.inherited_stock_code == "600519"
        assert r.primary_stock_code == "600519"

    def test_current_stock_code_wins(self):
        # 鎖定股置頂：inherited_stock_code 即繼承主碼
        session = {RECENT_STOCKS_KEY: ["600519"]}
        r = _resolver().resolve_first("你好", session_context=session, request_context={"current_stock_code": "300750"})
        assert r.inherited_stock_code == "300750"
        assert r.primary_stock_code == "300750"

    def test_followup_inherits_executing_last_intent(self):
        # 追問不佔意圖名額：繼承上輪執行類意圖（source="context"）
        session = {
            LAST_INTENT_KEY: "stock_analysis",
            RECENT_STOCKS_KEY: ["600519"],
        }
        r = _resolver().resolve_first("继续", session_context=session)
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.source == "context"
        assert r.confidence == 0.75
        assert r.inherited_stock_code == "600519"
        assert not r.needs_confirmation

    def test_followup_after_portfolio(self):
        session = {LAST_INTENT_KEY: "portfolio_analysis"}
        r = _resolver().resolve_first("接着看看", session_context=session)
        assert r.intent == WebIntent.PORTFOLIO_ANALYSIS

    def test_followup_needs_executing_last_intent(self):
        # 上輪閒聊：無產物可追問 → 不繼承，按無信號解析
        session = {LAST_INTENT_KEY: "general_chat"}
        r = _resolver().resolve_first("继续", session_context=session)
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_followup_requires_session(self):
        r = _resolver().resolve_first("继续")
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_followup_with_new_entity_is_research(self):
        # followup 詞 + 新股票指稱 → 新的個股分析，不是追問
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver().resolve_first("继续分析600519", session_context=session)
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]


# =========================================================================
# 意圖邊界矩陣 — 三判別測試的易混淆對照（web_intent_types docstring 基線）
# =========================================================================


class TestIntentBoundaryMatrix:
    """每對 query 只差一兩個字、意圖完全不同；與 web_intent_types 模塊
    docstring 的"易混淆對照"表互為基線——改邊界定義必須兩側同步。"""

    @pytest.mark.parametrize("text,expected", [
        # T2 深度：報數據 vs 給觀點（同一實體）
        ("茅台多少钱", WebIntent.QUOTE_LOOKUP),
        ("茅台估值贵不贵", WebIntent.STOCK_ANALYSIS),
        ("茅台的市盈率是多少", WebIntent.QUOTE_LOOKUP),
        ("茅台今天为什么大跌", WebIntent.STOCK_ANALYSIS),
        ("茅台今天跌了多少", WebIntent.QUOTE_LOOKUP),
        ("茅台能买吗", WebIntent.STOCK_ANALYSIS),
        # T2 數據詞 vs 知識（查數據源 vs 純 LLM 知識）
        ("什么是市盈率", WebIntent.GENERAL_CHAT),
        # T1 個性化：答案是否依賴用戶賬戶數據
        ("茅台基本面怎么样", WebIntent.STOCK_ANALYSIS),
        ("我的茅台还该拿着吗", WebIntent.PORTFOLIO_ANALYSIS),
        ("我的持仓今天怎么样", WebIntent.PORTFOLIO_ANALYSIS),
        # T2+T3：集合對象的報數 vs 結構判斷
        ("白酒板块今天涨了多少", WebIntent.QUOTE_LOOKUP),
        ("白酒板块怎么看", WebIntent.SECTOR_ANALYSIS),
        ("白酒板块今天领跌的是谁", WebIntent.QUOTE_LOOKUP),
        ("白酒板块哪只最有潜力", WebIntent.SECTOR_ANALYSIS),
        ("今天大盘怎么样", WebIntent.QUOTE_LOOKUP),
        ("大盘怎么看", WebIntent.SECTOR_ANALYSIS),
        # T2 深度內戰：比較數字 vs 比較觀點
        ("分析000858和300750谁涨得多", WebIntent.QUOTE_LOOKUP),
        ("分析000858和300750哪个好", WebIntent.STOCK_ANALYSIS),
        # T2 詞序優先級：強分析詞 > 數據詞 > 泛動作詞
        ("分析茅台的股价走势", WebIntent.STOCK_ANALYSIS),
        ("帮我查一下茅台的股价", WebIntent.QUOTE_LOOKUP),
    ])
    def test_boundary_pair(self, text, expected):
        r = _resolver().resolve_first(text)
        assert r.intent == expected, (
            f"边界矩阵失守：{text!r} 期望 {expected.value}，实际 {r.intent.value}"
        )


# =========================================================================
# extend 詞池交叉驗證 — 子串歧義詞的防盲撕迴歸
# =========================================================================


class TestExtendPoolCrossValidation:
    """extend 池的子串歧義詞只在 Step 6 DFS 全片段覆蓋時命中：被更長
    常見詞包含的場景（出現在/查一下午/他們）整段放棄交 LLM，絕不盲撕
    出錯誤語義的 token（"寧可不做，不可做錯"）。"""

    def test_superstring_not_blind_torn(self):
        # 現在 ⊂ "出現在"："出現在龍虎榜"不得撕出時間詞（無信號交 LLM）
        r = _resolver().resolve_first("出现在龙虎榜")
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.stocks == []

    def test_afternoon_query_not_torn_by_cha(self):
        # 查一下 ⊂ "查一下午"："查一下午的大盤"不撕出取數詞；大盤經
        # Step 4 命中，意圖仍為行情查詢
        r = _resolver().resolve_first("查一下午的大盘")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.stocks == []

    def test_pronoun_superstring_no_followup(self):
        # 他 ⊂ "他們"："他們說的對嗎"不判追問指代，不繼承上輪意圖
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver().resolve_first("他们说的对吗", session_context=session)
        assert r.source != "context"
        assert r.intent == WebIntent.GENERAL_CHAT


# =========================================================================
# ASCII 全詞匹配 — 連續英文字母段不切割
# =========================================================================


class TestAsciiWholeWordMatching:
    """ASCII 關鍵詞一律全詞匹配（詞邊界 = 空格/標點/CJK 鄰接）：
    "researching" 內不撕出 research、"markets" 內不撕出 market——Step 4/5
    正則帶詞邊界斷言，與 Step 6 整詞精確查表語義一致。"""

    def test_clean_pattern_whole_word_only(self):
        from src.agent.web_intent_types import _CLEAN_KEYWORDS_PATTERN as pat
        assert pat.search("research") is not None
        assert pat.search("researching") is None
        assert pat.search("analyze") is not None
        assert pat.search("analyzed") is None

    def test_market_pattern_whole_word_only(self):
        from src.agent.web_intent_tokenizer import _MARKET_TOKEN_PATTERN as pat
        assert pat.search("market") is not None
        assert pat.search("markets") is None
        # CJK 鄰接不算連續英文：夾在中文裡的 market 正常命中
        assert pat.search("美股market怎么样") is not None

    def test_pipeline_english_run_untouched(self):
        # 全管道：連續英文字母段整體保持未打標籤（交 LLM），不產生關鍵詞 tag
        _, tokens = _preprocess_text("researching")
        assert [(t.text, t.tag) for t in tokens] == [("researching", "")]


# =========================================================================
# WebIntentResolution 數據契約
# =========================================================================


class TestResolutionDataclass:
    def test_stock_string_normalized(self):
        r = WebIntentResolution(WebIntent.STOCK_ANALYSIS, 0.9, stocks=["600519"])
        assert r.stocks == [Stock(code="600519")]

    def test_stock_dict_normalized(self):
        # stocks 的 dict 載荷與 candidates 同口徑歸一為 Stock：兩列表
        # 共享同一 _coerce_stock map，dict 分支顯式轉換、缺 code/空 code/
        # None 條目剔除——不存在"stocks 字典原樣透傳"路徑（評審探針釘子）
        r = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9,
            stocks=[{"code": "600519", "name": "贵州茅台", "market": "a"},
                    {"name": "缺code"}, {"code": ""}, None, "000858"],
        )
        assert r.stocks == [
            Stock("600519", "贵州茅台", "a"), Stock(code="000858")]
        assert r.primary_stock_code == ""  # 雙標的（比較場景）按契約返回空串
        single = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9, stocks=[{"code": "600519"}])
        assert single.primary_stock_code == "600519"

    def test_candidate_dict_normalized(self):
        r = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9,
            candidates=[{"code": "BABA", "name": "阿里巴巴", "market": "us"}],
        )
        assert r.candidates == [Stock("BABA", "阿里巴巴", "us")]

    def test_primary_stock_code_single(self):
        r = _resolver().resolve_first("分析600519")
        assert r.primary_stock_code == "600519"

    def test_primary_stock_code_multi_empty(self):
        r = _resolver().resolve_first("对比000858和300750")
        assert r.primary_stock_code == ""

    def test_primary_stock_code_inherited(self):
        session = {RECENT_STOCKS_KEY: ["600519"]}
        r = _resolver().resolve_first("你好", session_context=session)
        assert r.primary_stock_code == "600519"


# =========================================================================
# SSE 事件構建
# =========================================================================


class TestInternalHelpers:
    # ---- _parse_llm_payload ----

    def test_parse_payload_plain_json(self):
        assert _parse_llm_payload('{"intent": "general_chat", "confidence": 0.5}')

    def test_parse_payload_code_fence(self):
        assert _parse_llm_payload('```json\n{"intent": "general_chat"}\n```')

    def test_parse_payload_surrounding_text(self):
        assert _parse_llm_payload('好的，结果如下：{"intent": "general_chat"} 以上。')

    def test_parse_payload_invalid(self):
        assert _parse_llm_payload("not json") is None
        assert _parse_llm_payload("") is None
        assert _parse_llm_payload('{"intent": "bogus"}') is None
        assert _parse_llm_payload('["array"]') is None

    # ---- _disambiguate_by_market ----

    def test_disambiguate_no_market(self):
        cands = [Stock("HK09988", "阿里巴巴", "hk"), Stock("BABA", "阿里巴巴", "us")]
        picked, display = _disambiguate_by_market(cands, [])
        assert picked is None
        assert display == cands

    def test_disambiguate_single_hit(self):
        cands = [Stock("HK09988", "阿里巴巴", "hk"), Stock("BABA", "阿里巴巴", "us")]
        picked, display = _disambiguate_by_market(cands, [Market.HK])
        assert picked == [Stock("HK09988", "阿里巴巴", "hk")]
        assert display == cands  # 展示仍帶全量候選

    def test_disambiguate_contradictory_market_keeps_all(self):
        cands = [Stock("HK09988", "阿里巴巴", "hk"), Stock("BABA", "阿里巴巴", "us")]
        picked, display = _disambiguate_by_market(cands, [Market.A])
        assert picked is None
        assert display == cands  # 市場詞與候選矛盾：保守保留全部

    # ---- _dedup_stocks ----

    def test_dedup_stocks(self):
        stocks = [Stock("600519", "贵州茅台", "a"), Stock("600519", "茅台", "a")]
        assert _dedup_stocks(stocks) == [Stock("600519", "贵州茅台", "a")]

    # ---- _session_context ----

    def test_session_context_shapes(self):
        assert _session_context(None) == {}
        assert _session_context({"k": 1}) == {"k": 1}
        assert _session_context(_FakeSession(context={"k": 2})) == {"k": 2}
        assert _session_context(object()) == {}

    # ---- _token_facts 直測 ----

    def test_token_facts_unique_name_promoted(self):
        from src.agent.web_intent_resolver import _token_facts
        _, tokens = _preprocess_text("分析贵州茅台")
        f = _token_facts(_identify_stock_codes(tokens))
        assert [s.code for s in f["stocks"]] == ["600519"]
        assert f["ambiguous"] == []
        assert f["code_entity"] is False  # 名稱路徑不算顯式代碼

    def test_token_facts_sector_combo(self):
        # "行業名+泛稱"相鄰組合（Step 6 DFS 自然產出）→ 板塊高置信事實
        from src.agent.web_intent_resolver import _token_facts
        _, tokens = _preprocess_text("建筑板块怎么样")
        f = _token_facts(_identify_stock_codes(tokens))
        assert f["sector_combo"] is True
        assert not f["has_entity"] and bool(
            {"sector", "sector_name"} & f["tags"])

    def test_token_facts_bare_sector_no_combo(self):
        # 裸行業名無泛稱後綴：不構成 combo（對象歧義未消）
        from src.agent.web_intent_resolver import _token_facts
        _, tokens = _preprocess_text("半导体怎么样")
        f = _token_facts(_identify_stock_codes(tokens))
        assert f["sector_combo"] is False
        assert not f["has_entity"] and bool(
            {"sector", "sector_name"} & f["tags"])

    def test_token_facts_ambiguous_group(self):
        from src.agent.web_intent_resolver import _token_facts
        _, tokens = _preprocess_text("分析阿里巴巴")
        f = _token_facts(_identify_stock_codes(tokens))
        assert f["stocks"] == []
        assert len(f["ambiguous"]) == 1
        name, group = f["ambiguous"][0]
        assert name == "阿里巴巴"
        assert {s.code for s in group} == {"HK09988", "BABA"}

    def test_token_facts_wrong_and_unknown_codes(self):
        from src.agent.web_intent_resolver import _token_facts
        _, tokens = _preprocess_text("分析SH999999")
        f = _token_facts(_identify_stock_codes(tokens))
        assert f["wrong_codes"] == ["SH999999"]

        _, tokens = _preprocess_text("分析ZZZZ")
        f = _token_facts(_identify_stock_codes(tokens))
        # 美股精選庫未命中 → 未驗證透傳（非全量庫無判定把握）
        assert f["unverified_codes"] == ["ZZZZ"]
        assert f["unknown_codes"] == []

    def test_token_facts_numeric_promotion(self):
        from src.agent.web_intent_resolver import _token_facts
        _, tokens = _preprocess_text("300750怎么样")
        f = _token_facts(_identify_stock_codes(tokens))
        assert [s.code for s in f["stocks"]] == ["300750"]


# =========================================================================
# 實戰場景迴歸 — 候選間比較重建 / 純市場詞重問 / 繼承守衛 / 載荷健壯性
# =========================================================================


class TestConfirmationHardening:
    @staticmethod
    def _pending_pingan() -> Dict[str, Any]:
        # "平安"歧義：平安銀行 / 中國平安 雙候選（同市場，名稱可區分）
        return {
            "action": "confirm_stock",
            "intent": "stock_analysis",
            "name": "平安",
            "candidates": [
                {"code": "000001", "name": "平安银行", "market": "a"},
                {"code": "601318", "name": "中国平安", "market": "a"},
            ],
            "original_request": "分析平安",
        }

    def test_candidate_comparison_rebuilt_by_reclassify(self):
        # 確認窗口中點名兩候選 + 比較詞 = 新的多股比較請求：競爭錨點
        # 攔截後按完整語義重新分類，不靜默確認第一隻、不丟比較語義
        session = {PENDING_ACTIONS_KEY: [self._pending_pingan()]}
        r = _resolver().resolve_first("平安银行和中国平安哪个好", session)
        assert r.source == "rule"
        assert not r.needs_confirmation
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["000001", "601318"]

    def test_comparison_with_third_stock_not_rebuilt(self):
        # 混入候選外第三標的（SOFI）的比較請求：不重建、不靜默確認第一
        # 只，交正常流程重新分類（存疑代碼轉 LLM 兜底）
        session = {PENDING_ACTIONS_KEY: [self._pending_pingan()]}
        r = _resolver().resolve_first("平安银行和中国平安和SOFI哪个好", session)
        assert r.source == "rule"
        assert r.reason != "candidate_comparison"
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["000001", "601318"]

    def test_research_anchor_reply_not_consumed(self):
        # 帶研究詞的回覆是新請求（競爭意圖錨點）：即便點名候選也不作
        # 確認消費，交正常流程按完整語義分類
        session = {PENDING_ACTIONS_KEY: [self._pending_pingan()]}
        tasks = _flat(_resolver().resolve("再分析下平安银行最近走势", session))
        assert [(t.source, _codes(t)) for t in tasks] == [
            ("confirmation", ["000001"]), ("rule", ["000001"])]
        assert all(t.intent == WebIntent.STOCK_ANALYSIS for t in tasks)
        assert not any(t.needs_confirmation for t in tasks)

    def test_resolved_stocks_merged_on_confirmation(self):
        # 確認消費合併 pending.resolved_stocks：原請求的另一端不丟失
        pending = _pending_ali()
        pending["resolved_stocks"] = [
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
        ]
        r = _resolver().resolve_first("港股", {PENDING_ACTIONS_KEY: [pending]})
        assert r.source == "confirmation"
        assert _codes(r) == ["HK09988", "00700"]

    def test_ambiguous_pending_carries_resolved_stocks(self):
        # 規則歧義確認的 pending_action 攜帶已解析實體
        r = _resolver().resolve_first("对比茅台和阿里巴巴")
        assert r.needs_confirmation
        pa = r.pending_action
        assert pa["resolved_stocks"][0]["code"] == "600519"
        assert {c["code"] for c in pa["groups"][0]["candidates"]} == {"HK09988", "BABA"}

    def test_entity_with_wrong_code_keeps_both(self):
        # 合法實體 + 非法代碼並存：實體保留，非法代碼進 unresolved 確認
        r = _resolver().resolve_first("分析600519和SH999999")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]
        assert r.unresolved_names == ["SH999999"]
        assert r.needs_confirmation
        assert r.reason == "stock_unresolved"


class TestFollowupInheritGuard:
    def test_research_with_unknown_subject_not_inherited(self):
        # "再分析一下你好股份"：名稱庫外 token 很可能是研究對象，
        # 不得誤判為對上輪股票的追問（寧可低置信也不做錯）
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver().resolve_first("再分析一下你好股份", session)
        assert r.source == "rule"
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_unknown_code_subject_not_inherited(self):
        # "再分析下SOFI"：存疑代碼是帶 tag 的未消化信號，不得繼承上輪
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver().resolve_first("再分析下SOFI", session)
        assert r.source == "rule"
        assert r.intent == WebIntent.STOCK_ANALYSIS  # 存疑代碼路徑

    def test_bare_number_subject_not_inherited(self):
        # "再分析下09988"：5 位裸數字不提升為實體，但也不得當作追問繼承
        session = {LAST_INTENT_KEY: "quote_lookup"}
        r = _resolver().resolve_first("再分析下09988", session)
        assert r.source == "rule"
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_clean_research_followup_still_inherits(self):
        # 全部 token 可識別的研究追問不受守衛影響，正常繼承
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver().resolve_first("继续分析一下", session)
        assert r.source == "context"
        assert r.intent == WebIntent.STOCK_ANALYSIS


class TestLlmPayloadHardening:
    def test_fence_with_trailing_text(self):
        # code fence 後夾帶含 } 的解釋文字：深度提取不被末個 } 帶偏
        raw = '好的：```json\n{"intent": "quote_lookup", "confidence": 0.9}\n``` 以上就是结果 }'
        payload = _parse_llm_payload(raw)
        assert payload is not None
        assert payload["intent"] == "quote_lookup"

    def test_bom_prefix(self):
        assert _parse_llm_payload('\ufeff{"intent": "general_chat"}') is not None

    def test_label_normalization(self):
        # 大小寫/連字符/尾部標點先規範化再校驗
        payload = _parse_llm_payload('{"intent": "Stock-Analysis。", "confidence": 0.9}')
        assert payload["intent"] == "stock_analysis"

    def test_market_variants_normalized(self):
        payload = _parse_llm_payload('{"intent": "general_chat", "market": "港股"}')
        assert payload["market"] == Market.HK
        payload = _parse_llm_payload('{"intent": "general_chat", "market": "USA"}')
        assert payload["market"] == Market.US

    def test_braces_inside_string_not_confused(self):
        # JSON 字符串值裡的 } 不終止對象提取
        raw = '结果 {"intent": "general_chat", "note": "含}花括号"} 完毕'
        payload = _parse_llm_payload(raw)
        assert payload is not None
        assert payload["intent"] == "general_chat"

    def test_invalid_intent_rejected(self):
        assert _parse_llm_payload('{"intent": "bogus"}') is None

    @staticmethod
    def _merge(payload):
        rule = WebIntentResolution(intent=WebIntent.GENERAL_CHAT, confidence=0.5)
        return _merge_llm_result(rule, payload, {})

    def test_nan_confidence_treated_as_missing(self):
        # NaN 擊穿一切比較（nan < 0.6 恆 False）會偽裝成高置信跳過確認
        r = self._merge({"intent": "general_chat", "confidence": float("nan")})
        assert r.confidence == 0.5

    def test_llm_market_disambiguates_rule_candidates(self):
        # LLM 市場推斷消解規則歧義候選："美股"語境下雙候選收斂到 BABA。
        # 觸發路徑：詞池外語氣詞留下空 tag 殘段 → 非全識別豁免 → 兜底
        stub = _StubLLMAdapter(
            content='{"intent": "stock_analysis", "confidence": 0.9, "market": "us"}'
        )
        r = _resolver(stub).resolve_first("阿里巴巴哈哈哈")
        assert r.source == "llm"
        assert _codes(r) == ["BABA"]
        assert r.candidates == []
        assert not r.needs_confirmation

    def test_llm_market_pick_then_extra_code_rejected(self):
        # 市場推斷消解唯一歧義組清空 candidates 後，組外庫內代碼
        # （600519，原文未提及）仍須拒收——閘門判據是輸入屬性快照，
        # 不隨市場消解收縮
        stub = _StubLLMAdapter(content=(
            '{"intent": "stock_analysis", "confidence": 0.9, '
            '"market": "us", "stock_codes": ["600519"]}'))
        r = _resolver(stub).resolve_first("阿里巴巴哈哈哈")
        assert r.source == "llm"
        assert _codes(r) == ["BABA"]
        assert not r.needs_confirmation

    def test_multi_mentions_via_stock_codes(self):
        # 多標的提及（多股比較）：stock_codes 列表逐個過三道閘門
        stub = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_codes=["AAPL", "600519"]))
        r = _resolver(stub).resolve_first("对比下这两只")
        assert r.source == "llm"
        assert _codes(r) == ["AAPL", "600519"]
        assert not r.needs_confirmation

    def test_adapter_unavailable_skips_llm(self):
        # is_available 為假（未配 key 等）時不發調用，規則結果直接落確認
        stub = _StubLLMAdapter(
            content='{"intent": "general_chat", "confidence": 0.9}'
        )
        stub.is_available = False
        r = _resolver(stub).resolve_first("阿里巴巴怎么样")
        assert stub.calls == []
        assert r.needs_confirmation


# =========================================================================
# 惰性 LLM adapter — 構造零成本，首次兜底才從 config 構建
# =========================================================================


class TestLazyLlmAdapter:
    """構造函數契約：config 進、adapter 不動；構建點被替換為本地樁，
    單元內不觸真 litellm provider 棧。"""

    @staticmethod
    def _patch_builder(monkeypatch, builder) -> None:
        import src.agent.llm_adapter as llm_mod

        monkeypatch.setattr(llm_mod, "LLMToolAdapter", builder)

    def test_config_only_defers_build_until_first_fallback(self, monkeypatch):
        marker = object()
        built = []

        def fake_builder(config):
            built.append(config)
            return marker

        self._patch_builder(monkeypatch, fake_builder)
        config = object()
        resolver = WebIntentResolver(config)
        assert resolver._llm_adapter is None  # 構造完成 ≠ LLM 已初始化
        assert resolver._ensure_llm_adapter() is marker
        assert built == [config]
        assert resolver._ensure_llm_adapter() is marker  # 冪等複用
        assert len(built) == 1

    def test_injected_adapter_skips_lazy_build(self, monkeypatch):
        def unexpected(_config):
            raise AssertionError("injected adapter must bypass lazy build")

        self._patch_builder(monkeypatch, unexpected)
        stub = _StubLLMAdapter()
        resolver = WebIntentResolver(llm_adapter=stub)
        assert resolver._ensure_llm_adapter() is stub

    def test_init_failure_disables_fallback_permanently(self, monkeypatch):
        calls = []

        def failing_builder(_config):
            calls.append(1)
            raise RuntimeError("no api key")

        self._patch_builder(monkeypatch, failing_builder)
        resolver = WebIntentResolver(object())
        assert resolver._ensure_llm_adapter() is None
        assert resolver._ensure_llm_adapter() is None  # 失敗後不再重試
        assert len(calls) == 1

    def test_no_config_no_adapter_stays_disabled(self, monkeypatch):
        def unexpected(_config):
            raise AssertionError("no-config must not reach builder")

        self._patch_builder(monkeypatch, unexpected)
        assert WebIntentResolver()._ensure_llm_adapter() is None


# =========================================================================
# 兼容 re-export — resolver 自身消費的符號經其入口可取（tokenizer 側由
# 文件頂部 import 釘住：_preprocess_text/_identify_stock_codes）
# =========================================================================


class TestReExports:
    def test_types_symbols(self):
        from src.agent.web_intent_resolver import (  # noqa: F401
            ALL_WEB_INTENTS,
            CONFIRMATION_CONFIDENCE_THRESHOLD,
            LLM_FOLLOWUP_LABEL,
            Token as _Token,
            WebIntentResolution as _Resolution,
        )
        assert "stock_analysis" in ALL_WEB_INTENTS
        assert LLM_FOLLOWUP_LABEL == "followup"
        assert LLM_FOLLOWUP_LABEL not in ALL_WEB_INTENTS  # 偽標籤不入意圖枚舉
        assert CONFIRMATION_CONFIDENCE_THRESHOLD == 0.6

    def test_service_symbols(self):
        from src.services.name_to_code_resolver import (
            is_known_stock_name,
            lookup_stock_by_code,
            resolver_name_to_code_list,
        )
        assert lookup_stock_by_code("600519") is not None
        assert is_known_stock_name("贵州茅台")
        assert [s.code for s in resolver_name_to_code_list("酒鬼酒")] == ["000799"]


# =========================================================================
# 板塊槽位填充 — sector_analysis / 板塊報數的分析對象（與 stocks 同構）
# =========================================================================


class TestSectorSlotFilling:
    def test_combo_sector_analysis_fills_slot(self):
        # "行業名+泛稱"相鄰組合：高置信直達，板塊名入槽
        r = _resolver().resolve_first("分析一下白酒板块")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.sectors == ["白酒"]

    def test_combo_sector_quote_fills_slot(self):
        # 板塊報數（quote_lookup）同樣需要分析對象：槽位照填
        r = _resolver().resolve_first("白酒板块今天涨了多少")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.sectors == ["白酒"]

    def test_bare_sector_name_fills_slot(self):
        # 裸行業名精確命中詞池：0.85 直達免確認，槽位填充
        r = _resolver().resolve_first("半导体")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.needs_confirmation is False
        assert r.sectors == ["半导体"]

    def test_sector_n_stock_fills_slot(self):
        # 行業名兼股票全名（"機器人"）：板塊語境下按板塊名入槽
        r = _resolver().resolve_first("机器人板块怎么样")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["机器人"]
        assert r.stocks == []

    def test_multiple_sectors_kept_in_order(self):
        r = _resolver().resolve_first("白酒和半导体板块怎么样")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["白酒", "半导体"]

    def test_repeated_sector_deduped(self):
        r = _resolver().resolve_first("白酒白酒板块")
        assert r.sectors == ["白酒"]

    def test_broad_market_uses_market_name_slot(self):
        # 泛市場無具名板塊：槽位填市場名（無限定為"大盤"，範圍語義
        # 同時由 market 字段表達）
        r = _resolver().resolve_first("大盘怎么看")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["大盘"]

    def test_stock_intent_has_empty_sector_slot(self):
        r = _resolver().resolve_first("分析茅台")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.sectors == []
        assert _codes(r) == ["600519"]

    def test_out_of_pool_sector_before_generic_suffix(self):
        # 詞池外行業名 + 泛稱後綴（"CPO板塊"）：回溯提取為板塊名，代碼
        # 身份解除，combo 高置信直達（不經存疑代碼分支/LLM）
        r = _resolver().resolve_first("查一下现在CPO板块的情况")
        assert r.source == "rule"
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.confidence == 0.85
        assert r.sectors == ["CPO"]
        assert not r.needs_confirmation

    def test_view_phrase_rule_direct_after_pool_extension(self):
        # "看下"在 extend 詞池（action_quote）：整段 DFS 全覆蓋成功，
        # 雙板塊組合（人工智能+賽道 / AI+板塊）規則 0.85 直達（交 LLM
        # 會壓置信至 0.75 並引入板塊名改寫風險）；sectors 按原文順序
        # 保序填充
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["人工智能", "AI"],
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("看下现在人工智能赛道和AI板块的走势")
        assert stub.calls == []
        assert r.source == "rule"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.sectors == ["人工智能", "AI"]

    def test_stock_code_before_suffix_not_backtracked(self):
        # 顯式股票代碼 + 泛稱（"600519板塊成分"）保持股票語義：代碼即
        # 標的，不回溯提取為板塊名
        r = _resolver().resolve_first("分析600519板块成分")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.sectors == []
        assert _codes(r) == ["600519"]

    def test_numeric_and_short_prefix_not_backtracked(self):
        # 純數字（"3板塊"）與單字段（"看板塊"）不提取為板塊名
        from src.agent.web_intent_resolver import _token_facts
        f = _token_facts(_identify_stock_codes(_preprocess_text("聊聊3板块")[1]))
        assert f["sectors"] == []
        f2 = _token_facts(_identify_stock_codes(_preprocess_text("看板块怎么样")[1]))
        assert f2["sectors"] == []

    def test_hk_unverified_code_passed_through(self):
        # hk 非全量庫存疑（未命中 ≠ 非法）：確認機制不適用——系統對
        # 無把握判定的指稱不做確認，未驗證代碼透傳執行端實查
        r = _resolver().resolve_first("hk66373和酒鬼酒对比分析")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["000799"]
        assert r.unverified_codes == ["hk66373"]
        assert not r.needs_confirmation

    def test_hk_unverified_before_entity_variant(self):
        r = _resolver().resolve_first("酒鬼酒和hk66373对比")
        assert r.unverified_codes == ["hk66373"]
        assert not r.needs_confirmation

    def test_aside_unknown_code_passthrough(self):
        # "順便"切分出附帶任務：規則判 stock（與主任務 quote 意圖不同，
        # 不折疊）→ 兩任務各自透傳；附帶 unverified 不影響主任務直達
        rs = _resolver().resolve("茅台多少钱顺便看下SOFI")
        assert len(_flat(rs)) == 2
        assert _flat(rs)[0].intent == WebIntent.QUOTE_LOOKUP
        assert _codes(_flat(rs)[0]) == ["600519"]
        assert not any(t.needs_confirmation for t in _flat(rs))
        assert _flat(rs)[1].unverified_codes == ["SOFI"]

    def test_broad_market_word_is_context_not_subject(self):
        # 泛市場詞（行情）是 clean 池獨立存活，板塊 extend 詞靠 DFS 全
        # 覆蓋——"XX板塊的行情"裡泛市場信號更易存活。泛市場是兜底對象
        # 而非競爭對象：具名板塊在場時落穿板塊分支（不被 ['大盤'] 劫持）
        r = _resolver().resolve_first("白酒板块今天行情怎么样")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["白酒"]

    def test_unverified_code_with_market_context_routes_to_llm(self):
        # 未驗證代碼 + 泛市場語境共存（"PEEK板塊的整體行情"，PEEK 未
        # 收錄）：板塊 tag 隨 DFS 失敗陪葬，規則無法判定板塊 vs 個股
        # ——低置信交 LLM 讀原文裁定，sectors 經原文閘門、unverified
        # 保留。（CPO 在 clean 詞池：同型消息規則層直達 sectors=['CPO']）
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["PEEK"],
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("分析PEEK板块的整体行情")
        assert r.source == "llm"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["PEEK"]
        assert r.unverified_codes == ["PEEK"]

    def test_index_product_combo_direct(self):
        # combo 白名單含指數主題：指數 + ETF 泛稱組合（指數 ETF 是
        # 最大品類）高置信直達，指數文本入 sectors 槽位；裸指數（無
        # 泛稱）仍走分支 4 的 index_subjects 路徑，兩者不衝突
        r = _resolver().resolve_first("沪深300ETF")
        assert r.source == "rule"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.sectors == ["沪深300"]
        # 雙指數 ETF 組合比較：主題保序直達
        r2 = _resolver().resolve_first("中证500ETF和沪深300ETF对比")
        assert r2.sectors == ["中证500", "沪深300"]
        assert r2.confidence == 0.85
        # 裸指數：仍走報數路徑，槽位為指數原文
        r3 = _resolver().resolve_first("沪深300怎么样")
        assert r3.intent == WebIntent.QUOTE_LOOKUP
        assert r3.sectors == ["沪深300"]

    def test_product_suffix_forms_combo(self):
        # ETF/LOF/REITs 是產品類泛稱後綴（"銀行ETF"與"銀行板塊"結構
        # 同構）：相鄰組合高置信直達（ASCII 泛稱經關鍵詞放行，不被
        # Step 3 當美股 ticker 摳走）
        r = _resolver().resolve_first("综合分析下银行ETF")
        assert r.source == "rule"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.sectors == ["银行"]
        assert r.unverified_codes == []
        # 雙主題 ETF 組合比較：多板塊保序直達
        r2 = _resolver().resolve_first("军工ETF和银行ETF对比")
        assert r2.sectors == ["军工", "银行"]
        assert r2.confidence == 0.85
        # 裸泛稱（無主題名）：泛指 ETF 產品，低置信交 LLM/確認
        r3 = _resolver().resolve_first("哪些ETF好")
        assert r3.sectors == []
        assert r3.confidence == 0.5

    def test_abbrev_concept_in_clean_pool_survives_dfs_failure(self):
        # 英文縮寫概念在 clean 池獨立存活（詞邊界全詞匹配 + Step 3
        # ticker 放行）：泛稱詞隨 DFS 失敗陪葬時縮寫不連帶丟失
        r = _resolver().resolve_first("分析CPO板块的整体行情")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["CPO"]
        r2 = _resolver().resolve_first("分析AI行情")
        assert r2.sectors == ["AI"]

    def test_pure_broad_market_still_direct(self):
        # 純泛市場（無任何具體對象殘渣）：兜底對象成立，直達不變
        r = _resolver().resolve_first("今天大盘怎么样")
        assert r.source == "rule"
        assert r.sectors == ["大盘"]

    def test_broad_market_sectors_unified_slot(self):
        # 泛市場/指數的 sectors 統一槽位：指數用原文、純泛市場用市場名
        # （無限定"大盤"）——執行端與具名板塊同構，只消費 sectors
        r = _resolver().resolve_first("分析昨天大A的整体行情")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["A股"]
        assert _resolver().resolve_first("今天大盘怎么样").sectors == ["大盘"]
        assert _resolver().resolve_first("港股行情怎么样").sectors == ["港股"]
        assert _resolver().resolve_first("研究下上证指数").sectors == ["上证"]
        assert _resolver().resolve_first("沪深300怎么样").sectors == ["沪深300"]

    def test_action_intent_upgrades_broad_market_to_sector(self):
        # 泛市場語境的明確動作意圖（分析/看看等 request）升級板塊分析
        # ——"分析昨天大A的整體行情"要結構論述而非一個點位；純疑問
        # （無動作詞）"今天大盤怎麼樣"仍默認報數
        r = _resolver().resolve_first("分析昨天大A的整体行情")
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert _resolver().resolve_first("看看大盘行情").intent == WebIntent.SECTOR_ANALYSIS
        assert _resolver().resolve_first("今天大盘怎么样").intent == WebIntent.QUOTE_LOOKUP
        assert _resolver().resolve_first("研究下上证指数").intent == WebIntent.SECTOR_ANALYSIS

    def test_deep_verb_keeps_stock_default(self):
        # 個股語境動作詞：裸個股默認分析不變
        r = _resolver().resolve_first("分析茅台")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.confidence == 0.85

    def test_coordination_unknown_name_routed_to_llm(self):
        # 並列未知名稱（庫中不存在）：整段 DFS 失敗 → LLM 兜底裁定，
        # 茅臺查庫採信、西藏建工無庫可驗由 LLM 語境判斷
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "stock_analysis", "confidence": 0.9,
            "stock_code": "600519",
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("分析茅台和西藏建工")
        assert r.source == "llm"
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["600519"]

    def test_probe_extracts_multiple_entities_per_segment(self):
        # 段內多股並列的兩個實體都提取
        r = _resolver().resolve_first("分析茅台和五粮液")
        assert _codes(r) == ["600519", "000858"]
        assert not r.needs_confirmation

    def test_out_of_pool_word_routed_to_llm(self):
        # "近況"不在詞池 → 整段 DFS 放棄 → LLM 兜底；"情況"在詞池
        # 時 DFS 全覆蓋成功，取數詞與實體共現高置信直達
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "quote_lookup", "confidence": 0.9,
            "stock_code": "600519",
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("查一下现在茅台的近况")
        assert r.source == "llm"
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(r) == ["600519"]
        r2 = _resolver().resolve_first("查一下现在茅台的情况")
        assert r2.source == "rule"
        assert r2.intent == WebIntent.QUOTE_LOOKUP
        assert r2.confidence == 0.85

    def test_entity_probe_full_name_in_mixed_segment(self):
        r = _resolver().resolve_first("聊聊三花智控呗")
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["002050"]

    def test_entity_probe_ambiguous_two_candidates(self):
        # 雙候選（平安銀行/中國平安）保留歧義確認語義，不靜默選一
        r = _resolver().resolve_first("平安的情况")
        assert _candidate_codes(r) == ["000001", "601318"]
        assert r.needs_confirmation is True
        assert r.reason == "ambiguous_stock_name"

    def test_entity_probe_generic_word_gated_by_candidates(self):
        # 泛詞"中國"命中 5 候選（中國平安/中石化/…整族前綴）：歧義組
        # 候選數上限統一擋住，不觸發無意義確認
        r = _resolver().resolve_first("中国的情况怎么样")
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.stocks == [] and r.candidates == []

    def test_unseen_concept_routed_to_llm(self):
        # 從未收錄的概念名（詞池外）+ 泛稱後綴：整段 DFS 失敗 → 規則
        # 低置信交 LLM 兜底，LLM 板塊名經原文閘門填充槽位
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["固态电池"],
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("固态电池概念有哪些股票")
        assert r.source == "llm"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["固态电池"]

    def test_trading_action_word_keeps_sector_tokens(self):
        # 交易決策詞（抄底等）在池 → DFS 全覆蓋成功，規則直達且槽位
        # 填充；詞池外表述（"該止盈"的"該"不在池）整段失敗交 LLM 兜底
        r = _resolver().resolve_first("白酒板块现在能抄底吗")
        assert r.source == "rule"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.sectors == ["白酒"]
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["白酒"],
        }, ensure_ascii=False))
        r2 = WebIntentResolver(llm_adapter=stub).resolve_first("白酒板块该止盈了吗")
        assert r2.source == "llm"
        assert r2.sectors == ["白酒"]

    def test_llm_unresolved_name_channel(self):
        # LLM schema 的 unresolved_names 通道：LLM 判定意圖但標的無法
        # 解析（"你好股份"生造名）時原文報告，經原文閘門後走既有
        # stock_unresolved 確認——空標的執行任務是無效產出
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "stock_analysis", "confidence": 0.9,
            "unresolved_names": ["你好股份", "编造的名称"],
        }, ensure_ascii=False))
        rs = WebIntentResolver(llm_adapter=stub).resolve("分析一下你好股份")
        r = _flat(rs)[0]
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.unresolved_names == ["你好股份"]  # 編造名被原文閘門拒
        assert r.needs_confirmation is True
        assert r.reason == "stock_unresolved"

    def test_llm_sectors_filled_with_text_gate(self):
        # 規則側未提取到板塊（長尾措辭整段 DFS 失敗）時，LLM 返回的
        # 板塊名經"原文出現"閘門合入：命中的保留，編造的丟棄
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["固态电池", "编造的板块"],
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("吧固态电池呢")
        assert r.source == "llm"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["固态电池"]

    def test_llm_sectors_merge_with_rule_base(self):
        # 無泛稱後綴的裸概念（規則無從提取）由 LLM 返回並過原文閘門填充；
        # 編造板塊被閘門丟棄
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["固态电池", "编造板块"],
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("固态电池和CPO呢")
        assert r.source == "llm"
        # 規則基底（CPO 在詞池）優先，LLM 補充原文出現的新板塊
        assert r.sectors == ["CPO", "固态电池"]

    def test_combo_phrase_bypasses_llm(self):
        # "AI板塊呢"類裸板塊短語：combo 已消除對象歧義，規則 0.85 直達
        # 不進 LLM（進 LLM 會降置信至 0.75 並引入板塊名重複入槽）
        r = _resolver().resolve_first("AI板块呢")
        assert r.source == "rule"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.confidence == 0.85
        assert r.sectors == ["AI"]

    def test_llm_sector_suffix_variant_deduped(self):
        # LLM 返回"半導體板塊"（帶泛稱後綴）與規則基底"半導體"是同一
        # 板塊的兩種表述：按去後綴鍵去重，不重複入槽；編造項仍被原文
        # 閘門丟棄
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "sector_analysis", "confidence": 0.9,
            "sectors": ["机器人板块", "编造板块"],
        }, ensure_ascii=False))
        r = WebIntentResolver(llm_adapter=stub).resolve_first("机器人呢")
        assert r.source == "llm"
        assert r.sectors == ["机器人"]

    def test_llm_override_keeps_rule_sectors(self):
        # 裸行業名走 LLM 複核改判時，規則側提取的板塊名不丟
        stub = _StubLLMAdapter(
            content='{"intent": "sector_analysis", "confidence": 0.9}',
        )
        r = WebIntentResolver(llm_adapter=stub).resolve_first("机器人")
        assert r.source == "llm"
        assert r.intent == WebIntent.SECTOR_ANALYSIS
        assert r.sectors == ["机器人"]
        assert not r.needs_confirmation

# =========================================================================
# =========================================================================
# 多意圖 — 任務序列（子消息序列保序 + 同句並存分解）
# =========================================================================


class TestTaskSplitting:
    def test_heterogeneous_subjects_split_to_tasks(self):
        # 同句並存（無標點）：個股主體 + 板塊對象分解為任務序列；
        # 頂層字段即首任務形態（板塊對象歸位到板塊任務自身）
        rs = _resolver().resolve("分析茅台和白酒板块")
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.STOCK_ANALYSIS, WebIntent.SECTOR_ANALYSIS,
        ]
        assert _codes(_flat(rs)[0]) == ["600519"]
        assert _flat(rs)[1].sectors == ["白酒"]

    def test_etf_subject_split_to_tasks(self):
        rs = _resolver().resolve("茅台和银行ETF对比")
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.STOCK_ANALYSIS, WebIntent.SECTOR_ANALYSIS,
        ]
        assert _flat(rs)[1].sectors == ["银行"]

    def test_pure_subject_single_task(self):
        # 無並存不分解：單任務消息（resolve 返回單元素列表）
        rs = _resolver().resolve("分析茅台")
        assert len(_flat(rs)) == 1
        assert _flat(rs)[0].sectors == []
        assert len(_resolver().resolve("白酒板块怎么样")) == 1

    def test_three_intents_with_sequence(self):
        # 子消息序列 + 消息內並存疊加：按用戶表達順序保序，頂層投影
        # 為首個任務（sector＝用戶說的第一件事）
        rs = _resolver().resolve("分析下CPO和AI板块，然后再分析茅台走势和我的持仓")
        assert _flat(rs)[0].intent == WebIntent.SECTOR_ANALYSIS
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.SECTOR_ANALYSIS,
            WebIntent.STOCK_ANALYSIS,
            WebIntent.PORTFOLIO_ANALYSIS,
        ]
        assert _flat(rs)[0].sectors == ["CPO", "AI"]
        assert _codes(_flat(rs)[1]) == ["600519"]

    def test_pure_stock_portfolio_task(self):
        rs = _resolver().resolve("茅台走势和我的持仓")
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.STOCK_ANALYSIS, WebIntent.PORTFOLIO_ANALYSIS,
        ]

    def test_portfolio_dominant_keeps_sector_task(self):
        rs = _resolver().resolve("我的持仓和白酒板块怎么样")
        assert _flat(rs)[0].intent == WebIntent.PORTFOLIO_ANALYSIS
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.PORTFOLIO_ANALYSIS, WebIntent.SECTOR_ANALYSIS,
        ]
        assert _flat(rs)[1].sectors == ["白酒"]

    def test_institutional_holdings_single_task(self):
        # 領屬限定："分析茅臺的持倉"是機構持倉研究維度，不分解組合任務
        assert len(_resolver().resolve("分析茅台的持仓")) == 1

    def test_group_level_source_request(self):
        # 兩級上下文：任務級 original_request=該子消息文本，組級
        # source_request=歧義組的來源子消息，與分歧一一對應
        # ——不折疊，每個確認任務各自攜帶自己的組
        rs = _resolver().resolve("阿里的走势怎么样，平安呢")
        tasks = _flat(rs)
        assert len(tasks) == 2
        pa0, pa1 = tasks[0].pending_action, tasks[1].pending_action
        assert pa0["original_request"] == "阿里的走势怎么样"
        assert pa1["original_request"] == "平安呢"
        assert [g["name"] for g in pa0["groups"]] == ["阿里"]
        assert [g["name"] for g in pa1["groups"]] == ["平安"]
        assert pa0["groups"][0]["source_request"] == "阿里的走势怎么样"
        assert pa1["groups"][0]["source_request"] == "平安呢"
        # 一條回覆兩組獨立消解（last_resolutions 攜帶全部確認任務；
        # 會話經 apply 雙鍵同步構造——pending_actions 是消費閘門的
        # 存活權威，單鍵手寫會話不構成合法消費源）
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, rs)
        rs2 = _resolver().resolve("美股 平安银行", session)
        assert not any(t.needs_confirmation for t in _flat(rs2))

    def test_aggregated_confirmation_full_cycle(self):
        # 雙歧義全聚合：一次 pending.groups 兩組，用戶逐組給聚合項解除
        # → tasks 彙總執行；只解除一組時未解組再次 pending（已解組暫存
        # confirmed）
        r = _resolver()
        session: Dict[str, Any] = {}
        rs = r.resolve("阿里巴巴多少钱，平安呢")
        apply_resolution_to_session(session, rs)
        confirmings = [t for t in _flat(rs) if t.needs_confirmation]
        # 兩個確認任務各自獨立成組，組隨任務保留
        assert [g["name"] for c in confirmings
                for g in c.pending_action["groups"]] == ["阿里巴巴", "平安"]
        # 只解除阿里組（"美股"→BABA）：平安確認任務保留，阿里任務落位執行
        rs2 = r.resolve("美股", session)
        apply_resolution_to_session(session, rs2)
        p2 = next(t for t in _flat(rs2) if t.needs_confirmation).pending_action
        assert [g["name"] for g in p2["groups"]] == ["平安"]
        assert (WebIntent.QUOTE_LOOKUP, ["BABA"]) in [
            (t.intent, _codes(t)) for t in _flat(rs2)]
        # 解除平安組（"中國平安"全等命中）：全解除，任務按上輪序執行
        rs3 = r.resolve("中国平安", session)
        assert not any(t.needs_confirmation for t in _flat(rs3))
        assert [(t.intent, _codes(t)) for t in _flat(rs3)] == [
            (WebIntent.QUOTE_LOOKUP, ["BABA"]),
            (WebIntent.STOCK_ANALYSIS, ["601318"]),
        ]

    def test_chained_confirmation_decline_cancels_all(self):
        # 拒絕取消全鏈：全部待確認組作廢，閒聊產出無確認無任務
        r = _resolver()
        rs = r.resolve("阿里巴巴多少钱，平安呢")
        rs2 = r.resolve("算了", {PENDING_ACTIONS_KEY: [_flat(rs)[0].pending_action]})
        assert _flat(rs2)[0].intent == WebIntent.GENERAL_CHAT
        assert not any(t.needs_confirmation for t in _flat(rs2))
        assert len(_flat(rs2)) == 1

    def test_single_confirmation_no_chain(self):
        # 單歧義：確認消費直接落位（pending 無鏈式附加結構）
        r = _resolver()
        res = r.resolve_first("阿里巴巴多少钱")
        assert "queued" not in res.pending_action
        consumed = r.resolve_first("美股", {PENDING_ACTIONS_KEY: [res.pending_action]})
        assert not consumed.needs_confirmation
        # "美股" 收窄到組內唯一的 us 候選（BABA）
        us_codes = [c["code"] for g in res.pending_action["groups"]
                    for c in g["candidates"] if c["market"] == "us"]
        assert _codes(consumed) == us_codes

    def test_confirmation_suspends_sibling_sector_task(self):
        # 確認短路期間分解出的板塊任務是確認任務的兄弟任務：組結構保留
        # ——兄弟任務隨確認任務一起返回/入 last_resolutions（即跨輪暫存
        # 器，不散裝 sectors），結算後隨 ③ 拼接恢復
        rs = _resolver().resolve("阿里巴巴和白酒板块分析")
        flat = _flat(rs)
        confirming = next(t for t in flat if t.needs_confirmation)
        sibling = next(t for t in flat if t.intent == WebIntent.SECTOR_ANALYSIS)
        assert sibling.sectors == ["白酒"]
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, rs)
        rs2 = _resolver().resolve("港股", session)
        assert not any(t.needs_confirmation for t in _flat(rs2))
        # ③ 列表合併保原序：主任務（消解後就位）在前、分解兄弟在後
        assert [(t.intent, t.sectors) for t in _flat(rs2)] == [
            (WebIntent.STOCK_ANALYSIS, []),
            (WebIntent.SECTOR_ANALYSIS, ["白酒"]),
        ]

    def test_wrong_code_confirmation_keeps_sector_sibling(self):
        # 單子消息內 wrong-code 確認與板塊對象並存：醫藥板塊作為兄弟
        # 任務隨確認短路暫存，不被早返回分支吞掉
        rs = _resolver().resolve("分析医药板块和SH6005190")
        flat = _flat(rs)
        confirming = next(t for t in flat if t.needs_confirmation)
        assert confirming.intent == WebIntent.STOCK_ANALYSIS
        assert confirming.reason == "stock_unresolved"
        assert confirming.unresolved_names == ["SH6005190"]
        sector = next(t for t in flat if t.intent == WebIntent.SECTOR_ANALYSIS)
        assert sector.sectors == ["医药"]
        assert sector.stocks == []
        assert not sector.needs_confirmation

    def test_sequential_tasks_ordered(self):
        # 順序形態：子消息按用戶表達順序，鏈式保序
        rs = _resolver().resolve("先看看白酒板块，然后分析贵州茅台")
        assert _flat(rs)[0].intent == WebIntent.SECTOR_ANALYSIS
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.SECTOR_ANALYSIS, WebIntent.STOCK_ANALYSIS,
        ]
        assert _codes(_flat(rs)[1]) == ["600519"]

    def test_parallel_objects_not_split(self):
        # 並列對象（和/與）不切分：屬於同一任務的兩個標的
        rs = _resolver().resolve("茅台和五粮液对比")
        assert len(_flat(rs)) == 1
        assert len(_flat(rs)[0].stocks) == 2

    def test_quoted_code_not_split(self):
        # 英文句點是代碼組成（600519.HK）不是任務邊界
        sub = _split_sub_messages("分析600519.HK")
        assert len(sub) == 1

    def test_word_internal_connective_not_split(self):
        # X然複合詞 + 後/悔 拼出"然後"子串：連接詞切口要求"然後"是
        # token 文本起點，詞內"然後"（"居|然後市"＝居然+後市）無從
        # 觸發，詞界不撕裂——詞界完整性是"居然智家"簡稱提取與"後市"
        # 關鍵詞的共同前提
        assert _sub_texts("居然后市趋势如何") == ["居然后市趋势如何"]
        assert _sub_texts("仍然后悔没买茅台") == ["仍然后悔没买茅台"]

    def test_conflicting_cut_vetoed_without_sitting_good_boundaries(self):
        # 切口獨立判定：詞內"然後"不構成切口，同句的逗號邊界照常下刀
        assert _sub_texts("居然后市如何，分析茅台") == [
            "居然后市如何",
            "分析茅台",
        ]

    def test_connective_token_starts_new_sub_message(self):
        # 連接詞切分的下刀條件是"然後"為 token 文本起點："一下"在 clean
        # 詞池參與分詞，"分析茅臺然後看一下常山的價格"的"然後"被撕出為
        # 獨立 token → 兩個任務各歸各組；切分只分組不改寫元素（子消息
        # token 按序拼接 == 原文）。連接詞真正埋在無標籤 unknown_token
        # 內部無從下刀的契約由 test_probe_two_connective_cuts_in_one_
        # unknown_token 覆蓋。
        subs = _split_sub_messages("分析茅台然后看一下常山的价格")
        assert ["".join(t.text for t in sub) for sub in subs] == [
            "分析茅台", "然后看一下常山的价格",
        ]
        assert [t.text for t in subs[0]] == ["分析", "茅台"]
        assert "".join(t.text for t in subs[1]) == "然后看一下常山的价格"

    def test_juran_abbreviation_resolved_end_to_end(self):
        # 端到端：詞界保住後"居然"經子串匹配解析為"居然智家"（生產
        # 全量庫的一對一簡稱），強研究信號（後市/趨勢/如何）+ 實體 →
        # stock_analysis@0.85。mock 庫不含該股，按 tokenizer 測試慣例
        # 原地註冊並失效名稱緩存（autouse fixture 負責還原）
        from src.services import name_to_code_resolver as resolver_mod

        resolver_mod.stockDB["000785"] = "居然智家"
        resolver_mod._names_cache[:] = [None, None, None]
        rs = _resolver().resolve("居然后市趋势如何")
        assert _flat(rs)[0].intent == WebIntent.STOCK_ANALYSIS
        assert _codes(_flat(rs)[0]) == ["000785"]
        assert not _flat(rs)[0].needs_confirmation


class TestAggregationFixRegressions:
    """聚合/消歧的迴歸用例（兄弟任務保留、按任務獨立確認、繼承碼
    透傳、多輪鏈路衛生）。"""

    def test_cross_sub_message_sibling_preserved(self):
        # 跨子消息的兄弟任務（板塊）不靜默丟失——組
        # 結構保留，隨確認任務入 last_resolutions，結算後隨 ③ 拼接恢復
        rs = _resolver().resolve("分析阿里巴巴，然后看看白酒板块")
        flat = _flat(rs)
        confirming = next(t for t in flat if t.needs_confirmation)
        sibling = next(t for t in flat if t.intent == WebIntent.SECTOR_ANALYSIS)
        assert sibling.sectors == ["白酒"]
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, rs)
        rs2 = _resolver().resolve("港股", session)
        assert not any(t.needs_confirmation for t in _flat(rs2))
        # ③ 列表合併保原序：主任務（消解後就位）在前、兄弟板塊在後
        assert [(t.intent, _codes(t), t.sectors) for t in _flat(rs2)] == [
            (WebIntent.STOCK_ANALYSIS, ["HK09988"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["白酒"]),
        ]

    def test_low_confidence_confirmation_independent_tasks(self):
        # 確認按任務獨立成立：裸板塊任務 0.5 轉 low_confidence 確認，
        # 不受同意圖鄰居影響
        rs = _resolver().resolve("分析白酒板块，再看看机器人")
        tasks = _flat(rs)
        assert len(tasks) == 2
        assert all(t.intent == WebIntent.SECTOR_ANALYSIS for t in tasks)
        assert tasks[0].sectors == ["白酒"] and tasks[0].confidence == 0.85
        assert not tasks[0].needs_confirmation
        assert tasks[1].sectors == ["机器人"] and tasks[1].confidence < 0.6
        assert tasks[1].needs_confirmation
        assert tasks[1].reason == "low_confidence"

    def test_unresolved_confirmation_kept(self):
        # stock_unresolved 確認與 unresolved_names 按任務獨立保留——
        # 非法指稱（SH999999）不靜默消失
        rs = _resolver().resolve("先看看五粮液，然后分析600519和SH999999")
        tasks = _flat(rs)
        assert len(tasks) == 2
        assert _codes(tasks[0]) == ["000858"] and not tasks[0].needs_confirmation
        assert tasks[1].intent == WebIntent.STOCK_ANALYSIS
        assert tasks[1].needs_confirmation
        assert tasks[1].reason == "stock_unresolved"
        assert tasks[1].unresolved_names == ["SH999999"]
        assert _codes(tasks[1]) == ["600519"]

    def test_split_sibling_keeps_inherited_code(self):
        # 同句分解的兄弟任務透傳繼承代碼（歷史標的
        # 的持久化通道是會話鍵 recent_stocks，任務僅攜帶標量視圖）
        session = {RECENT_STOCKS_KEY: ["300750"]}
        rs = _resolver().resolve(
            "港股阿里巴巴和白酒板块分析", session_context=session)
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.STOCK_ANALYSIS, WebIntent.SECTOR_ANALYSIS,
        ]
        assert _codes(_flat(rs)[0]) == ["HK09988"]
        for t in _flat(rs):
            assert t.inherited_stock_code == "300750"
        assert _flat(rs)[0].primary_stock_code == "HK09988"

    def test_requeue_whitelist_no_duplicate_confirmed(self):
        # 部分消解的 pending 重建：resolved_stocks 並進 confirmed 後
        # 不隨行——多輪鏈路不重複累積
        pending = _pending_ali()
        pending["groups"] = [
            {"name": "阿里巴巴", "candidates": pending["candidates"],
             "source_request": "分析阿里巴巴"},
            {"name": "平安", "candidates": [
                {"code": "000001", "name": "平安银行", "market": "a"},
                {"code": "601318", "name": "中国平安", "market": "a"},
            ], "source_request": "分析平安"},
        ]
        pending["resolved_stocks"] = [
            {"code": "00700", "name": "腾讯控股", "market": "hk"},
        ]
        r = _resolver()
        # 第一輪只解阿里組：確認任務自身 stocks 合併隨行實體（騰訊 +
        # 消解 HK09988），confirmed 只記本輪消解——多輪不重複累積
        rs1 = r.resolve("港股", {PENDING_ACTIONS_KEY: [pending]})
        requeue = _flat(rs1)[0].pending_action
        assert sorted(_codes(_flat(rs1)[0])) == ["00700", "HK09988"]
        assert [s["code"] for c in requeue["confirmed"] for s in c["stocks"]] == ["HK09988"]
        # 第二輪解平安組：confirmed 無重複，全解結算包含全部實體
        rs2 = r.resolve("中国平安", {PENDING_ACTIONS_KEY: [requeue]})
        assert not any(t.needs_confirmation for t in _flat(rs2))
        settled = [s.code for t in _flat(rs2) for s in t.stocks]
        assert sorted(settled) == ["00700", "601318", "HK09988"]

    def test_multi_group_single_reply_resolves_all(self):
        # 一條回覆攜帶多組聚合項：各組獨立判定，一次全解；兩組 intent
        # 相同（stock_analysis）時結算聚合為單任務雙標的
        pending = _pending_ali()
        pending["groups"] = [
            {"name": "阿里巴巴", "candidates": pending["candidates"],
             "source_request": "分析阿里巴巴"},
            {"name": "平安", "candidates": [
                {"code": "000001", "name": "平安银行", "market": "a"},
                {"code": "601318", "name": "中国平安", "market": "a"},
            ], "source_request": "分析平安"},
        ]
        rs = _resolver().resolve("美股 平安银行", {PENDING_ACTIONS_KEY: [pending]})
        assert not any(t.needs_confirmation for t in _flat(rs))
        assert [(t.intent, _codes(t)) for t in _flat(rs)] == [
            (WebIntent.STOCK_ANALYSIS, ["BABA", "000001"]),
        ]


# =========================================================================
# last_resolution 消費鏈 — 用戶實戰樣例：full_resolution = _consume_
# confirmations(last_resolution, full_resolution) 的取數與三步穩定性
# =========================================================================


class TestLastResolutionConsumption:
    """驗證第五步數據鏈：上一輪 resolve → apply 寫入 last_resolutions
    （二維組結構）→ 下一輪 resolve 的 last_resolution 正確讀取 →
    _consume_confirmations 嚴格三步（就地消歧 / 丟棄純消歧元素 /
    列表合併）穩定運行。"""

    @staticmethod
    def _register_changshan() -> None:
        # 常山雙候選（常山北明/常山藥業）——mock 庫外的真實歧義形態，
        # autouse fixture 負責還原
        from src.services import name_to_code_resolver as resolver_mod

        resolver_mod.stockDB["000158"] = "常山北明"
        resolver_mod.stockDB["300255"] = "常山药业"
        resolver_mod._names_cache[:] = [None, None, None]

    def test_user_example_full_chain(self):
        # 用戶實戰樣例：三子消息歧義短路 → 聚合回覆逐組收窄 + 新任務
        self._register_changshan()
        r = _resolver()
        session: Dict[str, Any] = {}

        # 輪 1：三條子消息 → 短路，last_resolution 寫入三組（阿里確認 /
        # 常山確認 / 醫藥CPO直達），tokens 與意圖原樣保留
        rs1 = r.resolve(
            "分析一下茅台和阿里然后看一下常山的价格，"
            "最后分析下医药和CPO板块的走势",
            session,
        )
        apply_resolution_to_session(session, rs1)
        lr = session[LAST_RESOLUTIONS_KEY]
        assert len(lr) == 3  # 二維：每子消息一組
        assert [t["needs_confirmation"] for g in lr for t in g] == [True, True, False]
        assert [g_["name"] for g in lr for t in g
                for g_ in (t.get("pending_action") or {}).get("groups", [])] \
            == ["阿里", "常山"]
        assert lr[1][0]["intent"] == WebIntent.QUOTE_LOOKUP  # 常山組屬行情子消息
        assert lr[0][0]["tokens"][:2] == ["分析", "一下"]     # tokens 不缺失

        # 輪 2："港股"收窄阿里組、"常山藥業"全等收窄常山組（同一條子
        # 消息的兩個聚合項）、"再分析下三花"是新任務（kept）
        rs2 = r.resolve("港股和常山药业，再分析下三花", session)
        flat = _flat(rs2)
        assert not any(t.needs_confirmation for t in flat)
        # ③ 列表合併保序：上輪三組（就地消解後就位）在前、本輪 kept 在後
        assert [(t.intent, _codes(t), t.sectors) for t in flat] == [
            (WebIntent.STOCK_ANALYSIS, ["600519", "HK09988"], []),
            (WebIntent.QUOTE_LOOKUP, ["300255"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["医药", "CPO"]),
            (WebIntent.STOCK_ANALYSIS, ["002050"], []),
        ]
        # ① 就地消歧：任務原樣保留——tokens / source_request 不缺失
        assert flat[0].tokens[:2] == ["分析", "一下"]
        assert flat[0].source_request == "分析一下茅台和阿里"
        assert flat[1].source_request == "然后看一下常山的价格"
        assert flat[3].source_request == "再分析下三花"

    def test_zero_interaction_returns_new_round(self):
        # 零交互（模糊回應"嗯嗯"）：本輪任務原樣返回（新話題），上輪
        # 確認任務不混入——resolve_first 即本輪閒聊
        self._register_changshan()
        r = _resolver()
        session: Dict[str, Any] = {}
        rs1 = r.resolve("分析一下茅台和阿里", session)
        apply_resolution_to_session(session, rs1)
        rs2 = r.resolve("嗯嗯", session)
        assert len(_flat(rs2)) == 1
        assert _flat(rs2)[0].intent == WebIntent.GENERAL_CHAT
        assert _flat(rs2)[0].source == "rule"

    def test_decline_cancels_whole_chain(self):
        # 拒絕詞：上輪整鏈作廢，返回閒聊單任務
        r = _resolver()
        session: Dict[str, Any] = {}
        rs1 = r.resolve("分析一下茅台和阿里", session)
        apply_resolution_to_session(session, rs1)
        rs2 = r.resolve("算了", session)
        flat = _flat(rs2)
        assert len(flat) == 1
        assert flat[0].intent == WebIntent.GENERAL_CHAT
        assert flat[0].source == "confirmation"
        assert not flat[0].needs_confirmation


# =========================================================================
# 評審迴歸用例 — 上下文純化 / LLM 合併閘門 / 切分契約 / 會話簿記。
# =========================================================================


class TestPRReviewProbes:
    """LLM 兜底的上下文契約：_session_context 純歸一化、上下文經
    _finalize_task/_classify_with_llm 顯式傳參。下列用例分別釘死
    request 上下文不覆蓋會話 / 無會話零殘留 / 併發不串會話與
    followup 繼承的正確性。"""

    def test_probe_request_context_clobbers_llm_prompt_context(self):
        # request_context 只貢獻 current_stock_code，不覆蓋會話上下文
        # ——LLM 兜底 prompt 的 recent_stocks / last_intent 保持會話側取值
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        session = {RECENT_STOCKS_KEY: ["600519"], LAST_INTENT_KEY: "stock_analysis"}
        _resolver(stub).resolve_first(
            "聊聊", session_context=session,
            request_context={"current_stock_code": "600519"},
        )
        assert len(stub.calls) == 1
        user_body = stub.calls[0]["messages"][1]["content"]
        assert "600519" in user_body, "recent_stocks 应进入 LLM prompt"
        assert "stock_analysis" in user_body, "last_intent 应进入 LLM prompt"

    def test_probe_request_context_breaks_followup_inheritance(self):
        # followup 偽標籤在 _merge_llm_result 讀顯式傳入的會話 context，
        # last_intent 正常繼承上輪執行類意圖
        stub = _StubLLMAdapter(content=_llm_json("followup", 0.9))
        session = {LAST_INTENT_KEY: "stock_analysis"}
        r = _resolver(stub).resolve_first(
            "再展开讲讲", session_context=session,
            request_context={"current_stock_code": "600519"},
        )
        assert r.intent == WebIntent.STOCK_ANALYSIS, "followup 应继承上轮执行类意图"

    def test_no_stale_context_across_resolves(self):
        # 無會話輪即空上下文，與上一輪無關——prompt 不殘留上一輪的
        # 會話鍵（跨會話/跨用戶零洩漏）
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        resolver = _resolver(stub)
        resolver.resolve_first("聊聊", session_context={
            RECENT_STOCKS_KEY: ["600519"], LAST_INTENT_KEY: "stock_analysis"})
        resolver.resolve_first("聊聊")  # 無會話輪：prompt 不得殘留上一輪
        body = json.loads(stub.calls[1]["messages"][1]["content"])
        assert body["recent_stocks"] == []
        assert body["last_intent"] == ""

    def test_concurrent_resolves_no_cross_session_pollution(self):
        # 零共享可變狀態：同一 resolver 併發複用（web 單例形態），
        # 兩把 stub 各自只收到本會話的鍵
        import threading

        results: Dict[str, List[str]] = {}

        def _run(tag: str, code: str) -> None:
            stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
            session = {RECENT_STOCKS_KEY: [code], LAST_INTENT_KEY: "stock_analysis"}
            resolver = WebIntentResolver(llm_adapter=stub)
            threads = [
                threading.Thread(target=resolver.resolve_first, args=("聊聊", session))
                for _ in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            results[tag] = [
                recent[0]
                for c in stub.calls
                if (recent := json.loads(c["messages"][1]["content"])["recent_stocks"])
            ]

        ta = threading.Thread(target=_run, args=("A", "600519"))
        tb = threading.Thread(target=_run, args=("B", "000858"))
        ta.start(); tb.start(); ta.join(); tb.join()
        assert set(results["A"]) == {"600519"}, "A 会话 prompt 不得混入他盘"
        assert set(results["B"]) == {"000858"}, "B 会话 prompt 不得混入他盘"

    def test_probe_llm_merge_drops_prehung_multi_groups(self):
        # _merge_llm_result 以 dataclasses.replace 攜帶規則結果基底：預掛
        # 的多組歧義結構（每組 name/candidates/source_request）在 LLM
        # 成功路徑不丟失，未指名字段自動隨行、逐組確認結構原樣
        stub = _StubLLMAdapter(content=_llm_json("quote_lookup", 0.9))
        rs = _resolver(stub).resolve("阿里巴巴多少钱，平安多少钱")
        confirmings = [t for t in _flat(rs) if t.needs_confirmation]
        assert len(confirmings) == 2, "两子消息歧义各自成确认任务"
        assert [[g["name"] for g in t.pending_action["groups"]]
                for t in confirmings] == [["阿里巴巴"], ["平安"]]
        assert all(len(g["candidates"]) == 2
                   for t in confirmings
                   for g in t.pending_action["groups"]), \
            "单组只含本组候选，不混入他组"

    def test_probe_llm_pick_drops_sibling_group(self):
        # LLM 在多組歧義中選定一組候選後，兄弟組保留待確認：阿里組由
        # stock_code 消解入 stocks，平安組保留（兩任務各自獨立）
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_code="HK09988"))
        rs = _resolver(stub).resolve("阿里巴巴多少钱，平安呢")
        flat = _flat(rs)
        assert any(
            t.needs_confirmation and any(
                g["name"] == "平安" for g in (t.pending_action or {}).get("groups", []))
            for t in flat
        ), "平安组应保留待确认"

    def test_probe_sector_sibling_never_carries_main_stocks(self):
        # 板塊兄弟任務不攜帶個股實體：stocks 按調用點顯式聲明，
        # primary_stock_code 不被鎖定到個股（#1619 股票範圍不注入
        # 錯誤標的）
        rs = _resolver().resolve("分析茅台和白酒板块")
        sector_task = _flat(rs)[1]
        assert sector_task.intent == WebIntent.SECTOR_ANALYSIS
        assert sector_task.sectors == ["白酒"]
        assert sector_task.stocks == [], "板块任务不应携带个股实体"
        assert sector_task.primary_stock_code == ""

    def test_probe_two_connective_cuts_in_one_unknown_token(self):
        # 契約（元素恆不變）：連接詞埋在 unknown_token 內部不切分——
        # 元素改寫違反不變量，同形態文本依賴標點邊界表達任務邊界
        from src.agent.web_intent_types import Token
        tokens = [
            Token("分析", "request"),
            Token("阿猫然后阿狗然后阿猪", ""),
        ]
        subs = _split_sub_messages(tokens, "分析阿猫然后阿狗然后阿猪")
        assert subs == [tokens], "unknown_token 不切分，元素原样归一组"
        assert ["".join(t.text for t in sub)
                for sub in _split_sub_messages("分析阿猫，然后阿狗，然后阿猪")] == [
            "分析阿猫", "然后阿狗", "然后阿猪",
        ], "标点形态（token 边界切口）正常三段"

    def test_probe_unknown_token_double_cut_keeps_middle_task(self):
        # 契約的 task 級形態：無標點時連接詞埋在 unknown_token 內無從
        # 下刀，整條消息單任務（低置信交 LLM 兜底）；同形態標點版
        # （token 邊界切口）三段、中段行情任務（"看下白酒板塊"）存活
        # ——多任務結構由標點邊界承載
        rs = _resolver().resolve("阿猫然后看下白酒板块然后聊聊")
        assert [(t.intent, t.sectors) for t in _flat(rs)] == [
            (WebIntent.GENERAL_CHAT, []),
        ]
        rs_ok = _resolver().resolve("阿猫，然后看下白酒板块，然后聊聊")
        assert [(t.intent, t.sectors) for t in _flat(rs_ok)] == [
            (WebIntent.GENERAL_CHAT, []),
            (WebIntent.QUOTE_LOOKUP, ["白酒"]),
            (WebIntent.GENERAL_CHAT, []),
        ]

    def test_probe_llm_bare_hk_code_identity(self):
        # LLM 按真實世界拼寫返回裸 5 位 "09988"：閘門前經
        # _canonical_digit_code 歸一到 HK+5 規範身份，直接命中組內候選、
        # 歧義收斂（與 tokenizer 規範身份同一拼寫）。觸發路徑：空 tag
        # 殘段 → 非全識別豁免
        stub = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_code="09988"))
        r = _resolver(stub).resolve_first("阿里巴巴哈哈哈")
        assert _codes(r) == ["HK09988"], "HK 代码应规范化为 HK+5 位拼写"
        assert r.candidates == [], "LLM 已选定候选，歧义应收敛"

    def test_history_recorded_at_session_level(self):
        # Resolution 不攜帶歷史標的字段：歷史標的的持久化通道是會話鍵
        # recent_stocks（apply 頭插去重，只記執行輪），任務僅攜帶標量
        # 視圖 inherited_stock_code；需要三元組時按 code 查庫派生
        # （持久化三元組會隨庫更新陳舊）
        session: Dict[str, Any] = {}
        rs = _resolver().resolve("茅台多少钱", session_context=session)
        r = _flat(rs)[0]
        assert not hasattr(r, "history_stocks"), "死字段应已删除"
        assert r.inherited_stock_code == ""  # 空會話：無繼承
        apply_resolution_to_session(session, rs)
        assert session[RECENT_STOCKS_KEY] == ["600519"]  # 會話級記錄即全部歷史


# =========================================================================
# 第五步消歧路徑專項 — 證據通道 / kinds 三分類 / 組結算三態（補覆蓋）
# =========================================================================


class TestStep5NarrowingEvidenceChannels:
    """第五步第二趟（組 × 預消歧子消息）的逐證據通道端到端：市場詞收窄
    到唯一 / 候選名全等 / 候選名唯一子串 / 確定實體命中候選 / 裸數字
    短碼（全等、裸數字、市場詞已有用例，此處補齊剩餘通道與邊界）。"""

    @staticmethod
    def _pending_pingan_session() -> Dict[str, Any]:
        # "平安"歧義：平安銀行 / 中國平安（同市場雙候選，全名可區分）
        return {PENDING_ACTIONS_KEY: [{
            "action": "confirm_stock", "intent": "stock_analysis", "name": "平安",
            "candidates": [
                {"code": "000001", "name": "平安银行", "market": "a"},
                {"code": "601318", "name": "中国平安", "market": "a"},
            ],
            "original_request": "分析平安",
        }]}

    @staticmethod
    def _pending_dual_cross_market() -> Dict[str, Any]:
        # 雙跨市場歧義組：阿里巴巴（hk/us）+ 中芯國際（a/hk）
        return {
            "action": "confirm_stock", "intent": "stock_analysis",
            "groups": [
                {"name": "阿里巴巴",
                 "candidates": [
                     {"code": "HK09988", "name": "阿里巴巴", "market": "hk"},
                     {"code": "BABA", "name": "阿里巴巴", "market": "us"},
                 ],
                 "source_request": "分析阿里巴巴"},
                {"name": "中芯国际",
                 "candidates": [
                     {"code": "688981", "name": "中芯国际", "market": "a"},
                     {"code": "HK00981", "name": "中芯国际", "market": "hk"},
                 ],
                 "source_request": "分析中芯国际"},
            ],
            "original_request": "分析阿里巴巴和中芯国际",
        }

    def test_unique_substring_channel(self):
        # 候選名唯一子串："看下平安銀行吧"（"看下"在 extend 池，無 clean
        # 意圖詞 → 純消歧）。全等通道不成立（子消息非候選全名），子串
        # 通道唯一命中平安銀行（中國平安不在文中）
        r = _resolver().resolve_first("看下平安银行吧", self._pending_pingan_session())
        assert r.source == "confirmation"
        assert _codes(r) == ["000001"]
        assert not r.needs_confirmation

    def test_market_word_zero_hit_is_not_evidence(self):
        # 市場詞與候選矛盾（"美股" × a/a 雙候選）：過濾後零隻 ≠ 證據 →
        # 零交互，整輪按新消息解析，pending 由 apply 收斂。市場詞是
        # 合法板塊主體（見 TestMarketWordAsSectorSubject），重開的
        # "美股"按新消息落為美股行情查詢——不變量是"零命中不消費確認
        # 任務"，而非重開消息的具體意圖
        r = _resolver().resolve_first("美股", self._pending_pingan_session())
        assert r.source == "rule"
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.sectors == ["美股"]
        assert not r.needs_confirmation

    def test_contradictory_reply_reopens_as_comparison(self):
        # 矛盾棄置→整輪判新話題（模塊 docstring 第五步契約）：同一條回
        # 復點名組內兩個候選（無意圖詞）＝比較/新請求——確認任務整組
        # 棄置剔除，貢獻子消息保留為雙標的比較任務（不空殼放行、不回
        # 退會話陳舊標的），pending 由 apply 清空
        session = self._pending_pingan_session()
        rs = _resolver().resolve("平安银行 中国平安", session)
        assert len(_flat(rs)) == 1
        r = _flat(rs)[0]
        assert r.source == "rule"
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert _codes(r) == ["000001", "601318"]
        assert not r.needs_confirmation
        assert r.pending_action is None
        apply_resolution_to_session(session, rs)
        assert session[PENDING_ACTIONS_KEY] == []

    def test_market_word_narrows_two_groups_at_once(self):
        # 市場詞可同時收窄多組："港股"對兩個跨市場組各過濾出唯一 hk
        # 候選 → 組間獨立結算、同 intent 聚合為單任務雙標的
        rs = _resolver().resolve(
            "港股", {PENDING_ACTIONS_KEY: [self._pending_dual_cross_market()]})
        assert len(_flat(rs)) == 1
        assert _codes(_flat(rs)[0]) == ["HK09988", "HK00981"]
        assert not _flat(rs)[0].needs_confirmation

    def test_entity_resolves_one_group_and_requeues_other(self):
        # 6 位裸碼提升為確定實體命中組內候選：中芯組消解、阿里組未解
        # → 重建 pending 繼續等待（confirmed 記累積、resolved_stocks 隨
        # 行實體），整鏈短路早退——第六步不跑，LLM 兜底零調用
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        rs = _resolver(stub).resolve(
            "688981", {PENDING_ACTIONS_KEY: [self._pending_dual_cross_market()]})
        assert stub.calls == []
        r = _flat(rs)[0]
        assert r.needs_confirmation
        assert _codes(r) == ["688981"]
        assert [g["name"] for g in r.pending_action["groups"]] == ["阿里巴巴"]
        assert [s["code"] for c in r.pending_action["confirmed"]
                for s in c["stocks"]] == ["688981"]
        assert [s["code"] for s in r.pending_action["resolved_stocks"]] == ["688981"]


class TestStep5ReplyKinds:
    """第五步第一趟 kinds 三分類（fresh / keep / narrow）的裁決與後果：
    fresh 不參與收窄（整輪判新話題）；keep 參與收窄且保留為新任務；
    narrow 參與收窄後被 ② 丟棄（不是任務）。"""

    def test_fresh_reply_reopens_topic(self):
        # fresh：子消息混入候選外新實體（600519）→ 整條子消息不參與收
        # 窄，零交互按新話題重析——重析自身又產生新的歧義確認
        r = _resolver().resolve_first("分析600519和阿里巴巴", _ali_session())
        assert r.source == "rule"
        assert _codes(r) == ["600519"]
        assert r.needs_confirmation
        assert r.reason == "ambiguous_stock_name"
        assert set(_candidate_codes(r)) == {"HK09988", "BABA"}

    def test_fresh_and_narrow_sub_messages_combined(self):
        # fresh + narrow 並存："分析600519，港股"——確認任務由"港股"消
        # 解，新任務（600519）保留；不折疊，兩標的各自獨立執行
        # （確認消解項在前、新任務在後）
        rs = _resolver().resolve("分析600519，港股", _ali_session())
        tasks = _flat(rs)
        assert len(tasks) == 2
        assert tasks[0].source == "confirmation" and _codes(tasks[0]) == ["HK09988"]
        assert tasks[1].source == "rule" and _codes(tasks[1]) == ["600519"]
        assert not any(t.needs_confirmation for t in tasks)

    def test_keep_sub_message_survives_as_task(self):
        # keep（模塊 docstring 示例）："港股"（narrow，被 ② 丟棄）消解上
        # 輪確認任務，"分析醫藥板塊"（keep，帶意圖詞）保留為新任務，
        # ③ 拼接後上輪組序在前、本輪在後
        rs = _resolver().resolve("港股，分析医药板块", _ali_session())
        assert [(t.intent, _codes(t), t.sectors) for t in _flat(rs)] == [
            (WebIntent.STOCK_ANALYSIS, ["HK09988"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["医药"]),
        ]
        assert _flat(rs)[0].source == "confirmation"
        assert _flat(rs)[1].source == "rule"

    def test_keep_task_coexists_with_consumed_task(self):
        # keep 與消費發生在同一子消息："阿里巴巴港股怎麼樣"（市場詞 +
        # clean 意圖詞"怎麼樣"）——確認任務消解、重析任務獨立保留
        # （不折疊：同標的兩任務並存，消費方可按需去重）
        rs = _resolver().resolve("阿里巴巴港股怎么样", _ali_session())
        tasks = _flat(rs)
        assert len(tasks) == 2
        assert all(_codes(t) == ["HK09988"] for t in tasks)
        assert tasks[0].source == "confirmation"
        assert tasks[1].source == "rule" and tasks[1].confidence == 0.85
        assert not any(t.needs_confirmation for t in tasks)

    def test_decline_word_with_content_is_not_decline(self):
        # 拒絕詞判定是整條消息拼接的全文匹配（^...$）："算了，再看看茅
        # 臺"不是拒絕——按新話題解析為 [閒聊, 個股分析]，無 confirmation
        # 產物混入
        rs = _resolver().resolve("算了，再看看茅台", _ali_session())
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.GENERAL_CHAT, WebIntent.STOCK_ANALYSIS]
        assert all(t.source == "rule" for t in _flat(rs))
        assert _codes(_flat(rs)[1]) == ["600519"]
        assert not any(t.needs_confirmation for t in _flat(rs))

    def test_stale_pending_ignored_when_last_resolutions_present(self):
        # 數據源優先級：last_resolutions 在場（且無確認任務）時不讀
        # pending_actions——兩鍵失配（外部寫髒）不誤觸發確認消費
        plain = WebIntentResolution(WebIntent.STOCK_ANALYSIS, 0.9,
                                    stocks=[Stock("600519", "贵州茅台", "a")])
        session = {LAST_RESOLUTIONS_KEY: [[asdict(plain)]],
                   PENDING_ACTIONS_KEY: [_pending_ali()]}
        r = _resolver().resolve_first("分析600519", session)
        assert r.source == "rule"
        assert _codes(r) == ["600519"]
        assert not r.needs_confirmation


class TestStep5Units:
    """第五步內部函數白盒：pending 形狀歸一（Stock 對象/壞條目/平鋪
    兜底）與無確認任務的直通契約。"""

    def test_normalize_pending_groups_filters_malformed(self):
        # groups[].candidates 為 Stock 對象與壞條目（非 dict 組 / 無
        # code 候選 / 空候選組）混排：逐條過濾只留有效組，組內候選
        # 統一為 Stock
        groups, all_stocks = _normalize_pending_groups({
            "groups": [
                "not-a-dict",
                {"name": "阿里巴巴", "candidates": [
                    Stock("HK09988", "阿里巴巴", "hk"), {"name": "无code"}]},
                {"name": "空组", "candidates": []},
            ],
        })
        assert [g["name"] for g in groups] == ["阿里巴巴"]
        assert [s.code for s in all_stocks] == ["HK09988"]

    def test_normalize_pending_groups_non_dict_pending(self):
        # pending 自身非 dict（外部會話毒化，如字符串 pending_action）：
        # 解析器入口類型守衛 → 空列表，不擊穿消費鏈
        groups, all_stocks = _normalize_pending_groups("confirm_stock")
        assert groups == [] and all_stocks == []

    def test_normalize_pending_groups_flat_fallback(self):
        # groups 全壞 → 頂層平鋪（name/candidates）視為單組，
        # source_request 取 original_request
        groups, all_stocks = _normalize_pending_groups({
            "groups": ["bad", {"candidates": []}],
            "name": "阿里巴巴",
            "candidates": [{"code": "BABA", "name": "阿里巴巴", "market": "us"}],
            "original_request": "分析阿里巴巴",
        })
        assert [g["name"] for g in groups] == ["阿里巴巴"]
        assert groups[0]["source_request"] == "分析阿里巴巴"
        assert [s.code for s in all_stocks] == ["BABA"]

    def test_consume_no_confirmings_returns_recovered(self):
        # last_resolution 無確認任務：① 不消費，原樣返回恢復後的二維結
        # 構（任務對象身份不變）
        plain = WebIntentResolution(WebIntent.STOCK_ANALYSIS, 0.9,
                                    stocks=[Stock("600519", "贵州茅台", "a")])
        new = WebIntentResolution(WebIntent.QUOTE_LOOKUP, 0.85)
        out = _consume_confirmations([[plain]], [new])
        assert out == [[plain]]
        assert out[0][0] is plain


class TestResolveOutputContract:
    """resolve 出口契約：一律二維（外層=子消息任務組），空輸入同樣。"""

    def test_empty_message_two_dim_shape(self):
        rs = _resolver().resolve("")
        assert isinstance(rs, list) and len(rs) == 1
        assert isinstance(rs[0], list)
        assert rs[0][0].intent == WebIntent.GENERAL_CHAT
        assert rs[0][0].source == "rule"

    def test_single_intent_message_two_dim_shape(self):
        rs = _resolver().resolve("分析600519")
        assert len(rs) == 1 and len(rs[0]) == 1
        assert _codes(rs[0][0]) == ["600519"]


# =========================================================================
# 第六步收尾專項 — LLM 兜底觸發面與代碼閘門 / 確認判定補齊
# =========================================================================


class TestStep6LlmFallbackChannels:
    """第六步① LLM 兜底：stock_code 三道閘門（候選命中 → 查庫 → 未命中
    按形態分流）與 confirmation 產物的豁免面。"""

    def test_llm_alpha_code_not_in_db_unverified(self):
        # 查庫未命中 + 純字母形態：透傳執行端實查（unverified），不做
        # 確認——LLM 代碼通道無原文閘門（與 sectors/unresolved 不同）
        stub = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_code="ZZZZ"))
        r = _resolver(stub).resolve_first("聊聊")
        assert r.source == "llm"
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.stocks == []
        assert r.unverified_codes == ["ZZZZ"]
        assert not r.needs_confirmation

    def test_llm_hk_code_not_in_db_unverified(self):
        # HK 前綴形態未命中：同樣透傳實查（hk 非全量庫無判定把握）
        stub = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_code="HK66373"))
        r = _resolver(stub).resolve_first("聊聊")
        assert r.source == "llm"
        assert r.unverified_codes == ["HK66373"]
        assert not r.needs_confirmation

    def test_llm_chat_with_bad_code_drops_code(self):
        # LLM 判閒聊但夾帶庫外代碼：閒聊無執行面，壞代碼不可信——
        # unresolved/unverified 清空，不轉確認
        stub = _StubLLMAdapter(content=_llm_json(
            "general_chat", 0.9, stock_code="888888"))
        r = _resolver(stub).resolve_first("聊聊电影")
        assert r.source == "llm"
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.confidence == LLM_CONFIDENCE_CAP
        assert r.unresolved_names == [] and r.unverified_codes == []
        assert not r.needs_confirmation

    def test_llm_resolution_withdraws_prehung_pending(self):
        # 確認判定補齊的收尾分支：LLM 消歧清空候選後，第四步預掛的
        # pending_action 載體撤下（不攜帶已消解的歧義組隨行）。
        # 觸發路徑：空 tag 殘段 → 非全識別豁免 → 兜底
        stub = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_code="HK09988"))
        r = _resolver(stub).resolve_first("阿里巴巴哈哈哈")
        assert _codes(r) == ["HK09988"]
        assert r.candidates == []
        assert r.pending_action is None
        assert not r.needs_confirmation

    def test_confirmation_source_exempt_from_llm(self):
        # 純確認碎片（source=confirmation）永不觸發大模型——即便攜帶
        # 未消解候選
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        resolver = WebIntentResolver(llm_adapter=stub)
        confirming = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.5, source="confirmation",
            candidates=[Stock("HK09988", "阿里巴巴", "hk"),
                        Stock("BABA", "阿里巴巴", "us")])
        assert resolver._should_use_llm(confirming) is False
        same_but_rule = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.5, source="rule",
            candidates=[Stock("HK09988", "阿里巴巴", "hk")])
        assert resolver._should_use_llm(same_but_rule) is True

    def test_fully_recognized_high_confidence_exempt(self):
        # tag 全識別 + ≥0.8：視野與判定雙完備，即便攜帶歧義候選也不
        # 複核（candidates 不參與觸發判據）；置信不足或空 tag 殘段
        # 則照常觸發兜底
        resolver = WebIntentResolver(llm_adapter=_StubLLMAdapter())
        base = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.85, source="rule",
            candidates=[Stock("HK09988", "阿里巴巴", "hk")],
            all_tags_recognized=True)
        assert resolver._should_use_llm(base) is False
        assert resolver._should_use_llm(replace(base, confidence=0.75)) is True
        assert resolver._should_use_llm(
            replace(base, all_tags_recognized=False)) is True


class TestStep6Finalization:
    """收尾（LLM 改寫意圖 / 任務不折疊各自獨立）與確認判定補齊
    （無預掛組的兜底建組 / 置信度鉗制）。"""

    def test_llm_rewrite_tasks_stay_separate(self):
        # LLM 兜底改寫意圖（裸板塊"半導體怎麼樣"被改判 quote）後不做
        # 同意圖合併——改寫產物獨立成任務；主任務高置信豁免不進 LLM
        stub = _StubLLMAdapter(content=_llm_json("quote_lookup", 0.9))
        rs = _resolver(stub).resolve("查一下茅台股价，然后机器人怎么样")
        assert len(stub.calls) == 1  # 主任務高置信豁免，僅雙解板塊任務進 LLM
        tasks = _flat(rs)
        assert len(tasks) == 2
        assert tasks[0].source == "rule" and tasks[0].confidence == 0.85
        assert tasks[0].intent == WebIntent.QUOTE_LOOKUP
        assert _codes(tasks[0]) == ["600519"]
        assert tasks[1].source == "llm" and tasks[1].confidence == 0.75
        assert tasks[1].sectors == ["机器人"]
        assert not any(t.needs_confirmation for t in tasks)

    def test_sequential_tasks_stay_independent(self):
        # 任務不折疊、各自獨立：首尾同為 stock_analysis 但中間隔著
        # quote 任務——保序返回不打亂用戶的表達順序；首任務的歧義
        # 確認使整鏈短路，兄弟任務隨組結構返回
        rs = _resolver().resolve("分析阿里巴巴，查一下茅台股价，再看看五粮液")
        assert [t.intent for t in _flat(rs)] == [
            WebIntent.STOCK_ANALYSIS,
            WebIntent.QUOTE_LOOKUP,
            WebIntent.STOCK_ANALYSIS,
        ]
        assert _flat(rs)[0].needs_confirmation
        assert _flat(rs)[0].reason == "ambiguous_stock_name"
        assert _codes(_flat(rs)[1]) == ["600519"]
        assert _codes(_flat(rs)[2]) == ["000858"]

    def test_finalize_confirmation_builds_fallback_group(self):
        # 無預掛組時的兜底建組：候選全量進單組、組名取首候選名/代碼、
        # original_request 記子消息文本（第四步規則路徑恆預掛，本分支
        # 防禦 resolve 之外構造 resolution 的調用方）
        res = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.85,
            candidates=[Stock("HK09988", "阿里巴巴", "hk"),
                        Stock("BABA", "阿里巴巴", "us")],
            source_request="分析阿里巴巴", tokens=["分析", "阿里巴巴"])
        out = _finalize_confirmation(res)
        assert out.needs_confirmation
        assert out.reason == "ambiguous_stock_name"
        groups = out.pending_action["groups"]
        assert len(groups) == 1
        assert groups[0]["name"] == "阿里巴巴"
        assert {c["code"] for c in groups[0]["candidates"]} == {"HK09988", "BABA"}
        assert out.pending_action["original_request"] == "分析阿里巴巴"

    def test_finalize_confirmation_clamps_confidence(self):
        # 置信度出界鉗制到 [0,1]：1.5 → 1.0（高於閾值不確認）
        res = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 1.5,
            stocks=[Stock("600519", "贵州茅台", "a")])
        out = _finalize_confirmation(res)
        assert out.confidence == 1.0
        assert not out.needs_confirmation


# =========================================================================
# 消歧收窄與 LLM 閘門迴歸
# =========================================================================


class TestDeepScanProbes:
    """消歧收窄與 LLM 代碼閘門的迴歸用例（均斷言期望行為）。"""

    @staticmethod
    def _register_zhongxin_dual() -> None:
        # 中芯國際 a/hk 雙上市（與 pending 組候選一致）
        from src.services import name_to_code_resolver as resolver_mod

        resolver_mod.stockDB["688981"] = "中芯国际"
        resolver_mod.stockDB["HK00981"] = "中芯国际"
        resolver_mod._names_cache[:] = [None, None, None]

    @staticmethod
    def _dual_group_pending() -> Dict[str, Any]:
        # 雙歧義組 pending：阿里巴巴（hk/us）+ 中芯國際（a/hk）
        return {
            "action": "confirm_stock", "intent": "stock_analysis",
            "groups": [
                {"name": "阿里巴巴",
                 "candidates": [
                     {"code": "HK09988", "name": "阿里巴巴", "market": "hk"},
                     {"code": "BABA", "name": "阿里巴巴", "market": "us"}],
                 "source_request": "分析阿里巴巴"},
                {"name": "中芯国际",
                 "candidates": [
                     {"code": "688981", "name": "中芯国际", "market": "a"},
                     {"code": "HK00981", "name": "中芯国际", "market": "hk"}],
                 "source_request": "分析中芯国际"},
            ],
            "original_request": "分析阿里巴巴和中芯国际",
        }

    def test_probe_low_confidence_withdraws_prehung_groups(self):
        # LLM 低置信（0.5）但在候選中選了碼：candidates 清空、conf <0.6
        # → low_confidence 確認。歧義已消解（stocks=[HK09988]）時預掛組
        # 撤下，確認意圖只針對"意圖待澄清"——殘留組會被 apply_pending
        # 寫回 pending_actions，彈出誤導性選股確認。
        # 觸發路徑：空 tag 殘段 → 非全識別豁免 → 兜底
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.5, stock_code="HK09988"))
        rs = _resolver(stub).resolve("阿里巴巴哈哈哈", {})
        t = _flat(rs)[0]
        assert t.needs_confirmation and t.reason == "low_confidence"
        assert _codes(t) == ["HK09988"]
        assert t.pending_action is None, \
            "low_confidence 不应携带 confirm_stock 载体（歧义已消解）"

    def test_probe_llm_single_code_keeps_sibling_group(self):
        # 單子消息雙歧義（阿里巴巴+中芯國際）時 LLM 只回
        # stock_code=HK09988：只消解阿里組，中芯組的候選與預掛組保留
        # 轉確認（candidates 整清會讓兄弟組靜默丟失）。
        # 觸發路徑：詞池外語氣詞留下空 tag 殘段 → 非全識別豁免 → 兜底
        # （兩名均全名，Step 1 先行消費，不被 unknown_token 陪葬）
        self._register_zhongxin_dual()
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_code="HK09988"))
        rs = _resolver(stub).resolve("阿里巴巴和中芯国际哈哈哈", {})
        t = _flat(rs)[0]
        assert _codes(t) == ["HK09988"], "阿里组由 LLM 代码消解"
        assert t.needs_confirmation, "中芯组未解，任务应转确认"
        assert [g["name"] for g in (t.pending_action or {}).get("groups", [])] \
            == ["中芯国际"], "兄弟组不得静默丢失"

    def test_probe_per_group_market_reply_scoped(self):
        # 兩組各點名市場（阿里→港股、中芯→A股）。
        # 按名指向的市場詞只作用於被點名組：不串擾他組（錯誤消解或矛盾
        # 棄置）；點名組不覆蓋的市場詞保留全局（"港股和常山藥業"行為
        # 見 test_user_example_full_chain）
        self._register_zhongxin_dual()
        rs = _resolver().resolve(
            "阿里巴巴要港股的，中芯国际要A股的",
            {PENDING_ACTIONS_KEY: [self._dual_group_pending()]})
        t = _flat(rs)[0]
        assert not t.needs_confirmation
        assert _codes(t) == ["HK09988", "688981"], \
            "两组应各按用户所指市场消解"

    def test_probe_named_market_word_does_not_leak_to_other_group(self):
        # 回覆只點名一組（"阿里巴巴要港股"）時，市場詞不得把他組頂到
        # 錯誤市場——中芯組應保持未解重建 pending 繼續等待，而非帶著
        # 用戶未選擇的 HK00981 提前放行
        self._register_zhongxin_dual()
        session: Dict[str, Any] = {}
        r = WebIntentResolver()
        rs1 = r.resolve("分析阿里巴巴和中芯国际", session)
        apply_resolution_to_session(session, rs1)
        rs2 = r.resolve("阿里巴巴要港股", session)
        t = _flat(rs2)[0]
        assert t.needs_confirmation, "中芯组未解，确认应继续等待"
        assert [g["name"] for g in t.pending_action["groups"]] == ["中芯国际"]
        assert [s["code"] for c in t.pending_action.get("confirmed", [])
                for s in c["stocks"]] == ["HK09988"], \
            "阿里组的消解结果记入 confirmed 累积"
        assert _codes(t) == ["HK09988"], "仅阿里组按港股消解"

    def test_probe_decline_across_sub_messages(self):
        # 拒絕詞逐子消息錨定匹配：全部片段為完整拒絕形才取消——整串
        # 拼接丟分隔符會把"算了，不分析了"拼成用戶從未說過的"算了不
        # 分析了"。"拒絕詞＋內容"非取消契約由
        # test_decline_word_with_content_is_not_decline 鎖定
        session = _ali_session()
        rs = _resolver().resolve("算了，不分析了", session)
        flat_ = _flat(rs)
        assert len(flat_) == 1
        assert flat_[0].source == "confirmation", "应识别为确认链取消"
        assert flat_[0].intent == WebIntent.GENERAL_CHAT

    def test_probe_llm_code_outside_groups_rejected(self):
        # 規則側已有歧義候選時，LLM 返回庫內命中但不在任何候選組的代碼
        # 是越權換標的，必須拒收——否則 fabricated 標的隨 resolved_
        # stocks 騎行進任務，消歧確認後與用戶所選並列執行
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_code="600519"))
        rs = _resolver(stub).resolve("阿里巴巴多少钱", {})
        t = _flat(rs)[0]
        assert _codes(t) == [], "候选组外的库内代码不得注入 stocks"
        assert t.needs_confirmation, "阿里组歧义仍待确认"
        assert [g["name"] for g in t.pending_action["groups"]] == ["阿里巴巴"]
        # 對照：無候選場景（描述性指稱/指代解析）注入不受影響——
        # 見 test_valid_stock_code_injected / test_multi_mentions_via_
        # stock_codes（"那隻白酒股"/"這兩隻"→ 代碼注入是設計特性）


# =========================================================================
# LLM 多意圖協議與複核觸發面
# =========================================================================


class TestLlmMultiIntent:
    """LLM 多意圖協議：觸發判據（multi_intent_hint）、載荷解析（intents
    數組優先/單對象兼容）、逐項合併護欄與保序任務列表產出。"""

    def test_multi_intent_hint_stamped_on_unexpressible_signals(self):
        # 規則自知單任務表達不完：數據對象級 quote 詞與強分析詞同場
        # （"股價+基本面"深度被裁決序吸收）→ hint 置位；純取數動詞
        # （看下…走勢）與單意圖消息不置位
        r = _resolver().resolve_first("看一下茅台股价和基本面再分析比亚迪")
        assert r.multi_intent_hint
        assert r.confidence == 0.85 and r.source == "rule", "无 LLM 时规则直达"
        assert not _resolver().resolve_first(
            "看下现在人工智能赛道和AI板块的走势").multi_intent_hint
        assert not _resolver().resolve_first("分析五粮液").multi_intent_hint

    def test_intents_array_parsed_and_invalid_items_dropped(self):
        payload = _parse_llm_payload(json.dumps({
            "intents": [
                {"intent": "quote_lookup", "confidence": 0.9, "stock_code": "600519"},
                {"intent": "bogus_intent", "confidence": 0.9},
                "not-a-dict",
                {"intent": "STOCK-Analysis。", "confidence": 0.85,
                 "stock_code": "002594"},
            ],
        }, ensure_ascii=False))
        assert [i["intent"] for i in payload["intents"]] == [
            "quote_lookup", "stock_analysis"], "非法项丢弃、标签规范化"

    def test_intents_array_all_invalid_falls_back_to_single(self):
        # 數組全非法 → 回退單對象形態判定
        payload = _parse_llm_payload(json.dumps({
            "intents": [{"intent": "bogus"}, 5],
            "intent": "general_chat", "confidence": 0.5,
        }))
        assert payload is not None and "intents" not in payload
        assert payload["intent"] == "general_chat"

    def test_multi_intent_end_to_end_ordered_task_list(self):
        # 端到端：hint 取消高置信豁免（0.85 全識別仍觸發兜底），intents
        # 數組逐項過閘（實體重置基底，規則壓縮的雙標的不汙染每張任務單），
        # 保序產出三張任務：報價茅臺 / 分析茅臺 / 分析比亞迪——同標的雙
        # 深度與順序動作均獨立成單
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9, "stock_code": "600519"},
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_codes": ["600519"]},
            {"intent": "stock_analysis", "confidence": 0.9, "stock_code": "002594"},
        ]}, ensure_ascii=False))
        rs = _resolver(stub).resolve("看一下茅台股价和基本面再分析比亚迪")
        flat_ = _flat(rs)
        assert len(stub.calls) == 1, "hint 破除高置信豁免，兜底被触发"
        assert [(t.intent, _codes(t)) for t in flat_] == [
            (WebIntent.QUOTE_LOOKUP, ["600519"]),
            (WebIntent.STOCK_ANALYSIS, ["600519"]),
            (WebIntent.STOCK_ANALYSIS, ["002594"]),
        ]
        assert all(t.source == "llm" for t in flat_)
        assert all(t.source_request == "看一下茅台股价和基本面再分析比亚迪"
                   for t in flat_), "兄弟任务继承来源子消息"

    def test_multi_intent_hallucinated_item_code_gated(self):
        # 逐項閘門：某項返回庫內命中但消息未提及的代碼（幻覺）→ 拒收，
        # 該項以空標的低置信轉確認（寧缺毋濫按項生效）
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9, "stock_code": "600519"},
            {"intent": "stock_analysis", "confidence": 0.9, "stock_code": "888888"},
        ]}, ensure_ascii=False))
        rs = _resolver(stub).resolve("看一下茅台股价和基本面")
        flat_ = _flat(rs)
        assert _codes(flat_[0]) == ["600519"]
        assert _codes(flat_[1]) == [] or flat_[1].needs_confirmation

    def test_multi_intent_followup_item_chains_previous(self):
        # 數組內 followup＝延續前一項意圖（與規則分支6鏈式繼承同構），
        # 不是會話級 last_intent——會話置 sector_analysis 作對照，第二
        # 項仍應繼承數組首項的 quote_lookup；單元素數組的會話級繼承由
        # 既有 test_followup_with_context_inherits_intent 覆蓋
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9, "stock_code": "600519"},
            {"intent": "followup", "confidence": 0.9},
        ]}, ensure_ascii=False))
        rs = _resolver(stub).resolve(
            "看一下茅台股价和基本面",
            {LAST_INTENT_KEY: "sector_analysis"})
        flat_ = _flat(rs)
        assert flat_[0].intent == WebIntent.QUOTE_LOOKUP
        assert flat_[1].intent == WebIntent.QUOTE_LOOKUP, \
            "数组内 followup 延续前一项，而非会话级 last_intent"

    def test_unread_unknown_token_without_subject_triggers_llm(self):
        # 視野殘缺×無主體：unknown_token 裡可能正是未讀出的主體或附加訴求——
        # 高置信裁決只對已讀部分可靠，未讀內容不得靜默丟棄（"查下我持
        # 倉的股票股價"：unknown_token"的股票股價"埋著數據對象詞，stocks/sectors
        # 全空無交叉驗證）。conf 保持路徑語義不回寫，觸發器消費視野軸。
        # 有主體的附帶 unknown_token 維持既有豁免（"茅臺多少錢順便看下SOFI"由
        # test_high_confidence_exempt_from_side_triggers 釘住）
        stub = _StubLLMAdapter(content=_llm_json("portfolio_analysis", 0.9))
        r = _resolver(stub).resolve_first("查下我持仓的股票股价")
        assert len(stub.calls) == 1, "视野残缺×无主体破除高置信放行"
        assert r.source == "llm"
        assert r.intent == WebIntent.PORTFOLIO_ANALYSIS

    def test_group_level_review_no_duplication(self):
        # 組級收尾（sub_message 最小單位）：出口分解的兄弟任務不各自
        # 觸發複核——同一條子消息至多一次多意圖枚舉，產出整組替換。
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "portfolio_analysis", "confidence": 0.9},
            {"intent": "quote_lookup", "confidence": 0.9},
        ]}, ensure_ascii=False))
        rs = _resolver(stub).resolve("看下我持仓的医药ETF")
        assert len(stub.calls) == 1, "一条子消息至多一次多意图枚举"
        flat_ = _flat(rs)
        assert [t.intent for t in flat_] == [
            WebIntent.PORTFOLIO_ANALYSIS, WebIntent.QUOTE_LOOKUP],             "枚举产出整组替换，不与规则兄弟拼接"

    def test_pipeline_split_on_generic_collection_subject(self):
        # 管道拆分原理（一般化契約）：顯式動作詞作用於賬戶泛指集合
        # （無顯式主體）→ 交大模型拆〔持倉分析（取集合）＋作用於集合的
        # 普遍化任務〕——全識別高置信 0.85 也破除豁免（否則完全分詞的
        # 管道形態會規則直達丟拆分）；主體顯式（持倉的茅臺股價）與
        # 中性問句（我的持倉怎麼樣）不觸發
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "portfolio_analysis", "confidence": 0.9},
            {"intent": "stock_analysis", "confidence": 0.9},
        ]}, ensure_ascii=False))
        rs = _resolver(stub).resolve("分析我的持仓")
        assert len(stub.calls) == 1, "泛指集合×动作词破除豁免"
        flat_ = _flat(rs)
        assert [t.intent for t in flat_] == [
            WebIntent.PORTFOLIO_ANALYSIS, WebIntent.STOCK_ANALYSIS]
        assert all(t.source == "llm" for t in flat_)
        stub2 = _StubLLMAdapter(content=_llm_json("portfolio_analysis", 0.9))
        _resolver(stub2).resolve_first("我的茅台还该拿着吗")
        assert stub2.calls == [], "主体显式不触发（不需账户数据的单任务形态）"
        _resolver(stub2).resolve_first("我的持仓今天怎么样")
        assert stub2.calls == [], "中性问句不触发（终态单一持仓分析）"

    def test_subjectless_action_defaults_to_it(self):
        # 主題缺失的動作問句默認主體為"它"（＝"它現在能買嗎"）走繼承
        # ——上輪執行類 + 會話主體在場 → 免複核直達執行；
        # 純疑問碎片（question 單獨在場）不繼承
        session = {LAST_INTENT_KEY: "quote_lookup",
                   RECENT_STOCKS_KEY: ["600519"]}
        r = _resolver().resolve_first("现在能买吗", session)
        assert r.source == "context"
        assert r.primary_stock_code == "600519"
        assert not r.needs_confirmation

    def test_sector_tag_with_code_entity_conflicts_to_llm(self):
        # 板塊泛稱 tag × 股票代碼實體＝對象無法判定 → hint 置位
        # 強制複核，不按存疑代碼分支 0.8 直達
        stub = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_code="HK09988"))
        r = _resolver(stub).resolve_first("板块HK09988")
        assert len(stub.calls) == 1
        assert r.source == "llm"
        assert _codes(r) == ["HK09988"]

    def test_portfolio_quote_class_conflict_triggers_llm(self):
        # 裁決類衝突（契約：衝突意圖詞交大模型判定拆分還是單一）：
        # "持倉＋股價"＝報數×賬戶聚合——即使全識別 0.85 也破除豁免。
        # 判據純語義（tag 級）：詞打成 tag 即被看見（"股價"extend 詞
        # 同樣如此）；詞埋進 unknown_token 則視野證兜住。單類共現與
        # 中性疑問不觸發
        stub = _StubLLMAdapter(content=_llm_json(
            "portfolio_analysis", 0.9))
        rs = _resolver(stub).resolve("查下我持仓的股价")
        assert len(stub.calls) == 1, "tag 级：extend 报数词×组合类冲突"
        assert _flat(rs)[0].source == "llm"
        assert _flat(rs)[0].intent == WebIntent.PORTFOLIO_ANALYSIS
        stub2 = _StubLLMAdapter(content=_llm_json(
            "portfolio_analysis", 0.9))
        rs2 = _resolver(stub2).resolve("我持仓的市值")
        assert len(stub2.calls) == 1, "报数词×组合类冲突（tag 级）"
        assert _flat(rs2)[0].intent == WebIntent.PORTFOLIO_ANALYSIS
        stub3 = _StubLLMAdapter(content=_llm_json(
            "portfolio_analysis", 0.9))
        _resolver(stub3).resolve_first("我的持仓今天怎么样")
        assert stub3.calls == [], "中性疑问不参与，单类不触发"

    def test_strict_review_subject_unknown_token_and_inherit(self):
        # 寧可不做不可做錯（默認複核）：豁免需三證齊全（視野完備＋置信
        # ≥0.8＋無多意圖信號），缺一即調 LLM。①主體在場但 unknown_token
        # 陪葬——附帶內容同樣是未讀內容；②上下文繼承產物 0.75——LLM
        # 說 followup 則經會話 last_intent 鏈式轉繼承，結果同構
        stub = _StubLLMAdapter(content=_llm_json("quote_lookup", 0.9))
        rs = _resolver(stub).resolve("茅台多少钱哈哈哈")
        assert len(stub.calls) == 1, "主体在场但视野残缺，必须复核"
        t = _flat(rs)[0]
        assert t.source == "llm" and _codes(t) == ["600519"],             "复核不丢规则主体（硬信号在基底随行）"

        stub2 = _StubLLMAdapter(content=_llm_json("followup", 0.9))
        r2 = _resolver(stub2).resolve_first(
            "该股现在怎么样",
            {LAST_INTENT_KEY: "stock_analysis", RECENT_STOCKS_KEY: []})
        assert len(stub2.calls) == 1, "继承产物 0.75<0.8，同样复核"
        assert r2.source == "llm" and r2.intent == WebIntent.STOCK_ANALYSIS

    def test_verdict_class_conflict_triggers_llm_review(self):
        # 裁決類競爭觸發：報數類數據對象詞與強分析類詞同場（"多少錢＋
        # 基本面"＝一句兩個深度），即使全識別高置信也破除豁免交 LLM 多
        # 意圖複核（hint 的 tag 級與文本級判據取或）。共現≠衝突：動賓
        # 搭配（分析＋走勢）、同類共現（多少錢＋市盈率，同為報數）、中
        # 性疑問（怎麼樣）都不觸發，規則直達零調用
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_code="600519"))
        rs = _resolver(stub).resolve("茅台多少钱和基本面")
        assert len(stub.calls) == 1, "裁决类竞争破除高置信豁免"
        assert _flat(rs)[0].source == "llm"
        stub2 = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        _resolver(stub2).resolve_first("分析五粮液的走势")
        assert stub2.calls == [], "动宾搭配（分析＋走势）不冲突，不触发"
        _resolver(stub2).resolve_first("茅台多少钱和市盈率")
        assert stub2.calls == [], "同类共现（报数×报数）不冲突，不触发"
        _resolver(stub2).resolve_first("分析下五粮液怎么样")
        assert stub2.calls == [], "中性疑问不参与竞争，不触发"


class TestDeepScanBlockingDefects:
    """切分對齊 / 鏈式主體 / 矛盾結算 / LLM 閘門 / 平權構造的阻斷級
    迴歸用例。"""

    def test_probe_lowercase_hk_prefix_keeps_tasks_separate(self):
        # 切分對齊：_identify_stock_codes 把小寫交易所前綴/後綴形態
        # （hk00700 / 00700.HK）canonical 改寫為 HK00700，切分定位按
        # token 文本大小寫摺疊 + canonical 改寫代碼的數字核回退，
        # 邊界兩側各歸各組——代碼 token 不跨標點邊界錯歸前一子消息、
        # 兩個獨立查詢不併成一條雙標的任務
        rs = _resolver().resolve("查下五粮液，hk00700也看下", {})
        flat_ = _flat(rs)
        assert len(flat_) == 2
        assert [_codes(t) for t in flat_] == [["000858"], ["HK00700"]], \
            "小写 hk 前缀代码不得跨边界并入前一任务"
        rs_suffix = _resolver().resolve("查下五粮液，00700.hk也看下", {})
        assert [_codes(t) for t in _flat(rs_suffix)] == [["000858"], ["HK00700"]], \
            "后缀重排形态（00700.HK→HK00700）经数字核回退同样不并组"

    def test_probe_trailing_followup_fragment_carries_chain_subject(self):
        # 鏈式主體線程：切分在"然後"token 前下刀，尾隨追問片段走分支6
        # 繼承前序子消息意圖——前序子消息恰收斂一隻標的時，追問片段經
        # inherited_stock_code 繼承該標的（不折疊架構下片段仍獨立成條）
        session: Dict[str, Any] = {RECENT_STOCKS_KEY: ["600519"]}
        rs = _resolver().resolve("分析五粮液，然后呢", session)
        followup = _flat(rs)[-1]
        assert followup.source == "context"
        assert followup.inherited_stock_code == "000858"
        assert followup.primary_stock_code == "000858", \
            "追问片段继承前序子消息标的，不得回退会话陈旧标的（600519）"

    def test_probe_subjectless_followup_fragment_not_executing(self):
        # 無可繼承主體的追問片段：鏈式主體線程以 prev_subject 單一
        # 狀態源投影前序狀態——比較集合整體繼承 stocks、板塊前序繼承
        # sectors，追問片段絕不以無錨點執行類任務放行（stocks/sectors/
        # 繼承碼全空會觸發無標的 Agent 工作流）。判空口徑＝無任何主體
        # 錨點（stocks/sectors/primary 全空）——多標的比較的 primary=''
        # 是設計行為（交執行端處理），不算空主體
        def _anchorless(t):
            return (t.source == "context"
                    and t.intent != WebIntent.GENERAL_CHAT
                    and not (t.primary_stock_code or t.stocks or t.sectors))

        rs = _resolver().resolve("对比茅台和五粮液，然后呢", {})
        assert not any(_anchorless(t) for t in _flat(rs)), \
            "比较前序的追问片段须继承标的集合，不得空主体执行"
        followup = _flat(rs)[-1]
        assert followup.source == "context"
        assert _codes(followup) == ["600519", "000858"], \
            "追问片段整体继承比较集合"

        rs2 = _resolver().resolve("看看白酒板块，然后呢", {})
        assert not any(_anchorless(t) for t in _flat(rs2)), \
            "板块前序的追问片段须继承板块槽位，不得空主体执行"
        followup2 = _flat(rs2)[-1]
        assert followup2.source == "context"
        assert followup2.sectors == ["白酒"], "追问片段继承前序板块槽位"

    def test_probe_contradiction_reply_reopened_as_new_topic(self):
        # 矛盾棄置不產空殼：點名雙候選的回覆按比較語義整輪判新話題
        # （docstring 契約），確認殼確定性剔除——primary_stock_code 不
        # 回退會話陳舊標的（600519 貴州茅臺）
        r = _resolver()
        session: Dict[str, Any] = {"recent_stocks": ["600519"],
                                   "last_intent": "stock_analysis"}
        rs1 = r.resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = r.resolve("BABA和HK09988", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert _codes(flat_[0]) == ["BABA", "HK09988"], \
            "点名双候选的回复应按比较语义重新开题，而非丢弃退壳"

    def test_probe_llm_extra_code_after_group_pick_rejected(self):
        # LLM 閘門判據取輸入屬性快照（had_candidates），不隨循環中收縮
        # 的 candidates 變化——組內選中清空列表後，組外庫內代碼同樣
        # 拒收（市場消解同樣收縮列表，快照取在市場塊之前）
        stub = _StubLLMAdapter(content=_llm_json(
            "quote_lookup", 0.9, stock_codes=["HK09988", "600519"]))
        rs = _resolver(stub).resolve("阿里巴巴哈哈哈", {})
        assert _codes(_flat(rs)[0]) == ["HK09988"], \
            "组内消解后，组外库内代码仍须拒收（闸门判据不得随循环收缩）"

    def test_probe_portfolio_sibling_requires_subject(self):
        # 平權構造：組合語境任務與主體任務共享實體解析——標的歧義時
        # 候選隨身（同樣轉確認，消歧後兩任務各自落位），不派生
        # 無 stocks 無候選無確認的空殼執行
        rs = _resolver().resolve("我的阿里巴巴持仓怎么看", {})
        for t in _flat(rs):
            assert (t.intent == WebIntent.GENERAL_CHAT
                    or t.stocks or t.candidates or t.needs_confirmation), \
                "执行类任务必须携带主体（stocks/candidates）或转确认"

    def test_portfolio_sibling_ambiguous_settles_both(self):
        # 消歧輪迴填：平權構造下主/兄弟雙確認任務各自攜帶候選——
        # 消歧輪必須同時落位（兄弟無候選則無從回填、空殼執行）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("我的阿里巴巴持仓怎么看", session)
        assert [(t.intent, set(_candidate_codes(t)), t.needs_confirmation)
                for t in _flat(rs1)] == [
            (WebIntent.STOCK_ANALYSIS, {"BABA", "HK09988"}, True),
            (WebIntent.PORTFOLIO_ANALYSIS, {"BABA", "HK09988"}, True)]
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股", session)
        assert [(_codes(t), t.needs_confirmation) for t in _flat(rs2)] == [
            (["HK09988"], False), (["HK09988"], False)]
        apply_resolution_to_session(session, rs2)
        assert session[PENDING_ACTIONS_KEY] == []

    def test_probe_malformed_pending_action_shape_survives(self):
        # pending_action 為字符串等非 dict 形態不得進
        # _normalize_pending_groups 的 pending.get（AttributeError 擊穿
        # resolve 主鏈）。守衛在解析器入口（覆蓋 consume 兩個調用點）：
        # 畸形被忽略按新消息解析，毒化條目隨 apply 覆寫自愈
        session: Dict[str, Any] = {
            LAST_RESOLUTIONS_KEY: [[{
                "intent": "stock_analysis", "confidence": 0.85,
                "source": "rule", "needs_confirmation": True,
                "pending_action": "confirm_stock",
                "source_request": "分析阿里巴巴",
            }]],
        }
        rs = _resolver().resolve("港股", session)
        assert rs, "畸形 pending_action 形状应被忽略（按新消息解析），不得击穿 resolve"


# =========================================================================
# 多意圖協議實體完整性 / 消歧回覆畫像 / 確認狀態遷移 / 載荷健壯性
# =========================================================================


class TestDeepScanRound3Defects:
    """多意圖數組實體協議與確認鏈路完整性的迴歸用例：

    - 多意圖數組實體完整性：單元素數組繼承完整規則基底，多元素經
      孤兒核算（_reclaim_orphan_entities）回收未認領實體，被消解組
      的餘留候選不回掛；
    - 消歧回覆畫像：fresh 的證據集是 stocks+candidates（_reply_profile），
      has_content 的意圖信號是 token 級 tag 查表（extend 詞池動作詞
      同權可見）；
    - 確認狀態遷移：全組落定時殘留 unresolved_names 一併清空（空
      groups 的澄清輪結構上不可滿足）；
    - 載荷健壯性：__post_init__ 對缺 code 的 dict 候選按
      _stock_from_payload 同口徑跳過，不裸下標擊穿構造。
    """

    def test_probe_intents_array_null_code_drops_ambiguity(self):
        # 單元素 intents 數組繼承完整規則基底——LLM 按"代碼無把握返回
        # null"的協議約束返回 null stock_code 時，規則側識別的跨市場
        # 歧義候選隨行保留並轉確認（與單對象協議同語義）
        stub = _StubLLMAdapter(content=json.dumps({"intents": [{
            "intent": "stock_analysis", "confidence": 0.9, "market": None,
            "stock_code": None, "stock_codes": [], "sectors": [],
            "unresolved_names": [],
        }], "note": "x"}))
        # 空格分隔的未登錄詞觸發 LLM 複核，規則側保留阿里巴巴雙候選
        t = _flat(_resolver(stub).resolve("分析阿里巴巴 叭叭叭", {}))[0]
        assert t.needs_confirmation, "歧义候选未随 LLM null 代码消失，须转确认"
        assert {c.code for c in t.candidates} == {"BABA", "HK09988"}

    def test_probe_intents_array_null_code_drops_resolved_stock(self):
        # 單元素 intents 數組未回填代碼時，規則側已解析的確定實體
        # （茅臺→600519）隨行保留——空標的執行任務不放行
        stub = _StubLLMAdapter(content=json.dumps({"intents": [{
            "intent": "stock_analysis", "confidence": 0.9, "market": None,
            "stock_code": None, "stock_codes": [], "sectors": [],
            "unresolved_names": [],
        }], "note": "x"}))
        t = _flat(_resolver(stub).resolve("分析茅台 叭叭叭", {}))[0]
        assert _codes(t) == ["600519"], "规则已解析实体不因 LLM 漏填代码丢失"

    def test_llm_multi_item_orphan_stock_reclaimed(self):
        # 多元素孤兒核算：LLM 拆分後逐項漏填代碼（僅板塊項帶 sectors），
        # 規則側已解析實體（600519）掛載到首個無實體執行任務——實體
        # 不因協議拆分靜默蒸發
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9, "market": None,
             "stock_code": None, "stock_codes": [], "sectors": [],
             "unresolved_names": []},
            {"intent": "sector_analysis", "confidence": 0.9, "market": None,
             "stock_code": None, "stock_codes": [], "sectors": ["医药"],
             "unresolved_names": []},
        ]}, ensure_ascii=False))
        # 未登錄詞以空格分隔（緊貼會令 DFS 整段放棄，規則實體陪葬）
        flat_ = _flat(_resolver(stub).resolve("看下茅台股价和医药板块 叭"))
        assert _codes(flat_[0]) == ["600519"], "孤儿实体挂载到首个空执行任务"
        assert flat_[1].sectors == ["医药"]

    def test_llm_multi_item_group_resolution_not_orphaned(self):
        # 組清賬口徑：LLM 在元素中消解歧義組（HK09988 落位）後，兄弟
        # 候選（BABA）屬被消解組餘留而非未決歧義——不作為孤兒回掛，
        # 不產生二次歧義確認
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "stock_analysis", "confidence": 0.9, "market": None,
             "stock_code": "HK09988", "stock_codes": [], "sectors": [],
             "unresolved_names": []},
            {"intent": "sector_analysis", "confidence": 0.9, "market": None,
             "stock_code": None, "stock_codes": [], "sectors": ["医药"],
             "unresolved_names": []},
        ]}, ensure_ascii=False))
        # 未登錄詞以空格分隔：規則側須真正提取阿里巴巴歧義（否則測試空轉）
        flat_ = _flat(_resolver(stub).resolve("分析阿里巴巴和医药板块 叭"))
        assert _codes(flat_[0]) == ["HK09988"]
        assert all(not t.candidates for t in flat_)
        assert not any(t.needs_confirmation for t in flat_)

    def test_probe_confirm_reply_sibling_ambiguous_mention_dropped(self):
        # '平安銀行，阿里巴巴呢'——前段正常消歧，後段新歧義提及
        # （無 stocks、'呢'非意圖詞）經 candidates 出圈畫像（fresh）
        # 保留為自己的任務並轉確認，不被判純消歧片段丟棄
        session: Dict[str, Any] = {}
        rs = _resolver().resolve("分析平安", session)
        apply_resolution_to_session(session, rs)
        flat_ = _flat(_resolver().resolve("平安银行，阿里巴巴呢", session))
        assert len(flat_) == 2, "消歧落位任务 + 新歧义提及任务都应保留"
        assert any(t.needs_confirmation and t.candidates for t in flat_), \
            "新提及的阿里巴巴歧义须走自己的确认"

    def test_probe_confirm_reply_fetch_verb_intent_overridden(self):
        # '查一下平安銀行'作為消歧回覆時，'查'（extend 詞池
        # action_quote_fetch）經 token 級 tag 查表構成 has_content 信號
        # → 保留為任務——原任務消解落位（stock_analysis）＋ 新任務
        # （quote_lookup）並存，取數語義不被上輪意圖靜默覆蓋
        session: Dict[str, Any] = {}
        rs = _resolver().resolve("分析平安", session)
        apply_resolution_to_session(session, rs)
        flat_ = _flat(_resolver().resolve("查一下平安银行", session))
        assert len(flat_) == 2
        assert flat_[0].intent == WebIntent.STOCK_ANALYSIS, "原任务消解落位"
        assert _codes(flat_[0]) == ["000001"]
        assert not flat_[0].needs_confirmation
        assert flat_[1].intent == WebIntent.QUOTE_LOOKUP, "取数动词按新任务保留"
        assert _codes(flat_[1]) == ["000001"]

    def test_probe_resolved_task_reblocked_by_unsatisfiable_confirmation(self):
        # '分析平安和SH600999'首輪歧義確認；'平安銀行'消解落定後殘留
        # unresolved_names 隨全組落定一併清空——不被結構上不可滿足的
        # 壞代碼澄清（空 groups pending）再次短路，消解成果 000001
        # 正常執行
        session: Dict[str, Any] = {}
        rs = _resolver().resolve("分析平安和SH600999", session)
        apply_resolution_to_session(session, rs)
        flat_ = _flat(_resolver().resolve("平安银行", session))
        assert len(flat_) == 1 and _codes(flat_[0]) == ["000001"]
        assert not flat_[0].needs_confirmation, \
            "歧义已消解、标的已落位，不得被无法满足的坏代码澄清再次阻断"

    def test_probe_candidates_dict_missing_code_crashes(self):
        # 缺 code 的 dict 候選按 _stock_from_payload 同口徑跳過，不裸
        # 下標 c["code"] 擊穿構造；攜帶 code 的正常 dict 候選仍完整
        # 轉換（防過度過濾的對照斷言）
        r = WebIntentResolution(
            intent=WebIntent.STOCK_ANALYSIS, confidence=0.9,
            candidates=[{"name": "某股"}])
        assert r.candidates == [], "缺 code 的 dict 候选应宽容跳过，不得击穿构造"
        r2 = WebIntentResolution(
            intent=WebIntent.STOCK_ANALYSIS, confidence=0.9,
            candidates=[{"code": "600519", "name": "贵州茅台", "market": "a"},
                        {"name": "无名"}])
        assert r2.candidates == [Stock("600519", "贵州茅台", "a")]


class TestReviewRound4BlockingDefects:
    """無錨點執行守衛的迴歸釘子——謂詞與
    test_probe_subjectless_followup_fragment_not_executing 同源：
    執行類任務不得無錨點放行。"""

    @staticmethod
    def _anchorless(t: WebIntentResolution) -> bool:
        return (t.source in ("context", "llm")
                and t.intent != WebIntent.GENERAL_CHAT
                and not (t.primary_stock_code or t.stocks or t.sectors
                         or t.candidates or t.unverified_codes))

    def test_probe_chain_ambiguous_prev_followup_inherits_candidates(self):
        # 前序片段主體歧義（stocks 空、candidates 非空）時，鏈式主體
        # 線程按 _ChainSubject 三形態（stocks/sectors/ambiguous）投影：
        # 歧義前序的候選組隨行繼承，與主體任務共待同一次消歧
        rs = _resolver().resolve("分析阿里，然后它怎么样", {})
        flat_ = _flat(rs)
        assert len(flat_) == 2
        assert not any(self._anchorless(t) for t in flat_), \
            "前序主体歧义时，追问片段不得以无锚点执行类任务放行"
        followup = flat_[-1]
        assert followup.source == "context"
        assert set(_candidate_codes(followup)) == {"HK09988", "BABA"}, \
            "追问片段继承前序歧义候选，与主体任务共待同一次消歧"
        # 消歧輪雙任務同時落位（不折疊架構下的同候選結算）
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, rs)
        rs2 = _resolver().resolve("港股", session)
        assert [(_codes(t), t.needs_confirmation) for t in _flat(rs2)] == [
            (["HK09988"], False), (["HK09988"], False)], \
            "一次消歧同时落位主体任务与追问片段"

    def test_probe_llm_followup_promotion_keeps_anchor(self):
        # LLM followup 偽標籤轉繼承可產出無錨點執行類任務——規則路徑
        # 分支6 有 prev_subject 繼承，LLM 合併路徑由 _finalize_
        # confirmation 的無錨點執行類守衛（所有出口的單一 choke point）
        # 收口：缺一切主體錨點時轉 low_confidence 澄清。板塊輪不寫
        # recent_stocks，會話級追問經 LLM 兜底後 sectors/stocks 全空
        # → 守衛收口
        stub = _StubLLMAdapter(content=json.dumps(
            {"intents": [{"intent": "followup", "confidence": 0.9}]},
            ensure_ascii=False))
        rs = _resolver(stub).resolve(
            "再展开讲讲", {LAST_INTENT_KEY: "sector_analysis"})
        flat_ = _flat(rs)
        assert len(flat_) == 1
        t = flat_[0]
        assert (t.intent == WebIntent.GENERAL_CHAT
                or t.needs_confirmation
                or t.stocks or t.sectors), \
            "followup 继承产物无任何主体锚点时不得以执行类任务放行"

    def test_probe_llm_sparse_multi_intent_fill_not_stale_anchored(self):
        # 多元素拆分的基底重置一併清 inherited_stock_code——LLM 稀疏
        # 填充（第二元素 stock_code=null）時該元素不得靜默回退會話陳舊
        # 標的（000858 五糧液）作 primary（單任務解讀產物不隨多元素
        # 拆分殘留）；未填實體的執行類元素由無錨點守衛轉確認
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9,
             "stock_code": "600519"},
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_code": None},
        ]}, ensure_ascii=False))
        session: Dict[str, Any] = {RECENT_STOCKS_KEY: ["000858"]}
        flat_ = _flat(_resolver(stub).resolve("看一下茅台股价和基本面", session))
        assert len(flat_) == 2
        second = flat_[1]
        assert second.primary_stock_code != "000858", \
            "拆分元素不得静默回退会话陈旧标的充当主体"
        assert (second.stocks or second.needs_confirmation), \
            "未填实体的执行类元素必须携带自身标的或转确认，不得无锚点放行"

    def test_probe_llm_followup_item_inherits_prev_subject(self):
        # 數組內 followup 主體繼承：followup 元素延續前一項意圖時
        # 主體槽空 → 隨行補齊前一項 stocks/sectors（與規則分支6
        # 鏈式繼承同構），不落成無錨點執行任務
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9,
             "stock_code": "600519"},
            {"intent": "followup", "confidence": 0.9},
        ]}, ensure_ascii=False))
        flat_ = _flat(_resolver(stub).resolve("看一下茅台股价和基本面", {}))
        assert [t.intent for t in flat_] == [
            WebIntent.QUOTE_LOOKUP, WebIntent.QUOTE_LOOKUP]
        assert _codes(flat_[1]) == ["600519"], \
            "followup 元素继承前一项主体标的"

    def test_probe_requeue_round_finalizes_kept_tasks(self):
        # 確認消費的重建輪：短路返回時 recovered 組原樣隨行（保住
        # confirmed 累積），kept 組按對象身份識別並照常收尾——本輪
        # kept 新任務的歧義/低置信確認當輪成立（裸"機器人"0.5 →
        # low_confidence 確認）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里，分析平安", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股，再看看机器人", session)
        flat_ = _flat(rs2)
        robot = next(
            (t for t in flat_ if t.intent == WebIntent.SECTOR_ANALYSIS), None)
        assert robot is not None, "kept 新任务（机器人板块双解）应在链上"
        assert robot.needs_confirmation, \
            "requeue 轮 kept 任务的低置信确认不得延迟一轮浮出"
        assert any(t.needs_confirmation for t in flat_), \
            "平安组未解，整链仍须短路等待"


class TestReviewRound5BlockingDefects:
    """確認消費輪收尾契約 / 繼承守衛 / 組結構不變量：

    - 確認消費後的 recovered 任務不重過第六步收尾——LLM 來源任務
      （≤0.75 低於豁免線）不被再次送審，用戶的消歧選擇不被 LLM
      二次意見汙染/改判，低置信任務不被再次短路（確認輪的置信度由
      用戶選擇背書）；
    - 繼承守衛對動作詞類不偏待：非 request 動作詞（能買/多少錢）
      攜帶未消化主語信號（裸數字/存疑代碼）時不繼承，用戶顯式指稱
      的標的不被靜默丟棄；
    - 確認消費保持"組=子消息"不變量：同子消息兄弟任務不各自觸發
      組級 LLM 枚舉（同一原文不重複枚舉產出重複任務）。
    """

    # ---- 確認消費後的 recovered 任務不重過收尾 ----

    def test_probe_resolved_task_not_re_adjudicated_by_llm(self):
        # LLM 路徑產生的歧義確認任務（source=llm，0.75<0.8 豁免線）被
        # "港股"消解後，不得對原消息重跑 LLM 兜底——二次意見的
        # stock_code=BABA 會併入 stocks，汙染用戶已確認的 HK09988
        stub1 = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.9))
        resolver = WebIntentResolver(llm_adapter=stub1)
        session: Dict[str, Any] = {}
        rs1 = resolver.resolve("阿里巴巴哈哈哈", session)
        assert rs1[0][0].needs_confirmation
        assert rs1[0][0].source == "llm"
        apply_resolution_to_session(session, rs1)

        stub2 = _StubLLMAdapter(content=_llm_json(
            "stock_analysis", 0.9, stock_code="BABA"))
        rs2 = WebIntentResolver(llm_adapter=stub2).resolve("港股", session)
        assert stub2.calls == [], "已确认任务不得重跑 LLM 兜底"
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert _codes(flat_[0]) == ["HK09988"], \
            "用户选定标的不被 LLM 二次意见污染"
        assert not flat_[0].needs_confirmation

    def test_probe_resolved_low_confidence_task_not_reblocked(self):
        # 低置信（0.55）LLM 歧義任務消解後：用戶已顯式選定標的，
        # 不得再被 low_confidence 二次短路——確認輪的置信度由用戶
        # 選擇背書（與 pending_actions 回退路徑的 confirmation/0.9
        # 契約同構）
        stub1 = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.55))
        resolver = WebIntentResolver(llm_adapter=stub1)
        session: Dict[str, Any] = {}
        rs1 = resolver.resolve("阿里巴巴哈哈哈", session)
        assert rs1[0][0].reason == "ambiguous_stock_name"
        apply_resolution_to_session(session, rs1)

        stub2 = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.55))
        rs2 = WebIntentResolver(llm_adapter=stub2).resolve("港股", session)
        assert stub2.calls == []
        flat_ = _flat(rs2)
        assert _codes(flat_[0]) == ["HK09988"]
        assert not flat_[0].needs_confirmation, "消解轮不得再次确认"

    def test_probe_recovered_llm_sibling_not_re_reviewed(self):
        # 上輪短路鏈中的非確認兄弟任務（LLM 來源，未執行）隨 survivors
        # 返回時同樣不得重過收尾——對上輪子消息重跑 LLM 屬重複裁決，
        # 且非確定性的二次輸出可能改掉上輪已敲定的任務形態
        stub1 = _StubLLMAdapter(content=_llm_json("stock_analysis", 0.9))
        resolver = WebIntentResolver(llm_adapter=stub1)
        session: Dict[str, Any] = {}
        rs1 = resolver.resolve("分析阿里，再看看茅台+哈哈哈", session)
        assert rs1[0][0].needs_confirmation  # 阿里歧義 → 整鏈短路
        assert rs1[1][0].source == "llm" and not rs1[1][0].needs_confirmation
        apply_resolution_to_session(session, rs1)

        stub2 = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        rs2 = WebIntentResolver(llm_adapter=stub2).resolve("港股", session)
        assert stub2.calls == [], "recovered 任务不得重过 LLM 收尾"
        flat_ = _flat(rs2)
        assert [(t.intent, _codes(t)) for t in flat_] == [
            (WebIntent.STOCK_ANALYSIS, ["HK09988"]),
            (WebIntent.STOCK_ANALYSIS, ["600519"]),
        ]

    # ---- 繼承守衛：未消化信號面前寧可不做不可做錯 ----

    def test_probe_action_word_with_bare_digit_not_inherited(self):
        # "現在能買09932嗎"：動作詞（能買）＋未消化裸數字（09932 是
        # HK 短碼形態）——不得繼承，09932 不被靜默丟棄、不對 600519
        # 而非用戶指稱的 09932 作答。與 test_bare_number_subject_
        # not_inherited（帶 request 詞）同語義：寧可低置信也不做錯
        session = {LAST_INTENT_KEY: "stock_analysis",
                   RECENT_STOCKS_KEY: ["600519"]}
        r = _resolver().resolve_first("现在能买09932吗", session)
        assert r.source == "rule", "未消化数字不得被继承吸收"
        assert r.intent == WebIntent.GENERAL_CHAT

    def test_probe_action_word_with_unknown_code_not_inherited(self):
        # "SOFI能買嗎"：存疑代碼是帶 tag 的未消化信號，不得當作追問
        # 繼承——應走存疑代碼透傳分支（與 test_unknown_code_subject_
        # not_inherited 同語義）
        session = {LAST_INTENT_KEY: "stock_analysis",
                   RECENT_STOCKS_KEY: ["600519"]}
        r = _resolver().resolve_first("SOFI能买吗", session)
        assert r.source == "rule"
        assert r.intent == WebIntent.STOCK_ANALYSIS
        assert r.unverified_codes == ["SOFI"], "存疑代码不得被继承静默丢弃"
        assert not r.needs_confirmation

    # ---- 確認消費保持"組=子消息"不變量 ----

    @staticmethod
    def _multi_intent_payload() -> str:
        return json.dumps({"intents": [
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_code": "600519"},
            {"intent": "sector_analysis", "confidence": 0.9,
             "sectors": ["医药"]},
        ]}, ensure_ascii=False)

    def test_probe_interacted_kept_siblings_not_split(self):
        # 消解輪 kept 的同子消息兄弟任務（個股＋板塊）被拍平成單例組
        # → 各自觸發組級 LLM 枚舉同一原文兩遍 → 任務重複。組級枚舉
        # 契約（一條子消息至多一次）必須跨確認消費保持
        stub = _StubLLMAdapter(content=self._multi_intent_payload())
        resolver = WebIntentResolver(llm_adapter=stub)
        session: Dict[str, Any] = {}
        rs1 = resolver.resolve("分析阿里", session)
        apply_resolution_to_session(session, rs1)

        rs2 = resolver.resolve("港股，分析茅台和医药板块+哈哈哈", session)
        assert len(stub.calls) == 1, "同一子消息至多一次多意图枚举"
        flat_ = _flat(rs2)
        assert [(t.intent, _codes(t), t.sectors) for t in flat_] == [
            (WebIntent.STOCK_ANALYSIS, ["HK09988"], []),
            (WebIntent.STOCK_ANALYSIS, ["600519"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["医药"]),
        ], "兄弟任务不得因组结构破坏而重复产出"

    def test_probe_zero_interaction_reply_groups_preserved(self):
        # 零交互早退同樣按組返回：子消息的兄弟任務保持同組，一次
        # 枚舉；拍平成單例組會兩遍枚舉同一原文（4 任務＋2 次調用）
        stub = _StubLLMAdapter(content=self._multi_intent_payload())
        resolver = WebIntentResolver(llm_adapter=stub)
        session: Dict[str, Any] = {}
        rs1 = resolver.resolve("分析阿里", session)
        apply_resolution_to_session(session, rs1)

        rs2 = resolver.resolve("分析茅台和医药板块+哈哈哈", session)
        assert len(stub.calls) == 1, "零交互轮同样一条子消息至多一次枚举"
        flat_ = _flat(rs2)
        assert [(t.intent, _codes(t), t.sectors) for t in flat_] == [
            (WebIntent.STOCK_ANALYSIS, ["600519"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["医药"]),
        ], "零交互返回不得拆散兄弟任务导致重复产出"


# =========================================================================
# 量詞閘門與組內集合提供者豁免 — 已修復缺陷的常規迴歸用例。
# =========================================================================


class TestReviewRound6BlockingDefects:
    """量詞閘門與組內集合提供者豁免：

    - 量詞閘門只攔無語義標籤的量詞 token：``_token_facts`` 裸數字
      四重閘門的排除條件按"下一 token 無 tag 且首字符 ∈ 量詞集"判定
      ——已打標關鍵詞（"股价"＝TAG_ACTION_QUOTE）不被首字符"股"
      誤傷，"600519股價"類取數句直達行情查詢（無 LLM 部署形態下
      無糾錯機會，不得靜默誤路由閒聊）；
    - 管道拆分產物 × 組內集合提供者：``LLM_SYSTEM_PROMPT`` 的管道
      拆分原理要求"泛指持倉×動作詞"拆出無需填代碼的動作元素——收尾
      以組為單位識別集合提供者（組內存在 portfolio_analysis），空
      實體執行任務主體＝提供者的賬戶標的集合輸出（任務間主體引用），
      無錨點守衛與低置信守衛對其豁免（轉無選項確認＝用戶任何回覆
      無法消解的死鎖）；無提供者的空實體任務照常攔截。
    """

    # ---- 量詞閘門不誤傷已打標數據詞 ----

    def test_probe_code_directly_before_quote_keyword_promotes(self):
        # "600519股價"：股價是 TAG_ACTION_QUOTE 已打標關鍵詞（非量詞），
        # 四重閘門應放行提升——代碼+數據詞的取數句直達行情查詢，
        # 不得靜默誤路由閒聊（無 LLM 形態下無糾錯機會）
        r = _resolver().resolve_first("600519股价")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(r) == ["600519"]

    def test_probe_fetch_verb_code_quote_promotes(self):
        # "查600519股價"：取數動詞 + 代碼 + 數據詞的最短取數句，
        # 同樣直達行情查詢
        r = _resolver().resolve_first("查600519股价")
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert _codes(r) == ["600519"]

    def test_probe_amount_and_tagged_keyword_gate_regression(self):
        # 量詞閘門邊界釘子：未打標的量詞 token（"元"/"萬元"）繼續阻止
        # 提升——金額/數量語義不因閘門收緊而放行；對照"的"間隔形態
        # 不受量詞閘門影響
        r = _resolver().resolve_first("我有300750万元")
        assert r.stocks == [] and r.intent == WebIntent.GENERAL_CHAT
        r2 = _resolver().resolve_first("600519的股价")
        assert r2.intent == WebIntent.QUOTE_LOOKUP and _codes(r2) == ["600519"]

    # ---- 組內集合提供者豁免空實體動作元素 ----

    def test_probe_pipeline_split_action_element_executes(self):
        # prompt 管道拆分原理的直接產物（prompt 示例原句）："查下我持倉
        # 的股票的股價"＝〔portfolio_analysis（取集合）＋quote_lookup（主體
        # ＝前一意圖的集合，無需填代碼）〕。動作元素主體是鏈內主體引用
        # 而非空缺——組內存在集合提供者即標記可執行，不得轉無選項確認
        # 整鏈死鎖（用戶任何回覆都無法消解）
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "portfolio_analysis", "confidence": 0.9},
            {"intent": "quote_lookup", "confidence": 0.9},
        ], "note": "泛指主体拆取持仓＋报价"}, ensure_ascii=False))
        rs = _resolver(stub).resolve("查下我持仓的股票的股价")
        flat_ = _flat(rs)
        assert [t.intent for t in flat_] == [
            WebIntent.PORTFOLIO_ANALYSIS, WebIntent.QUOTE_LOOKUP]
        assert not any(t.needs_confirmation for t in flat_), \
            "拆分动作元素主体＝前序泛指集合，不得整链死锁"

    def test_probe_provider_exempts_low_confidence_element_too(self):
        # 豁免必須覆蓋低置信出口：提供者在場時空實體動作元素即使置信度
        # <0.6 也不轉確認（無選項確認同樣是死鎖形態），主體引用不受
        # 意圖置信度影響
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "portfolio_analysis", "confidence": 0.9},
            {"intent": "stock_analysis", "confidence": 0.5},
        ], "note": "泛指主体拆取持仓＋分析"}, ensure_ascii=False))
        rs = _resolver(stub).resolve("分析我所有的持仓股票")
        flat_ = _flat(rs)
        assert not any(t.needs_confirmation for t in flat_)

    def test_probe_no_provider_empty_element_still_confirms(self):
        # 豁免邊界釘子：組內沒有集合提供者時，空實體執行類任務照常轉
        # low_confidence 待澄清——守衛對"LLM 判執行類但消息無主體"等來
        # 源不變
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "stock_analysis", "confidence": 0.9},
        ], "note": "无实体单元素"}, ensure_ascii=False))
        rs = _resolver(stub).resolve("分析一下")
        flat_ = _flat(rs)
        empty_executing = [t for t in flat_
                           if t.intent == WebIntent.STOCK_ANALYSIS
                           and not (t.stocks or t.candidates or t.sectors
                                    or t.unresolved_names
                                    or t.unverified_codes)]
        assert empty_executing, "前置：stub 场景应含空实体执行任务"
        assert all(t.needs_confirmation for t in empty_executing)

    def test_probe_provider_group_still_confirms_ambiguity(self):
        # 豁免只作用於空實體守衛：同組含提供者時，攜帶歧義候選的其他
        # 任務照常走歧義確認（不得因提供者在場放行錯誤標的）
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "portfolio_analysis", "confidence": 0.9},
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_codes": ["HK09988", "BABA"]},
        ], "note": "组合＋歧义标的"}, ensure_ascii=False))
        rs = _resolver(stub).resolve("查下我持仓的股票，再分析阿里巴巴")
        flat_ = _flat(rs)
        ambiguous = [t for t in flat_ if t.candidates]
        assert ambiguous and all(t.needs_confirmation for t in ambiguous)

    def test_probe_rule_path_pipeline_split_input_executes(self):
        # 對照釘子：無 LLM 形態同一輸入規則直達單一組合任務可執行
        # ——同一請求不因走 LLM 兜底反而死鎖
        r = _resolver().resolve_first("查下我持仓的股票的股价")
        assert r.intent == WebIntent.PORTFOLIO_ANALYSIS
        assert not r.needs_confirmation


# =========================================================================
# 跨輪追問繼承 / last_intent 落點 / 會話形狀健壯性 — 常規迴歸用例。
# =========================================================================


class TestReviewRound7BlockingDefects:
    """跨輪追問主體繼承 / last_intent 落點 / 會話形狀健壯性：

    - 跨輪追問主體繼承：分支6 的主體繼承（sectors / 多標的 stocks /
      歧義組）由 resolve 以 _session_chain_subject 播種初值——上一
      已執行輪的落點主體（與 last_intent 落點同規則同任務，短路輪
      排除），跨輪與同消息片段走同一條繼承路徑，"继续"一律指向
      last_intent 的任務（板塊/指數任務不寫 recent_stocks，無播種
      的追問會退無選項確認死鎖）；
    - last_intent 記對話落點（最後一個主體任務為執行類的組），與
      recent_stocks 頭插"後寫勝出"同源——意圖與標的錨點出自同一
      任務，前置寒暄/拒絕詞碎片不把真正的執行意圖擠出；
    - 會話形狀異常不擊穿：resolve 讀點單點歸一（recent_stocks 非
      字符串元素 / current_stock_code 非文本按缺失處理），與寫側
      apply_outcome 的 isinstance(str) 過濾對稱。
    """

    # ---- 跨輪追問主體繼承 ----

    def test_probe_cross_round_sector_followup_inherits_subject(self):
        # "分析白酒板塊"（正常執行）→"繼續"：追問繼承上輪落點主體的
        # 板塊槽位繼續板塊分析，不回無選項確認讓用戶無解
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析白酒板块", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("继续", session)
        t = _flat(rs2)[0]
        assert t.source == "context"
        assert t.intent == WebIntent.SECTOR_ANALYSIS
        assert t.sectors == ["白酒"], "跨轮追问须继承上轮板块槽位"
        assert not t.needs_confirmation, "继承主体后不得回无选项确认"

    def test_probe_cross_round_index_followup_inherits_subject(self):
        # "查一下上證指數" → "繼續"：繼續查上證指數
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下上证指数", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("继续", session)
        t = _flat(rs2)[0]
        assert t.source == "context"
        assert t.intent == WebIntent.QUOTE_LOOKUP
        assert t.sectors == ["上证"], "跨轮追问须继承上轮指数槽位"
        assert not t.needs_confirmation

    def test_probe_cross_round_comparison_followup_inherits_stock_set(self):
        # "對比茅臺和五糧液" → "繼續呢"：整體繼承兩隻標的的比較語義，
        # 不退化為 recent_stocks[0] 單股
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("对比茅台和五粮液", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("继续呢", session)
        t = _flat(rs2)[0]
        assert t.source == "context"
        assert set(_codes(t)) == {"600519", "000858"}, \
            "跨轮追问须继承比较集合，不得静默丢失一只"

    def test_probe_no_projection_session_followup_still_guarded(self):
        # 邊界釘子：無 last_resolutions 投影的會話（新會話/手工構造）
        # 不播種主體——追問仍由無錨點守衛收口，種子只來自已執行輪的
        # 會話投影
        session = {LAST_INTENT_KEY: "sector_analysis"}
        t = _flat(_resolver().resolve("继续", session))[0]
        assert t.source == "context"
        assert t.needs_confirmation and t.reason == "low_confidence"

    # ---- last_intent 記對話落點 ----

    def test_probe_leading_chat_fragment_does_not_pollute_last_intent(self):
        # 前置寒暄碎片不得把執行意圖擠出 last_intent——last_intent 記
        # 對話落點（最後一個主體任務為執行類的組）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("你好，分析茅台", session)
        apply_resolution_to_session(session, rs1)
        assert session[LAST_INTENT_KEY] == "stock_analysis", \
            "前置寒暄碎片不得把执行意图挤出 last_intent"
        rs2 = _resolver().resolve("继续", session)
        t = _flat(rs2)[0]
        assert t.intent == WebIntent.STOCK_ANALYSIS and t.source == "context"
        assert t.inherited_stock_code == "600519"

    def test_probe_landing_intent_from_last_executing_group(self):
        # 順序敘事兩任務（報價→分析）後，last_intent＝對話落點（最後的
        # 分析任務）——"繼續"延續分析，且意圖與標的錨點出自同一任務，
        # 不產生"任務1意圖×任務2標的"的錯配
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下茅台股价，然后分析五粮液", session)
        apply_resolution_to_session(session, rs1)
        assert session[LAST_INTENT_KEY] == "stock_analysis"
        rs2 = _resolver().resolve("继续", session)
        t = _flat(rs2)[0]
        assert t.intent == WebIntent.STOCK_ANALYSIS
        assert t.inherited_stock_code == "000858"

    def test_probe_trailing_light_task_pairs_intent_with_subject(self):
        # 落點規則的對偶釘子：尾隨輕任務（順帶查價）成為落點時，意圖與
        # 標的配套（都是旁支任務的對象），而非"主訴求意圖×旁支標的"的
        # 交叉錯配。注意連接詞用"然後"而非"順便"："順便"不在任何詞池，
        # 其開頭的片段 DFS 全覆蓋失敗整段陪葬（茅臺/股價均不提取），
        # 是分詞層"寧可不做"的既定保守行為
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析五粮液的基本面，然后查下茅台股价", session)
        apply_resolution_to_session(session, rs1)
        assert session[LAST_INTENT_KEY] == "quote_lookup"
        rs2 = _resolver().resolve("继续", session)
        t = _flat(rs2)[0]
        assert t.intent == WebIntent.QUOTE_LOOKUP
        assert t.inherited_stock_code == "600519"

    def test_probe_pure_chat_round_keeps_chat_last_intent(self):
        # 邊界釘子：純閒聊輪（無任何執行類任務）last_intent 照記
        # general_chat——落點規則只跳過閒聊碎片，不改變純閒聊輪的口徑
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("你好呀", session)
        apply_resolution_to_session(session, rs1)
        assert session[LAST_INTENT_KEY] == "general_chat"

    # ---- 會話形狀異常不擊穿（讀點類型歸一） ----

    def test_probe_malformed_recent_stocks_element_does_not_crash(self):
        # recent_stocks 混入非字符串元素（裸數字）時，低置信消息觸發
        # LLM 兜底不拋 AttributeError——非字符串元素按缺失處理（歸一
        # 為空繼承碼），與寫側過濾口徑對齊
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        session = {RECENT_STOCKS_KEY: [600519]}
        rs = _resolver(stub).resolve("它怎么样呢", session)
        t = _flat(rs)[0]
        assert isinstance(t.inherited_stock_code, str)

    def test_probe_malformed_current_stock_code_does_not_crash(self):
        # 對偶入口：request_context 的 current_stock_code 為非字符串
        # 真值（裸數字）時同形歸一為空繼承碼，不帶病透傳
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        rs = _resolver(stub).resolve("它怎么样呢", {}, {"current_stock_code": 600519})
        t = _flat(rs)[0]
        assert isinstance(t.inherited_stock_code, str)

    def test_probe_non_serializable_recent_element_does_not_crash(self):
        # 完整面：不可序列化元素（set/對象）會讓 LLM 請求體的
        # json.dumps（try 外）以 TypeError 擊穿——請求體只透傳字符串
        # 元素，其餘按缺失處理
        stub = _StubLLMAdapter(content=_llm_json("general_chat", 0.9))
        rs = _resolver(stub).resolve("它怎么样呢", {RECENT_STOCKS_KEY: [{1, 2}]})
        t = _flat(rs)[0]
        assert isinstance(t.inherited_stock_code, str)


# =========================================================================
# 確認回覆的內容保留契約 — 純消歧片段判定（板塊/未識別內容不丟棄）。
# =========================================================================


class TestReviewRound8BlockingDefects:
    """確認回覆中自帶新請求的保留契約（``_reply_profile`` 的 has_content）：

    - 板塊子消息是對象承載的請求：系統問"阿里巴巴指港股還是美股"，
      用戶答"港股，醫藥板塊"，醫藥板塊的請求不因確認消費在輪而
      靜默消失（同一句"醫藥板塊"在沒有待確認問題時能正常識別成
      板塊分析，對照釘子見 TestSectorSlotFilling）——板塊族 tag
      （板塊/行業/賽道/概念…）與指數詞同層級，都在自帶語義集合
      ``_COMPETING_TAGS`` 中；
    - 未識別內容計入自帶語義：用戶答"港股，茅臺和醫藥板塊咋樣呢"，
      第二段因詞池外的字（咋）整段無法全覆蓋分詞（分詞層"寧可
      不做"的既定保守行為，實體與意圖詞全部埋進 unknown token）——
      正常輪次這類消息交大模型複核，確認消費輪同樣保留（視野軸
      兜底只在任務被保留進第六步後才可能發生）。
    判定規則＝"子消息判為純消歧答案的必要條件是全部內容都落在待確認
    候選空間之內，消歧了才丟棄、否則保留作為新任務走完整 rule+LLM
    判定流程；充當過消歧證據不排斥請求角色"。兩類信號在唯一定義點
    ``_reply_profile`` 單點補齊。
    """

    # ---- 確認回覆中的板塊子消息不當純消歧片段丟棄 ----

    def test_probe_sector_submessage_survives_confirm_reply(self):
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股，医药板块", session)
        flat_ = _flat(rs2)
        sector = [t for t in flat_ if t.sectors == ["医药"]]
        assert sector, "确认消解轮不得丢弃回复中新带的板块请求子消息"
        assert sector[0].intent == WebIntent.SECTOR_ANALYSIS
        # 消歧主體照常落位（對照組：丟棄的只是不該丟棄的部分）
        resolved = [t for t in flat_ if t.source == "confirmation"]
        assert _codes(resolved[0]) == ["HK09988"]

    # ---- 確認回覆中的未識別內容不靜默丟棄 ----

    def test_probe_unread_submessage_survives_confirm_reply(self):
        # "咋"在詞池外：第二子消息整段 DFS 放棄成單個 unknown token，
        # 實體（茅臺）與意圖詞全部埋在裡面——正常輪次交 LLM 複核的輸入
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股，茅台和医药板块咋样呢", session)
        survivors = [t for t in _flat(rs2) if "茅台" in t.source_request]
        assert survivors, "整段未识别的回复子消息必须保留为任务（交 LLM 复核），不得丢弃"

    # ---- 規則釘子（判定規則的正反兩面對偶） ----

    def test_dual_role_fragment_narrows_and_keeps_request(self):
        # 規則釘子（正面）：子消息可同時充當消歧證據與新請求——"港股"
        # 把阿里巴巴收窄到港股候選（① 照常消費證據），"醫藥板塊怎麼
        # 看"作為新任務保留（命中過消歧通道不排斥請求角色）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股医药板块怎么看", session)
        flat_ = _flat(rs2)
        resolved = [t for t in flat_ if t.source == "confirmation"]
        assert _codes(resolved[0]) == ["HK09988"]
        sector = [t for t in flat_ if t.sectors == ["医药"]]
        assert sector and sector[0].intent == WebIntent.SECTOR_ANALYSIS

    def test_candidate_echo_in_compound_reply_still_dropped(self):
        # 規則釘子（反面）：候選空間內的實體提及（複述組名）是答案空間
        # 回聲——另一片段已給出答案時，回聲片段照舊丟棄，不得對剛消解
        # 的問題虛假重問（"所有實體參與消歧才判為答案"的邊界：複述組
        # 名與候選互動＝參與，不構成證據≠不參與）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("阿里巴巴，港股", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1, "回声片段不得重生为对已消解问题的重问"
        assert flat_[0].source == "confirmation"
        assert _codes(flat_[0]) == ["HK09988"]

    # ---- 邊界釘子：純答案形態照舊丟棄 ----

    def test_pure_market_reply_still_consumed(self):
        # 純消歧片段（"港股"單獨回覆）照舊被消費且不多出任務——
        # 純市場詞回覆不構成新話題
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1 and flat_[0].source == "confirmation"

    def test_vague_single_reply_zero_interaction_unchanged(self):
        # 單條模糊回應照舊走零交互出口按新消息解析
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("嗯嗯", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1 and flat_[0].source == "rule"
        assert flat_[0].intent == WebIntent.GENERAL_CHAT


# =========================================================================
# 市場詞作為板塊主體 — 聯動/消歧例外與裸數字守衛
# =========================================================================


class TestMarketWordAsSectorSubject:
    """純市場限定詞（港股/美股/a股）是句子的唯一對象解釋時，與大盤/
    指數同口徑進入分支4 兜底對象：默認報數、觀點/動作詞升級板塊分析，
    槽位填市場名（MARKET_SLOT_NAMES）。兩個例外釘死：

    - 聯動個股實體（"港股阿里"）：市場詞是限定詞不是對象——分支3 按
      市場消歧個股，sectors 恆空，不產生板塊任務；
    - 確認輪迴復（"港股"答"哪家阿里巴巴"）：純消歧答案被第五步消費，
      不得重開為美股/港股行情任務（test_pure_market_reply_still_
      consumed 的市場詞版釘子）。

    守衛：裸數字在場（"港股00700"）時對象解釋不唯一——不當板塊報市場
    行情而靜默丟實體，交 LLM 複核。
    """

    def test_bare_market_word_defaults_to_quote(self):
        # "港股怎麼樣"：市場詞是唯一對象 → 行情查詢，槽位"港股"，規則直達
        r = _resolver().resolve_first("港股怎么样", {})
        assert r.source == "rule"
        assert r.intent == WebIntent.QUOTE_LOOKUP
        assert r.sectors == ["港股"]
        assert r.confidence == 0.85 and not r.needs_confirmation

    def test_market_word_with_opinion_word_upgrades_to_sector_analysis(self):
        # "港股怎麼看"：觀點詞在場 → 板塊分析（與"大盤怎麼看"同口徑）
        r = _resolver().resolve_first("港股怎么看", {})
        assert (r.intent, r.sectors, r.source) == (
            WebIntent.SECTOR_ANALYSIS, ["港股"], "rule")

    def test_market_word_with_stock_entity_is_qualifier_not_sector(self):
        # 聯動例外："港股阿里巴巴"——市場詞與個股實體同場，按市場消歧
        # 個股（跨市場歧義組過濾出唯一港股候選），sectors 恆空，不產生
        # 板塊任務
        rs = _resolver().resolve("港股阿里巴巴", {})
        flat_ = _flat(rs)
        assert len(flat_) == 1
        assert flat_[0].intent == WebIntent.STOCK_ANALYSIS
        assert _codes(flat_[0]) == ["HK09988"]
        assert flat_[0].sectors == []

    def test_market_word_with_named_sector_stays_qualifier(self):
        # "美股醫藥板塊"：市場詞與具名板塊同場——板塊槽位只收具名行業，
        # 不追加市場槽（市場詞是限定不是對象）
        r = _resolver().resolve_first("美股医药板块", {})
        assert (r.intent, r.sectors) == (WebIntent.SECTOR_ANALYSIS, ["医药"])

    def test_market_word_reply_in_confirmation_consumed_not_reopened(self):
        # 參與消歧例外："分析阿里巴巴"→確認→答"港股"：回覆被第五步消費
        # 落位 HK09988，不得再生成一條港股行情任務（確認輪裡參與消歧的
        # 市場詞不是板塊主體）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert flat_[0].source == "confirmation"
        assert _codes(flat_[0]) == ["HK09988"]
        assert flat_[0].sectors == [] and not flat_[0].needs_confirmation

    def test_market_word_with_bare_digits_deferred_to_llm(self):
        # 守衛："港股00700看看"——裸數字在場（5 位 HK 短碼不提升），
        # 對象解釋不唯一：不得當港股行情直達而靜默丟掉代碼，低置信交
        # LLM 複核（無 LLM 形態退閒聊）
        r = _resolver().resolve_first("港股00700看看", {})
        assert r.intent == WebIntent.GENERAL_CHAT
        assert r.sectors == []


# =========================================================================
# 確認鏈迴歸：糾錯消費 / 存活閘門 / 構造載荷歸一
# =========================================================================


class TestConfirmationChainRegressions:
    """確認鏈語義迴歸：

    - stock_unresolved 糾錯消費：恰一隻純形實體回覆（fresh 且無
      has_content）結算原任務——原意圖隨任務存活、隨行實體合併保留，
      不從裸消息重新分類；單個確認任務被多個實體命中＝匹配失敗
      （比較/新請求語義，按新話題）；帶自身語義的回覆按新話題解析；
      混鏈已消解兄弟不因未消費的確認鏈連帶銷燬；
    - pending_actions 存活閘門：clear_pending_actions 是確認鏈的撤銷
      協議，清空後陳舊 last_resolutions 投影不構成消費源；
    - 構造載荷歸一：stocks 與 candidates 的 str/dict 載荷同口徑歸一為
      Stock，公開入口（primary_stock_code / 會話簿記）按 .code 契約
      消費。
    """

    # ---- stock_unresolved 糾錯消費 ----

    def test_unresolved_bare_code_correction_restores_task(self):
        # 裸代碼糾錯：確認提示所求形狀（只回正確代碼）結算原任務
        # （source=confirmation），不從裸消息重新分類；"查一下"是取數
        # 動作，原意圖為 quote_lookup（_depth_branch 同口徑裁決）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下SH999999", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("600519", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert flat_[0].source == "confirmation"
        assert flat_[0].intent == WebIntent.QUOTE_LOOKUP
        assert _codes(flat_[0]) == ["600519"]
        assert not flat_[0].needs_confirmation
        apply_resolution_to_session(session, rs2)
        assert session[PENDING_ACTIONS_KEY] == []

    def test_unresolved_correction_preserves_intent_and_entities(self):
        # 原意圖（quote_lookup）與隨行實體（600519）雙保留：糾錯回覆
        # 000858 後按原意圖兩隻一起落位執行
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下600519和SH999999的股价", session)
        assert _flat(rs1)[0].reason == "stock_unresolved"
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("000858", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        t = flat_[0]
        assert (t.source, t.intent) == ("confirmation", WebIntent.QUOTE_LOOKUP)
        assert _codes(t) == ["600519", "000858"]
        assert not t.needs_confirmation

    def test_unresolved_correction_bare_name_still_pure(self):
        # 裸名稱糾錯與裸代碼同過閘：全名解析出 stocks 即純形答案
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下SH999999", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("茅台", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert flat_[0].source == "confirmation"
        assert _codes(flat_[0]) == ["600519"]
        assert not flat_[0].needs_confirmation

    def test_unresolved_correction_expressive_reply_stays_new_topic(self):
        # 帶自身語義的回覆不構成糾錯答案：意圖詞在場 → 按新話題解析
        # （source=rule），糾錯消費只認純形實體回覆
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下SH999999", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("分析600519", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert flat_[0].source == "rule"
        assert flat_[0].intent == WebIntent.STOCK_ANALYSIS
        assert _codes(flat_[0]) == ["600519"]
        assert not any(t.needs_confirmation for t in flat_)

    def test_unresolved_mixed_chain_bare_reply_keeps_resolved_sibling(self):
        # 混鏈全鏈路：阿里歧義先落位（港股），糾錯回覆再結算 SH999999
        # 任務 → 已消解兄弟與糾錯任務一起存活執行（未消費的確認鏈
        # 不連帶銷燬已消解任務）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴，查一下SH999999", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股", session)
        apply_resolution_to_session(session, rs2)
        rs3 = _resolver().resolve("600519", session)
        flat_ = _flat(rs3)
        assert not any(t.needs_confirmation for t in flat_)
        assert [(t.source, _codes(t)) for t in flat_] == [
            ("confirmation", ["HK09988"]),
            ("confirmation", ["600519"]),
        ]

    def test_zero_interaction_expressive_reply_keeps_resolved_sibling(self):
        # 零交互出口：混鏈等待期收到帶意圖詞回覆（不構成任何確認
        # 的答案）→ 仍在等待的確認任務作廢，已消解待執行的兄弟保留
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴，查一下SH999999", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("港股", session)
        apply_resolution_to_session(session, rs2)
        rs3 = _resolver().resolve("分析600519", session)
        flat_ = _flat(rs3)
        assert [(t.source, _codes(t)) for t in flat_] == [
            ("confirmation", ["HK09988"]),
            ("rule", ["600519"]),
        ]
        assert not any(t.needs_confirmation for t in flat_)

    def test_double_unresolved_correction_settles_both(self):
        # 兩個 wrong-code 確認任務 × 單裸碼糾錯：各自結算同一實體——
        # 匹配按"每個任務 × 每個實體"獨立進行，單實體命中多任務是
        # 多組同答的"各自落位"，不是匹配失敗
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下SH999999，再查SH999998", session)
        assert len(_flat(rs1)) == 2
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("600519", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 2
        assert all(t.source == "confirmation" for t in flat_)
        assert all(_codes(t) == ["600519"] for t in flat_)

    def test_unresolved_multi_entity_reply_is_match_failure(self):
        # 恰一隻閘門：多段純實體回覆（600519，000858）對單確認任務是
        # 匹配失敗——比較/新請求語義，不消費，回覆按新話題解析、原鏈
        # 按零交互出口作廢（不得靜默擴張原任務的標的數量）
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析SH999999", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("600519，000858", session)
        flat_ = _flat(rs2)
        assert all(t.source == "rule" for t in flat_)
        assert [_codes(t) for t in flat_] == [["600519"], ["000858"]]
        assert not any(t.needs_confirmation for t in flat_)
        apply_resolution_to_session(session, rs2)
        assert session[PENDING_ACTIONS_KEY] == []

    def test_unresolved_multi_stock_fragment_is_match_failure(self):
        # 單片段並列多股（"000858和300750"，無消息級切口）同樣按匹配
        # 失敗處理：並列多標的是新請求不是糾錯答案
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下600519和SH999999的股价", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("000858和300750", session)
        flat_ = _flat(rs2)
        assert len(flat_) == 1
        assert flat_[0].source == "rule"
        assert _codes(flat_[0]) == ["000858", "300750"]
        assert not flat_[0].needs_confirmation

    # ---- pending_actions 存活閘門 ----

    def test_clear_pending_actions_stops_stale_consumption(self):
        # Agent 失敗收尾清 pending_actions 後舊確認鏈失效：陳舊
        # last_resolutions 不構成消費源，下一條消息按新話題解析
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("分析阿里巴巴", session)
        apply_resolution_to_session(session, rs1)
        clear_pending_actions(session)
        assert session[PENDING_ACTIONS_KEY] == []
        rs2 = _resolver().resolve("港股", session)
        flat_ = _flat(rs2)
        assert all(t.source != "confirmation" for t in flat_)
        # 新話題語義：裸市場詞 → 港股行情查詢（市場槽）
        assert flat_[0].intent == WebIntent.QUOTE_LOOKUP
        assert flat_[0].sectors == ["港股"]
        assert not flat_[0].needs_confirmation

    # ---- 構造載荷歸一 ----

    def test_stocks_dict_payload_normalized_public_entries(self):
        # stocks 傳 dict 載荷：__post_init__ 歸一為 Stock——
        # primary_stock_code 與 apply_resolution_to_session 的 stock-scope
        # 簿記按 .code 契約正常工作
        res = WebIntentResolution(
            WebIntent.QUOTE_LOOKUP, 0.9,
            stocks=[{"code": "600519", "name": "贵州茅台", "market": "a"}])
        assert all(isinstance(s, Stock) for s in res.stocks)
        assert res.primary_stock_code == "600519"
        session: Dict[str, Any] = {}
        apply_resolution_to_session(session, res)
        assert session[RECENT_STOCKS_KEY] == ["600519"]

    def test_stocks_mixed_payload_and_malformed_entries(self):
        # str 代碼 / dict / 混排歸一；空串與缺 code 的 dict 剔除
        # （與 candidates 同口徑）
        res = WebIntentResolution(
            WebIntent.STOCK_ANALYSIS, 0.9,
            stocks=["600519", {"code": "000858"}, "", {"name": "无code"}],
            candidates=["BABA"])
        assert [(s.code, s.name, s.market) for s in res.stocks] == [
            ("600519", "", ""), ("000858", "", "")]
        assert isinstance(res.candidates[0], Stock)
        assert res.candidates[0].code == "BABA"


class TestSubjectDepthBranchRegressions:
    """壞碼/存疑碼主體的深度語義保真：_depth_branch 單點裁決（T1 持倉
    語境 > T2 數據詞 > 默認分析）對確定實體（分支3）、壞碼（分支1）、
    存疑碼（分支7）三類主體形狀同口徑——標的可疑隻影響確認/透傳，
    不改寫請求的深度語義。"""

    def test_bad_code_subjects_keep_quote_and_portfolio_semantics(self):
        # 同句換合法代碼分別是 quote_lookup / portfolio_analysis——
        # 壞碼（確認短路）與存疑碼（透傳實查）不得丟失這些深度信號
        r = _resolver()
        t = r.resolve_first("查一下SH999999的股价")
        assert (t.intent, t.reason) == (
            WebIntent.QUOTE_LOOKUP, "stock_unresolved")
        assert t.unresolved_names == ["SH999999"]
        t = r.resolve_first("看下HK12345股价")
        assert t.intent == WebIntent.QUOTE_LOOKUP
        assert any("12345" in c for c in t.unverified_codes)
        assert not t.needs_confirmation
        t = r.resolve_first("我的SH999999还该拿着吗")
        assert (t.intent, t.reason) == (
            WebIntent.PORTFOLIO_ANALYSIS, "stock_unresolved")

    def test_bad_code_correction_executes_original_depth(self):
        # 糾錯鏈沿原始深度意圖執行：報數請求糾錯後仍是報數，不落成
        # 默認個股分析
        session: Dict[str, Any] = {}
        rs1 = _resolver().resolve("查一下SH999999的股价", session)
        apply_resolution_to_session(session, rs1)
        rs2 = _resolver().resolve("600519", session)
        t = _flat(rs2)[0]
        assert (t.source, t.intent) == ("confirmation", WebIntent.QUOTE_LOOKUP)
        assert _codes(t) == ["600519"]
        assert not t.needs_confirmation


class TestMultiIntentSplitRegressions:
    """LLM 多意圖拆分的實體核算與防幻覺不變量：

    - 越權代碼拒收：規則側有歧義候選時，庫內命中但不在候選組 ∪ 已解
      析實體內的代碼不得無確認執行（與單元素協議同口徑，見
      test_probe_llm_code_outside_groups_rejected）；候選組內回顯不受
      閘門誤傷，元素可直接認領；
    - 規則側指稱不因拆分蒸發：壞碼澄清（unresolved_names）逐元素保
      留（單元素合併同口徑），存疑代碼（unverified_codes）由孤兒核算
      單目標掛回隨行透傳；
    - 深度拆分與逗號展開同構：空主體元素平分規則側歧義組與預掛組，
      一次市場詞回覆同時落位；
    - 具名指數與個股共對象經板塊槽位平權分解為獨立任務。
    """

    def test_multi_intent_out_of_group_code_rejected(self):
        # 規則側阿里巴巴雙候選（歧義待確認），LLM 多意圖數組首元素返回
        # 庫內命中但不在候選組的 600519：越權換標的代碼拒收，歧義候
        # 選以確認形態保留（與單元素協議同口徑）
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_code": "600519"},
            {"intent": "quote_lookup", "confidence": 0.9},
        ]}, ensure_ascii=False))
        flat_ = _flat(_resolver(stub).resolve("阿里巴巴多少钱和走势", {}))
        assert len(stub.calls) == 1, "quote×research 共现触发多意图复核"
        leaking = [t for t in flat_ if "600519" in _codes(t)]
        assert not leaking or all(
            t.needs_confirmation for t in leaking
        ), "候选组外的库内代码（幻觉标的）不得无确认执行"
        assert any(
            {c.code for c in t.candidates} == {"BABA", "HK09988"}
            for t in flat_
        ), "规则侧歧义候选须以确认形态保留（孤儿核算回收）"

    def test_multi_intent_split_keeps_wrong_code_confirmation(self):
        # 規則側識別 SH123456 為確定非法代碼（stock_unresolved 待澄
        # 清），LLM 多元素拆分後即使無人回填 unresolved_names，壞碼澄
        # 清也經逐元素 seed 保留，短路等待用戶重給
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9,
             "stock_code": "000799"},
            {"intent": "stock_analysis", "confidence": 0.9},
        ]}, ensure_ascii=False))
        flat_ = _flat(_resolver(stub).resolve("看看SH123456和酒鬼酒哈", {}))
        assert any(
            t.unresolved_names == ["SH123456"] and t.needs_confirmation
            for t in flat_
        ), "多元素拆分不得丢弃规则侧坏码澄清（stock_unresolved 短路）"

    def test_multi_intent_split_keeps_unverified_code(self):
        # SOFI 是用戶顯式寫出的美股存疑代碼（透傳執行端實查），多元
        # 素拆分後無人認領時由孤兒核算掛回執行類任務隨行透傳，不靜默
        # 丟棄
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "stock_analysis", "confidence": 0.9},
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_code": "000799"},
        ]}, ensure_ascii=False))
        flat_ = _flat(_resolver(stub).resolve("分析SOFI呗和酒鬼酒", {}))
        assert any(
            "SOFI" in c for t in flat_ for c in t.unverified_codes
        ), "多元素拆分不得静默丢弃规则侧存疑代码"

    def test_stock_with_named_index_spawns_index_task(self):
        # 具名指數與個股共對象時經板塊槽位平權分解為獨立任務——與
        # "醫藥板塊和酒鬼酒哪個好"的板塊分解同構；全 token 識別 +
        # 0.85 高置信規則直達，零 LLM 調用（指數槽位與具名板塊同證據
        # 權重，sibling 深度裁決同享 exact 判據，不落低置信確認）
        stub = _StubLLMAdapter(content="{}")
        flat_ = _flat(_resolver(stub).resolve("茅台和上证指数哪个好", {}))
        assert len(stub.calls) == 0, "高置信规则直达，不触发 LLM 复核"
        assert [(t.intent, _codes(t), t.sectors) for t in flat_] == [
            (WebIntent.STOCK_ANALYSIS, ["600519"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["上证"]),
        ], "指数对象不得被个股主体静默丢弃"
        assert all(t.confidence == 0.85 and not t.needs_confirmation
                   for t in flat_)

    def test_named_index_qualifier_spawns_context_task(self):
        # 限定詞形態（與"醫藥板塊的酒鬼酒"同口徑）：指數作個股定語時
        # 同樣生成指數上下文任務——板塊/指數共有的平權分解，寧多一個
        # 上下文任務不靜默丟對象
        flat_ = _flat(_resolver().resolve("创业板的酒鬼酒怎么样"))
        assert [(t.intent, _codes(t), t.sectors) for t in flat_] == [
            (WebIntent.STOCK_ANALYSIS, ["000799"], []),
            (WebIntent.SECTOR_ANALYSIS, [], ["创业板"]),
        ]

    def test_conjunction_depth_split_mirrors_comma_form(self):
        # 「阿里巴巴的股價和走勢」的多意圖拆分與逗號展開形「阿里巴巴
        # 的股價，阿里巴巴的走勢」同構：兩個空主體元素各自繼承規則側
        # 歧義候選與預掛組，一次市場詞回覆同時落位（無 pending 的空主
        # 體確認是死端——回覆無從消費，且會連帶作廢已消解任務）
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9,
             "stock_code": None},
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_code": None},
        ]}, ensure_ascii=False))
        session: Dict[str, Any] = {}
        rs1 = _resolver(stub).resolve("阿里巴巴的股价和走势", session)
        apply_resolution_to_session(session, rs1)
        assert all(
            {c.code for c in t.candidates} == {"BABA", "HK09988"}
            and t.reason == "ambiguous_stock_name"
            for t in _flat(rs1)
        ), "深度拆分的每个空主体元素都应继承规则侧歧义组（逗号形同构）"
        rs2 = _resolver().resolve("港股", session)
        assert [(t.intent, _codes(t), t.needs_confirmation)
                for t in _flat(rs2)] == [
            (WebIntent.QUOTE_LOOKUP, ["HK09988"], False),
            (WebIntent.STOCK_ANALYSIS, ["HK09988"], False),
        ], "一次市场词回复应同时落位两个任务（与逗号形生命周期一致）"

    def test_multi_intent_candidate_echo_claimed(self):
        # 閘門不誤傷合法回顯：LLM 在候選組內做選擇（HK09988）時，多
        # 元素模式下元素槽雖已重置，候選組成員代碼仍可經 claimable 通
        # 道認領——兩個任務各帶標的直接執行，不轉確認
        stub = _StubLLMAdapter(content=json.dumps({"intents": [
            {"intent": "quote_lookup", "confidence": 0.9,
             "stock_code": "HK09988"},
            {"intent": "stock_analysis", "confidence": 0.9,
             "stock_code": "HK09988"},
        ]}, ensure_ascii=False))
        flat_ = _flat(_resolver(stub).resolve("阿里巴巴多少钱和走势", {}))
        assert [(t.intent, _codes(t), t.needs_confirmation)
                for t in flat_] == [
            (WebIntent.QUOTE_LOOKUP, ["HK09988"], False),
            (WebIntent.STOCK_ANALYSIS, ["HK09988"], False),
        ]

    def test_single_element_merge_keeps_rule_unresolved_names(self):
        # 單元素合併同口徑：LLM 未回填 unresolved_names 時，規則側壞
        # 碼名單仍作基底保留（stock_unresolved 短路）；unverified_codes
        # 的掛回見 test_multi_intent_split_keeps_unverified_code
        stub = _StubLLMAdapter(content=json.dumps({
            "intent": "stock_analysis", "confidence": 0.9,
            "stock_code": None}, ensure_ascii=False))
        t = _flat(_resolver(stub).resolve("看看SH123456和酒鬼酒哈", {}))[0]
        assert t.unresolved_names == ["SH123456"], \
            "规则侧坏码名单不因 LLM 未回填而丢失（stock_unresolved 短路保留）"
