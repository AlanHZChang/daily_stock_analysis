# -*- coding: utf-8 -*-
"""
===================================
名稱到代碼解析引擎
===================================

將股票名稱解析為代碼：全局 ``stockDB`` 上的精確匹配 + AkShare 擴充 +
混合匹配（子串/拼音/模糊）。
"""

from __future__ import annotations

import concurrent.futures
import difflib
import json
import logging
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from src.data.stock_mapping import STOCK_NAME_MAP
from src.services.stock_code_utils import is_code_like, normalize_code

logger = logging.getLogger(__name__)

# AkShare 結果緩存：(時間戳, name_to_code 字典)。TTL 過期後作為 stale
# 數據繼續服務（stale-while-revalidate），刷新由後臺線程完成。
_akshare_cache: Optional[tuple[float, Dict[str, str]]] = None
_AKSHARE_CACHE_TTL = 1800  # 30 MIN

# 失敗退避：最近一次拉取失敗的時間戳。不寫負緩存的話，網絡異常期間每次
# 解析都會重打網絡請求，慢速超時直接放大為全量消息的用戶延遲。
# 有 stale 緩存時退避窗口內仍服務 stale（網絡故障期間保持可用），
# 僅冷啟動（無任何緩存）才退化為本地庫。
_akshare_failure_cache: Optional[float] = None
_AKSHARE_FAILURE_TTL = 300  # 5 MIN

# 拉取超時：akshare 對交易所的部分請求無超時（如上交所 GET、北交所
# POST），掛起（非失敗）時拉取線程永不返回——掛起時異常路徑永不觸發、
# 失敗退避永不武裝。拉取經子進程包裝封頂時長後，掛起子進程在超時處被
# terminate/kill、以 TimeoutError 拋出，走常規失敗路徑寫入失敗退避。
_AKSHARE_FETCH_TIMEOUT = 25.0

# 冷啟動等待上限：拉取被子進程封頂在 _AKSHARE_FETCH_TIMEOUT 內，worker
# 在其後有限的清賬步內必然 resolve Future。等待上界從同一常數推導而非
# 獨立魔法數，結構上保證與在途拉取重疊的請求都能等到其結果——曾用獨立
# 常數 8s，實測拉取耗時 6.6~8.2s 與其同分布，冷啟動請求確定性漏解。
# 餘量覆蓋 DataFrame 解析與清賬；落盤/日誌在喚醒之後，不計入。TTL 過期
# 走 stale-while-revalidate 零等待，此值僅影響冷啟動場景。
_AKSHARE_WAIT_COLD_START = _AKSHARE_FETCH_TIMEOUT + 5.0

# 狀態鎖：只保證緩存/退避/在途句柄讀寫的原子性。鎖內唯一的 IO 例外是
# _try_load_disk_cache_locked 的首次懶加載（每進程一次、本地小文件毫秒
# 級）；網絡拉取與落盤都在鎖外的後臺刷新線程內。與 _db_lock 互不嵌套，
# 不構成鎖順序環。
_state_lock = threading.Lock()

# 在途拉取句柄：非 None 表示已有後臺線程在刷新。併發等待者等 Future 的
# 完成信號（成功/失敗都會精確喚醒），而非排隊搶鎖再雙重檢查——等待與
# 拉取耗時解耦，無 25<30 這類常數間隱式契約。
_akshare_inflight: Optional[concurrent.futures.Future] = None

# 磁盤緩存：成功拉取後原子落盤，重啟時懶加載為 stale 數據。股票名稱表
# 變化頻率極低，跨重啟複用把"冷啟動等待"壓縮到僅剩磁盤也無數據的場景。
# 路徑遵循 data/cache 約定（該目錄已 gitignore）。
_AKSHARE_DISK_CACHE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "cache" / "akshare_name_map.json"
)
_akshare_disk_checked = False

# stockDB 讀寫鎖：意圖解析在 asyncio.to_thread 工作線程中併發執行，
# extend_AkShare 的原地合併與迭代 stockDB 的讀路徑不加鎖會觸發
# "dictionary changed size during iteration"。RLock 允許嵌套獲取。
_db_lock = threading.RLock()


