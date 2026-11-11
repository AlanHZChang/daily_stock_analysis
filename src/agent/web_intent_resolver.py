# -*- coding: utf-8 -*-
"""
Web Chat 意圖識別層 — 主解析器（Intent Resolver）。

按六步流水線把一條用戶消息解析為**二維任務組列表**（保序、可含確認
短路；外層組=子消息，形狀契約見 ``resolve`` docstring）：
  - ``web_intent_types.py``     — 意圖枚舉、WebIntentResolution、Token、
                                  tag/關鍵詞/正則常量（共享數據字典）；
  - ``web_intent_tokenizer.py`` — 六步分詞管道與實體提取（本層只消費其
                                  產物，絕不重跑全管道）；
  - ``web_intent_resolver.py``  — 本模塊：主流程、規則/LLM/確認消費、
                                  session/SSE 輔助。

== 六步流程（resolve 主鏈，順序固定）==

  第一步 上下文準備與空輸入短路
     繼承股票（request_context.current_stock_code 優先，退
     recent_stocks[0]）；空/非文本/純標點 → 閒聊 0.5 規則直達（帶繼承
     股票，不動 pending——空消息不是確認響應）。

  第二步 全消息分詞（僅此一次）
     ``_preprocess_text`` + ``_identify_stock_codes`` 全局各調用一次，
     之後所有階段只消費這份 tokens，禁止重複冗餘調用。

  第三步 消息級多任務切分 ``_split_sub_messages(tokens, message)``
     輸出 tokens 二維列表（第一維 = 一條子消息的 token 序列），元素
     恆不變——只按序分組，絕不重分詞/改寫 token。兩類切口：消息消費
     型標點（，。！？；）落在相鄰 token 的原文間隙即下刀（token 文本
     大小寫摺疊定位，canonical 改寫的代碼退用數字核）；順序連接詞
     （然後/其次/接著/順便）開頭的 token 前下刀。切口全部落在 token
     邊界，詞內"然后"（"居然後市"= 居然+後市）無從觸發；並列連接詞
     （和/與/跟/及）不切——並列對象屬於同一個任務。

  第四步 逐子消息規則級解析（多意圖任務列表）
     對每條子消息跑"規則階段"（``_classify_rule``），產出【平權】任務
     列表（無主次）：主體判定梯選出主體對象任務（個股/泛市場·指數·純
     市場詞/板塊獨佔/追問繼承/存疑代碼/閒聊——純市場限定詞是唯一對象
     解釋時同大盤口徑進兜底對象，槽位填市場名；與個股實體聯動時是限
     定詞交分支3 消歧），板塊對象與組合語境未被主體消費
     時各自獨立生成任務（板塊任務/組合任務，與主體任務共享實體解析）
     ——組 = 子消息。歧義組/候選/裸數字等信號隨身攜帶。大模型兜底
     【延後不跑】。

  第五步 確認消費（pending confirm_stock 存在時）
     無 ambiguity_group 直接跳過。回覆子消息畫像：fresh＝點名候選外新
     entity；has_content＝候選空間外的自帶語義（意圖類 token／板塊指
     數對象／未識別名／存疑代碼／未識別內容）。保留是默認、丟棄是例
     外：判為純消歧答案的必要條件是子消息的全部內容都落在待確認候選
     空間之內，部分內容充當消歧證據不排斥請求角色。非 fresh 一律參
     與收窄（組 × 子消息 × entity 三重循環，複述組名跳過）；保留為任
     務＝fresh／has_content／矛盾貢獻者。無候選組的 stock_unresolved
     鏈以同口徑判答：恰一隻純形實體回覆（fresh 且無 has_content）結算
     為糾正標的（原意圖與隨行實體保留）；單個確認任務被多個實體命中
     ＝匹配失敗（比較/新請求，按新話題），帶自身語義的回覆按新話題。
     結算（組間獨立）：answers 去重後 0 個 → 未解；>1 個 → 矛盾（用戶
     在同一條回覆裡點名多個候選＝比較/新請求）——該組棄置且貢獻子消
     息整輪判新話題；恰 1 個 →
     消解記入 confirmed。出口：全部 answers 為空 → 未消解確認作廢、
     已消解兄弟隨行，按新
     話題解析；全部消解 → 確認解除就地落位 ＋ 保留任務；存在未解 →
     重建 pending_action（未解組 ＋ confirmed 累積 ＋ resolved_stocks
     隨行）繼續等待。消費出口統一身份選擇式收尾：recovered 組（重建的
     未消解任務／已消解任務／隨行兄弟）一律原樣隨行——它們上輪已收尾，
     重過收尾會對已確認任務重跑 LLM 兜底（二次意見汙染用戶消歧結果）、
     對低置信來源任務二次短路；本輪 kept 組按子消息分組照常過第六步
     收尾（組=子消息不變量跨消費保持，一條子消息至多一次多意圖枚舉），
     確認狀態與日誌當輪浮出。

  第六步 倖存任務收尾 ``_finalize_task()``
     ① 補跑 LLM 兜底：低置信/無信號才觸發，tag 全識別的高置信結果
        （≥0.8）與高置信主體豁免（candidates 不參與觸發判據——歧義
        出口是用戶確認）；失敗退回規則結果（source=llm_failed），
        代碼須過查庫閘門防編造。
     ② 確認判定補齊（``_finalize_confirmation``）：無錨點執行類 → 低
        置信守衛收口；歧義候選非空 → 建 ambiguity_group；無法解析名
        稱 → 等用戶重給；置信度 <0.6 → 低置信。

     確認收口：任一任務待確認 → 整鏈短路（判定權在消費方 any()）。
     不做同意圖摺疊——多標的任務（"阿里的走勢，平安呢"兩個標的）各自
     獨立執行、各自鎖定 stock scope，聚合不改變 Agent 輸出質量。

意圖邊界總綱（三判別測試 + 逐意圖收/推）見 web_intent_types 模塊
docstring；本模塊註釋只保留分支級依據。
"""

from __future__ import annotations

import json
import logging
import math
import threading
import unicodedata
from collections import defaultdict
from dataclasses import asdict, fields, replace
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from src.agent.web_intent_tokenizer import (
    _extract_markets_from_tokens, _identify_stock_codes, _preprocess_text,
)
from src.agent.web_intent_types import (
    A_CODE_FIRST_DIGITS, ALL_WEB_INTENTS, BARE_DIGIT_RE,
    BROAD_MARKET_SLOT_NAME, CONFIRMATION_CONFIDENCE_THRESHOLD,
    COORDINATION_PREFIXES, DECLINE_PATTERN, INTENT_WORD_RE, LAST_INTENT_KEY,
    LAST_RESOLUTIONS_KEY, LLM_CONFIDENCE_CAP, LLM_FENCE_RE, LLM_FOLLOWUP_LABEL,
    LLM_SYSTEM_PROMPT, MARKET_NORMALIZE, MARKET_SLOT_NAMES, Market,
    MAX_RECENT_STOCKS, NUMERIC_UNIT_SUFFIXES, PENDING_ACTIONS_KEY,
    POSSESSIVE_RE, RECENT_STOCKS_KEY, SEQUENCE_CONNECTIVE_RE,
    SUB_MESSAGE_PUNCT_RE, TAG_ACTION_PORTFOLIO,
    TAG_ACTION_QUOTE, TAG_ACTION_QUOTE_FETCH, TAG_ACTION_RESEARCH, TAG_COMPARISON,
    TAG_FOLLOWUP,
    TAG_OPINION, TAG_QUESTION, TAG_REQUEST, TAG_SECTOR, TAG_SECTOR_NAME,
    TAG_SECTOR_N_STOCK, TAG_STOCK_CODE, TAG_STOCK_NAME, TAG_SUBJECT_INDEX,
    TAG_SUBJECT_MARKET_BROAD, TAG_SUBJECT_PORTFOLIO, TAG_SUBJECT_RESEARCH,
    TAG_UNKNOWN_NUMBER, Token, WebIntent, WebIntentResolution,
    _EXECUTING_INTENTS, _MARKET_KEYWORD_MAP, _classify_keyword,
    is_unknown_code_tag, is_wrong_code_tag, normalize_intent_label,
    sector_dedup_key, unknown_code_tag,
)
from src.services.name_to_code_resolver import Stock, lookup_stock_by_code

logger = logging.getLogger("web_intent")

__all__ = [
    "WebIntentResolver", "WebIntentResolution", "WebIntent", "Token", "Stock",
    "Market", "ALL_WEB_INTENTS", "LLM_FOLLOWUP_LABEL",
    "CONFIRMATION_CONFIDENCE_THRESHOLD", "LLM_CONFIDENCE_CAP",
    "MAX_RECENT_STOCKS", "RECENT_STOCKS_KEY", "PENDING_ACTIONS_KEY",
    "LAST_INTENT_KEY", "lookup_stock_by_code", "_preprocess_text",
    "_identify_stock_codes", "_extract_markets_from_tokens", "_dedup_stocks",
    "_disambiguate_by_market", "_merge_llm_result", "_parse_llm_payload",
    "_session_context", "_split_sub_messages", "apply_pending",
    "apply_outcome", "apply_resolution_to_session", "clear_pending_actions",
]


# =========================================================================
# 置信度表 — 按決策路徑賦常量（表達"路徑可靠程度"而非校準概率）
# =========================================================================


_CONFIDENCE_EXPLICIT_CODE = 0.9     # 顯式代碼（含交易所標註形態）：代碼即標的
_CONFIDENCE_KEYWORD_STRONG = 0.85   # 意圖關鍵詞與實體共現（"分析茅臺"）
_CONFIDENCE_BARE_NAME = 0.8         # 裸唯一名稱（"茅臺"）／存疑代碼主體
_CONFIDENCE_CONTEXT_INHERIT = 0.75  # 上下文繼承（追問/LLM followup 偽標籤）
_CONFIDENCE_FALLBACK = 0.5          # 規則無可靠結論：必須 LLM 兜底或確認
_CONFIDENCE_LLM_EXEMPT = 0.8        # tag 全識別 + 該置信度以上：規則視野與判定雙完備，免 LLM 複核
_CONFIDENCE_CONFIRMATION = 0.9      # 確認消費輪：用戶已顯式選定標的

# 規則分類查看的"意圖標籤"集合：出現即構成意圖信號。filler/time/market
# 等輔助標籤不單獨構成意圖（market 只提供範圍與消歧）
_INTENT_TAGS = frozenset({
    TAG_REQUEST, TAG_SUBJECT_RESEARCH, TAG_ACTION_RESEARCH,
    TAG_QUESTION, TAG_OPINION, TAG_COMPARISON,
    TAG_SUBJECT_PORTFOLIO, TAG_ACTION_PORTFOLIO, TAG_ACTION_QUOTE,
    TAG_ACTION_QUOTE_FETCH, TAG_SUBJECT_MARKET_BROAD, TAG_SUBJECT_INDEX,
    TAG_FOLLOWUP,
})

# T2 強分析信號（"給觀點"側）：歸因/評價/比較/預測。與數據詞共現時獲勝
_STRONG_RESEARCH_TAGS = frozenset({
    TAG_SUBJECT_RESEARCH, TAG_ACTION_RESEARCH, TAG_OPINION, TAG_COMPARISON,
})

# T2 數據點信號（"報數據"側）。與泛動作詞（request）共現時獲勝，與強分析詞共現時讓位
_QUOTE_TAGS = frozenset({TAG_ACTION_QUOTE, TAG_ACTION_QUOTE_FETCH})

# 報數信號雙 tag：action_quote（數據對象詞）＋ action_quote_fetch（取數
# 動詞）——詞形區分在上游詞池完成，下游只讀 tag（T2 深度裁決兩者同權，
# multi_intent_hint 只認數據對象側）

# T1 個性化信號：持倉/自選股主題與操作
_PORTFOLIO_TAGS = frozenset({TAG_SUBJECT_PORTFOLIO, TAG_ACTION_PORTFOLIO})

# 確認輪的候選空間外錨點：這些 tag 出現說明回覆子消息攜帶候選空間
# 之外的內容——分析/比較/提問請求，或板塊/指數對象（板塊裸提是對象
# 承載的請求，無動詞形態）。保留是
# 默認：任一錨點在場，子消息保留為新任務走完整第六步收尾，⑤② 只丟棄
# 全部內容都落在待確認候選空間內的純答案片段（單消費點：_reply_profile）
_COMPETING_TAGS = frozenset({
    TAG_REQUEST, TAG_SUBJECT_RESEARCH, TAG_ACTION_RESEARCH,
    TAG_ACTION_QUOTE, TAG_ACTION_QUOTE_FETCH, TAG_FOLLOWUP, TAG_COMPARISON,
    TAG_QUESTION,
    TAG_OPINION, TAG_SUBJECT_PORTFOLIO, TAG_ACTION_PORTFOLIO,
    TAG_SUBJECT_MARKET_BROAD, TAG_SUBJECT_INDEX,
    TAG_SECTOR, TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK,
})

# 歧義組候選數上限：超過視為泛詞噪聲丟棄（"中國"命中中國平安/中石化/
# 中國聯通等整族前綴 5 候選——跨市場同名歧義至多 3 候選 a/hk/us，
# 合法歧義不受影響）
_AMBIGUOUS_MAX_CANDIDATES = 3

