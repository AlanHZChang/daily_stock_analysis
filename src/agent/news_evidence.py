# -*- coding: utf-8 -*-
"""Agent 運行期實際消費的新聞證據計數。

empty-news disclosure 必須反映「本次分析真正用到的新聞證據」。Agent 模式下情報
由 Agent 自己調用搜索工具取得，因此計數只能來自這些工具的真實返回，不能用分析
結束後補打的一次 `search_stock_news()` 代替：那次補查與 Agent 消費的證據無關，
兩個方向都會失真——Agent 明明用了新聞卻因補查失敗而被標成「未納入新聞面證據」，
或 Agent 沒拿到新聞卻因補查有結果而被錯誤地不提示。

用法：pipeline 在 `executor.run()` 前後開啟並讀取作用域；搜索工具在返回結果時
記錄本次真正交給 Agent 的條數。工具在 ThreadPoolExecutor 中執行，
`src/agent/runner.py` 通過 `contextvars.copy_context()` 提交任務，因此 ContextVar
中的**可變**累加器在工作線程與父線程之間是同一個對象，工具線程裡的累加對
pipeline 可見。請勿把它換成保存不可變值的 ContextVar，那樣父線程讀不到。
"""

from __future__ import annotations

import logging
import threading
from contextvars import ContextVar, Token
from typing import Optional

logger = logging.getLogger(__name__)


class NewsEvidenceAccumulator:
    """線程安全地累計 Agent 本次分析實際消費的新聞條數。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total = 0

    def record(self, count: int) -> None:
        """記錄一次搜索工具真實返回的條數；零命中也必須記錄（記 0）。"""
        try:
            value = int(count)
        except (TypeError, ValueError):
            value = 0
        if value < 0:
            value = 0
        with self._lock:
            self._total += value

    @property
    def total(self) -> int:
        with self._lock:
            return self._total

    def resolve(self, *, search_available: bool) -> Optional[int]:
        """收斂成 `news_result_count` 的三態語義。

        - 搜索渠道不可用：`None`，即未執行檢索，披露「未配置搜索渠道」。
        - 渠道可用：從 `0` 起步，Agent 調用工具拿到多少算多少。

        渠道可用但 Agent 一次都沒搜的情況刻意歸入 `0` 而不是 `None`：此時報告
        確實沒有新聞證據，但「未配置搜索渠道」是與事實相反的解釋，而「未獲取到
        可用的新聞面數據」在這兩種子情形下都成立。
        """
        if not search_available:
            return None
        return self.total


_CURRENT_ACCUMULATOR: ContextVar[Optional[NewsEvidenceAccumulator]] = ContextVar(
    "news_evidence_accumulator",
    default=None,
)


def activate_news_evidence_scope() -> Token:
    """開啟一次 Agent 運行的證據作用域，返回重置令牌。"""
    return _CURRENT_ACCUMULATOR.set(NewsEvidenceAccumulator())


def get_current_news_evidence() -> Optional[NewsEvidenceAccumulator]:
    return _CURRENT_ACCUMULATOR.get()


def reset_news_evidence_scope(token: Optional[Token]) -> None:
    if token is None:
        return
    try:
        _CURRENT_ACCUMULATOR.reset(token)
    except Exception as exc:  # pragma: no cover - 防禦性 fail-open
        logger.warning("news evidence scope reset failed: %s", exc)


def record_news_evidence(count: int) -> None:
    """供 Agent 搜索工具調用。

    沒有活動作用域時靜默忽略：非 Agent 路徑自己直接維護計數，工具也可能在
    Agent 分析之外被調用（例如報告頁的後續資訊檢索），那些都不應影響本次分析的
    披露判定。
    """
    accumulator = _CURRENT_ACCUMULATOR.get()
    if accumulator is None:
        return
    accumulator.record(count)
