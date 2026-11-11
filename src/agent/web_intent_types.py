# -*- coding: utf-8 -*-
"""
Web Chat 意圖識別層 — 類型與常量定義（Intent Types）。

== 模塊定位 ==
web_intent 拆分為三模塊，本模塊是三者共享的"數據字典"：
  - ``web_intent_types.py``     — 意圖枚舉、WebIntentResolution、Token、
                                  tag/關鍵詞/正則常量（本模塊）；
  - ``web_intent_tokenizer.py`` — 六步分詞管道與實體提取；
  - ``web_intent_resolver.py``  — WebIntentResolver 主流程、規則/LLM/確認消費、
                                  session/SSE 輔助（兼容入口 re-export 本模塊）。

== 支持的意圖類型（最終方案：五個互斥意圖 + 上下文繼承機制）==

意圖體系按三個正交判別測試劃分，裁決順序固定（個性化 → 深度 → 對象）：

  T1 個性化測試  答案是否依賴"這個用戶"的自選/持倉數據？換一個用戶來問，
     答案會不同嗎？——會 → portfolio_analysis。判據是"答案依賴賬戶數據"，
     不是句子裡有沒有"我"："我的茅臺基本面怎麼樣"對所有用戶答案相同，
     仍是 stock_analysis。
  T2 深度測試    答案是"一個數據點"還是"一段有觀點的論述"？只需報出價格、
     漲跌、成交、估值倍數、漲跌排名 → quote_lookup；需要綜合多源信息做
     歸因/評價/比較/預測 → 分析類意圖。"為什麼/怎麼看"是分析意圖的強
     信號詞。quote_lookup 按深度定義、不限對象粒度：個股、指數、板塊的
     "報數"都歸它。
  T3 對象測試    主對象是個股還是集合？落腳點是誰的狀態：≤3 只個股（含
     比較）→ stock_analysis；行業/概念/主題/市場整體結構 → sector_analysis。

五個意圖的邊界（收 = 判定條件；推 = 排除到哪）：

- ``stock_analysis`` 股票分析——"給一隻股票做體檢"
    收：單標的多維診斷（基本面/技術面/估值/資金面）、漲跌歸因（"為什麼
        跌"）、2-3 只比較（"哪個好"）、輿情資訊（作為子維度）、"能不能
        買"的合規化回答；裸個股指稱的默認歸屬（"茅臺"）。
    推：對象是用戶私有集合 → portfolio_analysis；只要一個數據點 →
        quote_lookup；對象是行業/概念/市場結構 → sector_analysis。
- ``sector_analysis`` 板塊分析——"看森林，不看單棵樹"（含市場整體結構）
    收：行業/概念熱度、資金流向、成分股分佈、輪動位置、驅動邏輯、板塊
        內優劣評價（"白酒板塊哪隻最有潛力"）、市場風格判斷（"A股什麼
        風格"——大盤當作"全市場板塊"處理，指數/大盤的觀點類問題歸此）。
    推：板塊的當日漲跌數據、領漲領跌排名 → quote_lookup；板塊內單隻
        股票的深度問題 → stock_analysis（帶板塊上下文）。
- ``portfolio_analysis`` 持倉/自選股分析——唯一離不開"我"的意圖
    收：組合聚合診斷（整體盈虧/行業集中度/風險暴露）、自選股批量表現、
        組合語境下的個股評估（"我的茅臺還該拿著嗎"——需成本/倉位，答案
        因人而異；與"茅臺能買嗎"→ stock_analysis 是一對經典對比）、
        持倉操作詞（加倉/減倉/拿著）指向的個股評估。
    推：句中提到個股但答案不依賴賬戶數據 → stock_analysis（"分析茅臺
        的持倉"= 機構/北向持倉，是研究維度）。
- ``quote_lookup`` 行情查詢——"只報儀表盤讀數"（確定性數據）
    收：實時/當日價格、漲跌幅、成交量、換手、市值、市盈率等估值快照、
        指數點位、板塊漲跌、領漲領跌排名（事實排序）、"查一下 XX 股價"
        類取數動作；大盤/指數無深度信號的默認歸屬（"今天大盤怎麼樣"）。
    推：一切"貴不貴/強不強/為什麼/怎麼看"——出現評價或歸因即離開本
        意圖；執行端必須直接返回工具調用的結構化結果，禁止 LLM 自由
        發揮數字。
- ``general_chat`` 閒聊——兜底但不是垃圾桶
    收：金融知識百科（"什麼是市盈率"）、非金融話題、"你能幹什麼"類系統
        問答、不依賴行情數據源的靜態公司信息（"茅臺的老闆是誰"）。
    推：凡需要查行情/財務/資金數據接口的，一律不歸閒聊；分類器低置信
        ≠ 閒聊——低置信走 low_confidence 澄清確認，兩者在日誌中必須
        可區分。

== 易混淆對照（迴歸測試基線，見 test_web_intent_resolver 邊界矩陣）==
    "茅臺多少錢"            → quote_lookup      "茅臺估值貴不貴"      → stock_analysis
    "茅臺的市盈率是多少"    → quote_lookup      "什麼是市盈率"        → general_chat
    "茅臺今天為什麼大跌"    → stock_analysis    "茅臺今天跌了多少"    → quote_lookup
    "茅臺基本面怎麼樣"      → stock_analysis    "我的茅臺還該拿著嗎"  → portfolio_analysis
    "茅臺能買嗎"            → stock_analysis    "我的持倉今天怎麼樣"  → portfolio_analysis
    "白酒板塊今天漲了多少"  → quote_lookup      "白酒板塊怎麼看"      → sector_analysis
    "白酒板塊領跌的是誰"    → quote_lookup      "白酒板塊哪隻最有潛力" → sector_analysis
    "今天大盤怎麼樣"        → quote_lookup      "大盤怎麼看"          → sector_analysis
    "兩隻股票誰漲得多"      → quote_lookup      "兩隻股票哪個好"      → stock_analysis
    "分析茅臺的股價走勢"    → stock_analysis    "查一下茅臺的股價"    → quote_lookup

== 追問不佔意圖名額（上下文繼承機制）==
"那五糧液呢""再細一點"本身沒有獨立語義——它追問的是什麼任務，取決於
上文。追問由上下文繼承機制處理（查詢改寫層的輕量實現）：識別為追問
（TAG_FOLLOWUP + 無新股票指稱 + 上輪為執行類意圖）時直接繼承上輪意圖
（source="context"），意圖枚舉保持純語義。LLM 兜底提示詞中的 "followup"
（``LLM_FOLLOWUP_LABEL``）是同一機制的偽標籤，合併時同樣轉為繼承，絕不
寫入會話上下文。

意圖識別只產生一個輕量級標籤 + 股票上下文，由 SSE 層據此行動：
先發送 ``intent_resolved``；置信度低或股票名稱歧義時發送 ``action_required``
等待用戶澄清；解析出的 ``stock_code`` 傳遞給 #1619 股票範圍機制。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.services.name_to_code_resolver import Stock

__all__ = [
    "ALL_WEB_INTENTS",
    "CONFIRMATION_CONFIDENCE_THRESHOLD",
    "LAST_INTENT_KEY",
    "LAST_RESOLUTIONS_KEY",
    "LLM_CONFIDENCE_CAP",
    "Market",
    "MAX_RECENT_STOCKS",
    "PENDING_ACTIONS_KEY",
    "RECENT_STOCKS_KEY",
    "Token",
    "WebIntent",
    "WebIntentResolution",
    "TAG_UNKNOWN_CODE",
    "TAG_UNKNOWN_NUMBER",
    "TAG_STOCK_CODE",
    "is_wrong_code_tag",
    "unknown_code_tag",
    "wrong_code_tag",
    "is_unknown_code_tag",
    "TAG_STOCK_NAME",
    "TAG_CODE_NAME",
    "TAG_SUBJECT_RESEARCH",
    "TAG_SUBJECT_PORTFOLIO",
    "TAG_SUBJECT_MARKET",
    "TAG_SUBJECT_MARKET_BROAD",
    "TAG_SUBJECT_INDEX",
    "TAG_REQUEST",
    "TAG_ACTION_RESEARCH",
    "TAG_ACTION_PORTFOLIO",
    "TAG_ACTION_QUOTE",
    "TAG_ACTION_QUOTE_FETCH",
    "TAG_FOLLOWUP",
    "TAG_QUESTION",
    "TAG_OPINION",
    "TAG_COMPARISON",
    "TAG_SECTOR",
    "TAG_SECTOR_NAME",
    "TAG_SECTOR_N_STOCK",
    "TAG_TIME",
    "TAG_FILLER",
    "TAG_CORP_SUFFIX",
    "LLM_FOLLOWUP_LABEL",
]


# =========================================================================
# 意圖常量定義
# =========================================================================

class WebIntent(str, Enum):
    """意圖標籤枚舉（str 子類，成員可直接與字符串比較）。

    邊界總綱（三判別測試 + 逐意圖收/推 + 易混淆對照表）見模塊 docstring；
    各成員註釋只保留一句話本質與最強邊界信號。追問不是意圖成員——由
    上下文繼承機制處理（見模塊 docstring"追問不佔意圖名額"節）。
    """

    STOCK_ANALYSIS = "stock_analysis"           # 股票分析：單標的體檢（≤3 只含比較）；裸個股指稱的默認歸屬
    SECTOR_ANALYSIS = "sector_analysis"         # 板塊分析：行業/概念/市場結構；指數/大盤的觀點類問題也歸此
    PORTFOLIO_ANALYSIS = "portfolio_analysis"   # 持倉/自選股分析：唯一依賴用戶賬戶數據（T1 定義性特徵）
    QUOTE_LOOKUP = "quote_lookup"               # 行情查詢：報數據點，不限對象粒度；大盤/指數裸詞的默認歸屬
    GENERAL_CHAT = "general_chat"               # 閒聊/兜底：不查數據接口的對話；低置信 ≠ 閒聊


# 所有合法意圖（字符串形式），校驗 LLM/session 返回
ALL_WEB_INTENTS = frozenset(w.value for w in WebIntent)

# LLM 兜底的追問偽標籤：非意圖枚舉成員，_merge_llm_result 合併時轉為
# "繼承上輪意圖"（上輪為執行類）或降級 general_chat，絕不寫入會話上下文
LLM_FOLLOWUP_LABEL = "followup"


# =========================================================================
# Token 語義標籤常量 — 5 大類 21 個標籤，近義詞歸入同一標籤，供正則匹配使用
# =========================================================================

# --- 股票識別 ---
TAG_UNKNOWN_CODE = "unknown_code"      # 待驗證的代碼形字符串，Step 3 提取的中間態，由 _identify_stock_codes 辨認
TAG_UNKNOWN_NUMBER = "unknown_number"  # 任意位裸數字（代碼/指數/價格/年份/數量/日期…形態歧義），Step 3 直接標記，不進入代碼校驗
TAG_STOCK_CODE = "stock_code"          # 庫命中的股票代碼（stocks 附完整 code/name/market 三元組）

# 代碼辨認失敗態按市場細分（_identify_stock_codes 產出）：
#   wrong_{market}_code   — 確定不存在：形態非法（交易所靜態規則），或該市場庫已
#                           全量（A 股 AkShare 已併入）仍未命中
#   unknown_{market}_code — 存疑：該市場庫非全量（hk/us 本地精選庫）未命中，
#                           交下游 LLM 判斷，絕不硬猜
_CODE_TAG_MARKETS = ("a", "hk", "us")


def wrong_code_tag(market: str) -> str:
    """確定非法代碼的 tag（market ∈ a/hk/us → wrong_a_code / wrong_hk_code / wrong_us_code）。"""
    return f"wrong_{market}_code"


def unknown_code_tag(market: str) -> str:
    """存疑代碼的 tag（market ∈ a/hk/us → unknown_a_code / unknown_hk_code / unknown_us_code）。"""
    return f"unknown_{market}_code"


def is_wrong_code_tag(tag: str) -> bool:
    """tag 是否屬於確定非法代碼族（wrong_{market}_code）。"""
    return isinstance(tag, str) and tag.startswith("wrong_") and tag.endswith("_code")


def is_unknown_code_tag(tag: str) -> bool:
    """tag 是否屬於存疑代碼族（Step 2 中間態 unknown_code + unknown_{market}_code）。"""
    return isinstance(tag, str) and tag.startswith("unknown_") and tag.endswith("_code")


TAG_STOCK_NAME = "stock_name"          # 股票實體（全名或一對一縮寫），Step 1 僅全名精確匹配、Step 6 多策略匹配提取
TAG_CODE_NAME = "code_name"            # 空 tag 經 name_code_list 解析為股票名稱後打此標籤

# --- 意圖主題 ---
TAG_SUBJECT_RESEARCH = "subject_research"       # 研究主題（走勢/趨勢/技術面/基本面/籌碼）
TAG_SUBJECT_PORTFOLIO = "subject_portfolio"     # 持倉主題（持倉/倉位/自選股/盈虧）
TAG_SUBJECT_MARKET = "subject_market"           # 市場標識（A股/港股/美股/滬市…）
TAG_SUBJECT_MARKET_BROAD = "subject_market_broad"  # 泛市場概念（大盤/行情/指數/兩市）
TAG_SUBJECT_INDEX = "subject_index"             # 具體指數（上證/恒生/納斯達克/滬深300…）

# --- 動作 ---
TAG_REQUEST = "request"                       # 泛分析動作（分析/看看/研究/診斷/評估）：深度上弱於數據詞（T2）
TAG_ACTION_RESEARCH = "action_research"       # 研究決策（能買/可以買/止損/目標價/buy/sell）：強分析信號
TAG_ACTION_PORTFOLIO = "action_portfolio"     # 持倉操作（加倉/減倉/調倉/滿倉/空倉/拿著/拿住）：組合語境信號（T1）
TAG_ACTION_QUOTE = "action_quote"             # 數據點查詢（賓語側：多少錢/股價/成交量/市盈率/收盤/領漲/新聞…）：T2 報數信號
TAG_ACTION_QUOTE_FETCH = "action_quote_fetch"  # 取數動作詞（動詞側：查/查下/看/看下）——與數據對象詞分立為兩個 tag，下游只讀 tag 即可區分"取數動詞"與"數據對象"，不私設詞表（多少錢/股價/漲了多少/成交量/市盈率/收盤/領漲…）：T2 報數信號

# --- 輔助 ---
TAG_FOLLOWUP = "followup"     # 追問延續（繼續/剛才/這隻/它/上面/上次/該股）
TAG_QUESTION = "question"     # 中性疑問（怎麼樣/怎麼/是否/嗎/？）：不構成深度信號；觀點/歸因問句見 TAG_OPINION
TAG_OPINION = "opinion"       # 觀點/歸因問句（怎麼看/為什麼/還會/如何/風格…）：深度測試的強分析信號
TAG_COMPARISON = "comparison"  # 對比（對比/比較/哪個好/vs/pk/二選一）：比較觀點是強分析信號
TAG_SECTOR = "sector"          # 板塊泛稱詞（板塊/行業/賽道/概念/題材/龍頭）+ XX+後綴 複合形態
TAG_SECTOR_NAME = "sector_name"        # 行業名（金融/建築/證券/農業…），裸用即行業意圖
TAG_SECTOR_N_STOCK = "sector_n_stock"  # 行業名兼股票全名（機器人=300024），裸用歧義交下游 LLM 消歧
TAG_TIME = "time"             # 時間指示（今天/現在/本週/最近/實時…）
TAG_FILLER = "filler"         # 高頻功能詞（代詞/情態/否定/介詞/語氣：的/我/會/不/在…），零意圖語義
TAG_CORP_SUFFIX = "corp_suffix"  # 通用公司後綴（公司/集團/控股/股份/國際）：零區分度，精確命中即跳過股票名匹配

# 所有合法 tag 的不可變集合
_ALL_TAGS = frozenset({
    TAG_UNKNOWN_CODE, TAG_UNKNOWN_NUMBER, TAG_STOCK_CODE,
    *(wrong_code_tag(m) for m in _CODE_TAG_MARKETS),
    *(unknown_code_tag(m) for m in _CODE_TAG_MARKETS),
    TAG_STOCK_NAME, TAG_CODE_NAME,
    TAG_SUBJECT_RESEARCH, TAG_SUBJECT_PORTFOLIO, TAG_SUBJECT_MARKET,
    TAG_SUBJECT_MARKET_BROAD, TAG_SUBJECT_INDEX,
    TAG_REQUEST, TAG_ACTION_RESEARCH, TAG_ACTION_PORTFOLIO, TAG_ACTION_QUOTE,
    TAG_ACTION_QUOTE_FETCH, TAG_FOLLOWUP, TAG_QUESTION, TAG_OPINION,
    TAG_COMPARISON, TAG_SECTOR,
    TAG_SECTOR_NAME, TAG_SECTOR_N_STOCK, TAG_TIME, TAG_FILLER, TAG_CORP_SUFFIX,
})


class Market(str, Enum):
    """市場標識枚舉（str 子類，成員可直接與字符串比較）。"""

    A = "a"    # A 股
    HK = "hk"  # 港股
    US = "us"  # 美股


# 執行類意圖：會觸發 Agent 工作流，低置信度/股票歧義時必須先經用戶確認。
# 閒聊不觸發工作流；追問走上下文繼承（繼承產物本身必為執行類，標的歧義
# 已在上輪確認過，無獨立確認需求）
_EXECUTING_INTENTS = frozenset({
    WebIntent.STOCK_ANALYSIS,
    WebIntent.SECTOR_ANALYSIS,
    WebIntent.PORTFOLIO_ANALYSIS,
    WebIntent.QUOTE_LOOKUP,
})

# 執行類意圖低於此置信度 → 轉用戶確認
CONFIRMATION_CONFIDENCE_THRESHOLD = 0.6

# LLM 兜底路徑的置信度上限（規則路徑 0.8~0.9，LLM 統一壓低，避免過度自信）
LLM_CONFIDENCE_CAP = 0.75

# 會話上下文最多保留的"最近關注股票"數量
MAX_RECENT_STOCKS = 10

# apply_resolution_to_session() 寫入會話上下文時使用的 key
RECENT_STOCKS_KEY = "recent_stocks"       # 最近關注股票代碼列表
PENDING_ACTIONS_KEY = "pending_actions"   # 待確認動作列表（僅 confirm_stock）
LAST_INTENT_KEY = "last_intent"           # 上一輪意圖標籤
# 上一輪任務列表的會話投影：intent/stocks/sectors/confidence/source/
# source_request/unverified_codes 的序列化形態——供下一輪 resolve 的
# 追問主體種子（跨輪"繼續"指向 last_intent 的任務）/確認消費/回看調試
# 讀取（每輪寫，含短路輪：確認消費的數據源；種子側短路輪自動排除）
LAST_RESOLUTIONS_KEY = "last_resolutions"


# =========================================================================
# Tag → 關鍵詞列表 — 所有中文關鍵詞的唯一定義處
# =========================================================================
# 後續正則全部從這裡編譯，不手寫中文關鍵詞；TAG_SUBJECT_MARKET 由 _MARKET_KEYWORD_MAP 派生。
# 排除項：多 token 跨詞模式（和.*比…）由 extra 參數承接；"值得"與股票名
# "值得買"衝突，不入池

_MARKET_KEYWORD_MAP: Dict[Market, tuple] = {
    Market.A: ("a股", "大a", "沪市", "深市", "沪深"),
    Market.HK: ("港股", "h股", "香港"),
    Market.US: ("美股", "美国"),
}

# 關鍵詞分兩池，劃分標準是 Step 5 盲匹配（finditer 子串命中即採信）下的
# 子串歧義風險，貫徹"寧可不做，不可做錯"：
#   clean — 詞形無子串歧義：不被更長常見詞包含（"怎麼樣"不會被更長詞從
#           中途撕出），Step 5 直接命中即採信；
#   extend — 存在子串歧義（"現在"⊂"出現在"、"後市"⊂"午後市場"、
#           "查一下"⊂"查一下午"、"買點"="買"+量詞）或可能與股票名混淆：
#           僅在 Step 6 DFS 全片段覆蓋（交叉驗證）時命中，覆蓋不了則整段
#           放棄交下游 LLM，絕不盲撕。
# 兩條硬約束：
#   - 超過 4 字符的 ASCII 關鍵詞（research/portfolio/market…）只能留在
#     clean：Step 6 字母段整體消費 + 漢字窗口長度上限 4，使其在 extend
#     永遠無法命中；
#   - 市場族 tag（subject_market / market_broad / index）在 Step 4 經合併
#     詞池匹配（見 _MARKET_TOKEN_PATTERN），clean/extend 之分對其不生效。
# 另：ASCII 關鍵詞一律全詞匹配（_compile_kw_fragment 加詞邊界斷言），
# 連續英文字母段（researching/markets）不被中途切出。
# _TAG_KEYWORD_LISTS 由兩者合併，下游邏輯不變

_TAG_KEYWORD_LISTS_CLEAN: Dict[str, List[str]] = {
    TAG_REQUEST: [
        # 泛分析動作，深度上弱於數據詞："看看茅臺股價"按 action_quote 歸
        # 行情查詢；取數動作詞（查一下/查下）屬 TAG_ACTION_QUOTE。
        # analyze/analyse/research 超 4 字符，Step 6 無法承接，只能留 clean
        "分析", "看看", "研究", "诊断", "评估",
        "analyze", "analyse", "research",
    ],
    TAG_SUBJECT_RESEARCH: [
        # 估值是研究維度（"茅臺估值貴不貴"是評價類問題），與基本面/技術面同級
        "走势", "走向", "趋势", "技术面", "基本面", "估值", "筹码",
    ],
    TAG_QUESTION: [
        # 中性疑問不構成深度信號："今天大盤怎麼樣"仍歸行情查詢；
        # 觀點/歸因問句（怎麼看/為什麼…）屬 TAG_OPINION
        "怎么样", "怎么", "是否", "吗", "？", "?",
    ],
    TAG_OPINION: [
        # 觀點/歸因/預測問句 + 市場結構判斷詞（風格/輪動——觀點語義非數據）。
        # 深度測試 T2 的強分析信號："為什麼跌"是歸因分析，"跌了多少"才是報數
        "怎么看", "为何", "为什么", "还会", "还能", "还该", "要不要",
        "能否", "能不能", "如何", "涨还是跌", "风格", "轮动",
    ],
    TAG_SUBJECT_PORTFOLIO: [
        "持仓", "仓位", "我的股票", "自选股", "盈亏", "成本价",
        "portfolio", "position",
    ],
    TAG_ACTION_PORTFOLIO: [
        # 拿著/拿住是口語化持有表述，強組合語境信號（"還該拿著嗎"的答案
        # 依賴成本與倉位）；"持有"不入池——"持有茅臺的基金有哪些"是研究
        # 語境而非組合語境
        "加仓", "减仓", "调仓", "满仓", "空仓", "拿着", "拿住",
    ],
    TAG_ACTION_QUOTE: [
        # 數據點查詢（T2 報數側）：價格/漲跌幅度/成交/估值快照/事實排名。
        # 與強分析詞（subject_research/action_research/opinion/comparison）
        # 共現時讓位——"分析茅臺的股價走勢"按"走勢"歸股票分析；與泛動作
        # 詞（request）共現時獲勝——"查一下茅臺股價"歸行情查詢
        "多少钱", "多少点", "什么价", "报价",
        "涨跌幅", "涨了多少", "跌了多少", "涨了", "跌了", "涨得", "跌得",
        "成交量", "成交额", "换手", "市值", "市盈率", "市净率",
        "收盘价", "开盘价", "收盘", "开盘", "点位", "最高价", "最低价",
        "领涨", "领跌", "价格",
    ],
    TAG_SUBJECT_MARKET_BROAD: [
        "大盘", "行情", "两市", "北向", "股市", "market", "sector", "指数",
    ],
    TAG_SECTOR_NAME: [
        # 高頻英文縮寫概念（A 股語境）。放 clean（Step 5 盲匹配獨立存活）
        # 而非與中文行業名同列 extend：ASCII 詞邊界斷言強制全詞匹配
        # （"CPOX"不命中）、無中文名庫子串衝突（"證券"⊂中信證券那類），
        # 無需 DFS 全覆蓋保護；且經 _ASCII_KEYWORD_UPPER 放行後 Step 3
        # 不當美股 ticker 摳走——縮寫的板塊語義優先於同形 ticker。
        # 數字混合詞（5G/6G）會被 Step 3 數字段撕開，不收
        "CPO", "AIGC", "GPT", "GPU", "HBM", "PCB",
        "LED", "OLED", "MCU", "SOC", "AR", "VR", "MR",
        "SaaS", "IoT",
    ],
    TAG_SUBJECT_INDEX: [
        "上证", "深证", "创业板",
        "恒指", "纳斯达克", "纳指",
        "标普", "道琼斯", "道指",
        "沪指", "深成指", "深证成指",
        "科创", "科创板", "index", "indices",
        # 含數字指數詞（CJK+數字複合詞）：數字段與裸數字共形，Step 3 由
        # _DIGIT_KEYWORDS_RE 保護區放行，否則整詞永遠無法在 Step 4/5 命中
        "中证A500", "中证1000", "中证2000", "中证500", "中证800", "中证100",
        "上证50", "北证50", "深证100", "创业板50", "沪深300", "科创50",
    ],
    TAG_FOLLOWUP: [
        "继续", "接着", "刚才", "上面", "上次", "这只", "该股",
    ],
    TAG_COMPARISON: [
        "哪个好", "哪个", "哪只", "谁更", "二选一",
        "差别", "区别", "优劣", "pk", "vs",
    ],
    TAG_TIME: [
        "今天", "本周", "交易日", "实时", "最近",
        # 目前/當前：無更長常見詞包含，Step 5 直接命中安全
        "目前", "当前",
    ],
    TAG_FILLER: [
        "那个", "这个", "一只", "一下", "帮我", "我要", "我想", "以及",
        "其他", "其它",
    ],
}

_TAG_KEYWORD_LISTS_EXTEND: Dict[str, List[str]] = {
    TAG_SUBJECT_INDEX: [
        "恒生",  # 與股票名"恒生電子"混淆
    ],
    TAG_TIME: [
        # 現在 ⊂ "出現在"：Step 5 盲匹配會從"出現在龍虎榜"中途撕出時間
        # 詞；DFS 全覆蓋下"茅臺現在"（茅臺+現在）正常命中，超串場景整段
        # 放棄交 LLM
        "现在", "未来",
    ],
    TAG_SUBJECT_RESEARCH: [
        # 後市 ⊂ "午後市場/最後市值"；漲勢 ⊂ "上漲勢頭"；trend ⊂
        # "trending"。獨立 gap（"後市怎麼看"）或整段覆蓋（"茅臺後市"）
        # 時正常命中
        "后市", "涨势", "trend",
    ],
    TAG_ACTION_RESEARCH: [
        # 能買 ⊂ "才能買到"；買點/賣點存在"買+量詞點"歧義（"買點茅臺"
        # 是"買一點茅臺"）；buy/sell ⊂ "buyer/selling"。≤4 字符 ASCII
        # 在 extend 可命中（standalone gap）。抄底/逃頂/止盈/止損是交易
        # 決策詞（強分析信號）：不入池會讓"現在能抄底嗎"整段 DFS 放棄，
        # 板塊名/時間詞一併丟失
        "能买", "买点", "卖点", "buy", "sell",
        "抄底", "逃顶", "止盈", "止损",
    ],
    TAG_ACTION_QUOTE: [
        # 現價 ⊂ "兌現價值/發現價格"；股價 ⊂ "個股價值"。數據對象詞
        # （取數句的賓語側）
        "现价", "股价", "新闻",
    ],
    TAG_ACTION_QUOTE_FETCH: [
        # 取數動作詞（動詞側）：查一下 ⊂ "查一下午"、查下 ⊂ "查下午盤"、
        # 看 ⊂ 更長詞。真實取數句（"查一下茅臺股價"）整段覆蓋
        # （查一下+茅臺+的+股價）正常命中
        "查", "查下", "看", "看下",
    ],
    TAG_FOLLOWUP: [
        # 它/他 ⊂ "它們/他們"：單字代詞 Step 5 盲命中會把"他們說"錯判
        # 追問指代；獨立 gap（"它怎麼樣"）正常命中
        "它", "他",
        # 然後 ⊂ "居然後市/仍然後悔"（X然複合詞 + 後/悔）：Step 5 盲命中
        # 會從詞界中途撕出追問 tag 並毀掉緊隨關鍵詞（"後市"）。入 extend
        # 後僅 DFS 全覆蓋時命中，代價見迴歸：句首"然後再展開講講"類
        # 後綴不可覆蓋的追問句 followup tag 丟失，繼承改由 LLM 兜底
        "然后",
    ],
    TAG_COMPARISON: [
        "对比", "比较", "多选", "选哪",
    ],
    TAG_SECTOR: [
        # 泛稱詞：XX行業名的後綴落款（板塊/行業/賽道/概念/題材）+ 龍頭。
        # Step 6 DFS 把"建築板塊"分解為相鄰 [sector_name]+[sector] 組合，
        # 該相鄰組合即高置信度板塊信號（由下游消費）；龍頭非後綴，指
        # 龍頭個股（"白酒龍頭"），不參與相鄰組合語義。
        # ETF/LOF/REITs 是產品類泛稱後綴——"銀行ETF"與"銀行板塊"結構
        # 同構（銀行主題的產品集合），同樣構成相鄰組合；ASCII 詞經
        # _ASCII_KEYWORD_UPPER 放行後 Step 3 不當美股 ticker 摳走
        "板块", "行业", "赛道", "概念", "题材", "龙头",
        "ETF", "LOF", "REITs",
    ],
    TAG_SECTOR_NAME: [
        # 行業名：裸用即行業意圖。含與股票名衝突的詞（全量庫實證："證券"⊂
        # 中信證券、"農業"⊂農業銀行…）——名稱庫子串命中置信度極低，
        # 行業語義優先，全管道不做個股名匹配
        "新能源", "半导体", "消费", "医药", "白酒",
        "军工", "银行", "地产", "保险", "券商",
        "煤炭", "有色", "钢铁", "汽车", "光伏", "锂电",
        "芯片", "人工智能", "互联网", "金融", "科技", "AI",
        "证券", "农业", "电力", "建筑", "传媒", "教育",
        "航空", "软件", "通信", "旅游",
    ],
    TAG_SECTOR_N_STOCK: [
        # 行業名兼庫中股票全名（"機器人"=300024）：精確全名命中，行業/個股
        # 雙解皆合理——裸用打歧義 tag 交下游 LLM/確認消歧，不直接打
        # stock_name，也不武斷打 sector_name
        "机器人",
    ],
    TAG_FILLER: [
        # ===== 高頻功能詞（extend / DFS 全覆蓋專用）=====
        # Step 6 DFS 要求片段全匹配才產出：gap 裡出現任一詞池外口語詞，
        # 整段放棄打 tag，同 gap 內的股票實體/關鍵詞一併丟失。以下收錄
        # 口語中最高頻、且對意圖判定零語義的功能詞作全覆蓋 filler，保住
        # "茅臺現在怎麼樣""你覺得呢""要不要跟一下"一類句子的實體提取。
        # 入池約束：零意圖語義（有語義的詞入對應 tag 詞池）；與更長的
        # 關鍵詞共形時長度優先級自動讓位（"還能"≠還+能、"為什麼"≠什麼）。
        "和", "下", "是", "再",
        "的", "买", "卖", "选", "了", "吧", "呢",
        "那", "这", "只", "支", "啊", "呀", "咯",
        "哦", "嘛", "么", "就", "请", "第", "个",
        # 情況：泛指名詞（"XX的情況/什麼情況"），零意圖語義
        "情况",
        # 人稱/疑問代詞（"我的茅臺"= 我+的+茅臺 三片段全覆蓋，實體才能
        # 從領屬短語中被提取；"幫我""我要"兩字詞在 clean 池優先整詞命中）
        "我", "你", "我们", "什么", "谁",
        # 情態/認知動詞（"你覺得""應該會漲"，對意圖無增量信號）
        "觉得", "感觉", "能", "会", "可以", "应该", "可能",
        # 否定/程度/關聯（"不太妙""又跌了""還是加倉"）
        "不", "没", "有", "很", "挺", "太", "还", "又", "也", "都", "还是", "或者",
        # 介詞/時地（"跟茅臺比""加到自選""在底部嗎"）
        "跟", "给", "让", "在",
    ],
    TAG_CORP_SUFFIX: [
        # 通用公司後綴（零區分度）：精確命中即打 corp_suffix tag 並跳過
        # 股票名掃描——子串匹配在名庫必然命中帶詞頭的全名（"公司"⊂中微
        # 公司、"集團"⊂上汽集團），命中是噪聲非信號；並作為可覆蓋片段
        # 參與 DFS 全覆蓋（"騰訊公司"→騰訊+公司）。帶區分度詞頭的
        # "蘋果公司"/"中芯國際"不受影響。區別於 filler：語義是公司名
        # 後綴而非填充詞，下游可單獨識別處理。僅 extend 不入 clean
        # （clean 正則會在 Step 5 從 token 中途撕出後綴）
        "公司", "集团", "控股", "股份", "国际",
    ],
}

_TAG_KEYWORD_LISTS: Dict[str, List[str]] = {
    tag: _TAG_KEYWORD_LISTS_CLEAN.get(tag, []) + _TAG_KEYWORD_LISTS_EXTEND.get(tag, [])
    for tag in {*_TAG_KEYWORD_LISTS_CLEAN, *_TAG_KEYWORD_LISTS_EXTEND}}

# 市場標識關鍵詞 → tag（從 _MARKET_KEYWORD_MAP 派生）
_MARKET_KW_TAG_MAP: Dict[str, str] = {
    kw: TAG_SUBJECT_MARKET
    for keywords in _MARKET_KEYWORD_MAP.values()
    for kw in keywords
}

# market keyword → Market 枚舉（反轉，O(1) 查詢）
_KW_TO_MARKET: Dict[str, Market] = {
    kw: mkt for mkt, keywords in _MARKET_KEYWORD_MAP.items() for kw in keywords
}

# keyword → tag（反轉 + 市場詞合併，供 _classify_keyword O(1) 查詢）
_KEYWORD_TAG_MAP: Dict[str, str] = {
    kw: tag for tag, kws in _TAG_KEYWORD_LISTS.items() for kw in kws
}
_KEYWORD_TAG_MAP.update(_MARKET_KW_TAG_MAP)

# 小寫歸一映射：關鍵詞大小寫不敏感分類的回退查詢點。詞池存儲形態混合
# （多數 ASCII 詞小寫、"AI"/"中證A500" 大寫），只做輸入 lower 回退會讓
# 大寫存儲詞的小寫形態（"ai賽道"/"中證a500"）整體失效，故關鍵詞側也
# 統一歸一到小寫。當前詞池無小寫同形詞；若將來出現會在本表靜默合併，
# 需保持詞池互斥。
_KEYWORD_TAG_MAP_LOWER: Dict[str, str] = {
    kw.lower(): tag for kw, tag in _KEYWORD_TAG_MAP.items()
}

# 含數字的枚舉關鍵詞（CJK+數字複合詞，如 "滬深300"/"中證1000"）：其數字段
# 與裸數字在文本中共形，若 Step 3 按裸數字提取，整詞將被拆成"前綴+數字"
# 永遠無法在 Step 4/5 命中。_split_by_codes 用本正則把關鍵詞 span 標記為
# 保護區，完全落在保護區內的數字候選 span 放行（部分重疊如 "滬深3000"
# 不適用，維持裸數字行為），整詞交 Step 4/5 關鍵詞分詞。
_DIGIT_KEYWORDS: Tuple[str, ...] = tuple(sorted(
    (
        kw
        for kws in _TAG_KEYWORD_LISTS.values()
        for kw in kws
        if any(ch.isdigit() for ch in kw) and any("\u3400" <= ch <= "\u9fff" for ch in kw)
    ),
    key=len,
    reverse=True,
))
# 大小寫不敏感編譯："中證a500" 與 "中證A500" 同受數字段保護（tag 分類側
# 的大小寫歸一見 _KEYWORD_TAG_MAP_LOWER）。
_DIGIT_KEYWORDS_RE = (
    re.compile("|".join(re.escape(kw) for kw in _DIGIT_KEYWORDS), re.IGNORECASE)
    if _DIGIT_KEYWORDS
    else None
)

# 全部純 ASCII 關鍵詞的大寫集合：Step 3 代碼候選的放行謂詞（大小寫不敏
# 感）——"PK"/"Buy"/"AI" 等關鍵詞形態不得被美股 ticker 正則摳走，否則
# 關鍵詞語義丟失、誤入代碼辨認（"HK"/"US" 非關鍵詞，仍照常作為代碼候選）
_ASCII_KEYWORD_UPPER: frozenset = frozenset(
    kw.upper() for kw in _KEYWORD_TAG_MAP if kw.isascii() and kw.isalpha()
)


# =========================================================================
# 正則編譯工具 — 全部從 _TAG_KEYWORD_LISTS 編譯
# =========================================================================

def _compile_kw_fragment(kw: str) -> str:
    """單個關鍵詞 → regex 片段：ASCII 詞包裹 (?i:) 並加詞邊界斷言，CJK 直接 escape。

    ASCII 關鍵詞一律全詞匹配：前後不得緊鄰字母/數字（"researching" 內的
    "research"、"markets" 內的 "market" 不被中途切出）。詞邊界由空格/標點
    （Step 2 已切分）或 CJK 鄰接界定，與 Step 6 的整詞精確查表語義一致。
    CJK 關鍵詞保持子串匹配——中文無空格分詞，"幫我分析一下"依賴中途命中。
    """
    if re.search(r"[A-Za-z]", kw):
        escaped = re.escape(kw)
        return f"(?i:(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9]))"
    return re.escape(kw)


def _compile_words(kws: Iterable[str], extra: str = "") -> re.Pattern:
    """關鍵詞集合 → 單個正則：長詞優先（"滬深300" 不被 "滬深" 截斷），
    extra 可追加原生 regex 片段（如 vs 詞邊界、多 token 跨詞模式）。"""
    fragments = {_compile_kw_fragment(k) for k in kws}
    if extra:
        fragments.add(extra)
    return re.compile("|".join(sorted(fragments, key=len, reverse=True)))


def _compile_kw_pattern(*tags: str, extra: str = "") -> re.Pattern:
    """從指定 tag 列表提取所有關鍵詞編譯為單個正則；市場類 tag
    （TAG_SUBJECT_MARKET）用市場詞池，extra 語義同 ``_compile_words``。"""
    kws: List[str] = [
        kw for tag in tags
        for kw in (_MARKET_KW_TAG_MAP.keys() if tag == TAG_SUBJECT_MARKET
                   else _TAG_KEYWORD_LISTS.get(tag, []))
    ]
    return _compile_words(kws, extra)


# Step 5 關鍵詞分詞正則（排除市場類 tag，Step 4 獨立處理，避免 "大港股份" 消歧失效）
_NON_MARKET_TAGS = frozenset({
    TAG_REQUEST, TAG_SUBJECT_RESEARCH, TAG_ACTION_RESEARCH, TAG_QUESTION,
    TAG_OPINION, TAG_SUBJECT_PORTFOLIO, TAG_ACTION_PORTFOLIO, TAG_ACTION_QUOTE,
    TAG_ACTION_QUOTE_FETCH,
    TAG_FOLLOWUP, TAG_COMPARISON, TAG_SECTOR, TAG_SECTOR_NAME,
    TAG_SECTOR_N_STOCK, TAG_TIME, TAG_FILLER,
})


def _compile_clean_kw_pattern(*tags: str) -> re.Pattern:
    """僅用 _TAG_KEYWORD_LISTS_CLEAN 編譯正則，排除可能混淆股票名的擴展關鍵詞。"""
    return _compile_words(
        kw for tag in tags for kw in _TAG_KEYWORD_LISTS_CLEAN.get(tag, []))


# Step 5 無歧義關鍵詞分詞正則（如"分析""走勢""持倉"等不可能混淆股票名的詞）
_CLEAN_KEYWORDS_PATTERN = _compile_clean_kw_pattern(*_NON_MARKET_TAGS)


# 純標點/空白過濾：至少含一個 CJK/字母/數字
_HAS_CONTENT_PATTERN = re.compile(r"[\u3400-\u9fffA-Za-z0-9]")

# 特殊標點集合（Step 1 分詞邊界）。排除 * - .：可能出現在股票名/代碼中（ST*、600519.SH）
_SPECIAL_PUNCT_CHARS = (
    "\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001\u201c\u201d\u2018\u2019"
    "\uff08\uff09\u3010\u3011\u300a\u300b\u2026\uff5e\u2014\uff0f\uff20"
    "\uff03\uff04\uff05\uff3e\uff06\uff0b\uff1d"
    ",!?;:\"'()[]{}<>/@#$%^&+=~`|\\\\"
)
# 空白（普通/全角空格、製表、換行）同為詞界一併切分：覆蓋 ASCII 詞與
# 代碼間的分隔（"tsla aapl"，小寫多詞同樣切分）；空白 token 無內容，
# 由管道末端 _HAS_CONTENT_PATTERN 過濾丟棄
_SPECIAL_PUNCT_RE = re.compile("[" + re.escape(_SPECIAL_PUNCT_CHARS) + r"|\s]")


# =========================================================================
# 意圖層文本模式與詞表 — resolver 消費的唯一定義處（本模塊是數據字典，
# 中文關鍵詞/正則/歸一映射不散落在流程代碼裡）
# =========================================================================

# T1 第一人稱領屬（個股路徑開關）："我的茅臺"是組合語境，"幫我看看茅臺"
# 的"我"是請求客套不算——限定"我"後緊鄰領屬/交易動詞
POSSESSIVE_RE = re.compile(r"我(?:的|持|买|卖|加|减|要|想|该|算)")

# 確認輪拒絕詞：取消全部待確認組
DECLINE_PATTERN = re.compile(
    r"^(?:不用了?|不需要|算了|算了吧|取消|不分析了?|错了|不是的?|换一个|无需)$"
)

# 消息消費型標點：Step 2 保證其必落在 token 邊界（，；。！？不出現於
# 股票名/代碼內），切分不撕裂任何 token
SUB_MESSAGE_PUNCT_RE = re.compile(r"[，。！？；,!?;]")

# 順序連接詞：之前下刀。並列連接詞（和/與/跟/及）不切——並列對象屬於
# 同一個任務（"茅臺和五糧液"是一個任務的兩個標的）
SEQUENCE_CONNECTIVES = ("然后", "其次", "接着", "顺便")
SEQUENCE_CONNECTIVE_RE = re.compile(
    "|".join(re.escape(c) for c in SEQUENCE_CONNECTIVES)
)

# 並列殘留防線的連接詞：空段以連接詞開頭且緊鄰前 token 是標的類
# （"茅臺|和西藏建工"）→ 剝離連接詞後的文本是並列名稱候選
COORDINATION_PREFIXES = ("还有", "以及", "和", "与", "跟", "及")

# 量詞單位後綴：裸數字後緊鄰這些字時是數量/價格語義（"我有300750元"），
# 不是股票代碼——數字提升的唯一排除條件
NUMERIC_UNIT_SUFFIXES = frozenset({
    "元", "万", "块", "股", "手", "份", "倍", "点", "年", "月", "日", "号", "折",
})

# A 股裸數字代碼的首碼白名單（0/3/6/4/8 開頭或 92 段北交所）
A_CODE_FIRST_DIGITS = frozenset("03648")

# 板塊泛稱後綴（TAG_SECTOR 詞池同源，不含指龍頭個股的"龍頭"）：
# "AI板塊"與"AI"是同一板塊的兩種表述，LLM 板塊名合入時按去後綴鍵去重
SECTOR_GENERIC_SUFFIXES = ("板块", "行业", "赛道", "概念", "题材")

# market 字段規範化：LLM 各種變體（大小寫/中英文/連字符）→ Market 枚舉
MARKET_NORMALIZE: Dict[str, Optional["Market"]] = {
    "a": Market.A, "a_share": Market.A, "a股": Market.A,
    "ashare": Market.A, "a-share": Market.A, "ashares": Market.A,
    "shanghai": Market.A, "shenzhen": Market.A,
    "hk": Market.HK, "港股": Market.HK,
    "hongkong": Market.HK, "hong_kong": Market.HK,
    "h-share": Market.HK, "hshare": Market.HK,
    "us": Market.US, "美股": Market.US,
    "american": Market.US, "america": Market.US, "usa": Market.US,
}

# LLM 意圖標籤的尾部標點修剪集（"Stock-Analysis。" → "stock_analysis"）
# 泛市場兜底槽名：市場代碼 → 中文槽名；無限定泛市場（"大盤"）
MARKET_SLOT_NAMES = {"a": "A股", "hk": "港股", "us": "美股"}
BROAD_MARKET_SLOT_NAME = "大盘"

INTENT_LABEL_TRIM_CHARS = ".,;:!?。，；：！？"

# LLM 回覆的 markdown code fence 清理
LLM_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*")


def normalize_intent_label(value: Any) -> Optional[str]:
    """規範化 LLM 返回的意圖標籤：空白/大小寫/連字符空格統一、去尾部
    標點，非法類型返回 None。"""
    if not isinstance(value, str):
        return None
    label = value.strip().lower().replace(" ", "_").replace("-", "_")
    label = label.strip(INTENT_LABEL_TRIM_CHARS)
    return label or None


def sector_dedup_key(name: str) -> str:
    """板塊名去重鍵：剝離尾部泛稱後綴並小寫（"AI板塊"与"AI"同鍵）。"""
    key = name.strip().lower()
    for suffix in SECTOR_GENERIC_SUFFIXES:
        if key.endswith(suffix) and len(key) > len(suffix):
            return key[: -len(suffix)]
    return key


LLM_SYSTEM_PROMPT = """你是股票分析助手的意圖分類器。把用戶當前消息分類為以下意圖之一：
- stock_analysis: 股票分析——指向具體股票的深度分析（"分析茅臺""茅臺為
  什麼跌""茅臺和五糧液哪個好"）