# 並列殘留防線的錨點：空段以連接詞開頭且緊鄰前 token 是標的類
# （"茅臺|和西藏建工"）→ 剝離連接詞後的文本是並列名稱候選，交確認輪補正
# （連接詞前綴表 COORDINATION_PREFIXES 定義於 web_intent_types）
_COORDINATION_ANCHOR_TAGS = frozenset({
    TAG_STOCK_NAME, TAG_STOCK_CODE, TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK,
})

# 非全量庫市場的存疑代碼 tag（未命中 ≠ 非法，透傳執行端實查）
_UNVERIFIED_MARKET_TAGS = frozenset({
    unknown_code_tag("hk"), unknown_code_tag("us"),
})

# 鏈式主體線程的狀態形態：上一子消息主體任務的三種
# 主體形態——確定標的集合 / 板塊槽位 / 待消歧歧義組（名稱+候選隨行）。
# 追問片段（_classify_rule 分支6）據此繼承：多標的整體繼承 stocks、
# 板塊前序繼承 sectors、歧義前序繼承候選組（與主體任務共待同一次消歧）；
# 單標的前序走 inherited_stock_code 通道（#1619 語義）
_ChainSubject = Tuple[List[Stock], List[str], List[Tuple[str, List[Stock]]]]


# =========================================================================
# 共享輔助 — Stock 載荷 / 去重 / 枚舉安全（各步通用）
# =========================================================================


def _dedup_stocks(stocks: Iterable[Stock]) -> List[Stock]:
    """按 (code, market) 去重保序（首個出現者勝出）。"""
    firsts: Dict[Tuple[str, str], Stock] = {}
    for s in stocks:
        firsts.setdefault((s.code, s.market), s)
    return list(firsts.values())

def _stock_payload(stock: Stock) -> Dict[str, Any]:
    """Stock → SSE/會話可序列化 dict（json 兼容形態）。"""
    return {"code": stock.code, "name": stock.name, "market": stock.market}

def _stock_from_payload(entry: Any) -> Optional[Stock]:
    """會話/LLM 載荷條目（dict 或 Stock）→ Stock；形狀異常（缺 code 的
    dict / 其它類型）返回 None。"""
    if isinstance(entry, Stock):
        return entry
    if isinstance(entry, dict) and entry.get("code"):
        return Stock(code=entry.get("code", ""), name=entry.get("name", ""),
                     market=entry.get("market", ""))
    return None

def _payload_stocks(entries: Any) -> List[Stock]:
    """載荷列表 → Stock 列表（逐條過 ``_stock_from_payload``，異常剔除）。"""
    return [s for s in map(_stock_from_payload, entries or []) if s]

def _group_payload(
    name: str, candidates: List[Stock], intent: str, source_request: str,
) -> Dict[str, Any]:
    """歧義組的可序列化投影（預掛/重建/兜底建組三處共用的構造點）。"""
    return {
        "name": name,
        "candidates": [_stock_payload(c) for c in candidates],
        "intent": intent,
        "source_request": source_request,
    }


def _group_codes(g: Dict[str, Any]) -> set:
    """歧義組載荷的候選代碼集合（dict 候選缺 code 記 None，集合運算自然忽略）。"""
    return {c.get("code") for c in g.get("candidates", [])
            if isinstance(c, dict)}


def _prehung_groups(
    ambiguous: List[Tuple[str, List[Stock]]],
    candidates: List[Stock],
    intent: str,
    source_request: str,
) -> Optional[Dict[str, Any]]:
    """歧義未消解時預掛的組級 pending_action（不置確認——第六步職責）。
    只收錄仍處歧義的組（候選已被市場詞消解的組隨之剔除），與 candidates
    保持同一擴張收縮視圖；無候選返回 None。"""
    if not candidates:
        return None
    cand_codes = {c.code for c in candidates}
    return {
        "action": "confirm_stock",
        "intent": intent,
        "groups": [
            _group_payload(name, group, intent, source_request)
            for name, group in ambiguous
            if any(c.code in cand_codes for c in group)
        ],
    }

def _safe_web_intent(label: str) -> WebIntent:
    """pending 中的意圖標籤 → 枚舉；形狀異常（bogus）回退 stock_analysis。"""
    try:
        return WebIntent(label)
    except ValueError:
        return WebIntent.STOCK_ANALYSIS


# =========================================================================
# 第一步 — 上下文準備：會話歸一 + 決策日誌（空輸入短路在 resolve 內）
# =========================================================================


def _session_context(source: Any) -> Dict[str, Any]:
    """任意會話形態（dict / 帶 .context 的對象 / 其他）→ 可讀 dict。
    純歸一化無副作用：LLM 兜底的會話上下文由 resolve 經 context 形參
    顯式傳遞，不經模塊級全局通道。"""
    if isinstance(source, dict):
        return source
    ctx = getattr(source, "context", None)
    return ctx if isinstance(ctx, dict) else {}


def _log_resolution(path: str, resolution: WebIntentResolution) -> None:
    """每次意圖決策一行 info 日誌（SSE 鏈路排障的主線索）。"""
    logger.info(
        "[WebIntent] resolved via %s: intent=%s confidence=%.2f source=%s "
        "reason=%s codes=%s inherited=%s confirm=%s",
        path,
        resolution.intent.value,
        resolution.confidence,
        resolution.source,
        resolution.reason or "-",
        ",".join(s.code for s in resolution.stocks) or "-",
        resolution.inherited_stock_code or "-",
        resolution.needs_confirmation,
    )


# =========================================================================
# 第三步 — 消息級多任務切分（tokens 二維；元素恆不變，僅按序分組）
# =========================================================================

def _split_sub_messages(
    tokens: Union[str, List[Token]],
    message: Optional[str] = None,
) -> List[List[Token]]:
    """消息級多任務切分（第三步，切口規則與不變量見模塊 docstring）：
    全局 tokens → 子消息 tokens 二維列表，元素恆不變，只按序分組。
    單參數形態（傳文本）為獨立入口：內部自跑全管道。
    """
    if message is None or isinstance(tokens, str):
        message = tokens if isinstance(tokens, str) else (message or "")
        tokens = _identify_stock_codes(_preprocess_text(message)[1])
    token_list: List[Token] = list(tokens)  # type: ignore[arg-type]
    if not token_list:
        return [token_list]
    low = unicodedata.normalize("NFKC", message or "").lower()
    subs: List[List[Token]] = [[]]
    pos = 0
    for t in token_list:
        needle = t.text.lower()
        start = low.find(needle, pos) if needle else -1
        step = len(needle)
        if start < 0:  # canonical 改寫代碼：數字核回退（hk00700 / 00700.HK）
            needle = "".join(ch for ch in t.text if ch.isdigit())
            step = len(needle)
            start = low.find(needle, pos) if needle else -1
        cut = (start >= 0
               and bool(SUB_MESSAGE_PUNCT_RE.search(low[pos:start])))
        if start >= 0:
            pos = start + step
        cut = cut or bool(SEQUENCE_CONNECTIVE_RE.match(t.text))
        if cut:
            subs.append([])
        subs[-1].append(t)
    subs = [s for s in subs if s]
    return subs if subs else [token_list]


# =========================================================================
# 第四步 — 規則級解析：tokens 進、規則態 resolution 出（LLM 延後不跑）
# =========================================================================


def _token_facts(sub_tokens: List[Token]) -> Dict[str, Any]:
    """一次遍歷收集判定樹所需的全部事實：標籤集合、確定實體、歧義組、
    代碼辨認失敗/存疑、裸數字（含四重閘門提升）、板塊槽位（含泛稱回溯
    與 combo）、指數、市場詞。
    """
    tags: set = set()
    stocks: List[Stock] = []
    seen: set = set()

    def _add_stock(s: Stock) -> None:
        key = (s.code, s.market)
        if key not in seen:
            seen.add(key)
            stocks.append(s)

    ambiguous: List[Tuple[str, List[Stock]]] = []
    wrong_codes: List[str] = []
    unknown_codes: List[str] = []
    unverified_codes: List[str] = []
    unknown_numbers: List[str] = []
    unresolved_names: List[str] = []
    index_subjects: List[str] = []
    named_sectors: List[Tuple[int, str]] = []
    sector_names: set = set()
    sector_combo = False
    code_entity = False

    def _add_sector(index: int, name: str) -> None:
        if name and name not in sector_names:
            sector_names.add(name)
            named_sectors.append((index, name))

    for i, t in enumerate(sub_tokens):
        if t.tag:
            tags.add(t.tag)
        # 泛稱後綴回溯——詞池外行業名提取（"固態電池概念"）：無語義/
        # 代碼形 token 緊鄰板塊泛稱 → 入板塊槽並置 combo；該 token 不
        # 按壞代碼/存疑代碼記賬
        nxt = sub_tokens[i + 1] if i + 1 < len(sub_tokens) else None
        label = t.text.strip()
        backtracked = bool(
            nxt is not None and nxt.tag == TAG_SECTOR
            and len(label) >= 2 and not label.isdigit()
            and (not t.tag or is_unknown_code_tag(t.tag)
                 or is_wrong_code_tag(t.tag)))
        if backtracked:
            _add_sector(i, label)
            sector_combo = True
        if t.tag == TAG_STOCK_CODE:
            code_entity = True
            for s in t.stocks or ():
                _add_stock(s)
        elif t.tag == TAG_STOCK_NAME:
            group = list(t.stocks or ())
            if len(group) == 1:
                _add_stock(group[0])
            elif group and len(group) <= _AMBIGUOUS_MAX_CANDIDATES:
                ambiguous.append((t.text, group))
        elif is_wrong_code_tag(t.tag) and not backtracked:
            wrong_codes.append(t.text)
        elif is_unknown_code_tag(t.tag) and not backtracked:
            if t.tag in _UNVERIFIED_MARKET_TAGS:
                unverified_codes.append(t.text)
            else:
                unknown_codes.append(t.text)
        elif t.tag == TAG_UNKNOWN_NUMBER:
            unknown_numbers.append(t.text)
            # 量詞閘門只攔無語義標籤的量詞 token（萬元/點/年/股…）；
            # 已打標籤的詞是語義成分不是量詞——"股價"（action_quote）首字
            # 撞量詞"股"不得誤傷代碼提升
            has_unit = (nxt is not None and not nxt.tag
                        and nxt.text[:1] in NUMERIC_UNIT_SUFFIXES)
            # 裸數字四重閘門提升：6 位 + 首碼白名單 + 非量詞後綴 + 查庫命中
            digits = t.text
            if (not has_unit and len(digits) == 6
                    and (digits[0] in A_CODE_FIRST_DIGITS
                         or digits.startswith("92"))):
                stock = lookup_stock_by_code(digits)
                if stock is not None:
                    code_entity = True
                    _add_stock(stock)
        elif (not t.tag and i > 0
                and sub_tokens[i - 1].tag in _COORDINATION_ANCHOR_TAGS):
            name = next(
                (t.text[len(p):].strip()
                 for p in COORDINATION_PREFIXES if t.text.startswith(p)), "")
            if (len(name) >= 2 and not name.isdigit()
                    and name not in unresolved_names):
                unresolved_names.append(name)
        # 具名指數與具名板塊同入板塊槽（"上證"）：未被主體消費的對象獨
        # 立成任務（_tasks 平權分解），不因與個股/壞碼等主體共存而靜默
        # 丟棄；tag 保持 SUBJECT_INDEX 不變，分支4 的路由與置信不受影響
        if t.tag in (TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK, TAG_SUBJECT_INDEX):
            _add_sector(i, t.text)
            if nxt is not None and nxt.tag == TAG_SECTOR:
                sector_combo = True
        if t.tag == TAG_SUBJECT_INDEX and t.text not in index_subjects:
            index_subjects.append(t.text)

    return {
        "tags": tags, "stocks": stocks, "ambiguous": ambiguous,
        "wrong_codes": wrong_codes, "unknown_codes": unknown_codes,
        "unverified_codes": unverified_codes, "unknown_numbers": unknown_numbers,
        "unresolved_names": unresolved_names, "index_subjects": index_subjects,
        "sectors": [n for _i, n in sorted(named_sectors)],
        "sector_combo": sector_combo, "code_entity": code_entity,
        "markets": _extract_markets_from_tokens(sub_tokens),
        "has_entity": bool(stocks or ambiguous),
    }


def _disambiguate_by_market(
    candidates: List[Stock], markets: List[Any]
) -> Tuple[Optional[List[Stock]], List[Stock]]:
    """市場詞消歧：候選按市場過濾後恰剩一隻 → 採信；零隻（矛盾）或
    多隻 → None（保守保留全量候選交確認/LLM）。展示列表恆為全量候選。"""
    if not markets:
        return None, candidates
    market_values = {m.value if hasattr(m, "value") else str(m) for m in markets}
    hits = [c for c in candidates if c.market in market_values]
    if len(hits) == 1:
        return hits, candidates
    return None, candidates