def _contains_cjk(text: str) -> bool:
    """當文本包含中日韓(CJK)字符時返回 True。"""
    return any("\u3400" <= ch <= "\u9fff" for ch in text)


def _normalize_stock_name(name: str) -> str:
    """股票名稱的統一歸一：NFKC 寬度歸一（全角字母/數字 → 半角）+ 去除全部
    空白。

    分詞管道對用戶輸入做同樣的 NFKC（web_intent_tokenizer._preprocess_text
    的工作副本），庫內名稱若保留源數據拼寫（AkShare 的 "京東方Ａ" 全角Ａ、
    "五 糧 液" 內嵌空格），窗口/片段與歸一後的輸入永遠不相等——不僅全名
    精確匹配落空，還會被更短的庫內名誤切出錯誤實體（"京東方Ａ" 落空後
    2 字窗口命中 "京东"）。輸入側與庫側必須同源同變換：本地映射初值、
    AkShare 構建與合併、磁盤緩存加載三個入庫口，與全部查詢口共用本函數
    （磁盤緩存裡的歷史未歸一數據同樣在此歸一）。展示名隨之統一為歸一拼寫
    （與 token 層"單一代碼身份"原則一致）。
    """
    return "".join(unicodedata.normalize("NFKC", name).split())


def _is_code_like(s: str) -> bool:
    """共享的“形似代碼”檢查的向後兼容包裝。"""
    return is_code_like(s)


def _normalize_code(raw: str) -> Optional[str]:
    """共享代碼規範化的向後兼容包裝。"""
    return normalize_code(raw)


def _build_reverse_map_no_duplicates(
    code_to_name: Dict[str, str],
) -> Dict[str, str]:
    """
    構建 name -> code 映射。若一個名稱映射到多個代碼（有歧義），則將其排除。
    """
    name_to_codes: Dict[str, Set[str]] = {}
    for code, name in code_to_name.items():
        if not name or not code:
            continue
        name = name.strip()
        if name not in name_to_codes:
            name_to_codes[name] = set()
        name_to_codes[name].add(code)
    # Only include names with exactly one code
    return {name: next(iter(codes)) for name, codes in name_to_codes.items() if len(codes) == 1}


def _build_local_name_indexes(code_to_name: Dict[str, str]) -> Tuple[Dict[str, str], Set[str]]:
    """
    Build cached local lookup structures:
    - unique name -> code
    - ambiguous names that should fail fast
    """
    name_to_codes: Dict[str, Set[str]] = {}
    for code, name in code_to_name.items():
        if not name or not code:
            continue
        normalized_name = _normalize_stock_name(name)
        if not normalized_name:
            continue
        name_to_codes.setdefault(normalized_name, set()).add(code)

    unique_names = {
        name: next(iter(codes))
        for name, codes in name_to_codes.items()
        if len(codes) == 1
    }
    ambiguous_names = {
        name
        for name, codes in name_to_codes.items()
        if len(codes) > 1
    }
    return unique_names, ambiguous_names


_LOCAL_REVERSE_MAP, _LOCAL_AMBIGUOUS_NAMES = _build_local_name_indexes(STOCK_NAME_MAP)


def _akshare_stock_info_worker():
    """子進程內執行：導入 akshare 並拉取全量 A 股代碼表。

    必須保持模塊級函數（spawn 經 pickle 按限定名傳遞）；akshare 及其
    pandas 等重依賴只進子進程，父進程不加載。
    """
    import akshare as ak

    return ak.stock_info_a_code_name()


def _fetch_akshare_df():
    """AkShare 全量拉取的唯一網絡出口（測試接縫）。

    經 data_provider 的子進程超時包裝（spawn）執行：掛起的網絡請求在
    _AKSHARE_FETCH_TIMEOUT 內被殺死，父進程側以 TimeoutError 拋出。
    akshare 內部的 @lru_cache 只存在於子進程，30 分鐘 TTL 過期後的
    刷新在父進程側始終拿到新數據。
    """
    from data_provider.akshare_fetcher import _akshare_call_with_timeout

    return _akshare_call_with_timeout(
        _akshare_stock_info_worker,
        timeout=_AKSHARE_FETCH_TIMEOUT,
        call_name="stock_info_a_code_name",
    )