- sector_analysis: 板塊分析——行業/概念/板塊或市場整體的結構與觀點
  （"白酒板塊怎麼看""現在什麼風格"）
- portfolio_analysis: 持倉/自選數據查詢——唯一需要調用用戶賬戶數據的
  個性化任務（取賬戶標的集合）；對持倉的中性聚合問句（"我的持倉今天
  怎麼樣"）與持倉操作決策（"我的茅臺還該拿著嗎"）以它為終態；
  顯式動作詞作用於持倉泛指集合時它是管道首段（見約束）
- quote_lookup: 行情查詢——只要數據點不要觀點和分析（"茅臺多少錢""今天大盤
  怎麼樣""白酒板塊領跌的是誰"）
- general_chat: 閒聊、金融知識問答或與股票分析無關的請求（"什麼是市盈率"）
- followup: 對上一輪分析的追問/延續（"继续""再詳細說說""那五糧液呢"），
  未提及新標的

判定規則（按順序裁決）：
- 答案依賴該用戶的持倉/自選數據嗎？是 → portfolio_analysis。句中有"我"
  但答案對所有用戶相同（"我的茅臺基本面怎麼樣"）→ 不是；
- 只需報出價格/漲跌/成交/估值數字或漲跌排名 → quote_lookup；需要歸因、
  評價、比較、預測 → 分析類意圖（"为什么"是分析信號）；