def _sector_branch(
    f: Dict[str, Any], sub_tokens: List[Token],
) -> Tuple[WebIntent, float]:
    """板塊類任務的深度小梯子（主體判定分支5 與板塊對象任務同口徑）：
    數據詞且無強分析詞 → 行情查詢；其餘板塊分析（精確池命中或相鄰
    組合 0.85，雙解未消 0.5）。"""
    if (_QUOTE_TAGS & f["tags"]) and not (_STRONG_RESEARCH_TAGS & f["tags"]):
        return WebIntent.QUOTE_LOOKUP, _CONFIDENCE_KEYWORD_STRONG
    # 指數槽位與具名板塊同證據權重："指數"後綴是 market_broad 非 sector
    # 泛稱，combo 判據覆蓋不到，須顯式計入 exact 判據
    exact_sector = any(t.tag in (TAG_SECTOR_NAME, TAG_SUBJECT_INDEX)
                       for t in sub_tokens)
    confidence = (_CONFIDENCE_KEYWORD_STRONG
                  if (f["sector_combo"] or exact_sector) else _CONFIDENCE_FALLBACK)
    return WebIntent.SECTOR_ANALYSIS, confidence


def _depth_branch(tags: set, text: str) -> WebIntent:
    """個股主體的 T1/T2 深度裁決（主體判定分支 1/3/7 單點共用）：
    T1 持倉操作詞指向個股＝組合語境下的個股評估，持倉主題＋第一人稱
    領屬＋無強分析詞（"我的茅臺倉位重不重"）同——強分析詞在場則是
    答案人人相同的研究維度；T2 強分析詞 > 數據詞 > 泛動作詞，裸個股
    默認分析。壞碼/存疑碼主體同享此梯：標的可疑隻影響確認/透傳，
    不改寫請求的深度語義。"""
    if (TAG_ACTION_PORTFOLIO in tags
            or (TAG_SUBJECT_PORTFOLIO in tags
                and POSSESSIVE_RE.search(text)
                and not (_STRONG_RESEARCH_TAGS & tags))):
        return WebIntent.PORTFOLIO_ANALYSIS
    if not (_STRONG_RESEARCH_TAGS & tags) and (_QUOTE_TAGS & tags):
        return WebIntent.QUOTE_LOOKUP
    return WebIntent.STOCK_ANALYSIS


def _classify_rule(
    sub_tokens: List[Token],
    last_intent: str = "",
    inherited_stock_code: str = "",
    prev_subject: Optional[_ChainSubject] = None,
) -> List[WebIntentResolution]:
    """規則優先的意圖判定（第四步：tokens 進、平權任務列表出；整體契約
    見模塊 docstring）。

    主體判定梯產出首個任務，裁決序固定：wrong code 確認 → T1 個性化
    （無個股指稱）→ T3 個股 [T1 組合語境 / T2 深度：強分析詞 > 數據詞 >
    泛動作詞 > 默認分析] → 泛市場指數 [兜底對象：默認報數，觀點/動作詞
    升級板塊] → 板塊 → 追問繼承 → 存疑代碼 → 無信號閒聊（邊界總綱見
    web_intent_types）。板塊對象/組合語境未被主體消費時各自獨立生成平權
    任務（板塊任務不攜帶 stocks——板塊語義排斥個股實體；組合任務與主體
    任務共享實體解析，"分析茅臺的持倉"無領屬不生成，是機構持倉研究
    維度）。prev_subject 是鏈式主體線程狀態源（上一子消息主體任務的
    (stocks, sectors, ambiguous) 三形態，首片段 None）——追問繼承（分支6）
    據此繼承前序主體狀態。
    """
    f = _token_facts(sub_tokens)
    text = "".join(t.text for t in sub_tokens)
    tokens_payload = [t.text for t in sub_tokens]
    # 視野完備性：任一空 tag 殘段（詞池外口語/刷屏 unknown_token）即
    # False，與置信度聯合構成第六步 LLM 兜底的豁免判據
    all_tagged = all(t.tag for t in sub_tokens)

    def _task(
        intent: WebIntent, confidence: float, multi_hint: bool,
        source: str = "rule",
        ambiguous: Optional[List[Tuple[str, List[Stock]]]] = None,
        **extra: Any,
    ) -> WebIntentResolution:
        """平權任務公共構造器：子消息級共享上下文（文本/tokens/繼承碼/
        視野完備性）單點裝配；歧義未消解時預掛組級 pending_action（不置
        確認——第六步職責）。組來源默認取本子消息事實，追問繼承任務
        顯式攜帶前序片段的歧義組。"""
        res = WebIntentResolution(
            intent=intent, confidence=confidence, source=source,
            inherited_stock_code=inherited_stock_code,
            tokens=tokens_payload, source_request=text,
            all_tags_recognized=all_tagged,
            multi_intent_hint=multi_hint, **extra)
        res.pending_action = _prehung_groups(
            f["ambiguous"] if ambiguous is None else ambiguous,
            res.candidates, res.intent.value, text)
        return res

    def _tasks(verdict: WebIntentResolution) -> List[WebIntentResolution]:
        """主體任務 ＋ 未被主體消費的並存對象任務（板塊/組合語境）。"""
        tasks = [verdict]
        if f["sectors"] and not verdict.sectors:
            sector_intent, sector_conf = _sector_branch(f, sub_tokens)
            tasks.append(_task(
                sector_intent, sector_conf, verdict.multi_intent_hint,
                sectors=list(f["sectors"])))
        if (TAG_SUBJECT_PORTFOLIO in f["tags"]
                and POSSESSIVE_RE.search(text)
                and verdict.intent != WebIntent.PORTFOLIO_ANALYSIS):
            tasks.append(_task(
                WebIntent.PORTFOLIO_ANALYSIS, _CONFIDENCE_KEYWORD_STRONG,
                verdict.multi_intent_hint,
                stocks=list(verdict.stocks), candidates=list(verdict.candidates)))
        return tasks

    tags = f["tags"]
    # multi_intent_hint＝"單任務表達不完"的自首：數據對象級 quote 詞與強
    # 分析/組合詞同場（純取數動詞"看下…走勢"不算）、組合泛指×顯式動作
    # 詞（主體顯式如"持倉的茅臺股價"不觸發）、個股代碼×板塊對象——
    # resolution 只有一個 intent 字段，這類並存交 LLM 多意圖複核拆分
    # （多標的單任務由 stocks[] 原生承載，不算自首）
    quote_obj = TAG_ACTION_QUOTE in tags
    action_cls = (_INTENT_TAGS - _PORTFOLIO_TAGS - {
        TAG_QUESTION, TAG_FOLLOWUP, TAG_SUBJECT_MARKET_BROAD,
        TAG_SUBJECT_INDEX})
    multi_hint = bool(
        (quote_obj and ((_STRONG_RESEARCH_TAGS & tags) or (_PORTFOLIO_TAGS & tags)))
        or ((not f["has_entity"]) and (_PORTFOLIO_TAGS & tags)
            and (action_cls & tags))
        or (TAG_SECTOR in tags and bool(
            f["code_entity"] or f["unverified_codes"] or f["unknown_codes"]))
    )
    markets = f["markets"]
    market_value = markets[0].value if len(markets) == 1 else None

    # 1) 確定不存在的代碼：直接以確認收尾，不走 LLM（LLM 也無法憑空造股）；
    #    深度語義照常過 _depth_branch——標的可疑隻影響確認，不改寫請求意圖
    if f["wrong_codes"] and not f["has_entity"]:
        return _tasks(_task(
            _depth_branch(tags, text), _CONFIDENCE_EXPLICIT_CODE, multi_hint,
            unresolved_names=list(f["wrong_codes"])))

    # 2) T1 個性化（無個股指稱）：整體組合語境，深度測試不介入
    #    （sectors 槽位由各執行類分支統一投影補掛）
    if _PORTFOLIO_TAGS & tags and not f["has_entity"]:
        return _tasks(_task(
            WebIntent.PORTFOLIO_ANALYSIS, _CONFIDENCE_KEYWORD_STRONG,
            multi_hint))

    # 3) T3 對象=個股：T1 定組合語境，T2 定深度
    if f["has_entity"]:
        confidence = (_CONFIDENCE_EXPLICIT_CODE if f["code_entity"]
                      else _CONFIDENCE_KEYWORD_STRONG if tags & _INTENT_TAGS
                      else _CONFIDENCE_BARE_NAME)

        stocks = list(f["stocks"])
        candidates: List[Stock] = []
        for _name, group in f["ambiguous"]:
            picked, display = _disambiguate_by_market(group, markets)
            if picked:
                stocks.extend(picked)
            else:
                candidates = _dedup_stocks(candidates + display)
        # T1/T2 深度裁決走 _depth_branch（判據註釋見該函數，與壞碼/存
        # 疑碼主體同口徑）；板塊/ETF 對象同句時由 _tasks 再分解
        return _tasks(_task(
            _depth_branch(tags, text), confidence, multi_hint,
            stocks=stocks, candidates=candidates,
            unresolved_names=[*f["wrong_codes"], *f["unresolved_names"]],
            unverified_codes=list(f["unverified_codes"])))

    # 4) 泛市場/指數/純市場詞：兜底對象——僅當市場詞是句子的唯一對象
    #    解釋時直達（具名板塊/存疑代碼在場時"行情"是語境而非對象；與
    #    個股實體聯動時是市場限定詞而非對象——"港股阿里"由分支3按市場
    #    消歧消費；裸數字在場（"港股00700"）時對象解釋不唯一，交 LLM
    #    複核，絕不當板塊報市場行情而靜默丟實體）；sectors 統一槽位用
    #    指數名原文，純泛市場用市場名（"大盤"），純市場限定詞用市場
    #    槽（"港股"）；觀點/動作詞升級板塊分析，默認報數
    _has_specific_subject = (
        f["unverified_codes"] or f["unknown_codes"]
        or bool({TAG_SECTOR, TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK} & tags)
    )
    _market_only_subject = bool(markets) and not f["unknown_numbers"]
    if ((TAG_SUBJECT_MARKET_BROAD in tags or TAG_SUBJECT_INDEX in tags
         or _market_only_subject)
            and not _has_specific_subject):
        broad_sectors = (list(f["index_subjects"]) if f["index_subjects"]
                         else [MARKET_SLOT_NAMES.get(market_value or "",
                                                      BROAD_MARKET_SLOT_NAME)])
        branch = (WebIntent.SECTOR_ANALYSIS
                  if (_STRONG_RESEARCH_TAGS & tags) or (TAG_REQUEST in tags)
                  else WebIntent.QUOTE_LOOKUP)
        return _tasks(_task(branch, _CONFIDENCE_KEYWORD_STRONG, multi_hint,
                            sectors=broad_sectors))

    # 5) 板塊/行業：數據詞報數，其餘板塊分析（``_sector_branch`` 同口徑）。
    #    行業名精確命中詞池或"行業名+泛稱"相鄰組合消除雙解 → 0.85；僅回
    #    溯提取的詞外語與行業兼股票名（"機器人"）雙解未消 → 0.5 交 LLM。
    #    unverified 只隨分析路徑攜帶（報數路徑不透傳存疑代碼）
    if not f["has_entity"] and bool(
            {TAG_SECTOR, TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK} & tags):
        intent, confidence = _sector_branch(f, sub_tokens)
        extra = ({"unverified_codes": list(f["unverified_codes"])}
                 if intent is WebIntent.SECTOR_ANALYSIS
                 and f["unverified_codes"] else {})
        return _tasks(_task(intent, confidence, multi_hint,
                            sectors=list(f["sectors"]), **extra))

    # 6) 追問繼承：無新股票 +（followup 詞或無主體意圖句——主題缺失默認
    #    主體為"它"；要求動作類意圖詞在場，純疑問碎片不繼承）+ 上輪執行
    #    類意圖。守衛：消息含"未消化"信號（空 tag 段/存疑代碼/裸數字）時
    #    不得繼承——門控對動作詞類不偏待，否則"現在能買09932嗎"類消息被
    #    繼承吸收、用戶顯式指稱的標的被靜默丟棄；被攔截的消息交 LLM 複核
    #    或存疑代碼透傳分支（寧可不做，不可做錯）
    unresolved_subject = (
        any(not t.tag for t in sub_tokens)
        or bool(f["unknown_numbers"]) or bool(f["unknown_codes"])
        or bool(f["unverified_codes"])
    )
    subjectless_intent = bool((_INTENT_TAGS - {TAG_QUESTION}) & tags)
    if ((TAG_FOLLOWUP in tags or subjectless_intent)
            and last_intent in ALL_WEB_INTENTS
            and WebIntent(last_intent) in _EXECUTING_INTENTS
            and not unresolved_subject):
        # 前序主體狀態繼承：多標的（比較）整體繼承 stocks、板塊前序繼承
        # sectors、歧義前序繼承候選組（組結構隨行，與主體任務共待同一次
        # 消歧，一次答覆各自落位）；單標的前序走 inherited_stock_code 通道
        # （#1619 語義）——三形態覆蓋主體全部在場形態，追問
        # 片段絕不以無錨點執行類任務放行（觸發無標的 Agent 工作流）
        inherit_stocks, inherit_sectors, inherit_ambiguous = [], [], []
        if prev_subject is not None:
            prev_stocks, prev_sectors, prev_ambiguous = prev_subject
            if len(prev_stocks) >= 2:
                inherit_stocks = list(prev_stocks)
            elif prev_sectors:
                inherit_sectors = list(prev_sectors)
            elif prev_ambiguous:
                inherit_ambiguous = [(n, list(g)) for n, g in prev_ambiguous]
        return _tasks(_task(
            WebIntent(last_intent), _CONFIDENCE_CONTEXT_INHERIT, multi_hint,
            source="context", sectors=inherit_sectors,
            stocks=inherit_stocks,
            candidates=_dedup_stocks(
                [c for _n, group in inherit_ambiguous for c in group]),
            ambiguous=inherit_ambiguous or None))

    # 7) 存疑代碼主體：hk/us 非全量庫未命中無法判定合法與否——用戶顯式
    #    寫出代碼即強指稱，高置信放行透傳實查（深度語義照常過
    #    _depth_branch）；與泛市場語境共存時對象無法判定（"板塊"tag 已
    #    隨 DFS 失敗陪葬）——低置信交 LLM 裁定
    if f["unverified_codes"]:
        broad_ctx = (TAG_SUBJECT_MARKET_BROAD in tags
                     or TAG_SUBJECT_INDEX in tags)
        return _tasks(_task(
            _depth_branch(tags, text),
            _CONFIDENCE_FALLBACK if broad_ctx else _CONFIDENCE_BARE_NAME,
            multi_hint,
            unverified_codes=list(f["unverified_codes"])))
    if f["unknown_codes"]:
        return _tasks(_task(
            _depth_branch(tags, text), _CONFIDENCE_FALLBACK, multi_hint,
            unverified_codes=list(f["unknown_codes"])))

    # 8) 無信號：閒聊兜底（低置信觸發 LLM 複核；非執行類不確認）
    return _tasks(_task(WebIntent.GENERAL_CHAT, _CONFIDENCE_FALLBACK, multi_hint))


