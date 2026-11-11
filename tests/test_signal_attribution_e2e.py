"""
端到端測試：signal_attribution 完整契約收斂測試。

驗證以下路徑：
1. LLM raw JSON → _parse_response() → AnalysisResult.dashboard (歸一化生效)
2. AnalysisResult.dashboard → notification (展示正確)
3. AnalysisResult.dashboard → Jinja2 template (渲染正確)
4. AnalysisResult.dashboard → HistoryService markdown (渲染正確)
5. check_content_integrity() (契約檢查)
"""
import sys
import os
import pytest
import json

# 添加 src 到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.analyzer import AnalysisResult, check_content_integrity
from src.utils.data_processing import normalize_dashboard_signal_attribution
from src.agent.runner import parse_dashboard_json
from src.services.report_renderer import render


class TestSignalAttributionE2E:
    """端到端測試：驗證 signal_attribution 在所有路徑中正確工作"""

    def _make_dashboard_with_signal_attr(self, signal_attr):
        """創建包含 signal_attribution 的 dashboard dict"""
        return {
            "core_conclusion": {
                "one_sentence": "测试结论",
                "signal": "buy",
                "confidence": "中",
            },
            "intelligence": {
                "risk_alerts": ["测试风险"],
            },
            "signal_attribution": signal_attr,
        }

    def _make_result(self, dashboard):
        """創建 AnalysisResult"""
        return AnalysisResult(
            code="600519",
            name="测试股票",
            sentiment_score=50,
            trend_prediction="震荡",
            operation_advice="持有",
            decision_type="hold",
            confidence_level="中",
            dashboard=dashboard,
            analysis_summary="测试摘要",
        )

    # ========== 測試 1: _parse_response() 歸一化 ==========
    def test_normalize_called_in_parse_response(self):
        """
        測試 _parse_response() 中歸一化函數被調用。

        驗證：
        1. 輸入貢獻度為字符串 "30%" → 歸一化後變為 int 30
        2. 輸入貢獻度之和不為 100 → 歸一化後變為之和=100
        """
        from src.analyzer import GeminiAnalyzer

        # 創建 analyzer 實例
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)

        # 模擬 LLM 返回的 JSON（貢獻度為字符串，總和≠100）
        response_text = json.dumps({
            "sentiment_score": 50,
            "trend_prediction": "震荡",
            "operation_advice": "持有",
            "decision_type": "hold",
            "confidence_level": "中",
            "analysis_summary": "测试",
            "dashboard": {
                "core_conclusion": {"one_sentence": "测试", "signal": "hold", "confidence": "中"},
                "intelligence": {"risk_alerts": []},
                "signal_attribution": {
                    "technical_indicators": "30%",
                    "news_sentiment": 20,
                    "fundamentals": 30,
                    "market_conditions": 10,  # 總和=90，且有一個是字符串
                    "strongest_bullish_signal": "测试看涨",
                    "strongest_bearish_signal": "测试看空",
                },
            },
        })

        # 調用 _parse_response()
        result = analyzer._parse_response(response_text, "600519", "测试")

        # 驗證歸一化已執行
        dash = result.dashboard
        assert isinstance(dash, dict), "dashboard 应该是 dict"

        signal_attr = dash.get("signal_attribution")
        assert signal_attr is not None, "signal_attribution 应该存在"

        # 驗證字符串已轉為 int
        assert isinstance(signal_attr.get("technical_indicators"), int), "technical_indicators 应该是 int"

        # 驗證總和=100
        total = sum([
            signal_attr.get("technical_indicators", 0),
            signal_attr.get("news_sentiment", 0),
            signal_attr.get("fundamentals", 0),
            signal_attr.get("market_conditions", 0),
        ])
        assert total == 100, f"贡献度之和应该=100，实际={total}"

    # ========== 測試 2: notification 渲染 ==========
    def test_notification_renders_signal_attribution(self):
        """
        測試 notification.py 中 generate_dashboard_report() 正確渲染 signal_attribution。

        驗證：
        1. signal_attribution 存在時，通知中包含"信號歸因"段落
        2. 四個貢獻度都正確顯示
        """
        from src.notification import NotificationService

        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD金叉",
            "strongest_bearish_signal": "成交量萎缩",
        }
        dashboard = self._make_dashboard_with_signal_attr(signal_attr)
        result = self._make_result(dashboard)

        # 調用 generate_dashboard_report()
        notification = NotificationService()
        report = notification.generate_dashboard_report([result], [dashboard])

        # 驗證包含信號歸因段落
        assert "信号归因" in report or "Signal Attribution" in report, "通知应包含信号归因段落"
        assert "35%" in report, "通知应显示 technical_indicators=35%"
        assert "25%" in report, "通知应显示 news_sentiment=25%"
        assert "20%" in report, "通知应显示 fundamentals=20%"
        assert "20%" in report, "通知应显示 market_conditions=20%"
        assert "MACD金叉" in report, "通知应显示 strongest_bullish_signal"

    # ========== 測試 3: Jinja2 模板渲染 ==========
    def test_jinja2_template_renders_signal_attribution(self):
        """
        測試 templates/report_markdown.j2 正確渲染 signal_attribution。

        驗證：
        1. signal_attribution 存在時，模板輸出中包含歸因權重
        2. 四個貢獻度都正確顯示
        """
        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD金叉",
        }
        result = self._make_result(self._make_dashboard_with_signal_attr(signal_attr))

        out = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        assert out is not None
        assert "35%" in out
        assert "MACD金叉" in out

    def test_parse_dashboard_json_normalizes_nested_dashboard_payload(self):
        """Agent JSON can return a full report object with nested dashboard."""
        payload = json.dumps({
            "dashboard": {
                "signal_attribution": {
                    "technical_indicators": "70%",
                    "news_sentiment": "10%",
                    "fundamentals": "10%",
                    "market_conditions": "10%",
                }
            }
        })

        parsed = parse_dashboard_json(payload)

        assert parsed is not None
        signal_attr = parsed["dashboard"]["signal_attribution"]
        assert signal_attr["technical_indicators"] == 70
        assert isinstance(signal_attr["technical_indicators"], int)

    def test_non_dict_signal_attribution_is_removed_before_rendering(self):
        """Invalid non-dict signal_attribution must not survive into renderers."""
        dashboard = {"signal_attribution": "bad payload"}

        normalize_dashboard_signal_attribution(dashboard)

        assert "signal_attribution" not in dashboard

    def test_partial_signal_attribution_uses_same_display_contract(self):
        """Partial weights should not render N/A% or None% in any report path."""
        from src.notification import NotificationService
        from src.services.history_service import HistoryService

        dashboard = self._make_dashboard_with_signal_attr({
            "technical_indicators": 35,
            "news_sentiment": None,
            "fundamentals": None,
            "market_conditions": 0,
            "strongest_bullish_signal": "MACD金叉",
        })
        result = self._make_result(dashboard)
        notification = NotificationService()

        dashboard_report = notification.generate_dashboard_report([result], [dashboard])
        single_report = notification.generate_single_stock_report(result)

        class MockRecord:
            created_at = None

        history_report = HistoryService.__new__(HistoryService)._generate_single_stock_markdown(result, MockRecord())
        template_report = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        for output in [dashboard_report, single_report, history_report, template_report]:
            assert output is not None
            assert "N/A%" not in output
            assert "None%" not in output
            assert "35%" in output

    def test_all_zero_signal_attribution_is_hidden_without_signals(self):
        """All-zero weights without strongest signals should not render attribution."""
        from src.notification import NotificationService
        from src.services.history_service import HistoryService

        dashboard = self._make_dashboard_with_signal_attr({
            "technical_indicators": 0,
            "news_sentiment": 0,
            "fundamentals": 0,
            "market_conditions": 0,
            "strongest_bullish_signal": None,
            "strongest_bearish_signal": None,
        })
        result = self._make_result(dashboard)
        notification = NotificationService()

        dashboard_report = notification.generate_dashboard_report([result], [dashboard])
        single_report = notification.generate_single_stock_report(result)

        class MockRecord:
            created_at = None

        history_report = HistoryService.__new__(HistoryService)._generate_single_stock_markdown(result, MockRecord())
        template_report = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        for output in [dashboard_report, single_report, history_report, template_report]:
            assert output is not None
            assert "信号归因" not in output
            assert "Signal Attribution" not in output

    def test_non_finite_signal_attribution_is_hidden_across_real_paths(self):
        """NaN/Infinity weights are missing values, not confident attribution."""
        from src.analyzer import GeminiAnalyzer
        from src.notification import NotificationService
        from src.services.history_service import HistoryService

        def non_finite_signal_attr():
            return {
                "technical_indicators": float("nan"),
                "news_sentiment": "NaN",
                "fundamentals": float("inf"),
                "market_conditions": "-Infinity",
                "strongest_bullish_signal": None,
                "strongest_bearish_signal": "",
            }

        response_text = json.dumps({
            "sentiment_score": 50,
            "trend_prediction": "震荡",
            "operation_advice": "持有",
            "decision_type": "hold",
            "confidence_level": "中",
            "analysis_summary": "测试",
            "dashboard": {
                "core_conclusion": {"one_sentence": "测试", "signal": "hold", "confidence": "中"},
                "intelligence": {"risk_alerts": []},
                "signal_attribution": non_finite_signal_attr(),
            },
        })

        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
        result = analyzer._parse_response(response_text, "600519", "测试")
        dashboard = result.dashboard
        signal_attr = dashboard["signal_attribution"]

        for key in ("technical_indicators", "news_sentiment", "fundamentals", "market_conditions"):
            assert signal_attr[key] is None
        assert signal_attr["strongest_bearish_signal"] is None

        parsed = parse_dashboard_json(json.dumps({
            "dashboard": {
                "signal_attribution": non_finite_signal_attr(),
            }
        }))
        assert parsed is not None
        parsed_attr = parsed["dashboard"]["signal_attribution"]
        for key in ("technical_indicators", "news_sentiment", "fundamentals", "market_conditions"):
            assert parsed_attr[key] is None

        notification = NotificationService()
        dashboard_report = notification.generate_dashboard_report([result], [dashboard])
        single_report = notification.generate_single_stock_report(result)

        class MockRecord:
            created_at = None

        history_report = HistoryService.__new__(HistoryService)._generate_single_stock_markdown(result, MockRecord())
        template_report = render("markdown", [result], summary_only=False, extra_context={"report_language": "zh"})

        for output in [dashboard_report, single_report, history_report, template_report]:
            assert output is not None
            assert "信号归因" not in output
            assert "Signal Attribution" not in output
            assert "NaN" not in output
            assert "Infinity" not in output

    # ========== 測試 4: HistoryService markdown 渲染 ==========
    def test_history_service_renders_signal_attribution(self):
        """
        測試 HistoryService._generate_single_stock_markdown() 正確渲染 signal_attribution。

        驗證：
        1. signal_attribution 存在時，markdown 中包含"信号归因分析"段落
        2. 四個貢獻度都正確顯示
        """
        from src.services.history_service import HistoryService

        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
            "strongest_bullish_signal": "MACD金叉",
            "strongest_bearish_signal": "成交量萎缩",
        }
        dashboard = self._make_dashboard_with_signal_attr(signal_attr)
        result = self._make_result(dashboard)

        # 創建 mock record
        class MockRecord:
            created_at = None

        # 調用 _generate_single_stock_markdown()
        history_service = HistoryService.__new__(HistoryService)
        markdown = history_service._generate_single_stock_markdown(result, MockRecord())

        # 驗證包含信號歸因段落
        assert "信号归因" in markdown or "Signal Attribution" in markdown, "Markdown 应包含信号归因段落"
        assert "35%" in markdown, "Markdown 应显示 technical_indicators=35%"
        assert "MACD金叉" in markdown, "Markdown 应显示 strongest_bullish_signal"

    # ========== 測試 5: check_content_integrity() optional 契約 ==========
    def test_check_content_integrity_treats_signal_attribution_as_optional(self):
        """
        測試 check_content_integrity() 將 signal_attribution 作為可選展示字段。

        驗證：
        1. signal_attribution 存在時，不添加到 missing
        2. signal_attribution 缺失時，不添加到 missing
        3. signal_attribution 貢獻度缺失時，不添加到 missing
        """
        # 情況 1: signal_attribution 完整
        signal_attr = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            "fundamentals": 20,
            "market_conditions": 20,
        }
        dashboard = self._make_dashboard_with_signal_attr(signal_attr)
        result = self._make_result(dashboard)

        passed, missing = check_content_integrity(result)
        signal_attr_missing = [m for m in missing if "signal_attribution" in m]
        assert len(signal_attr_missing) == 0, f"signal_attribution 完整时不应出现在 missing 中，实际: {signal_attr_missing}"

        # 情況 2: signal_attribution 缺失
        dashboard_no_attr = self._make_dashboard_with_signal_attr(None)
        dashboard_no_attr["battle_plan"] = {"sniper_points": {"stop_loss": "100"}}
        result_no_attr = self._make_result(dashboard_no_attr)

        passed, missing = check_content_integrity(result_no_attr)
        assert passed is True
        signal_attr_missing = [m for m in missing if "signal_attribution" in m]
        assert len(signal_attr_missing) == 0, "signal_attribution 缺失时不应出现在 missing 中"

        # 情況 3: signal_attribution 貢獻度缺失
        signal_attr_incomplete = {
            "technical_indicators": 35,
            "news_sentiment": 25,
            # 缺少 fundamentals 和 market_conditions
        }
        dashboard_incomplete = self._make_dashboard_with_signal_attr(signal_attr_incomplete)
        dashboard_incomplete["battle_plan"] = {"sniper_points": {"stop_loss": "100"}}
        result_incomplete = self._make_result(dashboard_incomplete)

        passed, missing = check_content_integrity(result_incomplete)
        assert passed is True
        signal_attr_missing = [m for m in missing if "signal_attribution" in m]
        assert len(signal_attr_missing) == 0, "signal_attribution 贡献度缺失时不应出现在 missing 中"

    # ========== 測試 6: 歸一化函數測試 ==========
    def test_normalize_dashboard_signal_attribution_direct(self):
        """
        直接測試 normalize_dashboard_signal_attribution() 函數。

        驗證：
        1. 字符串百分比轉為 int
        2. 負數轉為 0
        3. 總和≠100 時歸一化為 100
        4. None 值處理
        """
        # 情況 1: 字符串百分比
        dashboard = {
            "signal_attribution": {
                "technical_indicators": "30%",
                "news_sentiment": 20,
                "fundamentals": "30",
                "market_conditions": 10,
                "strongest_bullish_signal": "测试",
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        # 驗證字符串已轉為 int（具體值可能因歸一化而改變，但應該是 int）
        assert isinstance(attr["technical_indicators"], int), f"字符串百分比应转为 int: {attr['technical_indicators']}"
        assert isinstance(attr["fundamentals"], int), f"字符串应转为 int: {attr['fundamentals']}"

        # 驗證總和=100
        total = sum([
            attr.get("technical_indicators", 0),
            attr.get("news_sentiment", 0),
            attr.get("fundamentals", 0),
            attr.get("market_conditions", 0),
        ])
        assert total == 100, f"归一化后总和应为 100: {total}"

        # 情況 2: 負數
        dashboard = {
            "signal_attribution": {
                "technical_indicators": -10,
                "news_sentiment": 20,
                "fundamentals": 30,
                "market_conditions": 40,
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        assert attr["technical_indicators"] == 0, f"负数应转为 0: {attr['technical_indicators']}"

        # 情況 3: 總和=100，不需要歸一化
        dashboard = {
            "signal_attribution": {
                "technical_indicators": 25,
                "news_sentiment": 25,
                "fundamentals": 25,
                "market_conditions": 25,
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        total = sum([attr["technical_indicators"], attr["news_sentiment"], attr["fundamentals"], attr["market_conditions"]])
        assert total == 100, f"总和应为 100: {total}"

        # 情況 4: 總和≠100（需要歸一化）
        dashboard = {
            "signal_attribution": {
                "technical_indicators": 10,
                "news_sentiment": 20,
                "fundamentals": 30,
                "market_conditions": 30,  # 總和=90
            },
        }
        normalize_dashboard_signal_attribution(dashboard)
        attr = dashboard["signal_attribution"]
        total = sum([attr["technical_indicators"], attr["news_sentiment"], attr["fundamentals"], attr["market_conditions"]])
        assert total == 100, f"归一化后总和应为 100: {total}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