- 主對象是具體股票 → stock_analysis；是板塊/行業/市場整體 →
  sector_analysis（板塊內具體某隻股票的深度問題仍歸 stock_analysis）。

只輸出一個 JSON 對象，不要輸出其它文字，字段如下：
{"intents": [
  {"intent": "上述之一", "confidence": 0到1的小數, "market": "a|hk|us|null",
   "stock_code": "主股票代碼或null", "stock_codes": ["提及的全部股票代碼，可選"],
   "sectors": ["提及的板塊/行業名，原文用詞，可選"],
   "unresolved_names": ["提及但無法對應任何真實證券的名稱，原文用詞，可選"]}
 ],
 "note": "不超過20字的理由"}

其它約束：
- intents 按用戶表達順序保序，逐元素獨立判定；一條消息含多個意圖時必須
  拆成多個元素——並列的不同對象（"看醫藥板塊，分析茅臺"）、順序動作
  （"查完A再分析B"）、同一標的的不同深度（"看股價和基本面"＝報數＋
  分析兩個意圖）都要拆；單一意圖也輸出單元素數組；
- 管道拆分原理（個人持倉/自選集合 × 顯式動作/數據/深度詞）：主體為
  顯式標的（"持倉的茅臺的股價"——執行不需賬戶數據）＝單一動作意圖；
  主體為組合泛指（"我持倉的股票的股價""分析我所有的持倉股票""自選股
  今天漲了多少"）＝拆分為兩個意圖——持倉分析（取賬戶標的集合）在前、
  對應動作意圖（行情查詢/股票分析等普遍化流程，主體＝前一意圖的集合，
  無需填代碼）在後，保序；對持倉本身的中性問句（無顯式動作詞）＝
  單一持倉分析；