# =========================================================================
# 第五步 — 確認消費：上輪確認任務 × 本輪規則態任務 → 就地消歧合併（二維進出）
# =========================================================================


def _pending_confirming_tasks(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """pending_actions 會話鍵 → 確認任務投影：確認存活的唯一權威
    （resolve 的消費閘門）＋ last_resolutions 缺失時的兼容載荷，包裝為
    last_resolution 元素形態供消費鏈無感讀取。"""
    pending_list = context.get(PENDING_ACTIONS_KEY)
    pending = next(
        (item for item in (pending_list if isinstance(pending_list, list) else [])
         if isinstance(item, dict) and item.get("action") == "confirm_stock"),
        None,
    )
    if pending is None:
        return []
    return [{
        "intent": str(pending.get("intent") or "stock_analysis"),
        "confidence": _CONFIDENCE_CONFIRMATION,
        "source": "confirmation",
        "needs_confirmation": True,
        "pending_action": pending,
        "source_request": str(pending.get("original_request") or ""),
    }]


def _canonical_digit_code(raw: str) -> str:
    """裸數字 → 規範代碼形態：5 位純數字補 HK 前綴（與 tokenizer
    ``_canonical_stock_code`` 同口徑）；非純數字形態（如 "GOOGL"）原樣
    返回，不誤加前綴。"""
    digits = raw.strip()
    if len(digits) == 5 and digits.isdigit():
        return f"HK{digits}"
    return digits


def _normalize_pending_groups(
    pending: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Stock]]:
    """pending → (有效歧義組列表, 組內全部候選)。兼容 groups 組式與頂層
    平鋪（name/candidates 直接掛 pending 頂層）兩類形狀；候選逐條過
    ``_payload_stocks``（Stock 對象透傳）。形狀異常（非 dict／無候選）
    返回空列表——會話投影可能攜帶畸形 pending_action，解析器不得被擊穿。"""
    if not isinstance(pending, dict):
        return [], []
    groups: List[Dict[str, Any]] = [
        {
            "name": str(g.get("name") or ""),
            "candidates": cands,
            "intent": str(g.get("intent") or ""),
            "source_request": str(g.get("source_request") or ""),
        }
        for g in pending.get("groups") or [] if isinstance(g, dict)
        and (cands := _payload_stocks(g.get("candidates")))
    ]
    if not groups and (flat := _payload_stocks(pending.get("candidates"))):
        groups = [{
            "name": str(pending.get("name") or ""),
            "candidates": flat,
            "intent": "",
            "source_request": str(pending.get("original_request") or ""),
        }]
    return groups, [s for g in groups for s in g["candidates"]]


def _sub_names_group(group: Dict[str, Any], sub_text: str) -> bool:
    """子消息是否點名該組主體（組名或任一候選名出現在文中，子串口徑）。"""
    name = group.get("name") or ""
    return bool(name) and name in sub_text or any(
        c.name and c.name in sub_text for c in group["candidates"])


def _narrow_group_entities(
    group: Dict[str, Any],
    resolution: WebIntentResolution,
    all_groups: Optional[List[Dict[str, Any]]] = None,
) -> List[Stock]:
    """一個歧義組 × 一條子消息的收窄。證據通道（獨立產出，重複指向
    同一候選由結算去重）：市場詞收窄到唯一 > 候選名全等 > 候選名唯一
    子串 > 確定實體命中候選 > 裸數字短碼；複述組名與多命中不構成證據。
    返回本組收窄到的候選列表（可空）。
    """
    cands: List[Stock] = group["candidates"]
    out: List[Stock] = []
    group_name = group.get("name") or ""
    sub_text = resolution.source_request or "".join(resolution.tokens)
    # 市場詞從文本詞池恢復（resolution.tokens 只存文本無 tag）
    low = sub_text.lower()
    markets = [mkt for mkt, kws in _MARKET_KEYWORD_MAP.items()
               if any(kw.lower() in low for kw in kws)]

    # 市場詞：候選按市場過濾後恰剩一隻（可同時收窄多組）。多組場景的
    # 作用域：子消息點名了它組主體時，被點名組候選覆蓋的市場詞已綁定
    # 該組、不作用於本組（按名指向的市場詞串擾他組會造成錯誤消解或
    # 矛盾棄置）；點名組不覆蓋的市場詞保留全局證據
    if markets:
        market_values = {m.value for m in markets}
        if all_groups and not _sub_names_group(group, sub_text):
            market_values -= {
                c.market for g in all_groups
                if g is not group and _sub_names_group(g, sub_text)
                for c in g["candidates"]
            }
        filtered = [c for c in cands if c.market in market_values]
        if len(filtered) == 1:
            out.append(filtered[0])

    stripped = sub_text.strip()
    # 候選名全等（整條子消息就是一個候選全名）
    out += [c for c in cands
            if c.name and c.name == stripped and stripped != group_name]
    # 候選名唯一子串（"阿里巴巴港股"裡的"阿里巴巴"命中全部同組候選 ≠ 證據）
    sub_hits = [c for c in cands
                if c.name and c.name in sub_text and stripped != group_name]
    if len(sub_hits) == 1:
        out.append(sub_hits[0])

    # 確定實體命中候選（"平安銀行"解析為 000001 且在組內）＋ 裸數字短碼
    # （"09988" → HK09988，掃描 4-6 位數字段）：按代碼等值直查（同碼取首個）
    by_code: Dict[str, Stock] = {}
    for c in cands:
        by_code.setdefault(c.code, c)
    out += [by_code[s.code] for s in resolution.stocks if s.code in by_code]
    out += [by_code[code]
            for code in map(_canonical_digit_code,
                            set(BARE_DIGIT_RE.findall(sub_text)))
            if code in by_code]
    return out


def _reply_profile(
    resolution: WebIntentResolution, universe: set,
) -> Tuple[bool, bool]:
    """消歧回覆子消息畫像（契約見模塊 docstring 第五步）。

    - ``fresh``＝點名候選外實體（不參與收窄，整輪判新話題）：確定實體
      或歧義候選的代碼不在待確認候選全集（``universe``）——候選空間
      內的實體提及（複述組名/點名候選）是答案空間回聲，不構成保留理由；
    - ``has_content``＝候選空間外的自帶語義：未識別名/存疑代碼、板塊/
      指數對象、意圖詞（token 級 tag 查表，clean+extend 全池）、未讀
      內容（all_tags_recognized=False——保留後 LLM 視野軸兜底才可達）。
    兩者皆 False＝純消歧片段（市場詞/候選名/裸數字/複述組名），已被
    ① 消費，不構成任務。
    """
    fresh = any(e.code not in universe
                for e in (*resolution.stocks, *resolution.candidates))
    has_content = bool(
        resolution.unresolved_names or resolution.unverified_codes
        or not resolution.all_tags_recognized
        or any(_classify_keyword(tok) in _COMPETING_TAGS
               for tok in resolution.tokens))
    return fresh, has_content


def _iter_tasks(tasks: Any):
    """任務集合 → 任務迭代器（一律二維契約下的兼容展平：二維組列表 /
    一維任務列表 / 單個 resolution 對象 / dict 與對象混合形態）。"""
    if isinstance(tasks, (list, tuple)):
        if tasks and isinstance(tasks[0], (list, tuple)):
            yield from (r for group in tasks for r in group)
        else:
            yield from tasks
    elif tasks is not None:
        yield tasks


def _as_task_groups(tasks: Any) -> List[List[Any]]:
    """任務集合 → 二維組列表：二維原樣返回；一維非空列表整體視為單組
    （保持上輪組序，區別於逐元素成組）；空/非列表 → []（調用方兜底）。"""
    if isinstance(tasks, list) and tasks:
        return tasks if isinstance(tasks[0], list) else [tasks]
    return []


def _has_pending_action(task: Any) -> bool:
    """任務是否攜帶可消費的確認動作（needs_confirmation 且有 pending；
    low_confidence 確認無 pending 不算）。兼容對象與 asdict dict 投影。"""
    if isinstance(task, dict):
        return bool(task.get("needs_confirmation") and task.get("pending_action"))
    return bool(getattr(task, "needs_confirmation", False)
                and getattr(task, "pending_action", None))


def _is_pending_action(resolutions: Any) -> bool:
    """二維任務列表中是否存在待確認動作（判定權在消費方 any()；兼容
    一維/對象/dict 混合形態）。"""
    return any(_has_pending_action(r) for r in _iter_tasks(resolutions))


def _recover_resolution(payload: Dict[str, Any]) -> WebIntentResolution:
    """last_resolution 會話投影（asdict dict）→ WebIntentResolution：
    按 dataclass 字段反射取值（缺鍵落字段默認），僅 intent 與 Stock
    列表字段顯式轉換——字段增刪無需同步本函數。"""
    stock_lists = {"stocks", "candidates"}
    kwargs: Dict[str, Any] = {}
    for f in fields(WebIntentResolution):
        raw = payload.get(f.name)
        if f.name == "intent":
            # 兼容 str / str-Enum（asdict 投影保留枚舉實例，str() 會得到
            # "WebIntent.X" 形態——直接按值構造，不自作 str 包裝）
            kwargs[f.name] = (raw if isinstance(raw, WebIntent)
                              else _safe_web_intent(raw or "stock_analysis"))
        elif f.name in stock_lists:
            kwargs[f.name] = _payload_stocks(raw)
        elif isinstance(raw, list):
            kwargs[f.name] = list(raw)
        elif raw is not None:
            kwargs[f.name] = raw
    return WebIntentResolution(**kwargs)


def _session_chain_subject(context: Dict[str, Any]) -> Optional[_ChainSubject]:
    """上一已執行輪落點主體的會話種子（跨輪追問的繼承源）。落點＝最後
    一個執行類組的組首（與 apply_outcome 的 last_intent 同規則——意圖
    與主體錨點出自同一任務）；短路輪不作種子；無可繼承主體（stocks/
    sectors 皆空）返回 None，錨點退 recent_stocks 通道。"""
    groups = [
        [_recover_resolution(r) if isinstance(r, dict) else r for r in g]
        for g in _as_task_groups(context.get(LAST_RESOLUTIONS_KEY)) if g
    ]
    if not groups or any(t.needs_confirmation for g in groups for t in g):
        return None
    landing = next((g[0] for g in reversed(groups)
                    if g[0].intent in _EXECUTING_INTENTS), None)
    if landing is None:
        return None
    subject = (list(landing.stocks), list(landing.sectors), [])
    return subject if subject[0] or subject[1] else None


