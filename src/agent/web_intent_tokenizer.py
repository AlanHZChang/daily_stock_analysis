# -*- coding: utf-8 -*-
"""
Web Chat 意圖識別層 — 六步分詞管道（Intent Tokenizer）。

把一條用戶消息切分為攜帶語義標籤的 ``Token`` 序列，供
``web_intent_resolver.WebIntentResolver`` 做規則分類；本模塊不做任何
意圖判定，只負責"識別出消息裡有什麼"。

== 六步管道（_preprocess_text，按執行順序）==
  Step 1   多股票實體掃描（僅全名精確匹配，8~2 字窗口，含改名舊稱；入口
           extend_AkShare 把 AkShare 全量併入 stockDB——擴展點釘死在全
           管道最前）
  Step 2   特殊標點與空白切分（排除 * - .，可能出現在股票名/代碼中；僅
           作用於 Step 1 的 gap）
  Step 3   代碼形字符串提取（unknown_code；任意位裸數字 → unknown_number）
  Step 4   市場關鍵詞提取（含"股"+"份"消歧）
  Step 5   無歧義關鍵詞分詞（clean 詞池）
  Step 6   殘存 gap 多策略匹配（關鍵詞/精確/子串/拼音/模糊 DFS）

== 核心原則 ==
寧可不做，不可做錯，放棄一切低置信度的匹配。Step 1-5 只做精確匹配；
Step 6 混合匹配但要求整段 TAG 全覆蓋（交叉驗證）才產出，任一片段無 tag
則整體原樣返回，交下游 LLM 兜底。

== 關鍵不變量 ==
  - 實體掃描（Step 1）先於一切切分類步驟：全名一旦被撕裂即無法復原，
    含代碼形/關鍵詞子串的全名（"TCL科技"/"恒生電子"）必須先被整名消費。
    AkShare 擴展因此釘死在管道最前，Steps 1~6 自始面對同一合併後庫視圖。
  - 輸入側 NFKC 寬度歸一 + 窗口匹配時刪去輸入端空格："貴 州 茅 臺" 與
    常規書寫同樣整名命中（庫側源數據歸一屬 resolver 層，後續 PR 引入）。
  - token 層代碼身份的規範拼寫單一定義點 ``_canonical_stock_code``（a=6
    位裸數字、hk=HK+5 位、us=大寫 ticker）：名稱路徑與代碼路徑共享同一
    拼寫，下游從其它來源（LLM 輸出/session 繼承）構造 stocks 時必須複用，
    否則同一股票出現多重代碼身份。
  - sector 系三標籤詞池見 web_intent_types（泛稱/行業名/行業兼股票名），
    全管道不做個股名匹配；行業名+泛稱相鄰為高置信度板塊組合。

unknown_code 由 ``_identify_stock_codes`` 辨認：庫命中 → stock_code（附
三元組）；形態非法或該市場庫全量未命中 → wrong_{market}_code；庫非全量
未命中 → unknown_{market}_code（存疑交下游 LLM）。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from src.agent.stock_scope import extract_stock_codes  # 代碼格式校驗（不查庫）
from src.agent.web_intent_types import (
    Market,
    TAG_FILLER,
    TAG_SECTOR,
    TAG_SECTOR_NAME,
    TAG_SECTOR_N_STOCK,
    TAG_STOCK_CODE,
    TAG_STOCK_NAME,
    TAG_SUBJECT_INDEX,
    TAG_SUBJECT_MARKET,
    TAG_SUBJECT_MARKET_BROAD,
    TAG_UNKNOWN_CODE,
    TAG_UNKNOWN_NUMBER,
    Token,
    _ASCII_KEYWORD_UPPER,
    _CLEAN_KEYWORDS_PATTERN,
    _DIGIT_KEYWORDS_RE,
    _HAS_CONTENT_PATTERN,
    _KW_TO_MARKET,
    _SPECIAL_PUNCT_RE,
    _TAG_KEYWORD_LISTS_EXTEND,
    _classify_keyword,
    _compile_kw_pattern,
    unknown_code_tag,
    wrong_code_tag,
)
from src.services.name_to_code_resolver import (
    Stock,  # (code/name/market)
    US_stock_code_match,  # 美股代碼匹配
    _db_lock,  # stockDB 讀鎖：與下游 extend_AkShare 的併發合併串行
    extend_AkShare,  # Step 1 入口調用：合併 AkShare 全量進 stockDB（冪等）
    is_known_stock_name,  # 本地名稱表成員判定（不聯網）
    is_market_db_complete,  # 市場庫全量判定（wrong/unknown 細分依據）
    lookup_stock_by_code,  # 代碼查庫（stock_code 三元組來源）
    resolver_name_to_code_list,
    stockAliases,  # 改名舊稱（code→{舊名}）：實體索引與 resolver 口徑對齊
    stockDB,  # 全局名稱庫（code→name，可被 AkShare 原地擴充）
)
from src.services.stock_code_utils import (  # 交易所推斷權威實現（無 agent 反向依賴）
    _infer_cn_exchange,
)


def _extract_markets_from_tokens(tokens: List[Token]) -> List[Market]:
    """從 token 提取市場枚舉（唯一提取點）：TAG_SUBJECT_MARKET → _KW_TO_MARKET，
    另識別 ASCII 簡寫 "us"/"hk"。消歧已在 _split_market_tokens 完成，此處僅映射。

    小寫簡寫僅在消息含 CJK 時生效：純英文消息裡獨立的小寫 "us" 幾乎總是
    代詞；大寫 US/HK 是刻意形態，不受語境限制。"""
    has_cjk = any("\u3400" <= ch <= "\u9fff" for t in tokens for ch in t.text)
    markets: List[Market] = []
    seen: set = set()
    for t in tokens:
        if t.tag == TAG_SUBJECT_MARKET:
            mkt = _KW_TO_MARKET.get(t.text.lower())
            if mkt and mkt not in seen:
                markets.append(mkt)
                seen.add(mkt)
        else:
            stripped = t.text.strip()
            shorthand = stripped.lower()
            if shorthand in ("us", "hk") and (has_cjk or shorthand != stripped):
                mkt = Market(shorthand)
                if mkt not in seen:
                    markets.append(mkt)
                    seen.add(mkt)
    return markets


def _recognition_rate(tokens: List[Token]) -> float:
    """已打標籤 token 佔全部 token 的比例，低則升級 LLM 兜底。"""
    if not tokens:
        return 0.0
    return sum(1 for t in tokens if t.tag) / len(tokens)


def _market_of_code(code: str) -> str:
    """從代碼形態推斷市場：6 位→a、5 位→hk、字母 ticker→us（與
    name_to_code_resolver._infer_code_market 語義一致）。"""
    c = (code or "").strip().upper()
    if not c:
        return ""
    if c.isdigit():
        if len(c) == 5:
            return "hk"
        if len(c) == 6:
            return "a"
        return ""
    if re.match(r"^[A-Z]{1,5}(\.[A-Z])?$", c):
        return "us"
    return ""


def _canonical_stock_code(code: str, market: str) -> str:
    """token 層股票代碼的規範拼寫：hk → HK+5 位，a/us 保持 stockDB 鍵原樣
    （6 位裸數字 / 大寫 ticker）。名稱路徑產出的唯一歸一點——不歸一會與
    代碼路徑形成同一股票的雙重身份。"""
    if market == "hk" and code.isdigit():
        return f"HK{code}"
    return code


def _canonical_stocks(stocks: List[Stock]) -> List[Stock]:
    """批量套用 _canonical_stock_code（Stock 為 frozen，需重建）。"""
    return [
        Stock(code=_canonical_stock_code(s.code, s.market), name=s.name, market=s.market)
        for s in stocks
    ]


# =========================================================================
# Step 1 — 多股票實體掃描（僅全名精確匹配，管道首步）
# =========================================================================

def _build_entity_index() -> Tuple[List[str], Dict[str, List[Tuple[str, str, str]]]]:
    """構建實體掃描索引：全名列表 + 名稱 → [(code, market, 規範名)]。

    含 stockAliases 改名舊稱（與 resolver 口徑對齊），別名命中同樣展示當前
    規範名。每消息重建一次（stockDB 可能被 AkShare 擴充改變，不能跨消息
    緩存）；只讀當時的 stockDB，絕不主動發起擴展。
    """
    names: List[str] = []
    name_codes: Dict[str, List[Tuple[str, str, str]]] = {}
    # 持鎖迭代：與併發請求的 extend_AkShare 原地合併串行，防 dict 迭代崩潰
    with _db_lock:
        for code, name in stockDB.items():
            if not name or not code:
                continue
            if name not in name_codes:
                names.append(name)
                name_codes[name] = []
            market = _market_of_code(code)
            if market:
                name_codes[name].append((code, market, name))
        for code, aliases in stockAliases.items():
            market = _market_of_code(code)
            canonical = stockDB.get(code) or ""
            for alias in aliases:
                if not alias:
                    continue
                if alias not in name_codes:
                    names.append(alias)
                    name_codes[alias] = []
                entry = (code, market, canonical or alias)
                if market and entry not in name_codes[alias]:
                    name_codes[alias].append(entry)
    return names, name_codes


# 實體掃描壓縮長度上限：按刪空格後計，與庫內最長全名取小、封頂 8（9 字
# 以上 CJK 股名不存在，超長指稱交 Step 6/下游 LLM）；下探到 2 字（美團/
# 快手 等港股短名）——窗口必須整體等於全名，誤切風險有界
_MAX_ENTITY_LEN = 8

# sector 系詞池並集：與股票名衝突時行業語義優先，全管道不做個股名匹配。
# 含恰為庫中全名的詞（"機器人"=300024）——Step 1 放行，交 Step 6 打 tag
_SECTOR_KEYWORD_SET = frozenset(
    kw
    for tag in (TAG_SECTOR, TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK)
    for kw in _TAG_KEYWORD_LISTS_EXTEND.get(tag, [])
)

# ST 風險警示前綴（"ST德豪"/"*ST美麗"/"ST*美麗"）：前綴三型互認，AB 漢字
# 部分必須等於庫中全名；Step 3 放行其 ASCII 前綴不作代碼候選（見 _split_by_codes）
_ST_PREFIX_RE = re.compile(r"^(\*ST|ST\*|ST)([\u3400-\u9fff]+)$")


def _st_prefix_variants(name: str) -> set:
    """ST 前綴三型等價拼寫集合：STAB / *STAB / ST*AB 互認（前綴後須為
    CJK，排除 "STO" 等普通英文詞）；非該形態返回 {name} 自身。"""
    m = _ST_PREFIX_RE.match(name)
    if not m:
        return {name}
    tail = m.group(2)
    return {f"ST{tail}", f"*ST{tail}", f"ST*{tail}"}


def _split_by_stock_entities(text: str) -> List[Token]:
    """Step 1 子函數（管道首步）：多股票實體掃描（僅全名精確匹配，最長優先、
    非重疊）。

    入口先把空白（含 tab/換行）收斂為單空格，隨後逐位置嘗試"最寬跨度 ~ 2
    字"窗口（收斂後 max_len 字全名最寬佔 2*max_len-1 個 raw 字符，跨度上界
    靜態完備）；窗口刪空格後必須整體等於庫中全名（含改名舊稱），禁止
    子串/拼音/模糊（"貴 州 茅 臺"/"中 國 海 洋 石 油"→整名命中）。
    全名恰為枚舉行業詞（"机器人"）時放行交 Step 6
    打 sector；縮寫（"茅台"）非全名，交 Step 6 多策略匹配承接。唯一命中
    → TAG_STOCK_NAME 確定實體；跨市場同名多隻（"阿里巴巴"）→ 攜帶多候選
    交下游歧義確認。未命中片段保留為空 tag token 交後續步驟。
    """
    if not text:
        return []
    # 空白（含 tab/換行）收斂為單空格：收斂後 max_len 字全名最寬佔
    # 2*max_len-1 個 raw 字符，窗口跨度上界得以靜態封頂；亦統一本步
    # 刪 ' ' 與 Step 2 按空白切分的兩套口徑（tab 分隔指稱同樣可命中）。
    # gap 文本隨之規整——空白本就被後續步驟切分與過濾，無信息損失
    text = re.sub(r"\s+", " ", text)
    if not any("\u3400" <= ch <= "\u9fff" for ch in text):
        return [Token(text)]  # 純英文段由 Step 6 DFS（拼音/美股代碼）兜底
    names, name_codes = _build_entity_index()
    max_len = min(_MAX_ENTITY_LEN, max((len(n) for n in names), default=0))
    max_span = 2 * max_len - 1  # 收斂後最長全名的最寬 raw 跨度（靜態完備）
    tokens: List[Token] = []
    i, gap_start, n = 0, 0, len(text)
    while i < n:
        matched = False
        for length in range(max_span, 1, -1):  # 最寬跨度~2 字窗口（帶空格全名也整名命中）
            if i + length > n:
                continue
            window = text[i:i + length]
            if not any("\u3400" <= ch <= "\u9fff" for ch in window):
                continue  # 不含 CJK 的窗口不掃描（代碼/ASCII 由其他步驟處理）
            window = window.replace(' ', '')  # 輸入端刪去空格再與全名比較
            if len(window) > max_len:
                continue  # 壓縮後超庫內最長全名（無空格文本的長跨度窗口），必不命中
            pairs = name_codes.get(window)
            if not pairs:
                for variant in _st_prefix_variants(window):
                    if variant == window:
                        continue
                    pairs = name_codes.get(variant)
                    if pairs:
                        break
            if pairs and window not in _SECTOR_KEYWORD_SET:
                stocks = [
                    Stock(code=_canonical_stock_code(code, market),
                          name=canonical, market=market)
                    for code, market, canonical in pairs
                ]
                if gap_start < i:
                    tokens.append(Token(text[gap_start:i]))
                tokens.append(Token(window, TAG_STOCK_NAME, stocks=stocks))
                i += length
                gap_start = i
                matched = True
                break
        if not matched:
            i += 1
    if gap_start < n:
        tokens.append(Token(text[gap_start:]))
    return tokens


def _is_identified_token(token: Token) -> bool:
    """Token 是否已被前序步驟識別（有 tag 或是已知股票名/代碼）。"""
    if token.tag:
        return True
    if is_known_stock_name(token.text):
        return True
    return False


def _extract_full_names_first(normalized: str) -> List[Token]:
    """Step 1: 對整條歸一後消息做多股票全名精確匹配掃描（管道首步）。

    實體掃描先於一切切分類步驟（全名撕裂後無法復原，見模塊 docstring）。
    入口先 ``extend_AkShare``（冪等）把 AkShare 全量併入 stockDB——首條
    冷消息即與暖態產出一致。直接以整條消息為掃描對象（不經逐 token 包裝），
    實體索引每消息只構建一次。
    """
    if any("\u3400" <= ch <= "\u9fff" for ch in normalized):
        extend_AkShare()
    return _split_by_stock_entities(normalized)


# =========================================================================
# Step 4 — 市場關鍵詞提取（"股"+"份"消歧）
# =========================================================================

# 市場相關 tag 關鍵詞 union；"股"+"份"消歧見 _split_market_tokens
# （防 "大港股份" 中的 "港股" 子串被誤提取）
_MARKET_TOKEN_PATTERN = _compile_kw_pattern(
    TAG_SUBJECT_MARKET, TAG_SUBJECT_MARKET_BROAD, TAG_SUBJECT_INDEX,
)


def _split_market_tokens(text: str) -> List[Token]:
    """Step 4 子函數：提取市場關鍵詞打 tag。"股"後接"份"（股票名後綴）跳過不上報。"""
    if not text:
        return []
    tokens: List[Token] = []
    pos = 0
    for m in _MARKET_TOKEN_PATTERN.finditer(text):
        s, e = m.start(), m.end()
        matched = m.group()
        if matched.endswith("股") and e < len(text) and text[e] == "份":
            continue
        if pos < s:
            gap = text[pos:s].strip()
            if gap:
                tokens.append(Token(gap))
        tag = _classify_keyword(matched)
        tokens.append(Token(matched, tag))
        pos = e
    tail = text[pos:].strip()
    if tail:
        tokens.append(Token(tail))
    return tokens


def _apply_market_extraction(tokens: List[Token]) -> List[Token]:
    """Step 4: 對非代碼/非全名 token 做市場關鍵詞提取 + 股份消歧。"""
    result: List[Token] = []
    for t in tokens:
        if _is_identified_token(t):
            result.append(t)
        else:
            result.extend(_split_market_tokens(t.text))
    return result


# =========================================================================
# Step 5 — 無歧義關鍵詞分詞（clean 詞池）
# =========================================================================

def _tokenize_by_clean_keywords(text: str) -> List[Token]:
    """Step 5 子函數：無歧義關鍵詞分詞，間隙保留為空 tag token 交 Step 6。"""
    tokens: List[Token] = []
    pos = 0
    for m in _CLEAN_KEYWORDS_PATTERN.finditer(text):
        gap = text[pos:m.start()].strip()
        if gap:
            tokens.append(Token(gap))
        tokens.append(Token(m.group(), _classify_keyword(m.group())))
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        tokens.append(Token(tail))
    return tokens


def _apply_clean_keyword_extraction(tokens: List[Token]) -> List[Token]:
    """Step 5: 對未識別 token 用無歧義關鍵詞（如"分析""走势""怎樣"）分詞。"""
    result: List[Token] = []
    for t in tokens:
        if _is_identified_token(t):
            result.append(t)
        else:
            result.extend(_tokenize_by_clean_keywords(t.text))
    return result


# =========================================================================
# Step 6 — 多策略智能匹配（DFS 全匹配：板塊詞/關鍵詞/股票名）
# =========================================================================

def _isAlpha(s: str) -> bool:
    """檢測字符串是否為純英文字母（a-z, A-Z）。"""
    return bool(s) and all(c.isascii() and c.isalpha() for c in s)


# 單字 filler 集合：全由這些字符組成的片段絕不做股票名全庫掃描——否則
# "和"*200 一類刷屏文本在 DFS 逐位置觸發全庫掃描（5500 名庫實測秒級耗時）
_SINGLE_CHAR_FILLERS = frozenset(
    kw for kw in _TAG_KEYWORD_LISTS_EXTEND[TAG_FILLER] if len(kw) == 1
)


def _is_filler_only(segment: str) -> bool:
    """片段是否完全由單字 filler 關鍵詞字符組成（如"和和""的的"）。"""
    return bool(segment) and all(ch in _SINGLE_CHAR_FILLERS for ch in segment)


def _dfs_match(text: str) -> Optional[List[Token]]:
    """深度優先全匹配：0 位置起匹配關鍵詞/股票名並遞歸剩餘文本；無法全匹配
    返回 None（寧可不做也不做錯）。全匹配即交叉驗證。

    "XX板塊"類複合詞無專用正則：行業名與泛稱分別在各自詞池命中，DFS 自然
    產出相鄰 [sector_name/sector_n_stock]+[sector] 高置信度組合；未枚舉
    行業詞（"預製菜板塊"）無法全匹配則原樣返回，交下游 LLM 兜底。
    """
    if len(text) == 0:
        return []

    # 以字母開頭：提取連續英文字母組成的單詞
    if _isAlpha(text[0]):
        # 直接組成連續的最大單詞 例如 "Alibaba的基本面" → "Alibaba", "的基本面"
        i = 1
        while i < len(text) and _isAlpha(text[i]):
            i += 1
        segment = text[:i]
        # 純英文做股票名拼音檢測 + 美股代碼檢測；雙源按 (code, market) 去重
        # （名稱恰等於 ticker 的 AMD/Meta 兩源各出一份同實體），先歸一到
        # canonical 拼寫使去重鍵與產出一致
        stock_list = _canonical_stocks(resolver_name_to_code_list(segment))
        seen = {(s.code, s.market) for s in stock_list}
        stock_list += [
            s for s in US_stock_code_match(segment)
            if (s.code, s.market) not in seen
        ]
        if stock_list:
            rest = _dfs_match(text[i:])
            if rest is not None:
                return [Token(segment, TAG_STOCK_NAME, stocks=stock_list)] + rest

    # 嘗試連續 2~4 漢字片段（優先長匹配）
    for length in (4, 3, 2, 1):
        if length > len(text):
            continue
        segment = text[:length]

        # 不分割連續的字母
        if _isAlpha(segment[-1]) and length < len(text) and _isAlpha(text[length]):
            continue

        # 遞歸搜索匹配，策略不變
        tag = _classify_keyword(segment)  # 全部關鍵詞（clean + extend）
        stock_list = []
        # filler 連續片段不構成股票名：跳過全庫掃描，杜絕逐位置掃描失控；
        # 通用公司後綴（公司/集團…）在 extend 詞池打 corp_suffix tag，tag
        # 路徑同樣跳過掃描（詞池為單一事實源，見 web_intent_types）
        if not tag and not _is_filler_only(segment):
            stock_list = _canonical_stocks(resolver_name_to_code_list(segment))
        if tag or len(stock_list) > 0:
            rest = _dfs_match(text[length:])
            if rest is not None:
                return [Token(segment, tag or TAG_STOCK_NAME, stocks=stock_list or None)] + rest
            # 庫內全名"精確"命中（別名規範名 != 輸入，不計）即實體自證：
            # 直接確認返回，余文留空 tag 交 LLM；關鍵詞/子串/拼音/模糊命中
            # 不享此待遇，維持全覆蓋交叉驗證
            if not tag and stock_list and all(s.name == segment for s in stock_list):
                tail = text[length:]
                return [Token(segment, TAG_STOCK_NAME, stocks=stock_list or None)] + (
                    [Token(tail)] if tail else []
                )

    return None


# Step 6 單 token 長度上限：50 字連續無標點且無前序步驟信號，即非正常
# 對話（刷屏/粘貼大段文字），整體放棄交 LLM。技術上封頂逐字符遞歸深入
# （實測 ~1500 字 RecursionError）與最壞線性×全庫掃描，保證有界；正常
# 聊天分片經 Step 2 標點切分後遠短於該上限
_MAX_MULTI_MATCH_TEXT_LEN = 50


# 動態混合匹配文本
def _multi_match(text: str) -> List[Token]:
    """Step 6 子函數：多策略智能匹配（關鍵詞/名稱庫精確/子串/拼音/模糊）；
    無法完全匹配則原樣返回（寧可不做也不做錯）。

    前置條件：AkShare 擴展與全名精確消費由管道 Step 1 獨佔承擔——直接
    調用本函數喂冷庫長文本會重新暴露無記憶化 DFS 的指數回溯面，調用方應
    走 ``_preprocess_text``。"""
    if not text:
        return []
    if len(text) > _MAX_MULTI_MATCH_TEXT_LEN: # DFS 複雜度控制, 過長 token 交由 LLM 判斷
        return [Token(text)]
    result = _dfs_match(text)
    return result if result is not None else [Token(text)]


def _apply_multi_extraction(tokens: List[Token]) -> List[Token]:
    """Step 6: 對每個空 tag token 做多策略智能匹配，已打 tag 的 token 受保護。"""
    result: List[Token] = []
    for t in tokens:
        if t.tag:
            result.append(t)
        else:
            result.extend(_multi_match(t.text))
    return result


# =========================================================================
# Step 2 — 特殊標點切分
# =========================================================================

def _split_by_special_punct(text: str) -> List[Token]:
    """Step 2: 按特殊標點與空白邊界切分（排除 * - .；空白同為詞界，
    "tsla aapl" 與 "tsla,aapl" 同構處理）。僅作用於 Step 1 的 gap；切分符
    留作空 tag token，由末端 _HAS_CONTENT_PATTERN 過濾。"""
    if not text:
        return []
    tokens: List[Token] = []
    pos = 0
    for m in _SPECIAL_PUNCT_RE.finditer(text):
        if pos < m.start():
            gap = text[pos:m.start()].strip()
            if gap:
                tokens.append(Token(gap))
        tokens.append(Token(m.group()))
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        tokens.append(Token(tail))
    return tokens


# =========================================================================
# Step 3 — 代碼形字符串提取
# =========================================================================

# ---- _CODE_CANDIDATE_PATTERNS — 代碼形字符串候選正則（_split_by_codes 專用） ----
# 寬鬆匹配（寧多勿漏）：命中"像代碼"的片段打 TAG_UNKNOWN_CODE，合法性交
# _identify_stock_codes。純文本匹配不查庫、同位置多正則取最長、不推斷市場。
_CODE_CANDIDATE_PATTERNS: List[Tuple[str, int]] = [
    # 1. 交易所前綴 + 任意位數字: SH600519, HK88888, SZ123
    (r'(?<![a-zA-Z])(?:SH|SZ|BJ|HK)\d{1,}(?!\d)', re.IGNORECASE),
    # 2. 數字.交易所後綴: 123456.HK, 235454354.sh
    (r'(?<!\d)\d{1,}\.(?:SH|SZ|BJ|HK)(?!\d)', re.IGNORECASE),
    # 3. 裸任意位數字: 600519, 12（形態歧義 → unknown_number，不按位數猜測）
    (r'(?<!\d)\d{1,}(?!\d)', 0),
    # 4. 美股大寫 ticker（左右不緊鄰字母數字），可選交易所後綴 BRK.B——
    #    後綴與主體整體成 span，防止 "BRK" 與 ".B" 撕成兩段
    (r'(?<![A-Za-z0-9.])([A-Z]{2,5}(?:\.[A-Z]{1,2})?)(?![A-Za-z0-9])', 0),
    # 5. 連續字母 + .us 後綴（大小寫不敏感）: aapl.us, BABA.US
    (r'(?<![A-Za-z0-9.])([A-Za-z]{1,5}\.us)(?![A-Za-z0-9])', re.IGNORECASE),
]


def _split_by_codes(text: str) -> List[Token]:
    """Step 3 子函數：寬口徑代碼形字符串提取。

    5 類正則命中"像代碼"的片段 → TAG_UNKNOWN_CODE，任意位裸數字 →
    TAG_UNKNOWN_NUMBER（形態歧義，交下游 LLM 辨析）；間隙保留為空 tag
    token。只做形態匹配與最大連續合併，不校驗合法性、不推斷市場。
    不復用 extract_stock_codes：其首碼白名單會丟棄 777777 這類非法代碼，
    本函數保留供下游二次確認。
    """
    if not text:
        return []

    # 階段 1：正則獨立掃描收集 span，重疊/嵌套交階段 2 合併。兩類放行保
    # 證不影響關鍵詞語義：關鍵詞池內純 ASCII 詞（"AI"/"PK" 大寫也不作代碼
    # 候選，交關鍵詞分類）；含數字枚舉指數詞（"滬深300"）內的數字段（完全
    # 包含於關鍵詞 span 才放行，部分重疊如 "滬深3000" 不適用）
    digit_keyword_spans: List[Tuple[int, int]] = (
        [(m.start(), m.end()) for m in _DIGIT_KEYWORDS_RE.finditer(text)]
        if _DIGIT_KEYWORDS_RE is not None
        else []
    )
    spans: List[Tuple[int, int]] = []
    for pattern, flags in _CODE_CANDIDATE_PATTERNS:
        for m in re.finditer(pattern, text, flags):
            if m.group().upper() in _ASCII_KEYWORD_UPPER:
                continue
            # ST 前綴放行：後繼 CJK / 前鄰 * / 後繼 *+CJK 時 "ST" 不作代碼
            # 候選，整名交 Step 1（兜底庫外 ST 名不被撕走前綴）
            if m.group() == "ST" and (
                (m.end() < len(text) and "\u3400" <= text[m.end()] <= "\u9fff")
                or (m.start() > 0 and text[m.start() - 1] == "*")
                or (m.end() + 1 < len(text) and text[m.end()] == "*"
                    and "\u3400" <= text[m.end() + 1] <= "\u9fff")
            ):
                continue
            if any(ps <= m.start() and m.end() <= pe for ps, pe in digit_keyword_spans):
                continue
            spans.append((m.start(), m.end()))

    # 無命中 → 整段文本作為一個空 tag token 返回
    if not spans:
        return [Token(text)]

    # 階段 2：最大連續合併（重疊 span 取最長，不被子串截斷）
    spans.sort()
    merged: List[Tuple[int, int]] = []
    for s, e in spans:
        if merged and s < merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    # 階段 3：按合併後 span 切分：候選 → unknown_code；間隙 → 空 tag token
    tokens: List[Token] = []
    pos = 0
    for s, e in merged:
        if pos < s:
            gap = text[pos:s].strip()
            if gap:
                tokens.append(Token(gap))
        span_text = text[s:e]
        if span_text.isdigit():
            # 裸數字形態歧義（代碼/指數/價格/年份/日期…）→ unknown_number，
            # 不進代碼校驗，交下游 LLM 辨析
            tokens.append(Token(span_text, TAG_UNKNOWN_NUMBER))
        else:
            tokens.append(Token(span_text, TAG_UNKNOWN_CODE))
        pos = e
    tail = text[pos:].strip()
    if tail:
        tokens.append(Token(tail))
    return tokens


def _apply_code_extraction(tokens: List[Token]) -> List[Token]:
    """Step 3: 對空 tag token 做代碼形提取（已識別 token 受保護）。"""
    result: List[Token] = []
    for t in tokens:
        if _is_identified_token(t):
            result.append(t)
        else:
            result.extend(_split_by_codes(t.text))
    return result


# =========================================================================
# _preprocess_text — 六步管道入口
# =========================================================================

def _preprocess_text(text: str) -> Tuple[str, List[Token]]:
    """六步管道分詞，返回 (原文本, token列表)。步驟與不變量見模塊 docstring。

    入口對工作副本做 NFKC 寬度歸一（返回的原文本不變）：全角數字/字母
    （"６００５１９"/"Ａ股"）與半角同形參與全部步驟。unknown_code 隨後由
    _identify_stock_codes 辨認為 stock_code / wrong_{market}_code /
    unknown_{market}_code。
    """
    # ---- 六步管道 ----
    normalized = unicodedata.normalize("NFKC", text)  # 寬度歸一（工作副本，原文原樣返回）
    tokens: List[Token] = []
    for t in _extract_full_names_first(normalized):   # Step 1: 全名實體掃描
        if t.tag:
            tokens.append(t)                # 已識別 token 不再切分
        else:
            tokens.extend(_split_by_special_punct(t.text))  # Step 2: 標點/空白只切 gap
    tokens = _apply_code_extraction(tokens)           # Step 3: 代碼形提取
    tokens = _apply_market_extraction(tokens)         # Step 4: 市場關鍵詞
    tokens = _apply_clean_keyword_extraction(tokens)  # Step 5: 無歧義關鍵詞
    tokens = _apply_multi_extraction(tokens)          # Step 6: 多策略匹配

    # 過濾純標點/空白 token
    tokens = [t for t in tokens if t.text.strip() and _HAS_CONTENT_PATTERN.search(t.text)]

    return text, tokens


# =========================================================================
# 代碼辨認 — unknown_code → stock_code / wrong_{market}_code / unknown_{market}_code
# =========================================================================

def _is_valid_canonical_numeric_code(code: str) -> bool:
    """extract_stock_codes 規範化後的數字代碼是否滿足裸格式約束（6 位 A 股
    首碼白名單 0/3/6/4/8 或 92 段、HK+5 位）。extract 只去前綴不校驗白名單，
    規範化結果必須再過本閘門，否則帶前綴的非法代碼會繞過確認直接執行。
    """
    c = (code or "").strip().upper()
    if c.startswith("HK"):
        digits = c[2:]
        return digits.isdigit() and len(digits) == 5
    if c.isdigit():
        return len(c) == 6 and (c[0] in "03648" or c.startswith("92"))
    return False


def _shape_market(text: str, canonical: str) -> str:
    """代碼市場推斷：優先規範化形態（HK 前綴 → hk、6 位 → a、字母 → us），
    形態非法（canonical 為空）時回退原始文本的前綴/後綴形狀；兜底 a。"""
    if canonical:
        if canonical.startswith("HK"):
            return "hk"
        m = _market_of_code(canonical)
        if m:
            return m
    t = (text or "").upper()
    if t.startswith("HK") or t.endswith(".HK"):
        return "hk"
    if _isAlpha(t.split(".", 1)[0]) and not any(ch.isdigit() for ch in t):
        return "us"
    return "a"


# 顯式交易所標註解析：前綴 SH/SZ/BJ/HK 或後綴 .SH/.SZ/.BJ/.HK（大小寫
# 不敏感），後綴優先。判決層權威解析，不復用 extract_stock_codes（那是
# 候選收集器，位數不符時靜默放行，不適用於判決）；標註市場與數字形態
# 矛盾 → wrong_{標註市場}，絕不靜默換市場解析
_EXPLICIT_MARKER_RE = re.compile(
    r"^(?P<pfx>SH|SZ|BJ|HK)?(?P<digits>[0-9]+)(?:[.](?P<sfx>SH|SZ|BJ|HK))?$",
    re.IGNORECASE,
)
_MARKER_MARKET = {"SH": "a", "SZ": "a", "BJ": "a", "HK": "hk"}


def _identify_one_code(t: Token) -> Token:
    """單個 TAG_UNKNOWN_CODE token 的辨認（_identify_stock_codes 子函數）：
    顯式標註優先的確定性判決。

    標註市場/交易所與數字形態矛盾 → wrong_{標註市場}（HK600519 / SH00700 /
    SH000001 不靜默改按其它市場或交易所解析）；形態合法則查庫 → stock_code，
    未命中按該市場庫全量與否細分 wrong/unknown。純字母 → 美股 ticker 路徑；
    無標註的防禦形態走 extract 兜底（管道契約下 Step 3 不會產出該形態）。"""
    text = t.text

    # 純字母 → 美股 ticker：僅本地庫命中才認可，未命中一律存疑交 LLM
    if not any(ch.isdigit() for ch in text):
        ticker = text.split(".", 1)[0].upper()
        matched = US_stock_code_match(ticker)
        if matched:
            # 統一規範大寫拼寫（aapl.us → AAPL），同一股票共享同一代碼身份
            return Token(ticker, TAG_STOCK_CODE, stocks=tuple(matched))
        return Token(text, unknown_code_tag("us"))

    m = _EXPLICIT_MARKER_RE.match(text)
    pfx, sfx = (m.group("pfx"), m.group("sfx")) if m else (None, None)
    if pfx and sfx and pfx.upper() != sfx.upper():
        # 前後綴雙標註市場互斥（HK600519.SH）：靜態規則斷非法，按後綴市場
        return Token(text, wrong_code_tag(_MARKER_MARKET[sfx.upper()]))
    marker = (sfx or pfx) if m else None
    if marker is not None:
        market = _MARKER_MARKET[marker.upper()]
        digits = m.group("digits")
        # HK 短碼先補零再校驗（1810.HK/HK700 → HK01810/HK00700，對齊
        # stock_code_utils zfill(5) 歸一口徑；≥5 位 zfill 無操作，位數
        # 超標判決不受影響）
        canonical = f"HK{digits.zfill(5)}" if marker.upper() == "HK" else digits
        # 標註市場的形態閘門（HK=5 位、A 股=6 位+首碼白名單）：不符即
        # wrong_{標註市場}，即使數字段恰為其它市場合法代碼也不改判
        if not _is_valid_canonical_numeric_code(canonical):
            return Token(text, wrong_code_tag(market))
        if marker.upper() != "HK" and _infer_cn_exchange(digits) != marker.upper():
            # 數字形態所屬交易所與標註點名矛盾（SH000001/BJ600519）：
            # wrong_{標註市場}，不得靜默解析成其它交易所的同號代碼
            return Token(text, wrong_code_tag(market))
        stock = lookup_stock_by_code(canonical)
        if stock is not None:
            # 規範化拼寫（hk00700 → HK00700、600519.SH → 600519）
            return Token(canonical, TAG_STOCK_CODE, stocks=(stock,))
        if is_market_db_complete(market):
            # 該市場庫已全量仍未命中（如 A 股 AkShare 已併入）：確定不存在
            return Token(text, wrong_code_tag(market))
        # 庫非全量（A 股未擴展 / hk/us 本地精選庫）：存疑交下游 LLM 判斷
        return Token(text, unknown_code_tag(market))

    # 無標註防禦路徑（管道契約下不出現：Step 3 裸數字 → unknown_number）
    extracted = [c.upper() for c in extract_stock_codes(text)]
    canonical = extracted[0] if extracted else ""
    if not canonical or not all(_is_valid_canonical_numeric_code(c) for c in extracted):
        return Token(text, wrong_code_tag(_shape_market(text, canonical)))
    stock = lookup_stock_by_code(canonical)
    if stock is not None:
        return Token(canonical, TAG_STOCK_CODE, stocks=(stock,))
    market = _shape_market(text, canonical)
    if is_market_db_complete(market):
        return Token(text, wrong_code_tag(market))
    return Token(text, unknown_code_tag(market))


def _identify_stock_codes(tokens: List[Token]) -> List[Token]:
    """對 TAG_UNKNOWN_CODE 逐個辨認，三種產出：

    - 庫命中 → ``stock_code``：``stocks`` 附完整三元組，文本用規範化拼寫
      （hk00700 → HK00700、600519.SH → 600519，與名稱路徑
      ``_canonical_stock_code`` 同源歸一，同一股票共享同一代碼身份）；
    - 形態非法或該市場庫已全量未命中 → ``wrong_{market}_code``：確定不存在；
    - 該市場庫非全量未命中 → ``unknown_{market}_code``：存疑交下游 LLM。
    """
    result: List[Token] = []
    for t in tokens:
        if t.tag != TAG_UNKNOWN_CODE:
            result.append(t)
            continue
        result.append(_identify_one_code(t))
    return result