def _build_name_map_from_df(df) -> Dict[str, str]:
    """把 AkShare 的 code/name DataFrame 轉為去歧義的 name->code 映射。"""
    code_to_name = {}
    for _, row in df.iterrows():
        code = row.get("code")
        name = row.get("name")
        if code is None or name is None:
            continue
        code_str = str(code).strip()
        # Strip .SH/.SZ suffix
        if "." in code_str:
            base, suffix = code_str.rsplit(".", 1)
            if suffix.upper() in ("SH", "SZ", "SS") and base.isdigit():
                code_str = base
        code_to_name[code_str] = _normalize_stock_name(str(name))
    return _build_reverse_map_no_duplicates(code_to_name)


def _try_load_disk_cache_locked() -> None:
    """懶加載磁盤緩存到內存（每進程至多嘗試一次）。調用方必須持有 _state_lock。"""
    global _akshare_cache, _akshare_disk_checked
    if _akshare_disk_checked:
        return
    _akshare_disk_checked = True
    try:
        payload = json.loads(_AKSHARE_DISK_CACHE_PATH.read_text(encoding="utf-8"))
        ts = payload.get("ts")
        raw_map = payload.get("map")
        if isinstance(ts, (int, float)) and isinstance(raw_map, dict):
            # 歷史落盤可能含未歸一名稱（全角拼寫/內嵌空格）：加載即歸一
            name_map = {
                _normalize_stock_name(str(k)): str(v)
                for k, v in raw_map.items()
                if k and v
            }
            if name_map:
                _akshare_cache = (float(ts), name_map)
                logger.info(
                    "[NameResolver] AkShare 磁盤緩存已加載: "
                    f"{len(name_map)} 條, age={time.time() - float(ts):.0f}s"
                )
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.debug(f"[NameResolver] AkShare 磁盤緩存不可用，忽略: {e}")