def _consume_confirmations(
    last_resolution: List[List[Any]],
    reply_groups: List[List[WebIntentResolution]],
) -> List[List[WebIntentResolution]]:
    """第五步（三步契約與結算規則見模塊 docstring）：上輪確認任務 × 本輪
    規則態任務 → 證據驅動結算，二維進出、嚴格就地。

        last_resolution  = "分析茅臺和阿里"        （上輪短路任務，整鏈未執行）
        reply_groups     = "港股，分析醫藥板塊"      （聚合項 + 新任務）
        返回              ≈ "分析茅臺和阿里(港股)，分析醫藥板塊"

        特殊出口：拒絕詞（逐子消息錨定、全部片段為完整拒絕形）→ [閒聊]
        （上輪整鏈作廢）；全部確認任務零交互（純模糊回應）→ 丟棄仍在
        等待的確認任務、已消解兄弟隨行 ＋ 本輪任務原樣（新話題，二維
        組結構保持）；stock_unresolved 鏈（無候選組）恰一隻純形實體回覆
        按糾正標的結算原任務（intent 不從回覆重推；單任務被多實體命中
        ＝匹配失敗，按新話題）。
    """
    # 輸入歸一：二維組列表，dict 投影恢復為對象（字段完整：tokens 等）
    recovered = [[_recover_resolution(r) if isinstance(r, dict) else r
                  for r in g] for g in _as_task_groups(last_resolution)]
    reply_groups = _as_task_groups(reply_groups)
    reply_tasks = [t for g in reply_groups for t in g]
    confirmings = [t for g in recovered for t in g if _has_pending_action(t)]
    if not confirmings:
        return recovered
    all_candidate_codes = {
        s.code for task in confirmings
        for g in _normalize_pending_groups(task.pending_action)[0]
        for s in g["candidates"]
    }
    # 拒絕判定逐子消息錨定匹配（整串拼接丟分隔符會把"算了，不分析
    # 了"拼成用戶從未說過的"算了不分析了"）：全部片段都是完整拒絕
    # 詞形才取消——"算了，再看看茅臺"類拒絕詞＋內容仍按新話題解析
    texts = [(r.source_request or "".join(r.tokens)).strip()
             for r in reply_tasks]
    if texts and all(DECLINE_PATTERN.match(t) for t in texts):
        logger.info("confirm_stock declined by user")
        return [[WebIntentResolution(
            intent=WebIntent.GENERAL_CHAT, source="confirmation",
            confidence=_CONFIDENCE_CONFIRMATION)]]

    # 回覆子消息畫像：非 fresh 一律參與收窄；是否保留為任務由此畫像＋
    # ① 的矛盾事實共同決定
    profiles = [_reply_profile(res, all_candidate_codes)
                for res in reply_tasks]

    # ---- ① 對 last_resolution 消歧聚合（逐確認任務，就地落位）----
    interacted = False
    voided_tasks: List[WebIntentResolution] = []
    contradiction_sources: set = set()  # 矛盾組貢獻子消息（比較/新請求重開）
    correction_sources: set = set()  # 已被糾錯消費的回覆子消息（不保留為新任務）
    for task in confirmings:
        pending = task.pending_action
        groups, _all = _normalize_pending_groups(pending)
        if not groups:
            # stock_unresolved 糾錯鏈：pending 無候選組，判答口徑與歧義
            # 收窄同哲學——子消息全部內容就是候選空間外的實體指稱
            # （fresh 且無 has_content）才算答案；帶自身語義（意圖詞/
            # 板塊/疑問）的回覆按新話題走原路徑。非 dict 的畸形 pending
            # 按形狀異常跳過（不得擊穿消費鏈）
            if (not isinstance(pending, dict)
                    or not pending.get("unresolved_names")):
                continue
            pure = [si for si, (res, (fr, hc)) in
                    enumerate(zip(reply_tasks, profiles))
                    if fr and not hc and res.stocks]
            # 恰一隻才算糾正答案（每個確認任務 × 每個實體互相匹配）：
            # 單個任務被多個實體命中＝匹配失敗——多實體並列是比較/新
            # 請求語義（與歧義組 ">1＝矛盾棄置" 同裁決），不消費；0 只
            # 純片段同交零交互出口按新話題處理
            corrected = _dedup_stocks(
                s for si in pure for s in reply_tasks[si].stocks)
            if len(corrected) != 1:
                continue
            # 結算與"全部組落定"同口徑：原意圖隨任務對象存活（不從回覆
            # 重推）、隨行實體合併保留、確認產物蓋戳
            task.stocks = _dedup_stocks(task.stocks + corrected)
            task.candidates = []
            task.needs_confirmation = False
            task.reason = ""
            task.unresolved_names = []
            task.pending_action = None
            task.source = "confirmation"
            task.confidence = max(task.confidence, _CONFIDENCE_CONFIRMATION)
            correction_sources.update(pure)
            interacted = True
            continue
        answers: Dict[int, List[Stock]] = defaultdict(list)
        sources: Dict[int, List[int]] = defaultdict(list)
        for gi, group in enumerate(groups):
            for si, (fresh, _has_content) in enumerate(profiles):
                if not fresh and (hits := _narrow_group_entities(
                        group, reply_tasks[si], groups)):
                    answers[gi].extend(hits)
                    sources[gi].append(si)

        resolved: List[Stock] = []
        unresolved_groups: List[Dict[str, Any]] = []
        dropped_groups: List[int] = []
        for gi, group in enumerate(groups):
            uniq = _dedup_stocks(answers[gi])
            if len(uniq) == 1:
                resolved.append(uniq[0])
            elif len(uniq) > 1:
                dropped_groups.append(gi)  # 矛盾棄置：該組退出等待
            else:
                unresolved_groups.append(group)

        if not resolved and not dropped_groups:
            continue  # 零交互：該確認任務原樣保留
        interacted = True
        # 矛盾＝同一條回覆點名多個候選＝比較/新請求：貢獻子消息整輪判新話題
        contradiction_sources.update(
            si for gi in dropped_groups for si in sources[gi])
        # 組全部矛盾棄置且無消解/隨行實體：請求整體作廢——用戶已在同一
        # 條回覆裡給出新語義，空殼執行任務不產出
        voided = (bool(dropped_groups) and not unresolved_groups
                  and not resolved and not task.stocks)

        # 消解就地落位：原 stocks + 消解 + resolved_stocks 隨行實體合併，去重保序
        carried = _payload_stocks(pending.get("resolved_stocks"))
        task.stocks = _dedup_stocks(task.stocks + resolved + carried)

        if unresolved_groups:
            # 歧義聚合不完全：未解組 + confirmed 累積隨 pending_action 更新
            base_intent = str(pending.get("intent") or task.intent.value)
            confirmed = [c for c in pending.get("confirmed", [])
                         if isinstance(c, dict)]
            if resolved:
                confirmed.append({
                    "intent": base_intent,
                    "name": str(pending.get("name") or ""),
                    "stocks": [_stock_payload(s) for s in resolved],
                })
            task.pending_action = {
                "action": "confirm_stock",
                "intent": base_intent,
                "groups": [
                    _group_payload(
                        g.get("name", ""), g["candidates"],
                        g.get("intent") or base_intent,
                        g.get("source_request", ""))
                    for g in unresolved_groups
                ],
                "confirmed": confirmed,
                "original_request": str(pending.get("original_request") or ""),
                # 已落位實體隨行（下輪消費合併回 stocks，多輪鏈不丟）
                "resolved_stocks": [_stock_payload(s) for s in task.stocks],
            }
        else:
            # 全部組落定：確認狀態解除，任務就位為普通執行任務。
            # unresolved_names 一併清空——用戶已通過標的交互給出主體，
            # 壞代碼澄清輪結構上不可滿足，保留只會把已消解標的重新短路
            task.candidates = []
            task.needs_confirmation = False
            task.reason = ""
            task.unresolved_names = []
            task.pending_action = None
            # 確認產物蓋戳：用戶顯式選定標的是終局裁決，置信度抬升到
            # 確認檔（來源路徑的低置信標籤不保留）
            task.source = "confirmation"
            task.confidence = max(task.confidence, _CONFIDENCE_CONFIRMATION)
            logger.info("confirm_stock resolved: %d group(s)", len(resolved))

        if voided:
            voided_tasks.append(task)

    if not interacted:
        # 全部確認任務零收窄：純模糊回應。仍在等待的確認任務按"跑題即
        # 作廢"丟棄；已消解待執行的兄弟任務保留（混鏈不因未消費的確認
        # 鏈連帶銷燬）；本輪任務原樣隨行（新話題，組結構保持）
        survivors = [g for g in (
            [t for t in g if not t.needs_confirmation] for g in recovered) if g]
        return survivors + reply_groups

    # ---- ② 丟棄本輪的純消歧元素（fresh／自帶語義／矛盾貢獻者保留）----
    # 按子消息分組保留——"組=子消息"不變量保持，第六步的組級 LLM 枚舉
    # 據此維持一條子消息至多一次；已被糾錯消費的純答案片段一併排除
    # （答案不雙跑）
    keep_flags = [((fresh or has_content) and si not in correction_sources)
                  or si in contradiction_sources
                  for si, (fresh, has_content) in enumerate(profiles)]
    kept: List[List[WebIntentResolution]] = []
    cursor = 0
    for group in reply_groups:
        members = [res for res, keep in zip(group, keep_flags[cursor:]) if keep]
        cursor += len(group)
        if members:
            kept.append(members)

    # ---- ③ 一個列表合併：上輪（消歧後就位、作廢殼剔除）＋ 本輪保留 ----
    survivors = [g for g in (
        [t for t in g if t not in voided_tasks] for g in recovered) if g]
    return survivors + kept


# =========================================================================
# 第六步 — 倖存任務收尾：LLM 兜底 → 確認判定
# =========================================================================


def _extract_json_object(text: str) -> Optional[str]:
    """從 LLM 噪聲輸出中提取第一個完整 JSON 對象：深度計數 + 字符串狀態
    機，正確處理嵌套與字符串內花括號，不誤並 JSON 之後的解釋文字。"""
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if escaped:  # 轉義字符無條件跳過（escaped 只在字符串內置位）
            escaped = False
        elif in_string:
            if ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _normalize_llm_item(item: Any) -> Optional[Dict[str, Any]]:
    """多意圖數組單項 → 規範化載荷（與單對象形態同構）：intent 規範化
    校驗、market 歸一、sectors/unresolved_names 清洗。非法項 None。"""
    if not isinstance(item, dict):
        return None
    intent = normalize_intent_label(item.get("intent"))
    if intent is None or (intent != LLM_FOLLOWUP_LABEL
                          and intent not in ALL_WEB_INTENTS):
        return None
    item = dict(item)
    item["intent"] = intent
    raw_market = item.get("market")
    if isinstance(raw_market, str):
        item["market"] = MARKET_NORMALIZE.get(raw_market.strip().lower())
    elif not isinstance(raw_market, Market):
        item["market"] = None
    for list_field in ("sectors", "unresolved_names"):
        raw_list = item.get(list_field)
        if isinstance(raw_list, list):
            stripped_iter = (s.strip() for s in raw_list if isinstance(s, str))
            item[list_field] = [s for s in dict.fromkeys(stripped_iter) if s]
        else:
            item[list_field] = []
    return item


def _parse_llm_payload(content: str) -> Optional[Dict[str, Any]]:
    """從 LLM 文本回復解析 JSON 載荷；非 JSON/缺字段/非法 intent 返回 None
    （寧缺毋濫）。容錯：首尾空白/BOM、code fence、JSON 前後噪聲（深度
    計數提取）；``intents`` 數組優先（非法項丟棄，全非法回退單對象形態）。
    """
    cleaned = (content or "").strip().lstrip("\ufeff")
    if not cleaned:
        return None
    if "```" in cleaned:
        cleaned = LLM_FENCE_RE.sub("", cleaned).strip()
    result: Any = None
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        fragment = _extract_json_object(cleaned)
        if fragment is None:
            return None
        try:
            result = json.loads(fragment)
        except json.JSONDecodeError:
            return None
    if not isinstance(result, dict):
        return None
    raw_items = result.get("intents")
    if isinstance(raw_items, list):
        items = [i for i in map(_normalize_llm_item, raw_items) if i]
        if items:
            result["intents"] = items
            return result
        # 數組全非法：彈掉殘鍵再回退單對象形態判定（下游只見規範化
        # 數組或不見該鍵，原始非法數組絕不流入多模式合併）
        result.pop("intents", None)
    # 單對象形態與數組元素共用同一規範化（_normalize_llm_item 是唯一
    # 規範化點，兩條協議路徑字段契約同構）
    item = _normalize_llm_item(result)
    if item is None:
        return None
    result.update(item)
    return result


def _drop_resolved_group(
    candidates: List[Stock], picked: List[Stock],
    pending: Optional[Dict[str, Any]],
) -> List[Stock]:
    """組感知候選收斂：剔除被選中代碼所屬歧義組的候選，兄弟組保留
    （整清會讓未消解組靜默丟失）；無預掛組結構退化為整清。"""
    groups = [g for g in (pending or {}).get("groups") or []
              if isinstance(g, dict)]
    if not groups:
        return []
    picked_codes = {c.code for c in picked}
    drop = set(picked_codes)
    for g in groups:
        g_codes = _group_codes(g)
        if g_codes & picked_codes:
            drop |= g_codes
    return [c for c in candidates if c.code not in drop]


