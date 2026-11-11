# -*- coding: utf-8 -*-
"""新聞檢索未執行或零命中時的報告披露文案。

單一事實來源：字符串拼接渲染器（src/notification.py）與模板渲染鏈路
（src/services/report_renderer.py + templates/*.j2）共用本模塊，避免
同一份分析結果在部分渠道披露、在另一些渠道沉默。

披露斷言的是「本次結論有沒有用到新聞面證據」，因此第一依據是分析實際收到的消息面
證據（news_context）是否非空，而不是搜索命中了幾條。news_context 可能來自實時檢索、
社交情緒或本地已落庫的資訊池，後兩者同樣進入模型輸入卻不產生搜索命中；只看計數會把
這類分析誤報成「未納入新聞面證據」（review OR-COR-2e4b9d61）。

news_result_count 因此退居第二位，只用來解釋「確實沒有證據」時的原因：
    None  未執行檢索（未配置搜索渠道）
    0     執行了檢索但零命中（限流、全部失敗等）
    > 0   實時檢索有命中（此時證據必然存在）
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Optional, Tuple

from src.report_language import SUPPORTED_REPORT_LANGUAGES

_ZH_NOT_CONFIGURED = "⚠️ 未配置搜索渠道，本次分析未納入新聞面證據。"
_EN_NOT_CONFIGURED = (
    "⚠️ No news search channel is configured; "
    "this analysis does not incorporate news-based evidence."
)
_ZH_ZERO_RESULTS = "⚠️ 本次未獲取到可用的新聞面數據，以下結論未納入新聞維度證據。"
_EN_ZERO_RESULTS = (
    "⚠️ No news data could be retrieved for this run; "
    "the conclusions below do not incorporate news-based evidence."
)
_KO_NOT_CONFIGURED = (
    "⚠️ 뉴스 검색 채널이 설정되지 않아 이번 분석에는 "
    "뉴스 근거를 반영하지 않았습니다."
)
_KO_ZERO_RESULTS = (
    "⚠️ 이번 분석에서 사용 가능한 뉴스 데이터를 가져오지 못해 "
    "아래 결론에는 뉴스 근거를 반영하지 않았습니다."
)

_DISCLOSURES = {
    "zh": (_ZH_NOT_CONFIGURED, _ZH_ZERO_RESULTS),
    "en": (_EN_NOT_CONFIGURED, _EN_ZERO_RESULTS),
    "ko": (_KO_NOT_CONFIGURED, _KO_ZERO_RESULTS),
}

if set(_DISCLOSURES) != set(SUPPORTED_REPORT_LANGUAGES):
    raise RuntimeError(
        "Empty-news disclosures must cover every SUPPORTED_REPORT_LANGUAGES value"
    )


def persisted_news_result_state(
    raw_result: Any,
    context_snapshot: Any = None,
) -> Tuple[Optional[int], bool]:
    """從持久化載荷恢復計數及其可信度。

    新記錄的 raw_result 明確保存三態值；舊記錄可在 context_snapshot 中留下
    0 / >0 計數。兩處都沒有字段時只能判定為 legacy unknown，不能把缺字段
    當成明確的 None。
    """
    if isinstance(raw_result, Mapping):
        if raw_result.get("news_result_count_known") is False:
            return None, False
        if "news_result_count" in raw_result:
            return raw_result.get("news_result_count"), True

    if isinstance(context_snapshot, Mapping) and "news_result_count" in context_snapshot:
        return context_snapshot.get("news_result_count"), True

    return None, False


def news_evidence_present(*sources: Any) -> bool:
    """本次分析是否真的收到了消息面證據。任一來源為真即為真。

    每個來源要麼是真實條數（int），要麼是**已排除佔位文本**的內容字符串。
    實時檢索、社交情緒、本地資訊池各算一路，pipeline 兩條路徑都用本函數，
    不要在別處另寫判斷。

    **不要把 pipeline 拼好的整段 news_context 傳進來。**
    `src/search_service.py` 的 `format_intel_report()` 在零命中時仍會輸出
    `【XX 情報搜索結果】` 標題和每個維度的「未找到相關信息」佔位文本，整段永遠
    非空；用它判定會把「搜了但一條沒拿到」翻成「有證據」，恰好吞掉本模塊要補的
    披露（review OR-COR-8f4c2d1b）。判定必須按來源逐個登記，不能聞字符串。
    """
    for source in sources:
        if source is None or isinstance(source, bool):
            if source:
                return True
            continue
        if isinstance(source, (int, float)):
            if source > 0:
                return True
            continue
        if str(source).strip():
            return True
    return False


def _disclosure_for_state(
    news_result_count: Optional[int],
    *,
    known: bool,
    evidence_present: bool,
    language: str,
) -> Optional[str]:
    try:
        not_configured, zero_results = _DISCLOSURES[language]
    except KeyError as exc:
        raise ValueError(f"Unsupported report language for empty-news disclosure: {language}") from exc

    if not known:
        return None
    # 證據存在就不提示，無論它來自哪一路來源；計數只解釋「沒有證據」的原因。
    if evidence_present:
        return None
    if news_result_count is None:
        return not_configured
    if news_result_count == 0:
        return zero_results
    return None


def empty_news_disclosure(result: Any, language: str = "zh") -> Optional[str]:
    """未執行或零命中時返回對應提示；正常命中時返回 None。

    判定必須獨立於模型是否產出了消息面文字：analyzer 的輸出 schema 即使
    在沒有新聞時也會要求填 market_sentiment / hot_topics，若以這些字段
    是否為空來決定，就會出現「展示模型生成的情緒判斷、卻隱瞞無新聞證據」
    這一最糟的組合。
    """
    if isinstance(result, Mapping):
        news_result_count, known = persisted_news_result_state(result)
        evidence_present = persisted_news_evidence_present(result, news_result_count)
    else:
        news_result_count = getattr(result, "news_result_count", None)
        known = getattr(result, "news_result_count_known", True)
        evidence_present = bool(getattr(result, "news_evidence_present", False))
    return _disclosure_for_state(
        news_result_count,
        known=known,
        evidence_present=evidence_present,
        language=language,
    )


def empty_news_disclosure_from_stored(
    raw_result: Any,
    context_snapshot: Any,
    language: str = "zh",
) -> Optional[str]:
    """為歷史/API 入口從持久化載荷生成披露；舊記錄缺字段時保持靜默。"""
    news_result_count, known = persisted_news_result_state(raw_result, context_snapshot)
    return _disclosure_for_state(
        news_result_count,
        known=known,
        evidence_present=persisted_news_evidence_present(raw_result, news_result_count),
        language=language,
    )


def persisted_news_evidence_present(raw_result: Any, news_result_count: Optional[int]) -> bool:
    """從持久化載荷恢復「本次分析是否用到新聞面證據」。

    本 PR 之前寫入的記錄沒有該字段，此時退回按計數推斷：>0 說明確有證據，
    其餘按無證據處理，與該記錄當時的報告表現一致，不會追溯改變舊報告。
    """
    if isinstance(raw_result, Mapping) and "news_evidence_present" in raw_result:
        return bool(raw_result.get("news_evidence_present"))
    return bool(news_result_count)