def _persist_akshare_map(name_map: Dict[str, str]) -> None:
    """原子落盤（每進程唯一 tmp 名 + os.replace）。失敗非致命，僅記日誌。

    tmp 名摻入 PID：web 與 CLI 可能是兩個進程，共用同一 tmp 名會在
    os.replace 前互相覆蓋對方尚未寫完的文件。
    """
    try:
        path = _AKSHARE_DISK_CACHE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
        tmp.write_text(
            json.dumps({"ts": time.time(), "map": name_map}, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except Exception as e:
        logger.debug(f"[NameResolver] AkShare 磁盤緩存寫入失敗（非致命）: {e}")


def _spawn_refresh_locked() -> concurrent.futures.Future:
    """啟動後臺刷新線程並登記在途句柄。調用方必須持有 _state_lock。

    網絡拉取、DataFrame 解析、落盤全部發生在這個 daemon 線程內——請求
    路徑只讀取狀態或等待 Future，永不執行網絡 IO。
    """
    global _akshare_inflight
    fut: concurrent.futures.Future = concurrent.futures.Future()
    # 先登記再啟動：worker 理論上可能在 start() 返回前就完成，其清賬
    # 分支 `is fut` 必須能看到已登記的句柄
    _akshare_inflight = fut

    def _worker():
        global _akshare_cache, _akshare_failure_cache, _akshare_inflight
        result: Optional[Dict[str, str]] = None
        try:
            try:
                df = _fetch_akshare_df()
                if df is not None and not df.empty:
                    # 空數據視同失敗退避：短時間內重試只會得到同樣的空結果
                    result = _build_name_map_from_df(df)
            except Exception as e:
                logger.warning(f"[NameResolver] AkShare fallback failed: {e}")
        finally:
            # 先清賬並喚醒全部等待者，再做日誌/落盤等 best-effort 副作用：
            # 慢日誌 handler 或慢磁盤不得拖住等待者拿結果（曾把落盤排在
            # set_result 之前，慢盤時緩存已就緒、等待者卻超時漏解）。
            # finally 兜底：BaseException 逃逸時句柄/退避/Future 也必然
            # 清賬，不留死句柄（否則之後每個冷啟動請求都白等滿超時）。
            with _state_lock:
                now = time.time()
                if result:
                    _akshare_cache = (now, result)
                    _akshare_failure_cache = None
                else:
                    _akshare_failure_cache = now
                    result = None
                if _akshare_inflight is fut:
                    _akshare_inflight = None
            # 成功/失敗都精確喚醒全部等待者；失敗以 result=None 表達
            fut.set_result(result)
            if result:
                logger.info(
                    f"[NameResolver] AkShare cache loaded: {len(result)} name->code mappings"
                )
                _persist_akshare_map(result)

    try:
        threading.Thread(
            target=_worker, name="akshare-name-refresh", daemon=True
        ).start()
    except RuntimeError as e:
        # 線程啟動失敗（如進程線程數耗盡）：歸還句柄並喚醒等待者
        _akshare_inflight = None
        fut.set_result(None)
        logger.warning(f"[NameResolver] AkShare 刷新線程啟動失敗: {e}")
    return fut


def _get_akshare_name_to_code() -> Optional[Dict[str, str]]:
    """獲取 AkShare name->code：新鮮緩存直讀；過期走 stale-while-revalidate
    （立即返回舊值 + 後臺刷新）；冷啟動限時等待在途 Future；失敗退避。

    請求路徑最壞只阻塞冷啟動等待（_AKSHARE_WAIT_COLD_START）；TTL 過期
    的請求零等待；網絡 IO 全部在後臺刷新線程。
    """
    with _state_lock:
        if _akshare_cache is None:
            _try_load_disk_cache_locked()
        now = time.time()
        if _akshare_cache is not None and (now - _akshare_cache[0]) < _AKSHARE_CACHE_TTL:
            return _akshare_cache[1]
        stale_map = _akshare_cache[1] if _akshare_cache is not None else None
        in_backoff = (
            _akshare_failure_cache is not None
            and (now - _akshare_failure_cache) < _AKSHARE_FAILURE_TTL
        )
        fut = _akshare_inflight
        if fut is None and not in_backoff:
            fut = _spawn_refresh_locked()
    if stale_map is not None:
        # stale-while-revalidate：TTL 的語義就是容忍陳舊，過期瞬間等待
        # 毫無收益；返回舊值，下輪調用命中後臺刷新出的新緩存。
        return stale_map
    if fut is None:
        # 冷啟動且處於失敗退避窗口：本地庫照常服務
        return None
    try:
        result = fut.result(timeout=_AKSHARE_WAIT_COLD_START)
    except concurrent.futures.TimeoutError:
        # 正常情況下不可能到達：拉取被封頂、worker 在 finally 中必然
        # resolve。到達即 worker 違約（如子進程 kill 本身掛死）。
        logger.warning(
            "[NameResolver] 在途 AkShare 拉取超過死線未 resolve"
            f"（{_AKSHARE_WAIT_COLD_START:g}s），本輪退化為本地庫解析"
        )
        return None
    except Exception as e:
        # worker 以 result=None 表達失敗，這裡只可能是 Future 內部異常
        logger.warning(f"[NameResolver] 等待在途 AkShare 拉取異常: {e}")
        return None
    return result


def warmup_akshare_cache() -> None:
    """進程啟動預熱：後臺線程觸發一次解析鏈填充（冪等、非阻塞）。

    命中磁盤緩存則零網絡加載；否則發起後臺單飛拉取。冷啟動等待發生在
    本 daemon 線程內，不阻塞調用方。重複調用共享同一在途句柄，不會
    觸發多次網絡拉取。
    """

    def _warm():
        try:
            _get_akshare_name_to_code()
        except Exception as e:  # noqa: BLE001 - 預熱必須 best-effort
            logger.warning(f"[NameResolver] AkShare 預熱失敗: {e}")

    threading.Thread(target=_warm, name="akshare-warmup", daemon=True).start()


# =========================================================================
# Stock — immutable code/name/market value object
# =========================================================================


@dataclass(frozen=True)
class Stock:
    """股票條目：code / name / market（"a" | "hk" | "us"）。"""

    code: str
    name: str = ""
    market: str = ""


# =========================================================================
# stockDB — 全局 code->name 數據庫，由 AkShare A 股數據擴充
# =========================================================================


stockDB: Dict[str, str] = {
    # 初值即歸一（與輸入側 NFKC 同變換）：源數據的全角拼寫/內嵌空白
    # 不帶入庫內視圖
    code: _normalize_stock_name(name) for code, name in STOCK_NAME_MAP.items()
}

# 已存在代碼被 AkShare 更新為當前官方名稱時，舊名稱作為別名保留，
# 避免證券改名後舊名稱徹底不可解析。
stockAliases: Dict[str, Set[str]] = {}

_MARKET_ORDER: Dict[str, int] = {"a": 0, "hk": 1, "us": 2}

# 已合併的 AkShare 緩存對象（冪等短路：同一份緩存不重複合併）
_akshare_merged: Optional[Dict[str, str]] = None


def extend_AkShare() -> bool:
    """用 AkShare 全量 A 股數據擴充 stockDB（冪等，30 分鐘緩存）。

    Returns:
        True — stockDB 實際併入了新條目或更新了已存在代碼的名稱；
        False — 無需擴展（同一份緩存已合併 / 拉取失敗 / 返回空數據 /
        無任何變化）。
    """
    global _akshare_merged
    akshare_map = _get_akshare_name_to_code()
    if not akshare_map:
        return False
    # 合併段整體持鎖：與讀路徑的 stockDB 迭代串行，且"已合併對象"判定原子。
    # 網絡抓取（上方）保持在鎖外。
    with _db_lock:
        if _akshare_merged is akshare_map:
            return False
        changed = False
        # akshare_map 是 name->code 反向映射，stockDB 是 code->name；名稱
        # 統一歸一（NFKC 寬度 + 去內嵌空白）後比較/寫入，避免與歸一後的
        # 輸入/本地拼寫形成假性改名（製造無謂別名）——磁盤緩存裡的歷史
        # 未歸一數據同樣在此歸一
        for name, code in akshare_map.items():
            compact = _normalize_stock_name(name)
            if not compact:
                continue
            if code not in stockDB:
                stockDB[code] = compact
                changed = True
            elif stockDB[code] != compact:
                # 證券改名：保留舊名稱作為別名，再更新為 AkShare 當前官方名稱。
                stockAliases.setdefault(code, set()).add(stockDB[code])
                stockDB[code] = compact
                changed = True
        _akshare_merged = akshare_map
        if changed:
            # stockDB 值更新或別名變化時 len(stockDB) 可能不變，
            # 必須顯式失效名稱/拼音緩存，否則改名後的新名稱不可見。
            _names_cache[:] = [None, None, None]
            _pinyin_cache[:] = [None, None]
        return changed


# =========================================================================
# 名稱/拼音緩存 —— 以 (database 對象, len) 為鍵：對數據庫的任何插入或
# 刪除都會自動使其失效，無需手動重置。
# =========================================================================


_names_cache: List = [None, None, None]  # [database, len(database), names]
_pinyin_cache: List = [None, None]  # [names, pinyins]


def _database_names(database: Dict[str, str]) -> List[str]:
    """*database* 中去重、保持順序的名稱列表（帶緩存）。

    除了 canonical（規範）名稱，還會包含 stockDB 的舊名稱別名；這樣舊名稱也能參與
    精確、子串、拼音和模糊匹配。
    """
    with _db_lock:
        if _names_cache[0] is database and _names_cache[1] == len(database):
            return _names_cache[2]
        names = list(dict.fromkeys(database.values()))
        if database is stockDB:
            for aliases in stockAliases.values():
                for alias in aliases:
                    if alias not in names:
                        names.append(alias)
        _names_cache[:] = [database, len(database), names]
        return names


def _database_pinyins(
    database: Dict[str, str], names: Optional[List[str]] = None
) -> List[str]:
    """與 *names* 對齊的全拼小寫拼音列表（帶緩存）。

    傳入外層快照時按快照構建，保證與調用方本地 names 同源同序，
    避免併發合併期間兩次取列表導致 zip 錯位配對。
    """
    if names is None:
        names = _database_names(database)
    with _db_lock:
        if _pinyin_cache[0] is not names:
            try:
                from pypinyin import lazy_pinyin

                pinyins = ["".join(lazy_pinyin(name)).lower() for name in names]
            except Exception:
                pinyins = [""] * len(names)
            _pinyin_cache[:] = [names, pinyins]
        return _pinyin_cache[1]


# =========================================================================
# 名稱匹配輔助函數
# =========================================================================


def _exact_names(fragment: str, database: Dict[str, str]) -> List[str]:
    """返回 database 名稱中與 *fragment* 不區分大小寫精確匹配的結果。"""
    fragment_lower = fragment.lower()
    return [name for name in _database_names(database) if name.lower() == fragment_lower]


def _is_single_char_typo(input_name: str, candidate_name: str) -> bool:
    """當兩個名稱僅有一個字符位不同時返回 True。"""
    if not input_name or not candidate_name:
        return False
    if len(input_name) != len(candidate_name):
        return False
    # Keep typo fallback conservative: only for names with enough signal.
    if len(input_name) < 3:
        return False
    diff = sum(1 for a, b in zip(input_name, candidate_name) if a != b)
    return diff == 1


# 拼音子串匹配的最短長度：拼音字母是逐音節的高頻粒子，過短片段（o/k/ai/ma）
# 會命中大量無關名稱的拼音子串，把普通英文輸入誤解析成股票。
_MIN_PINYIN_FRAGMENT_LEN = 5


def _fix_name(fragment: str, database: Dict[str, str]) -> List[str]:
    """通過混合匹配將名稱片段解析為完整股票名稱。

    策略鏈（按順序）：
    1. 精確匹配（不區分大小寫）
    2. 子串匹配（不區分大小寫；片段含 >= 2 個 CJK 字符，如 茅臺 -> 貴州茅臺）
    3. 拼音子串匹配（如 "maotai" ⊂ "guizhoumaotai"）
    4. difflib 模糊匹配（cutoff 0.8，另加 0.7 的保守單字符錯別字回退，
       如 貴州茅苔 -> 貴州茅臺）
    """
    if not fragment:
        return []
    fragment_lower = fragment.lower()
    names = _database_names(database)

    # 1. Exact match
    exact = [name for name in names if name.lower() == fragment_lower]
    if exact:
        return exact

    # 2. Substring match
    if sum(1 for ch in fragment if "\u3400" <= ch <= "\u9fff") >= 2:
        matches = [name for name in names if fragment_lower in name.lower()]
        if matches:
            return matches

    # 3. Pinyin substring match — 僅對純 ASCII 片段生效
    # （設計場景是英文拼音輸入："maotai" ⊂ "guizhoumaotai"）。CJK 片段
    # 轉拼音後粒度失控：實義字 + 助詞（"阿里的" → "alide"）恰好 5 字母
    # 過最短長度閘門，與不相干全名（"alide" ⊂ "zhongdalide" 中大力德）
    # 發生子串碰撞；且 CJK 的合法場景已被其餘三層覆蓋（精確/子串/difflib）
    if _contains_cjk(fragment):
        fragment_pinyin = ""
    else:
        try:
            from pypinyin import lazy_pinyin

            fragment_pinyin = "".join(lazy_pinyin(fragment)).lower()
        except Exception:
            fragment_pinyin = ""
    if len(fragment_pinyin) >= _MIN_PINYIN_FRAGMENT_LEN:
        matches = [
            name
            for name, pinyin in zip(names, _database_pinyins(database, names))
            if fragment_pinyin in pinyin
        ]
        if matches:
            return matches

    # 4. Fuzzy match
    if len(fragment) > 2:
        matches = difflib.get_close_matches(fragment, names, n=5, cutoff=0.8)
        if matches:
            return matches
        typo_matches = difflib.get_close_matches(fragment, names, n=5, cutoff=0.7)
        matches = [m for m in typo_matches if _is_single_char_typo(fragment, m)]
        if matches:
            return matches

    return []


def _infer_code_market(code: str) -> Optional[str]:
    """根據代碼格式推斷市場：6 位數字→"a"，5 位數字→"hk"，字母→"us"。"""
    c = code.strip()
    if c.isdigit():
        return {5: "hk", 6: "a"}.get(len(c))
    return "us" if re.fullmatch(r"[A-Z]{1,5}(\.[A-Z])?", c) else None


def _find_codes_for_name(name: str, database: Dict[str, str]) -> List[Tuple[str, str]]:
    """查找 *database* 中映射到 *name* 的所有 (code, market) 組合。"""
    results: List[Tuple[str, str]] = []
    # 持鎖迭代：與 extend_AkShare 的併發寫串行
    with _db_lock:
        for code, mapped_name in database.items():
            if mapped_name == name or (
                database is stockDB and name in stockAliases.get(code, set())
            ):
                market = _infer_code_market(code)
                if market:
                    results.append((code, market))
    return results


# =========================================================================
# 公開 API
# =========================================================================


def resolver_name_to_code_list(name: str) -> List[Stock]:
    """將股票名稱解析為匹配的 ``Stock`` 條目（最多 5 個）。暫不解析股票代碼。

    1. 對 CJK 輸入，用 AkShare A 股數據擴充 ``stockDB``（冪等，帶失敗退避）；
       非 CJK 輸入完全跳過網絡拉取。
    2. 在 ``stockDB`` 上做精確匹配。
    3. 在擴充後的數據庫上做混合匹配（精確/子串/拼音/模糊）。

    結果按 A 股 → 港股 → 美股 排序。

    示例：
        "阿里巴巴" → [Stock("09988", "阿里巴巴", "hk"), Stock("BABA", "阿里巴巴", "us")]
        "茅台"     → [Stock("600519", "贵州茅台", "a")]
        "你好世界"  → []
    """
    if not name or not isinstance(name, str):
        return []
    # 查詢輸入與入庫同源歸一：源形態（全角拼寫/內嵌空格，如自 AkShare 數據
    # 複製的 "京東方Ａ"/"五 糧 液"）與常規拼寫同樣可解析
    s = _normalize_stock_name(name)
    # 單字符不可能是股票名（最短 2 字），短路避免全名錶掃描
    if len(s) < 2:
        return []

    # A 股名稱全是 CJK —— 非 CJK 輸入無法從網絡擴充獲益，但仍可參與本地
    # 混合（拼音）匹配。
    # 即使是本地精確命中也要先執行 AkShare 擴充：本地已有的同名港股/美股
    # 不能阻止 AkShare 中同名 A 股被併入，否則跨市場候選會不完整。
    if _contains_cjk(s):
        extend_AkShare()

    full_names = _exact_names(s, stockDB)
    if not full_names:
        full_names = _fix_name(s, stockDB)
    if not full_names:
        return []

    stocks: List[Stock] = []
    seen: Set[str] = set()
    for full_name in full_names:
        for code, market in _find_codes_for_name(full_name, stockDB):
            if code not in seen:
                seen.add(code)
                stocks.append(Stock(code=code, name=stockDB.get(code, full_name), market=market))

    stocks.sort(key=lambda r: _MARKET_ORDER.get(r.market, 99))
    return stocks[:5]


def US_stock_code_match(segment: str) -> List[Stock]:
    """匹配美股代碼：1~5 個英文字母的 ticker，僅本地庫存在該代碼時才返回。

    避免把普通英文單詞（hello/open/...）誤判為股票代碼。
    """
    if not isinstance(segment, str) or not segment.isascii() or not segment.isalpha():
        return []
    if not 1 <= len(segment) <= 5:
        return []
    upper = segment.upper()
    name = stockDB.get(upper, "")
    return [Stock(code=upper, name=name, market="us")] if name else []


def lookup_stock_by_code(code: str) -> Optional[Stock]:
    """按規範化代碼查庫，返回完整 (code/name/market) 三元組；查不到返回 None。

    格式合法不等於存在：stockDB 未命中即 None，絕不虛構（LLM 幻覺/過期
    代碼不得直接注入 stocks）。本地庫港股鍵為裸 5 位（"00700"），HK 前綴
    形態（"HK00700"）自動補查去前綴裸鍵。
    """
    c = (code or "").strip().upper()
    if not c:
        return None
    with _db_lock:
        name = stockDB.get(c)
        if not name and c.startswith("HK"):
            name = stockDB.get(c[2:])
        if not name:
            return None
    if c.startswith("HK"):
        market = "hk"
    else:
        market = _infer_code_market(c) or ""
    return Stock(code=c, name=name, market=market)


def is_market_db_complete(market: str) -> bool:
    """該市場名稱庫是否已擴展為全量（庫未命中即可斷定代碼不存在）。

    A 股：AkShare 全量列表已併入 stockDB（extend_AkShare 成功過，
    ``_akshare_merged`` 非空）。港股/美股：本地精選庫，永不視為全量，
    未命中只能存疑交下游判斷。
    """
    return market == "a" and _akshare_merged is not None


def is_known_stock_name(name: str) -> bool:
    """判斷 *name* 是否為 stockDB 中已知的股票全名（含改名別名）。

    只做本地名稱表成員判定，絕不觸發 AkShare 網絡擴展。代碼鍵
    （如 "600519"）不算名稱命中：分詞管道（web_intent_tokenizer）用本
    函數保護"已識別名稱 token"，代碼形文本必須繼續進入代碼提取步驟
    重新標註，而不是被當作名稱跳過。
    """
    if not isinstance(name, str):
        return False
    s = _normalize_stock_name(name)
    if not s:
        return False
    return s in _database_names(stockDB)


def resolve_name_to_code(name: str) -> Optional[str]:
    """
    Resolve stock name to code.

    Strategy (in order):
    1. If input looks like a code (5-6 digits or 1-5 letters), return it normalized.
    2. Local STOCK_NAME_MAP reverse (exclude ambiguous names).
    3. Pinyin match against local names.
    4. AkShare online fallback (A-shares).
    5. Fuzzy match (difflib).
    6. Return None.

    Args:
        name: Stock name or code string.

    Returns:
        Resolved stock code, or None if ambiguous/failed.
    """
    if not name or not isinstance(name, str):
        return None
    s = _normalize_stock_name(name)
    if not s:
        return None

    # 1. Input looks like code
    if _is_code_like(s):
        return _normalize_code(s)

    # 2. Local reverse map (no duplicates)
    local_reverse = _LOCAL_REVERSE_MAP
    if s in local_reverse:
        return local_reverse[s]
    if s in _LOCAL_AMBIGUOUS_NAMES:
        logger.debug(f"[NameResolver] 命中本地歧義名稱，快速返回 None: {s}")
        return None

    # 3. Pinyin match (exact)
    try:
        from pypinyin import lazy_pinyin

        input_pinyin = "".join(lazy_pinyin(s)).lower()
        for local_name, code in local_reverse.items():
            local_pinyin = "".join(lazy_pinyin(local_name)).lower()
            if input_pinyin == local_pinyin:
                return code
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"[NameResolver] Pinyin match failed: {e}")

    # Skip AkShare/fuzzy fallback for non-CJK free text such as random Latin noise.
    # These paths are expensive and only meaningfully help Chinese stock names.
    if not _contains_cjk(s):
        logger.debug(f"[NameResolver] Skip CJK-only fallbacks for non-CJK input: {s}")
        return None

    # 4. AkShare fallback
    akshare_map = _get_akshare_name_to_code()
    if akshare_map and s in akshare_map:
        logger.debug(f"[NameResolver] 命中 AkShare 映射: {s} -> {akshare_map[s]}")
        return akshare_map[s]

    # 5. Fuzzy match (local + akshare, local takes precedence)
    all_name_to_code = dict(local_reverse)
    if akshare_map:
        all_name_to_code.update(akshare_map)
    # Skip fuzzy matching for very short inputs (<=2 chars) to avoid false positives,
    # e.g. '中國' matching arbitrary company names in a pool of 5000+ stocks.
    # Use a higher cutoff (0.8) to reduce mis-hits on longer inputs as well.
    if len(s) > 2:
        names = list(all_name_to_code.keys())
        matches = difflib.get_close_matches(s, names, n=1, cutoff=0.8)
        if matches:
            logger.debug(f"[NameResolver] 命中模糊匹配: input={s}, matched={matches[0]}")
            return all_name_to_code[matches[0]]

        # Conservative fallback for one-character typo in medium/long names.
        # This keeps the strict default threshold while fixing obvious misspellings
        # such as "貴州茅苔" -> "貴州茅臺".
        typo_matches = difflib.get_close_matches(s, names, n=1, cutoff=0.7)
        if typo_matches and _is_single_char_typo(s, typo_matches[0]):
            logger.debug(f"[NameResolver] 命中單字誤寫兜底: input={s}, matched={typo_matches[0]}")
            return all_name_to_code[typo_matches[0]]

    logger.debug(f"[NameResolver] 解析失敗: {s}")
    return None