def _merge_llm_result(
    rule_resolution: WebIntentResolution,
    payload: Dict[str, Any],
    context: Dict[str, Any],
    rule_view: Optional[WebIntentResolution] = None,
) -> WebIntentResolution:
    """LLM 載荷 → WebIntentResolution：校驗、壓置信度（≤ LLM_CONFIDENCE_CAP）、
    防幻覺合併。followup 偽標籤轉繼承上輪意圖（非執行類降閒聊）；stock_code
    三道閘門（∈ 歧義候選 → 查庫命中 → 未命中按市場分流：hk/us 透傳實查、
    a 股記 unresolved 交確認）；規則側硬信號（實體/板塊）保留，LLM 板塊名/
    未解名以"原文出現"為閘門合入（板塊無註冊表，防編造）。

    ``rule_resolution`` 是元素基座：多元素拆分時其實體槽已被重置，只承擔
    鏈路字段與繼承；``rule_view`` 是防幻覺閘門的事實源（原始規則任務，
    缺省回退基座，單元素路徑兩者為同一對象）。閘門判據必須讀原始規則
    任務——重置後的基座在多元素模式下恆判"無歧義候選"，越權換標的的
    代碼會被採信執行，故多元素調用方必須顯式回傳。
    """
    try:
        raw_confidence = float(payload.get("confidence", 0.5))
        # NaN/Inf 按缺失處理（0.5）：NaN 會擊穿一切比較，把"毫無把握"偽裝
        # 成"高於確認閾值"跳過確認
        if not math.isfinite(raw_confidence):
            raise ValueError
    except (TypeError, ValueError):
        raw_confidence = 0.5
    confidence = min(LLM_CONFIDENCE_CAP, max(0.0, raw_confidence))

    if payload["intent"] == LLM_FOLLOWUP_LABEL:
        last_intent = context.get(LAST_INTENT_KEY, "")
        intent = (WebIntent(last_intent)
                  if last_intent in ALL_WEB_INTENTS
                  and WebIntent(last_intent) in _EXECUTING_INTENTS
                  else WebIntent.GENERAL_CHAT)
    else:
        intent = WebIntent(payload["intent"])

    # LLM 市場推斷僅用於打破跨市場同名歧義（規則市場詞已在分類層完成
    # 同樣的消歧，能走到這裡的歧義說明規則側無市場證據）
    market = payload.get("market")
    if not isinstance(market, Market):
        market = None

    stocks = list(rule_resolution.stocks)
    sectors = list(rule_resolution.sectors)
    candidates = list(rule_resolution.candidates)
    # 跨組採信閘門的判據是"規則側是否有歧義候選"——輸入屬性，不隨消
    # 費收縮：市場消解/組內選中清空列表後，後續庫內命中的組外代碼仍
    # 須拒收（幻覺標的不因先前的合法消解而洗白）；判據讀 rule_view，
    # 不隨多元素基座重置失明
    gate = rule_view if rule_view is not None else rule_resolution
    had_candidates = bool(gate.candidates)
    # 元素可經庫內通道認領的規則側代碼：恆含確定實體（消息中真實出現
    # 的標的，元素認領是分發不是幻覺）；多元素模式（基座已重置，據對
    # 象身份判別）追加歧義候選組成員——單元素模式的候選只走
    # in_candidates 受控通道（含選中組收縮語義），不在此列
    claimable = {s.code for s in gate.stocks}
    if gate is not rule_resolution:
        claimable |= {c.code for c in gate.candidates}
    unverified = list(rule_resolution.unverified_codes)
    # 規則側壞碼名單是硬信號（形態非法/全量庫未命中的確定性判定，存在
    # 性不依賴 LLM 回填）：作基底 seed，LLM 回填名經原文閘門去重合並
    # （下游循環的 in unresolved 判重天然銜接）；讀 gate 與
    # had_candidates 同源，多元素基座的實體槽已重置
    unresolved = list(gate.unresolved_names)

    # 用 LLM 市場推斷打破跨市場同名歧義：無確定實體時候選中恰有一隻與
    # 推斷市場一致 → 採納（"美股阿里巴巴"語境下 LLM 回 market=us）
    if market is not None and candidates and not stocks:
        market_filtered = [c for c in candidates if c.market == market.value]
        if len(market_filtered) == 1:
            stocks = market_filtered
            candidates = _drop_resolved_group(
                candidates, market_filtered, rule_resolution.pending_action)

    # stock_code / stock_codes 統一過三道閘門，多標的提及逐個過閘
    extra_codes = payload.get("stock_codes")
    raw_codes = [
        c.strip()
        for c in [payload.get("stock_code"),
                  *(extra_codes if isinstance(extra_codes, list) else [])]
        if isinstance(c, str) and c.strip()
    ]
    seen_codes: set = set()
    for raw in raw_codes:
        # LLM 常按真實世界拼寫返回裸 5 位 HK 碼（"09988"）：先歸一到
        # HK+5 規範身份，與候選匹配/查庫/確認輪共用同一代碼拼寫
        code = _canonical_digit_code(raw.upper())
        if code in seen_codes:
            continue
        seen_codes.add(code)
        in_candidates = [c for c in candidates if c.code == code]
        if in_candidates:
            # LLM 在歧義候選中做了選擇：被選中組整體收斂，兄弟組保留交確認
            stocks = _dedup_stocks(stocks + in_candidates)
            candidates = _drop_resolved_group(
                candidates, in_candidates, rule_resolution.pending_action)
        else:
            stock = lookup_stock_by_code(code)
            if stock is not None:
                if not had_candidates or code in claimable:
                    stocks = _dedup_stocks(stocks + [stock])
                else:
                    # 跨組採信閘門：規則側已有歧義候選時，庫內命中但不在
                    # 規則側標的宇宙（候選組 ∪ 已解析實體）內的代碼是越
                    # 權換標的，拒收
                    logger.info(
                        "LLM stock_code %s rejected: outside ambiguity groups",
                        raw)
            else:
                if code.isalpha() or code.upper().startswith("HK"):
                    if code not in unverified:
                        unverified.append(code)
                else:
                    unresolved.append(raw)
                logger.info("LLM stock_code %s rejected: not in stockDB", raw)

    # LLM 報告的無法解析標的名稱（"你好股份"類生造名）：過原文閘門後併入
    # unresolved，走既有 stock_unresolved 確認——空標的執行任務是無效產出
    # 原文閘門用小寫歸一比對（str.lower 逐碼點映射保持子串包含，單一
    # 小寫比對即覆蓋原樣命中）
    low_text_llm = str(payload.get("message_text") or "").lower()

    def in_text(name: str) -> bool:
        """原文閘門：LLM 返回的名稱（小寫歸一）出現在消息原文裡。"""
        return name.lower() in low_text_llm

    for name in payload.get("unresolved_names") or []:
        if name in unresolved:
            continue
        if in_text(name):
            unresolved.append(name)
        else:
            logger.info("LLM unresolved_name %r rejected: not in message text", name)

    if (unresolved or unverified) and intent == WebIntent.GENERAL_CHAT:
        # LLM 提到股票但判成閒聊且代碼不可信：保持閒聊，忽略壞代碼
        unresolved = []
        unverified = []

    # LLM 板塊名合入（規則側為基底）：防幻覺閘門"原文出現"；同義去重按
    # 去後綴鍵——"AI板塊"與基底"AI"是同一板塊的兩種表述
    sector_keys = {sector_dedup_key(s) for s in sectors}
    for name in payload.get("sectors") or []:
        key = sector_dedup_key(name)
        if key in sector_keys:
            continue
        if in_text(name):
            sectors.append(name)
            sector_keys.add(key)
        else:
            logger.info("LLM sector %r rejected: not in message text", name)

    # 以規則結果為基底做 replace 而非手抄字段重建：未指名字段（預掛
    # 歧義組等）自動隨行，手抄清單漏字段的漂移從結構上不可能發生
    return replace(
        rule_resolution,
        intent=intent,
        confidence=confidence,
        source="llm",
        stocks=stocks,
        sectors=sectors,
        candidates=candidates,
        unresolved_names=unresolved,
        unverified_codes=unverified,
    )


def _merge_llm_tasks(
    rule_resolution: WebIntentResolution,
    payload: Dict[str, Any],
    context: Dict[str, Any],
) -> List[WebIntentResolution]:
    """LLM 載荷 → 任務列表（合併入口單路徑）：單對象載荷視同單元素
    intents 數組，逐項過 ``_merge_llm_result`` 閘門。單元素繼承完整規則
    基底（LLM 漏填代碼不構成實體丟失）；多元素實體槽重置（逐項繼承會把
    全部標的汙染進每個任務；繼承碼隨之一併重置，殘留會讓未填實體的元素
    靜默回退會話陳舊標的）——重置只作用於繼承槽位，防幻覺閘門的事實源
    經 ``rule_view`` 讀原始規則任務，不隨重置失明；鏈路字段
    （source_request/tokens）隨行。數組內 followup＝延續前一項意圖與
    主體，保序輸出。多元素孤兒核算見
    ``_reclaim_orphan_entities``——規則側實體絕不因協議拆分靜默蒸發。
    """
    items = payload.get("intents") or [payload]
    base = rule_resolution if len(items) == 1 else replace(
        rule_resolution,
        stocks=[], candidates=[], sectors=[],
        unresolved_names=[], unverified_codes=[],
        needs_confirmation=False, reason="", pending_action=None,
        multi_intent_hint=False, inherited_stock_code="",
    )
    out: List[WebIntentResolution] = []
    prev_intent_value = ""
    prev_stocks: List[Stock] = []
    prev_sectors: List[str] = []
    for item in items:
        sub = dict(item)
        sub["message_text"] = payload.get("message_text")
        # 數組內 followup＝延續前一項意圖與主體：意圖經改寫 context 複用
        # _merge_llm_result 的轉換邏輯；主體槽空時隨行補齊前一項對應槽，
        # 追問元素不落成無錨點執行任務
        is_followup = sub.get("intent") == LLM_FOLLOWUP_LABEL
        item_context = ({**context, LAST_INTENT_KEY: prev_intent_value}
                        if is_followup and prev_intent_value else context)
        merged = _merge_llm_result(
            base, sub, item_context, rule_view=rule_resolution)
        if (is_followup and (prev_stocks or prev_sectors)
                and not merged.stocks and not merged.sectors):
            merged = replace(
                merged, stocks=prev_stocks, sectors=prev_sectors)
        prev_stocks, prev_sectors = list(merged.stocks), list(merged.sectors)
        prev_intent_value = merged.intent.value
        out.append(merged)
    if len(items) > 1:
        _reclaim_orphan_entities(out, rule_resolution)
    return out


def _subject_anchor_empty(r: WebIntentResolution) -> bool:
    """六槽主體錨點全空（孤兒回填目標與 finalize 空錨點守衛同口徑）。"""
    return not any((r.stocks, r.candidates, r.sectors, r.unresolved_names,
                    r.unverified_codes, r.inherited_stock_code))


def _first_open_executing(out: List[WebIntentResolution]) -> Optional[WebIntentResolution]:
    """首個無 stocks/candidates 的執行類元素（孤兒單目標掛載點）。"""
    return next((t for t in out if t.intent in _EXECUTING_INTENTS
                 and not t.stocks and not t.candidates), None)


def _warn_unclaimed(codes: List[str]) -> None:
    """孤兒主體無掛載目標的顯式丟棄告警（寧可顯式損失不誤掛）。"""
    logger.warning(
        "LLM multi-intent split left rule entities unclaimed with no "
        "empty executing task to attach: %s", ",".join(codes))


def _reclaim_orphan_entities(
    out: List[WebIntentResolution],
    rule_resolution: WebIntentResolution,
) -> None:
    """多元素主體核算（就地）：規則側主體如何落位到拆分元素。

    單一主體單元（個股/歧義組/板塊槽）＝子消息主體，可安全平分給全部
    無主體執行元素——"X的股價和走勢"的多元素拆分與逗號展開形同構；
    個股/板塊單元被認領後不回填（防同標的重複執行），歧義組例外——
    認領者已解自己那份，無主體元素仍需各自的消歧問答。多主體混合視圖
    ＝協議層信息不足（無法確定性分發）：單目標孤兒回收（掛載到首
    個無 stocks/candidates 的執行元素），無目標時顯式 warning 丟棄——
    寧可顯式損失不誤掛；候選掛載時預掛組結構隨行（歧義組任一成員被
    認領即整組清賬）。unverified 認領按大小寫摺疊的代碼等值（規則側原
    始拼寫 vs 元素側歸一拼寫）、恆單目標掛載防重複實查——與
    unresolved_names 的逐元素 seed（澄清請求冪等）刻意不對稱。
    """
    rule = rule_resolution
    if not (rule.stocks or rule.candidates
            or rule.unverified_codes or rule.sectors):
        return
    claimed = ({e.code for t in out for e in (*t.stocks, *t.candidates)}
               | {c.upper() for t in out for c in t.unverified_codes})
    groups = [g for g in (rule.pending_action or {}).get("groups") or []
              if isinstance(g, dict)]

    # unverified 單目標回收先行：目標謂詞（無 stocks/candidates）與主
    # 體回填互不侵佔目標
    orphan_unverified = [c for c in rule.unverified_codes
                         if c.upper() not in claimed]
    if orphan_unverified:
        target = _first_open_executing(out)
        if target is not None:
            target.unverified_codes = list(dict.fromkeys(
                list(target.unverified_codes) + orphan_unverified))
        else:
            _warn_unclaimed(orphan_unverified)

    # 單元計數：個股逐只、候選按預掛組（組邊界即歧義問句邊界）、板塊
    # 逐槽；無主體元素＝六槽全空（與 finalize 的空錨點同口徑）
    unit_count = (len(rule.stocks)
                  + ((len(groups) or 1) if rule.candidates else 0)
                  + len(rule.sectors))
    subjectless = [t for t in out
                   if t.intent in _EXECUTING_INTENTS
                   and _subject_anchor_empty(t)]
    if subjectless and unit_count == 1:
        if rule.stocks and rule.stocks[0].code not in claimed:
            for t in subjectless:
                t.stocks = _dedup_stocks(list(t.stocks) + rule.stocks)
        elif rule.candidates:
            for t in subjectless:
                t.candidates = _dedup_stocks(
                    list(t.candidates) + rule.candidates)
                if rule.pending_action:
                    t.pending_action = rule.pending_action
        elif rule.sectors and not any(
                sector_dedup_key(s) == sector_dedup_key(rule.sectors[0])
                for t in out for s in t.sectors):
            for t in subjectless:
                t.sectors = list(dict.fromkeys(
                    list(t.sectors) + rule.sectors[:1]))
        return

    # 多主體混合視圖：保守單目標孤兒回收
    group_peers: Dict[str, set] = {}
    for g in groups:
        codes = _group_codes(g)
        for code in codes:
            group_peers.setdefault(code, set()).update(codes)

    def _orphaned(entity: Stock) -> bool:
        peers = group_peers.get(entity.code, set())
        return not (entity.code in claimed or peers & claimed)

    orphan_stocks = [s for s in rule.stocks if _orphaned(s)]
    orphan_candidates = [c for c in rule.candidates if _orphaned(c)]
    if not orphan_stocks and not orphan_candidates:
        return
    target = _first_open_executing(out)
    if target is None:
        _warn_unclaimed(
            [e.code for e in (*orphan_stocks, *orphan_candidates)])
        return
    if orphan_stocks:
        target.stocks = _dedup_stocks(list(target.stocks) + orphan_stocks)
    if orphan_candidates:
        target.candidates = _dedup_stocks(
            list(target.candidates) + orphan_candidates)
        if rule.pending_action:
            target.pending_action = rule.pending_action


