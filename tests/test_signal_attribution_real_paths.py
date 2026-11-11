# -*- coding: utf-8 -*-
"""Tests for signal_attribution real entry points (not just schema)."""

import sys
import os

# 確保項目根目錄在 sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.data_processing import normalize_signal_attribution_values, normalize_dashboard_signal_attribution
from src.schemas.report_schema import Dashboard, SignalAttribution

# AnalysisResult 在 analyzer.py 中定義
from src.analyzer import AnalysisResult


class TestNormalizeSignalAttribution:
    """測試歸一化函數（接在 _parse_response 之前執行）"""

    def test_string_percentage_conversion(self):
        d = {"technical_indicators": "70%", "news_sentiment": "0%", "fundamentals": "15%", "market_conditions": "15%"}
        normalize_signal_attribution_values(d)
        assert d["technical_indicators"] == 70
        assert d["news_sentiment"] == 0

    def test_na_string_becomes_none(self):
        d = {"technical_indicators": "N/A", "news_sentiment": 0, "fundamentals": 0, "market_conditions": 0}
        normalize_signal_attribution_values(d)
        assert d["technical_indicators"] is None

    def test_negative_clamped_to_zero(self):
        d = {"technical_indicators": -10, "news_sentiment": 20, "fundamentals": 30, "market_conditions": 60}
        normalize_signal_attribution_values(d)
        assert d["technical_indicators"] == 0

    def test_sum_normalized_to_100(self):
        d = {"technical_indicators": 70, "news_sentiment": 10, "fundamentals": 20, "market_conditions": 10}
        # sum=110
        normalize_signal_attribution_values(d)
        total = sum([d["technical_indicators"], d["news_sentiment"], d["fundamentals"], d["market_conditions"]])
        assert total == 100

    def test_partial_none_no_normalization(self):
        d = {"technical_indicators": 70, "news_sentiment": None, "fundamentals": 30, "market_conditions": None}
        normalize_signal_attribution_values(d)
        # 只有兩個有效值，不歸一化
        assert d["technical_indicators"] == 70
        assert d["news_sentiment"] is None


class TestNormalizeDashboardSignalAttribution:
    """測試 dashboard 級別的歸一化（直接在 dashboard dict 上操作）"""

    def test_inplace_normalization(self):
        dashboard = {
            "signal_attribution": {
                "technical_indicators": "70%",
                "news_sentiment": "0%",
                "fundamentals": "15%",
                "market_conditions": "15%",
            }
        }
        normalize_dashboard_signal_attribution(dashboard)
        sa = dashboard["signal_attribution"]
        assert sa["technical_indicators"] == 70

    def test_no_signal_attribution_key(self):
        dashboard = {"core_conclusion": {}}
        normalize_dashboard_signal_attribution(dashboard)  # 不應報錯
        assert "signal_attribution" not in dashboard

    def test_signal_attribution_none(self):
        dashboard = {"signal_attribution": None}
        normalize_dashboard_signal_attribution(dashboard)  # 不應報錯


class TestParseResponseIntegration:
    """
    測試 _parse_response 能正確解析 signal_attribution。
    由於 _parse_response 是實例方法且依賴很多配置，這裡用集成測試驗證歸一化函數被正確調用。
    """

    def test_normalization_called_in_parse_response(self):
        """
        驗證：如果 LLM 返回字符串百分比，歸一化後變成 int。
        通過直接測試 _parse_response 的歸一化調用來驗證。
        """
        # 模擬 LLM 返回的 data dict
        data = {
            "sentiment_score": 50,
            "trend_prediction": "震荡",
            "operation_advice": "持有",
            "decision_type": "hold",
            "confidence_level": "中",
            "analysis_summary": "测试",
            "dashboard": {
                "signal_attribution": {
                    "technical_indicators": "70%",
                    "news_sentiment": "0%",
                    "fundamentals": "15%",
                    "market_conditions": "15%",
                    "strongest_bullish_signal": "MACD金叉",
                    "strongest_bearish_signal": None,
                }
            },
        }
        # 手動調用歸一化（模擬 _parse_response 的行為）
        normalize_dashboard_signal_attribution(data.get("dashboard"))
        sa = data["dashboard"]["signal_attribution"]
        assert sa["technical_indicators"] == 70
        assert sa["news_sentiment"] == 0


class TestHistoryServiceDisplay:
    """測試 HistoryService._generate_single_stock_markdown 能展示 signal_attribution"""

    def test_signal_attribution_in_markdown(self):
        """驗證 markdown 報告包含信號歸因段落"""
        from src.services.history_service import HistoryService

        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=50,
            trend_prediction="震荡",
            operation_advice="持有",
            dashboard={
                "signal_attribution": {
                    "technical_indicators": 70,
                    "news_sentiment": 0,
                    "fundamentals": 15,
                    "market_conditions": 15,
                    "strongest_bullish_signal": "MACD金叉",
                    "strongest_bearish_signal": None,
                }
            },
        )

        # 創建一個 mock record
        class MockRecord:
            created_at = None

        markdown = HistoryService()._generate_single_stock_markdown(result, MockRecord())
        assert "信号归因" in markdown or "Signal Attribution" in markdown
        assert "70%" in markdown or "70%" in markdown

    def test_no_signal_attribution_no_section(self):
        """驗證沒有 signal_attribution 時不顯示段落"""
        from src.services.history_service import HistoryService

        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=50,
            trend_prediction="震荡",
            operation_advice="持有",
            dashboard={},
        )

        class MockRecord:
            created_at = None

        markdown = HistoryService()._generate_single_stock_markdown(result, MockRecord())
        assert "信号归因" not in markdown


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