- "followup" 是追問偽標籤（不是意圖成員）：延續上一輪或數組前一個
  元素的意圖，整條回覆就是追問時作為唯一元素使用，與其它意圖混在
  同一數組時直接寫要延續的具體意圖；
- message 可能是多任務消息中的一個片段：current_stock 是當前討論標的
  （同消息前序片段已確定，或會話鎖定的當前股票）；片段自身無標的而
  語義指向它（如"和市盈率"）時，按片段語義判定 intent 並在 stock_code
  返回 current_stock 的代碼；
- 各意圖的候選股票若有用戶所指，在該元素 stock_code 返回其代碼；多股
  比較/多標的在該元素 stock_codes 返回全部代碼；
- 板塊/行業意圖在 sectors 返回原文中的板塊名（不要自行改寫措辭）；
- 提及的標的名若確定不是真實證券（如生造名"你好股份"），原文放入
  unresolved_names——不要為它編造代碼，也不要靜默忽略；
- 不要編造代碼：沒有把握時 stock_code 返回 null 並降低該意圖置信度。

示例（輸入＝user 消息的 JSON 載荷，輸出＝要求的全量 JSON；代碼一律規範
拼寫：A股 6 位裸數字、港股 HK+5 位、美股大寫 ticker）：

輸入: {"message": "茅臺多少錢", "current_stock": null}
輸出: {"intents": [{"intent": "quote_lookup", "confidence": 0.95, "market": null, "stock_code": "600519", "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "詢價"}

輸入: {"message": "茅臺和五糧液哪個好", "current_stock": null}
輸出: {"intents": [{"intent": "stock_analysis", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": ["600519", "000858"], "sectors": [], "unresolved_names": []}], "note": "比較是一個意圖，多標的入stock_codes，不拆分"}

輸入: {"message": "白酒板塊怎麼看", "current_stock": null}
輸出: {"intents": [{"intent": "sector_analysis", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": ["白酒"], "unresolved_names": []}], "note": "板塊觀點"}

輸入: {"message": "我的持倉今天怎麼樣", "current_stock": null}
輸出: {"intents": [{"intent": "portfolio_analysis", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "依賴賬戶數據"}

輸入: {"message": "幫我看下我持倉的股票的股價", "current_stock": null}
輸出: {"intents": [{"intent": "portfolio_analysis", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}, {"intent": "quote_lookup", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "泛指主體拆取持倉＋報價"}

輸入: {"message": "幫我分析我所有的持倉股票", "current_stock": null}
輸出: {"intents": [{"intent": "portfolio_analysis", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}, {"intent": "stock_analysis", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "泛指主體拆取持倉＋分析"}

輸入: {"message": "什麼是市盈率", "current_stock": null}
輸出: {"intents": [{"intent": "general_chat", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "知識問答"}

輸入: {"message": "再展開講講", "current_stock": {"code": "600519", "name": "贵州茅台", "market": "a"}}
輸出: {"intents": [{"intent": "followup", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "追問延續上輪"}

輸入: {"message": "和市盈率", "current_stock": {"code": "HK00700", "name": "腾讯控股", "market": "hk"}}
輸出: {"intents": [{"intent": "quote_lookup", "confidence": 0.85, "market": "hk", "stock_code": "HK00700", "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "片段無標的，指稱current_stock"}

輸入: {"message": "看一下茅臺股價和基本面", "current_stock": null}
輸出: {"intents": [{"intent": "quote_lookup", "confidence": 0.9, "market": null, "stock_code": "600519", "stock_codes": [], "sectors": [], "unresolved_names": []}, {"intent": "stock_analysis", "confidence": 0.9, "market": null, "stock_code": "600519", "stock_codes": [], "sectors": [], "unresolved_names": []}], "note": "同標的不同深度拆兩個意圖"}

輸入: {"message": "查完五糧液再看下醫藥板塊", "current_stock": null}
輸出: {"intents": [{"intent": "quote_lookup", "confidence": 0.9, "market": null, "stock_code": "000858", "stock_codes": [], "sectors": [], "unresolved_names": []}, {"intent": "quote_lookup", "confidence": 0.9, "market": null, "stock_code": null, "stock_codes": [], "sectors": ["医药"], "unresolved_names": []}], "note": "順序動作按表達順序拆分"}"""


# 意圖層文本模式與詞表（resolver 消費）的補充正則 ==========================

# 意圖詞並集（clean 池）：文本級"有無意圖信號"判據。用 clean 池而非
# 全池——extend 詞（"看下"）在 unknown_token 陪葬場景仍可能出現在文本里，clean
# 命中才構成可靠意圖證據（"分析ZZZZ"有信號不觸發 LLM、"順便看下SOFI"
# 的"看下"不在 clean 池→無信號觸發兜底）
INTENT_WORD_RE = _compile_clean_kw_pattern(
    "request", "subject_research", "action_research", "question",
    "opinion", "subject_portfolio", "action_portfolio", "action_quote",
    "followup", "comparison",
)


# 裸數字段（確認輪短碼解讀："09988" → HK09988）
BARE_DIGIT_RE = re.compile(r"(?<!\d)(\d{4,6})(?!\d)")


def _classify_keyword(token_text: str) -> str:
    """查 _KEYWORD_TAG_MAP 取語義標籤；未精確命中按小寫歸一表回退
    （大小寫不敏感與 (?i:) 編譯聲明同構，見 _KEYWORD_TAG_MAP_LOWER 註釋）；
    未命中返回空串。"""
    tag = _KEYWORD_TAG_MAP.get(token_text)
    if tag:
        return tag
    return _KEYWORD_TAG_MAP_LOWER.get(token_text.lower(), "")


# =========================================================================
# Token — 分詞結構體，text + tag
# =========================================================================


@dataclass(frozen=True)
class Token:
    """分詞結構體：文本 + 語義標籤 + 可選的已解析股票實體。

    frozen=True 使 Token 可哈希；tag 為空表示未識別；stocks 透傳已解析實體
    避免下游重複解析。stocks 構造時傳 list 會被 __post_init__ 歸一為 tuple
    （frozen 字段值必須可哈希），下游按序列消費不受影響。
    """
    text: str
    tag: str = ""
    stocks: Optional[Tuple["Stock", ...]] = None

    def __post_init__(self) -> None:
        if isinstance(self.stocks, list):
            object.__setattr__(self, "stocks", tuple(self.stocks))


# =========================================================================
# WebIntentResolution — 單次意圖識別的完整結果
# =========================================================================


def _coerce_stock(entry: Any) -> Optional["Stock"]:
    """構造載荷條目（Stock / str 代碼 / dict）→ Stock。

    空串與缺 code 的 dict 返回 None（形狀異常剔除——與 resolver
    ``_stock_from_payload`` 的缺鍵守衛同口徑）；其餘類型原樣透傳：
    構造器面對的是進程內對象，不做形態審判，鴨子對象交由消費側按
    ``.code`` 契約使用。
    """
    if isinstance(entry, str):
        return Stock(code=entry) if entry else None
    if isinstance(entry, dict):
        return (Stock(code=entry["code"], name=entry.get("name", ""),
                      market=entry.get("market", ""))
                if entry.get("code") else None)
    return entry


@dataclass
class WebIntentResolution:
    """一次 Web Chat 意圖識別流程的完整產出。

    各字段的含義：
    - ``intent``: 最終的意圖標籤（來自 ALL_WEB_INTENTS 之一）
    - ``confidence``: 置信度 [0.0, 1.0]，影響是否需要用戶確認。注意：是
      按決策路徑賦的常量（顯式代碼 0.9、關鍵詞獨高 0.85、LLM 上限 0.75…），
      表達"路徑可靠程度"而非校準概率。
    - ``source``: 意圖來源標識
        - ``"rule"`` — 正則/規則直接判定（高置信直達，未調 LLM）
        - ``"llm"`` — LLM 分類結果
        - ``"llm_failed"`` — LLM 兜底已觸發但調用失敗（超時/異常/壞
          輸出），結果退回規則判定；置信度與 stocks 與 rule 同源，
          排障時據此區分"未調 LLM"與"調了但失敗"
        - ``"context"`` — 從會話上下文中繼承（如繼承 current_stock 推斷為追問）
        - ``"confirmation"`` — 用戶對上一個待確認動作的響應
    - ``stocks``: 已解析出的置信度較高的股票或板塊實體——能精確解析出
      的股票列表（已去重），每項為 Stock(code, name, market)
    - ``sectors``: 板塊槽位——執行端統一消費的板塊/市場對象（去重保序）：
      具名板塊用板塊名（"分析白酒板塊" → ["白酒"]）；泛市場/指數場景
      用指數名原文（"研究上證指數" → ["上证"]）或市場名（"分析大A行情"
      → ["A股"]，無限定 → ["大盘"]）；個股路徑為空列表
    - ``candidates``: 已解析出的帶有歧義的股票實體——能解析名字，但
      股票名稱有歧義時的候選列表，每項為 Stock(code, name, market)
    - ``unresolved_names``: 未知的股票名——確定不存在的指稱（A 股全量
      庫未命中的錯誤代碼、並列未知名稱）：確認機制僅收錄可判定市場的
      確定非法指稱，前提是系統有把握判定用戶錯了
    - ``unverified_codes``: 未知的股票代碼——非全量庫市場（hk/us 精選
      庫）未命中的存疑代碼：無法判定合法與否，不做確認，作為未驗證
      標的透傳執行端實查（行情工具/Futu 數據源有真實判定能力）；
      查無此股由 Agent 回覆
    - ``needs_confirmation``: True 表示該意圖需要用戶確認後才能執行
    - ``reason``: 需要確認時的原因說明（如 "ambiguous_stock_name" / "low_confidence" / "stock_unresolved"）
    - ``pending_action``: 需要用戶執行的確認動作描述，供 SSE 層發送
      action_required 事件。多輪確認鏈路的運行時鍵（original_request /
      resolved_stocks / confirmed）寄生在其內部
    - ``source_request``: 當前的 sub_message 文本——該任務的來源子消息
      （多任務切分/同句分解的任務各自攜帶；確認產物無當前子消息，
      為空串）
    - ``all_tags_recognized``: 子消息全部 token 均帶語義標籤（分詞層無
      空 tag 殘段）——規則視野完備性判據，由第四步單源設置，與置信度
      聯合構成 LLM 兜底豁免（``_should_use_llm``）
    """

    intent: WebIntent
    confidence: float
    source: str = "rule"       # 默認為規則來源
    stocks: List[Stock] = field(default_factory=list)
    sectors: List[str] = field(default_factory=list)   # 板塊名槽位（去重保序）
    candidates: List[Stock] = field(default_factory=list)
    unresolved_names: List[str] = field(default_factory=list)
    unverified_codes: List[str] = field(default_factory=list)  # hk/us 存疑代碼，透傳執行端實查
    needs_confirmation: bool = False
    reason: str = ""
    pending_action: Optional[Dict[str, Any]] = None
    source_request: str = ""             # 當前的 sub_message（任務來源子消息）
    tokens: List[str] = field(default_factory=list)  # 對應的tokens
    # 子消息全部 token 均帶語義標籤（分詞層無空 tag 殘段）——規則視野
    # 完備性判據，由第四步單源設置，與置信度聯合構成 LLM 兜底豁免
    # （見 resolver _should_use_llm）
    all_tags_recognized: bool = True
    # 規則裁決自知"單任務表達不完"：quote 詞與強分析詞共存（深度被裁決
    # 序吸收）——由第四步單源設置，_should_use_llm 見它即取消高置信豁
    # 免，交 LLM 多意圖複核
    multi_intent_hint: bool = False
    inherited_stock_code: str = ""    # 從會話/請求上下文繼承的當前股票代碼（#1619）；歷史標的的持久化通道是會話鍵 recent_stocks，任務不攜帶副本

    def __post_init__(self) -> None:
        """stocks/candidates 統一過 ``_coerce_stock``：str 代碼與 dict 載荷
        歸一為 Stock，形狀異常條目剔除（兩個列表同一契約、同一口徑）。"""
        self.stocks = [s for s in map(_coerce_stock, self.stocks) if s]
        self.candidates = [s for s in map(_coerce_stock, self.candidates) if s]

    @property
    def primary_stock_code(self) -> str:
        """注入 stock-scope 的主股票代碼。

        單代碼直接返回；多代碼（比較場景）返回空串交執行端處理——絕不
        返回歷史標的，否則"對比000858和300750"會錯誤鎖定上一輪的股票；
        無代碼時返回 inherited_stock_code（#1619 鎖定股置頂，退
        recent_stocks[0]）保持鎖定。
        """
        if len(self.stocks) == 1:
            return self.stocks[0].code
        if len(self.stocks) >= 2:
            return ""
        return self.inherited_stock_code