def _pending_skeleton(
    resolution: WebIntentResolution,
    sub_text: str,
    groups: List[Dict[str, Any]],
    unresolved_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """確認動作 pending_action 構造骨架：action/intent/groups/
    original_request + resolved_stocks（原請求已解析實體，消費輪合併回
    stocks，比較語義不丟）+ 可選 unresolved_names。"""
    pending: Dict[str, Any] = {
        "action": "confirm_stock",
        "intent": resolution.intent.value,
        "groups": groups,
        "original_request": sub_text,
    }
    if resolution.stocks:
        pending["resolved_stocks"] = [_stock_payload(s) for s in resolution.stocks]
    if unresolved_names:
        pending["unresolved_names"] = unresolved_names
    return pending


def _mark_confirm(r: WebIntentResolution, reason: str) -> None:
    """置確認標誌（needs_confirmation + reason）——各收口分支的公共落點。"""
    r.needs_confirmation = True
    r.reason = reason


def _finalize_confirmations(
    resolutions: List[WebIntentResolution],
) -> List[WebIntentResolution]:
    """第六步②組級入口：一條子消息（組）全部任務的確認判定。歧義組優先
    消費第四步預掛的 pending_action.groups，無預掛按 candidates 兜底建組；
    僅執行類意圖需要確認（三/四類 reason 見模塊 docstring）。

    集合提供者（組內存在 portfolio_analysis）是組級事實：空主體錨點的
    執行類任務主體＝提供者的賬戶標的集合輸出（任務間主體引用），無錨點
    守衛與低置信守衛對其豁免——對空實體動作元素轉無選項確認會死鎖（用戶
    重說同一句原樣重入管道，任何回覆無法消解）。執行端契約：空實體執行
    任務綁定同組組合任務的輸出，不得做"沿用上一隻股票"之類兜底。
    """
    has_provider = any(
        r.intent is WebIntent.PORTFOLIO_ANALYSIS for r in resolutions)

    def _finalize(resolution: WebIntentResolution) -> WebIntentResolution:
        resolution.confidence = max(0.0, min(1.0, resolution.confidence))
        sub_text = resolution.source_request or "".join(resolution.tokens)
        if resolution.intent not in _EXECUTING_INTENTS:
            # 有意圖信號但對象未解的閒聊候選（"分析…哈嘍板塊"）是實義
            # 請求黑洞，轉澄清確認；完全無信號的寒暄（"你好呀"）放行
            if (resolution.source == "llm_failed"
                    and INTENT_WORD_RE.search(sub_text)
                    and resolution.confidence < CONFIRMATION_CONFIDENCE_THRESHOLD):
                _mark_confirm(resolution, "low_confidence")
            return resolution

        # 無錨點執行類守衛：執行類任務缺一切主體錨點時轉低置信澄清——
        # followup 意圖提升與多意圖拆分的未填實體元素在此單點收口；
        # 組內存在集合提供者時豁免（空實體任務主體＝其輸出，轉無選項
        # 確認會讓用戶任何回覆都無法消解）
        empty_anchor = _subject_anchor_empty(resolution)
        if (resolution.intent != WebIntent.PORTFOLIO_ANALYSIS
                and empty_anchor and not has_provider):
            _mark_confirm(resolution, "low_confidence")
            resolution.pending_action = None
            return resolution

        if resolution.candidates:
            _mark_confirm(resolution, "ambiguous_stock_name")
            # 權威結構 groups：優先消費第四步預掛的組（已被 LLM 消解的組
            # 其候選不在 candidates 中，隨之過濾），無預掛按候選兜底
            cand_codes = {c.code for c in resolution.candidates}
            groups = [
                g for g in (resolution.pending_action or {}).get("groups", [])
                if isinstance(g, dict) and (_group_codes(g) & cand_codes)
            ] or [
                _group_payload(
                    resolution.candidates[0].name or resolution.candidates[0].code,
                    resolution.candidates, resolution.intent.value, sub_text)
            ]
            # 原請求中已解析的確定實體隨 pending 保留（消費輪合併回 stocks）
            resolution.pending_action = _pending_skeleton(
                resolution, sub_text, groups,
                unresolved_names=list(resolution.unresolved_names) or None)
            return resolution

        if resolution.unresolved_names:
            _mark_confirm(resolution, "stock_unresolved")
            # groups 為空：無歧義候選，等待用戶重新提供名稱/代碼
            resolution.pending_action = _pending_skeleton(
                resolution, sub_text, [],
                unresolved_names=list(resolution.unresolved_names))
            return resolution

        if (resolution.confidence < CONFIRMATION_CONFIDENCE_THRESHOLD
                and not (has_provider and empty_anchor)):
            # low_confidence 不產生 pending_action（意圖待澄清而非選標的），
            # 預掛載體一併撤下——殘留組會被 apply_pending 寫回，彈出誤導性
            # 選股確認；提供者在場的空實體任務不走此出口（轉無選項確認同
            # 樣會死鎖）
            _mark_confirm(resolution, "low_confidence")
            resolution.pending_action = None
        elif resolution.pending_action and not resolution.needs_confirmation:
            # 預掛組已隨 LLM 消歧/市場收窄清空候選：撤下預掛載體
            resolution.pending_action = None
        return resolution

    return [_finalize(r) for r in resolutions]


def _finalize_confirmation(
    resolution: WebIntentResolution,
) -> WebIntentResolution:
    """第六步②的單任務便捷入口（無組上下文＝無提供者，守衛原口徑）。"""
    return _finalize_confirmations([resolution])[0]


# =========================================================================
# 主類 — 六步流水線宿主（類內方法即執行序：構造/LLM/收尾/主入口）
# =========================================================================


class WebIntentResolver:
    """Web Chat 意圖識別器：token 序列 → 二維任務組列表（組=子消息）。

    LLM adapter 惰性構建（litellm provider 棧加載昂貴）：首次真正觸發
    兜底的 resolve 才構建，失敗永久禁用（兜底退化為低置信轉確認），
    構建受鎖保護可全局複用。config 與 llm_adapter 均省略則禁用兜底。
    """

    # request_context 中當前股票（#1619 股票範圍機制）的讀取鍵
    CURRENT_STOCK_CODE_KEY = "current_stock_code"

    def __init__(
        self,
        config: Optional[Any] = None,
        *,
        llm_adapter: Optional[Any] = None,
        llm_timeout: float = 45.0,
    ) -> None:
        """config 傳入即啟用 LLM 兜底（adapter 惰性構建，失敗永久禁用）；
        llm_adapter 直接注入則跳過構建（測試/複用場景）。"""
        self._config = config
        self._llm_adapter = llm_adapter
        self._llm_timeout = llm_timeout
        self._llm_init_failed = False
        self._llm_init_lock = threading.Lock()

    # ------------------------------------------------------------------
    # LLM 兜底（第六步①）
    # ------------------------------------------------------------------

    def _ensure_llm_adapter(self) -> Optional[Any]:
        """返回可用的 LLM adapter；從 config 按需構建（首次兜底才
        import，litellm 棧加載昂貴），失敗置 ``_llm_init_failed`` 永久
        禁用——初始化問題不擊穿解析主鏈路。
        """
        if self._llm_adapter is not None or self._llm_init_failed:
            return self._llm_adapter
        with self._llm_init_lock:
            if (self._llm_adapter is None
                    and not self._llm_init_failed
                    and self._config is not None):
                from src.agent.llm_adapter import LLMToolAdapter

                try:
                    self._llm_adapter = LLMToolAdapter(self._config)
                except Exception as exc:  # noqa: BLE001 — 初始化失敗不該擊穿意圖層
                    logger.warning(
                        "web intent LLM fallback disabled (adapter init failed): %s",
                        exc,
                    )
                    self._llm_init_failed = True
        return self._llm_adapter

    def _should_use_llm(
        self, resolution: WebIntentResolution,
    ) -> bool:
        """LLM 兜底觸發條件（寧可不做不可做錯：默認複核，豁免需三證
        齊全；adapter 不可用時恆 False——規則結果是唯一防線）。

        豁免三證（缺一即複核）：
          ① 視野完備——``all_tags_recognized``（未讀內容可能藏著主體/
             附加訴求，不得靜默丟棄）；
          ② 判定可靠——置信度 ≥ ``_CONFIDENCE_LLM_EXEMPT``（0.8：關鍵詞
             共現 0.85 / 顯式代碼 0.9 達標；繼承 0.75 不達標）；
          ③ 表達完備——無 multi_intent_hint：數據對象詞 × 強分析/組合類
             同場（"多少錢＋基本面"＝一句兩個深度）交 LLM 判定拆分還是
             單一。
        繼承產物主體在場同享豁免（繼承機制確定性；歧義候選同為主體
        在場——消歧是用戶確認事務）。純確認碎片（source="confirmation"）
        與 hk/us 存疑代碼永不觸發。
        """
        if resolution.source == "confirmation":
            return False
        # 繼承產物主體在場同享豁免（繼承機制確定性，0.75 是路徑標籤非
        # 疑義信號；歧義候選同為主體在場——消歧是用戶確認事務；空主體
        # 繼承無錨點，仍復核）
        subject_backed = (resolution.source == "context" and bool(
            resolution.stocks or resolution.sectors
            or resolution.candidates or resolution.inherited_stock_code))
        if (resolution.all_tags_recognized
                and not resolution.multi_intent_hint
                and (resolution.confidence >= _CONFIDENCE_LLM_EXEMPT
                     or subject_backed)):
            return False
        return self._ensure_llm_adapter() is not None

    def _classify_with_llm(
        self,
        resolution: WebIntentResolution,
        context: Dict[str, Any],
    ) -> Optional[List[WebIntentResolution]]:
        """調用 LLM 做意圖分類併合並結果（多意圖協議下為任務列表，保
        序）；任何失敗返回 None（用規則結果，由收尾鏈標記
        source="llm_failed"）。失敗面全覆蓋：adapter 異常、超時、error
        provider、非 JSON 回覆、非法 intent——寧可退回規則低置信（轉
        確認）也不被壞輸出汙染。
        """
        adapter = self._ensure_llm_adapter()
        if adapter is None:
            return None
        # is_available 在真實適配器上是 property（返回 bool），兼容方法
        # 形態兩種接口；不可用（如未配 API key）時跳過調用
        available = getattr(adapter, "is_available", True)
        if callable(available):
            available = available()
        if not available:
            logger.info("web intent LLM fallback skipped: adapter unavailable")
            return None
        text = resolution.source_request or "".join(resolution.tokens)
        recent = context.get(RECENT_STOCKS_KEY) or []
        # 繼承碼隨 prompt 下發為 current_stock：無自身標的的片段（"和市盈
        # 率"）只有拿到 current_stock 才能判回執行類意圖
        current_stock = None
        if resolution.inherited_stock_code:
            stock = lookup_stock_by_code(resolution.inherited_stock_code)
            current_stock = (_stock_payload(stock) if stock is not None
                             else {"code": resolution.inherited_stock_code})
        request_body = {
            "message": text,
            "current_stock": current_stock,
            "resolved_stocks": [_stock_payload(s) for s in resolution.stocks],
            "ambiguous_candidates": [_stock_payload(c)
                                     for c in resolution.candidates],
            "unresolved_codes": list(resolution.unresolved_names),
            # 讀點歸一：不可序列化元素（set/對象）會讓 json.dumps 在 try
            # 外以 TypeError 擊穿，只透傳字符串元素
            "recent_stocks": ([c for c in recent if isinstance(c, str)]
                              if isinstance(recent, list) else []),
            "last_intent": context.get(LAST_INTENT_KEY, ""),
        }
        messages = [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request_body, ensure_ascii=False)},
        ]
        try:
            # max_tokens=5000：思考型模型（deepseek 系）思考 token 與正文
            # 共享預算，200 會被思考燒光、正文恆空 → 兜底確定性失敗
            response = adapter.call_text(
                messages, temperature=0.0, max_tokens=5000,
                timeout=self._llm_timeout)
        except Exception as exc:  # noqa: BLE001 — LLM 棧任意異常都不該擊穿意圖層
            logger.warning("web intent LLM fallback failed: %s", exc)
            return None
        if response is None or getattr(response, "provider", "") == "error":
            return None
        payload = _parse_llm_payload(getattr(response, "content", None) or "")
        if payload is None:
            logger.warning("web intent LLM returned unparseable payload")
            return None
        # 原文隨載荷傳遞：merge 側用它對 LLM 返回的板塊名做原文出現校驗
        payload["message_text"] = text
        return _merge_llm_tasks(resolution, payload, context)

    # ------------------------------------------------------------------
    # 第六步 — 倖存任務收尾
    # ------------------------------------------------------------------

    @staticmethod
    def _group_base(group: List[WebIntentResolution],
                    ) -> WebIntentResolution:
        """組視圖並集基底：鏈路字段全組同源（同一子消息），取首任務
        即取代表（無主次語義）；實體槽按任務對象歸屬分佈在各組員上，
        並集才是該子消息的完整規則視野。"""
        first = group[0]
        if len(group) == 1:
            return first
        return replace(
            first,
            stocks=_dedup_stocks(s for r in group for s in r.stocks),
            candidates=_dedup_stocks(c for r in group for c in r.candidates),
            sectors=list(dict.fromkeys(x for r in group for x in r.sectors)),
            unresolved_names=list(dict.fromkeys(
                x for r in group for x in r.unresolved_names)),
            unverified_codes=list(dict.fromkeys(
                x for r in group for x in r.unverified_codes)),
        )

    def _finalize_task(
        self,
        group: List[WebIntentResolution],
        context: Dict[str, Any],
    ) -> List[WebIntentResolution]:
        """一條子消息（組）的收尾——sub_message 是收尾的最小單位：
        ① 組級複核：組內任一任務觸發 → 以組視圖並集為基底發起一次 LLM
        調用，產出即該子消息的全部任務，【整組替換】（一條子消息至多
        一次多意圖枚舉）；失敗退回規則任務逐任務收尾並標 llm_failed；
        ② 逐任務確認判定補齊（``_finalize_confirmations``）與日誌。
        """
        resolutions = list(group)
        if any(self._should_use_llm(r) for r in group):
            llm_tasks = self._classify_with_llm(
                self._group_base(group), context)
            if llm_tasks:
                resolutions = llm_tasks
            else:
                # 複核調用失敗：整組退回規則判定，source 標記區分"未調"
                # 的 rule（組內成員同屬這次失敗複核）
                for r in group:
                    r.source = "llm_failed"

        out = _finalize_confirmations(resolutions)
        for r in out:
            _log_resolution(r.source, r)
        return out

    # ------------------------------------------------------------------
    # 主入口 — 六步流水線
    # ------------------------------------------------------------------

    def resolve(
        self,
        message: str,
        session_context: Any = None,
        request_context: Any = None,
    ) -> List[List[WebIntentResolution]]:
        """解析一條用戶消息，返回**二維任務組列表**（按用戶表達順序保
        序）。

        外層 = 子消息任務組（一條消費型標點/順序連接詞切開的一段），
        組內是平權任務（主體任務＋未被消費的板塊/指數/組合兄弟任務）；
        單意圖消息同樣是雙層結構 ``[[task]]``。確認狀態在需確認任務自
        身：任一組的任一任務 ``needs_confirmation=True`` 即
        整條消息短路（消費方 ``any()`` 判斷），鏈式確認的 confirmed
        寄生在該任務的 ``pending_action`` 上。
        session_context 提供 recent_stocks / pending_actions / last_intent；
        request_context 提供 ``current_stock_code``（#1619）
        """
        # ---- 第一步：上下文準備與空輸入短路 ----
        context = _session_context(session_context)
        request = _session_context(request_context)
        recent = context.get(RECENT_STOCKS_KEY) or []
        # 會話形狀異常不擊穿（與寫側 apply_outcome 的 str 過濾同口徑）：
        # 繼承碼來源值非文本按缺失處理，不帶病流入查庫/LLM 兜底路徑
        raw_current = request.get(self.CURRENT_STOCK_CODE_KEY, "")
        current_stock_code = raw_current if isinstance(raw_current, str) else ""
        first_recent = (recent[0] if isinstance(recent, list) and recent
                        and isinstance(recent[0], str) else "")
        inherited_stock_code = current_stock_code or first_recent
        # 確認存活的唯一權威是 pending_actions（clear_pending_actions 的
        # 清理協議只作用於它）；last_resolutions 是消費載荷投影——開關
        # 關閉時陳舊投影不得被消費（Agent 失敗收尾後舊確認鏈立即失效）
        pending_gate = _pending_confirming_tasks(context)
        last_resolution = (context.get(LAST_RESOLUTIONS_KEY) or pending_gate
                           ) if pending_gate else []

        if not isinstance(message, str) or not message.strip():
            # 空/非文本：閒聊直達（帶繼承股票；空消息不清 pending——
            # 它不是確認響應，pending 留待真正回覆時消費）
            empty = WebIntentResolution(
                intent=WebIntent.GENERAL_CHAT,
                confidence=_CONFIDENCE_FALLBACK,
                source="rule",
                inherited_stock_code=inherited_stock_code,
            )
            _log_resolution("rule", empty)
            return [[empty]]  # 一律二維

        # ---- 第二步：全消息分詞（_preprocess_text / _identify_stock_codes
        #      全局僅此一次，後續各階段只消費這份 tokens）----
        _, tokens = _preprocess_text(message)
        tokens = _identify_stock_codes(tokens)

        # ---- 第三步：消息級多任務切分（tokens 二維）----
        sub_token_lists = _split_sub_messages(tokens, message)

        # ---- 第四步：逐子消息規則級解析（多意圖任務列表；LLM 延後不跑）----
        full_resolution: List[List[WebIntentResolution]] = []
        prev_intent = context.get(LAST_INTENT_KEY, "")
        prev_subject: Optional[_ChainSubject] = _session_chain_subject(context)
        for i, sub_tokens in enumerate(sub_token_lists):
            chain_code = inherited_stock_code if i == 0 else (
                prev_subject[0][0].code if len(prev_subject[0]) == 1 else "")
            tasks = _classify_rule(
                sub_tokens,
                prev_intent,
                chain_code,
                prev_subject,)
            full_resolution.append(tasks)
            verdict = tasks[0]
            prev_intent = verdict.intent.value   # 繼承意圖＝上組主體任務意圖
            prev_ambiguous = [
                (str(g.get("name") or ""),
                 [s for s in map(_stock_from_payload, g.get("candidates", []))
                  if s])
                for g in (verdict.pending_action or {}).get("groups", [])
                if isinstance(g, dict)
            ]
            prev_subject = (list(verdict.stocks), list(verdict.sectors),
                            prev_ambiguous)

        # ---- 第五步：確認消費（pending 存在時優先判定本輪是否為確認響應）----
        if _is_pending_action(last_resolution):  # 有歧義需要消歧
            reply_tasks = [t for g in full_resolution for t in g]
            full_resolution = _consume_confirmations(last_resolution, full_resolution)
            this_round = {id(t) for t in reply_tasks}
            return [
                self._finalize_task(group, context)
                if group and all(id(t) in this_round for t in group)
                else group
                for group in _as_task_groups(full_resolution)
            ]

        # ---- 第六步：逐倖存任務收尾（LLM 兜底 → 確認判定）----
        # ---- 確認收口（判定權在消費方）----
        # 不做同意圖摺疊：多標的任務各自獨立執行、各自鎖定 stock scope，
        # 聚合不改變 Agent 輸出質量；任一任務待確認即整鏈短路（消費方
        # any() 判定），確認任務與其餘任務隨組結構寫入 last_resolutions
        return [self._finalize_task(group, context) for group in full_resolution]

    def resolve_first(
        self,
        message: str,
        session_context: Any = None,
        request_context: Any = None,
    ) -> WebIntentResolution:
        """單任務便捷視圖：二維任務列表的首組首任務（首子消息首個任務）。"""
        return self.resolve(message, session_context, request_context)[0][0]


# =========================================================================
# 會話簿記 — resolve 之後的出口寫回（pending 結算 / recent / last_intent）
# =========================================================================


def _writable_context(session: Any) -> Optional[Dict[str, Any]]:
    """簿記目標 dict：None session / 無 context 對象返回 None（no-op）。
    空 dict 會話與空 .context 同為有效目標——宿主可能掛 update_context
    持久化鉤子，真值判斷會誤傷（getattr(None) 得 None，免顯式判空）。"""
    if isinstance(session, dict):
        return session
    context = getattr(session, "context", None)
    return context if isinstance(context, dict) else None


def _write_context(
    session: Any, context: Dict[str, Any], key: str, value: Any
) -> None:
    """寫會話鍵：宿主對象提供 ``update_context``（ConversationSession 的
    簿記入口，可能帶持久化鉤子）時走它，否則直接寫 context dict。"""
    updater = getattr(session, "update_context", None)
    if callable(updater):
        updater(key, value)
    else:
        context[key] = value


def apply_pending(
    session: Any,
    tasks: "Union[WebIntentResolution, List[WebIntentResolution],"
           " List[List[WebIntentResolution]]]",
) -> None:
    """resolve 邊界同步調用：寫/清 pending_actions（消費即結算，替換式
    ——確認任務存在則寫其 pending_action，否則清空，舊 pending 絕不跨輪
    殘留）。必須在 SSE 層發出 action_required 之前完成，否則用戶下一條
    回覆會先於 pending 落庫、被當成新消息解析；空輸入輪由調用方跳過
    （空消息不得清 pending）。確認任務掃描全部組全部位置——多意圖消息
    的確認任務可以不在首組，只看首位會把 pending 寫丟。入參以 resolve
    的二維產出為主形態（兼容一維任務列表/單個 resolution，經
    ``_iter_tasks`` 展平——組結構不影響本函數，掃描本就按全部位置）。
    """
    task_list = list(_iter_tasks(tasks))
    context = _writable_context(session)
    if context is None:
        return
    confirming = next(
        (t for t in task_list if _has_pending_action(t)), None)
    _write_context(session, context, PENDING_ACTIONS_KEY,
                   [confirming.pending_action] if confirming else [])


def apply_outcome(
    session: Any,
    executed_tasks: "Union[WebIntentResolution, List[WebIntentResolution],"
                    " List[List[WebIntentResolution]]]",
) -> None:
    """任務執行完成後調用：recent_stocks 頭插去重截斷（候選/未解析標的
    不入列）+ last_intent（落點＝最後一個執行類組的組首，與頭插"後寫勝
    出"同源；無執行類組退末位）。只記真正執行的任務——短路輪不寫，
    未執行的 stocks/意圖不得汙染繼承上下文。入參以執行端實際執行的
    resolve 原始二維形態為主（組結構是落點判定的輸入，展平即丟）；
    兼容一維任務列表/單個 resolution。
    """
    task_list = list(_iter_tasks(executed_tasks))
    context = _writable_context(session)
    if context is None:
        return
    recent = [c for c in context.get(RECENT_STOCKS_KEY) or [] if isinstance(c, str)]
    for code in [s.code for t in task_list for s in t.stocks if s.code]:
        if code in recent:
            recent.remove(code)
        recent.insert(0, code)
    _write_context(session, context, RECENT_STOCKS_KEY, recent[:MAX_RECENT_STOCKS])
    if task_list:
        # last_intent＝對話落點（最後一個執行類主體任務的組首），與 recent_stocks 頭插"後寫勝出"同源；無執行類組退末位（純閒聊輪）
        landing = next((g[0] for g in reversed(_as_task_groups(executed_tasks))
                        if g and g[0].intent in _EXECUTING_INTENTS),
                       task_list[-1])
        _write_context(session, context, LAST_INTENT_KEY, landing.intent.value)


def apply_resolution_to_session(
    session: Any,
    resolution: "Union[WebIntentResolution, List[WebIntentResolution],"
                " List[List[WebIntentResolution]]]",
) -> None:
    """把一次解析結果寫入會話上下文（組合入口 = apply_pending +
    apply_outcome）。入參以 resolve 的二維任務組產出為主形態
    （兼容一維任務列表/單個 resolution，經 ``_iter_tasks`` 展平），
    確認任務可位於任意組任意位置。短路輪（存在任一 needs_confirmation
    任務）整鏈未執行：只結算 pending，recent_stocks / last_intent 不寫；
    last_resolutions 每輪二維投影——第五步確認消費的數據源，上輪歧義
    任務的 pending_action 必須跨輪可見。
    """
    tasks = list(_iter_tasks(resolution))
    short_circuited = any(t.needs_confirmation for t in tasks)
    apply_pending(session, tasks)
    # 傳原始（二維）結構：組結構是 last_intent 落點判定的輸入，展平即丟
    apply_outcome(session, [] if short_circuited else resolution)
    # last_resolutions 每輪寫（含短路輪，信息不缺失）：二維組結構原樣
    # 投影——第五步確認消費的數據源，上輪歧義任務的 pending_action
    # 必須跨輪可見；分組信息（子消息邊界）隨鏈路保留
    if (ctx := _writable_context(session)) is not None:
        two_dim = _as_task_groups(resolution) or [tasks]
        _write_context(session, ctx, LAST_RESOLUTIONS_KEY,
                       [[asdict(t) for t in g] for g in two_dim])


def clear_pending_actions(session: Any) -> None:
    """清空待確認動作（Agent 失敗路徑的顯式收尾；正常輪由 apply 替換）。
    pending_actions 是確認存活的唯一權威：清空即舊確認鏈失效（消費
    閘門關閉，陳舊 last_resolutions 投影惰性化，下輪寫側覆寫自愈）。"""
    if (context := _writable_context(session)) is not None:
        _write_context(session, context, PENDING_ACTIONS_KEY, [])
