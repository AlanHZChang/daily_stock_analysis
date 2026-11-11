# -*- coding: utf-8 -*-
"""新聞面為空時必須在報告裡如實標註。

背景：消息面章節原先是「有內容才渲染」，檢索一條沒拿到時整段直接消失，
讀報告的人無從判斷是確實沒新聞，還是檢索靜默失敗了（搜索源限流、
未配置可用渠道等）。這會把「抓取失敗」呈現成「確實沒有新聞」，
比單純的慢更容易誤導結論。

這些用例鎖住三個狀態：
1. 未執行檢索（count is None）時，說明未配置渠道且未納入新聞面證據；
2. 檢索執行了但為空（count == 0）時，保留原有零命中提示；
3. 正常拿到新聞（count > 0）時，不出現缺失提示。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.notification import NotificationService


ZERO_HIT_DISCLOSURE = "⚠️ 本次未获取到可用的新闻面数据，以下结论未纳入新闻维度证据。"
NO_CHANNEL_DISCLOSURE = "⚠️ 未配置搜索渠道，本次分析未纳入新闻面证据。"
EN_ZERO_HIT_DISCLOSURE = (
    "⚠️ No news data could be retrieved for this run; "
    "the conclusions below do not incorporate news-based evidence."
)
EN_NO_CHANNEL_DISCLOSURE = (
    "⚠️ No news search channel is configured; "
    "this analysis does not incorporate news-based evidence."
)
KO_ZERO_HIT_DISCLOSURE = (
    "⚠️ 이번 분석에서 사용 가능한 뉴스 데이터를 가져오지 못해 "
    "아래 결론에는 뉴스 근거를 반영하지 않았습니다."
)
KO_NO_CHANNEL_DISCLOSURE = (
    "⚠️ 뉴스 검색 채널이 설정되지 않아 이번 분석에는 "
    "뉴스 근거를 반영하지 않았습니다."
)


def _make_result(
    *,
    news_summary="",
    news_result_count=None,
    report_language="zh",
    news_evidence_present=False,
):
    """構造一個最小可渲染的分析結果。

    只填渲染日報必需的字段，避免與被測行為無關的細節耦合。
    """
    from src.analyzer import AnalysisResult

    return AnalysisResult(
        code="600519",
        name="测试标的",
        sentiment_score=50,
        trend_prediction="震荡",
        operation_advice="观望",
        analysis_summary="用于测试的综合分析。",
        report_language=report_language,
        news_summary=news_summary,
        news_result_count=news_result_count,
        news_evidence_present=news_evidence_present,
        success=True,
    )


def _make_service():
    """造一個用於渲染的 NotificationService。

    走真實 __init__ 以拿到全部渲染所需屬性；本測試只讀取返回的報告文本，
    不調用任何推送方法，因此不會向外發送。
    """
    return NotificationService()


class EmptyNewsDisclosureTestCase(unittest.TestCase):
    def setUp(self):
        self.service = _make_service()

    def _render(self, result):
        return NotificationService.generate_daily_report(
            self.service, [result], report_date="2026-08-18"
        )

    def test_discloses_when_search_ran_but_returned_nothing(self):
        """檢索執行了但零命中：報告必須說出來。"""
        report = self._render(_make_result(news_result_count=0))

        self.assertIn(ZERO_HIT_DISCLOSURE, report)
        self.assertNotIn(NO_CHANNEL_DISCLOSURE, report)
        self.assertIn("消息面", report)

    def test_discloses_when_search_was_not_performed(self):
        """未配置搜索渠道時，報告必須說明新聞面證據沒有納入。"""
        report = self._render(_make_result(news_result_count=None))

        self.assertIn(NO_CHANNEL_DISCLOSURE, report)
        self.assertNotIn(ZERO_HIT_DISCLOSURE, report)

    def test_unchanged_when_news_is_available(self):
        """拿到新聞時行為與改動前一致：渲染正文，不出現提示。"""
        report = self._render(
            _make_result(news_summary="公司发布季度财报，营收同比增长。", news_result_count=3)
        )

        self.assertIn("公司發佈季度財報", report)
        self.assertNotIn(ZERO_HIT_DISCLOSURE, report)
        self.assertNotIn(NO_CHANNEL_DISCLOSURE, report)

    def test_disclosure_states_the_consequence_not_just_the_absence(self):
        """提示要說清後果，讓讀者知道結論該打幾折，而不只是「沒數據」。"""
        report = self._render(_make_result(news_result_count=0))

        self.assertIn("未納入新闻維度證據", report)


class ResultFieldContractTestCase(unittest.TestCase):
    def test_result_defaults_to_none_not_zero(self):
        """默認必須是 None，才能與執行後零命中使用不同披露文案。"""
        result = _make_result()

        self.assertIsNone(result.news_result_count)


class ActiveRenderersDiscloseTestCase(unittest.TestCase):
    """真實流程走的是 dashboard / brief / single_stock，不是 generate_daily_report。

    只在 generate_daily_report 里加提示等於沒加——標準 REPORT_TYPE 一個都覆蓋不到。
    這些用例鎖住四個渲染器全部接入同一個共享判定。
    """

    def setUp(self):
        self.service = _make_service()

    def test_dashboard_report_discloses_empty_news(self):
        report = NotificationService.generate_dashboard_report(
            self.service, [_make_result(news_result_count=0)], report_date="2026-08-18"
        )

        self.assertIn(ZERO_HIT_DISCLOSURE, report)

    def test_brief_report_discloses_empty_news(self):
        report = NotificationService.generate_brief_report(
            self.service, [_make_result(news_result_count=0)], report_date="2026-08-18"
        )

        self.assertIn(ZERO_HIT_DISCLOSURE, report)

    def test_single_stock_report_discloses_empty_news(self):
        report = NotificationService.generate_single_stock_report(
            self.service, _make_result(news_result_count=0)
        )

        self.assertIn(ZERO_HIT_DISCLOSURE, report)

    def test_renderers_disclose_when_search_not_performed(self):
        for name, call in (
            ("dashboard", lambda r: NotificationService.generate_dashboard_report(
                self.service, [r], report_date="2026-08-18")),
            ("brief", lambda r: NotificationService.generate_brief_report(
                self.service, [r], report_date="2026-08-18")),
            ("single", lambda r: NotificationService.generate_single_stock_report(
                self.service, r)),
        ):
            with self.subTest(renderer=name):
                report = call(_make_result(news_result_count=None))
                self.assertIn(NO_CHANNEL_DISCLOSURE, report)
                self.assertNotIn(ZERO_HIT_DISCLOSURE, report)


class DisclosureIndependentOfModelTextTestCase(unittest.TestCase):
    """最糟的組合：檢索零命中，但模型仍按 schema 寫出了情緒判斷。

    此時若以「消息面文字是否為空」決定是否提示，報告會展示模型生成的情緒，
    同時隱瞞沒有新聞證據這一事實。判定必須獨立於模型輸出。
    """

    def setUp(self):
        self.service = _make_service()

    def test_warns_even_when_model_supplied_sentiment(self):
        result = _make_result(news_result_count=0)
        result.market_sentiment = "市场情绪偏中性。"
        result.hot_topics = "暂无明显热点。"

        report = NotificationService.generate_daily_report(
            self.service, [result], report_date="2026-08-18"
        )

        self.assertIn(ZERO_HIT_DISCLOSURE, report)
        self.assertIn("市場情绪偏中性", report)


class TemplateRendererDiscloseTestCase(unittest.TestCase):
    """REPORT_RENDERER_ENABLED=true 時走模板鏈路，會在 render() 處提前返回。

    此前只修了字符串拼接分支，模板鏈路一路沉默——同一份分析結果在部分渠道
    披露、在另一些渠道不披露，跨渠道事實呈現不一致。
    """

    def setUp(self):
        self.service = _make_service()

    def _render_with_templates(self, method, result, platform_hint=""):
        from unittest.mock import patch
        from src.config import get_config

        cfg = get_config()
        with patch.object(type(cfg), "report_renderer_enabled", True, create=True):
            return method(self.service, [result], report_date="2026-08-18")

    def test_markdown_template_discloses_empty_news(self):
        from src.services.report_renderer import render

        out = render(
            platform="markdown",
            results=[_make_result(news_result_count=0)],
            report_date="2026-08-18",
            summary_only=False,
            extra_context={"report_language": "zh"},
        )
        self.assertTrue(out)
        self.assertIn(ZERO_HIT_DISCLOSURE, out)

    def test_brief_template_discloses_empty_news(self):
        from src.services.report_renderer import render

        out = render(
            platform="brief",
            results=[_make_result(news_result_count=0)],
            report_date="2026-08-18",
            summary_only=False,
            extra_context={"report_language": "zh"},
        )
        self.assertTrue(out)
        self.assertIn(ZERO_HIT_DISCLOSURE, out)

    def test_wechat_template_discloses_empty_news(self):
        from src.services.report_renderer import render

        out = render(
            platform="wechat",
            results=[_make_result(news_result_count=0)],
            report_date="2026-08-18",
            summary_only=False,
            extra_context={"report_language": "zh"},
        )
        self.assertTrue(out)
        self.assertIn(ZERO_HIT_DISCLOSURE, out)

    def test_templates_disclose_when_search_not_performed(self):
        from src.services.report_renderer import render

        for platform in ("markdown", "brief", "wechat"):
            with self.subTest(platform=platform):
                out = render(
                    platform=platform,
                    results=[_make_result(news_result_count=None)],
                    report_date="2026-08-18",
                    summary_only=False,
                    extra_context={"report_language": "zh"},
                )
                self.assertIn(NO_CHANNEL_DISCLOSURE, out or "")
                self.assertNotIn(ZERO_HIT_DISCLOSURE, out or "")


class WechatDashboardDiscloseTestCase(unittest.TestCase):
    """generate_wechat_dashboard 是企業微信非 brief 場景的真實入口，
    pipeline 會直接調用它，此前完全沒有接入披露。"""

    def setUp(self):
        self.service = _make_service()

    def test_wechat_dashboard_discloses_empty_news(self):
        out = NotificationService.generate_wechat_dashboard(
            self.service, [_make_result(news_result_count=0)]
        )
        self.assertIn(ZERO_HIT_DISCLOSURE, out)

    def test_wechat_dashboard_discloses_when_search_not_performed(self):
        out = NotificationService.generate_wechat_dashboard(
            self.service, [_make_result(news_result_count=None)]
        )
        self.assertIn(NO_CHANNEL_DISCLOSURE, out)
        self.assertNotIn(ZERO_HIT_DISCLOSURE, out)


class NoSearchProviderDisclosureTestCase(unittest.TestCase):
    """鎖住 #2225 的 fresh-clone 場景：沒有 key，公共實例默認關閉。"""

    def test_no_registered_providers_discloses_missing_news_evidence(self):
        from src.search_service import SearchService

        search_service = SearchService(searxng_public_instances_enabled=False)
        self.assertEqual([], search_service._providers)
        self.assertFalse(search_service.is_available)

        report = NotificationService.generate_daily_report(
            _make_service(), [_make_result(news_result_count=None)], report_date="2026-08-18"
        )
        self.assertIn(NO_CHANNEL_DISCLOSURE, report)
        self.assertNotIn(ZERO_HIT_DISCLOSURE, report)


class SupportedLanguageDisclosureTestCase(unittest.TestCase):
    """每種受支持報告語言都必須顯式映射，不能把未知語言默認為中文。"""

    EXPECTED = {
        "zh": (NO_CHANNEL_DISCLOSURE, ZERO_HIT_DISCLOSURE),
        "en": (EN_NO_CHANNEL_DISCLOSURE, EN_ZERO_HIT_DISCLOSURE),
        "ko": (KO_NO_CHANNEL_DISCLOSURE, KO_ZERO_HIT_DISCLOSURE),
    }

    def setUp(self):
        self.service = _make_service()

    def _string_renderers(self, result):
        return {
            "daily": NotificationService.generate_daily_report(
                self.service, [result], report_date="2026-08-18"
            ),
            "dashboard": NotificationService.generate_dashboard_report(
                self.service, [result], report_date="2026-08-18"
            ),
            "brief": NotificationService.generate_brief_report(
                self.service, [result], report_date="2026-08-18"
            ),
            "single": NotificationService.generate_single_stock_report(
                self.service, result
            ),
            "wechat_dashboard": NotificationService.generate_wechat_dashboard(
                self.service, [result]
            ),
            "wechat_summary": NotificationService.generate_wechat_summary(
                self.service, [result]
            ),
        }

    def test_every_supported_language_is_used_by_string_renderers(self):
        from src.report_language import SUPPORTED_REPORT_LANGUAGES

        self.assertEqual(set(SUPPORTED_REPORT_LANGUAGES), set(self.EXPECTED))
        for language in SUPPORTED_REPORT_LANGUAGES:
            for count, expected_index in ((None, 0), (0, 1)):
                expected = self.EXPECTED[language][expected_index]
                result = _make_result(
                    news_result_count=count,
                    report_language=language,
                )
                for renderer, report in self._string_renderers(result).items():
                    with self.subTest(
                        language=language,
                        count=count,
                        renderer=renderer,
                    ):
                        self.assertIn(expected, report)
                        if language != "zh":
                            self.assertNotIn(NO_CHANNEL_DISCLOSURE, report)
                            self.assertNotIn(ZERO_HIT_DISCLOSURE, report)

    def test_every_supported_language_is_used_by_templates(self):
        from src.report_language import SUPPORTED_REPORT_LANGUAGES
        from src.services.report_renderer import render

        for language in SUPPORTED_REPORT_LANGUAGES:
            result = _make_result(news_result_count=0, report_language=language)
            for platform in ("markdown", "brief", "wechat"):
                for summary_only in (False, True):
                    with self.subTest(
                        language=language,
                        platform=platform,
                        summary_only=summary_only,
                    ):
                        out = render(
                            platform=platform,
                            results=[result],
                            report_date="2026-08-18",
                            summary_only=summary_only,
                            extra_context={"report_language": language},
                        )
                        self.assertIn(self.EXPECTED[language][1], out or "")
                        if language != "zh":
                            self.assertNotIn(ZERO_HIT_DISCLOSURE, out or "")

    def test_summary_only_string_renderers_keep_disclosure(self):
        self.service._report_summary_only = True
        result = _make_result(news_result_count=0)

        for renderer, report in (
            (
                "daily",
                NotificationService.generate_daily_report(
                    self.service, [result], report_date="2026-08-18"
                ),
            ),
            (
                "dashboard",
                NotificationService.generate_dashboard_report(
                    self.service, [result], report_date="2026-08-18"
                ),
            ),
            (
                "wechat",
                NotificationService.generate_wechat_dashboard(self.service, [result]),
            ),
        ):
            with self.subTest(renderer=renderer):
                self.assertIn(ZERO_HIT_DISCLOSURE, report)

    def test_unknown_language_fails_loudly(self):
        from src.services.empty_news import empty_news_disclosure

        with self.assertRaisesRegex(ValueError, "Unsupported report language"):
            empty_news_disclosure(_make_result(news_result_count=0), "future-language")


class PipelineCountSemanticsTestCase(unittest.TestCase):
    """計數的三態語義必須在 pipeline 側就正確產生，否則展示層再周全也無用。

    兩個曾經的缺口：
    1. 搜索服務整體失敗（intel_results 為空）時計數停留在 None，
       於是「所有搜索源全線失敗」這一最該提示的場景反而不提示；
    2. Agent 模式（_analyze_with_agent）自行檢索卻從不記錄計數，
       該路徑下零命中永遠靜默。
    """

    def _read_pipeline_source(self):
        from pathlib import Path

        return (Path(__file__).resolve().parents[1] / "src" / "core" / "pipeline.py").read_text(
            encoding="utf-8"
        )

    def test_count_set_to_zero_once_search_is_attempted(self):
        """檢索一旦發起就置 0，不能等到拿到結果對象才賦值。"""
        src = self._read_pipeline_source()
        idx = src.index("开始多维度情报搜索")
        window = src[idx : idx + 600]

        self.assertIn("news_result_count = 0", window)
        self.assertLess(
            window.index("news_result_count = 0"),
            window.index("search_comprehensive_intel"),
            "计数必须在发起检索之前置 0，否则整体失败时会落回 None",
        )

    def test_post_hoc_persistence_query_does_not_write_the_count(self):
        """分析結束後的補查只為持久化情報，絕不能回寫計數。

        它發生在 executor.run() 之後，與 Agent 實際消費的證據無關；用它做披露
        判定會兩個方向都失真（review OR-COR-5f5d7a2e）。真正的計數由
        src/agent/news_evidence.py 的證據作用域收集。
        """
        src = self._read_pipeline_source()
        idx = src.index("Agent 模式: 新闻情报已保存")
        window = src[max(0, idx - 1200) : idx]
        # 只看代碼：解釋這條約束的註釋本身就含有該標識符。
        code_only = "\n".join(
            line for line in window.splitlines() if not line.strip().startswith("#")
        )

        self.assertNotIn("result.news_result_count", code_only)


class _StubSearchResult:
    def __init__(self, index):
        self.title = f"标题{index}"
        self.snippet = f"摘要{index}"
        self.url = f"https://example.invalid/{index}"
        self.source = "stub"
        self.published_date = "2026-08-20"


class _StubSearchResponse:
    def __init__(self, count, *, success=True, query="stub-query"):
        self.success = success
        self.results = [_StubSearchResult(i) for i in range(count)]
        self.query = query
        self.provider = "stub"
        self.error_message = None if success else "stub failure"


class _StubSearchService:
    """只實現搜索工具真正會用到的接口。

    intel_counts 是 Agent 通過 search_comprehensive_intel 實際拿到的證據，
    news_count 是 pipeline 事後為持久化而補打的 search_stock_news 的結果 ——
    兩者刻意不同，用來證明披露跟隨的是前者。
    """

    def __init__(self, *, intel_counts=None, news_count=0, news_success=True, available=True):
        self._intel_counts = intel_counts or {}
        self._news_count = news_count
        self._news_success = news_success
        self._available = available

    @property
    def is_available(self):
        return self._available

    def search_comprehensive_intel(self, stock_code, stock_name, max_searches=6):
        return {
            dimension: _StubSearchResponse(count)
            for dimension, count in self._intel_counts.items()
        }

    def format_intel_report(self, intel_results, stock_name):
        return "stub intel report"

    def search_stock_news(self, stock_code, stock_name, max_results=5):
        return _StubSearchResponse(self._news_count, success=self._news_success)


class AgentNewsEvidenceTestCase(unittest.TestCase):
    """Agent 模式的披露必須跟隨 Agent 真正消費的新聞證據。

    曾經的缺口（review OR-COR-5f5d7a2e）：計數取自分析結束後補打的一次
    search_stock_news()。Agent 明明通過 search_comprehensive_intel 用了新聞，
    卻可能因補查失敗被標成「未納入新聞面證據」；反過來 Agent 什麼都沒拿到，
    也可能因補查有結果而錯誤地不提示。
    """

    def setUp(self):
        from src.agent import news_evidence

        self.news_evidence = news_evidence
        token = news_evidence.activate_news_evidence_scope()
        self.accumulator = news_evidence.get_current_news_evidence()
        self.addCleanup(news_evidence.reset_news_evidence_scope, token)

    def _install_service(self, service):
        from unittest.mock import patch

        patcher = patch(
            "src.agent.tools.search_tools._get_search_service", return_value=service
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        db_patcher = patch("src.agent.tools.search_tools._get_db")
        db_patcher.start()
        self.addCleanup(db_patcher.stop)

    def test_agent_evidence_survives_a_failing_post_hoc_query(self):
        """Agent 用了 6 條新聞，事後補查零命中 —— 不得謊稱未納入新聞證據。"""
        from src.agent.tools.search_tools import _handle_search_comprehensive_intel

        service = _StubSearchService(
            intel_counts={"latest_news": 4, "risk_check": 2}, news_count=0
        )
        self._install_service(service)

        _handle_search_comprehensive_intel("600519", "测试标的")

        # pipeline 事後的持久化補查返回完全不同的結果，且不經過證據作用域
        post_hoc = service.search_stock_news("600519", "测试标的", max_results=5)
        self.assertEqual(0, len(post_hoc.results))

        self.assertEqual(6, self.accumulator.resolve(search_available=True))

    def test_agent_zero_hit_is_not_masked_by_a_successful_post_hoc_query(self):
        """反方向：Agent 一條沒拿到，事後補查有結果 —— 提示不得被抑制。"""
        from src.agent.tools.search_tools import _handle_search_comprehensive_intel

        service = _StubSearchService(
            intel_counts={"latest_news": 0}, news_count=5
        )
        self._install_service(service)

        _handle_search_comprehensive_intel("600519", "测试标的")

        post_hoc = service.search_stock_news("600519", "测试标的", max_results=5)
        self.assertEqual(5, len(post_hoc.results))

        self.assertEqual(0, self.accumulator.resolve(search_available=True))

    def test_failed_agent_search_records_zero_rather_than_nothing(self):
        """檢索發起但失敗，是「搜過但沒拿到」，不是「未配置渠道」。"""
        from src.agent.tools.search_tools import _handle_search_stock_news

        service = _StubSearchService(news_count=0, news_success=False)
        self._install_service(service)

        _handle_search_stock_news("600519", "测试标的")

        self.assertEqual(0, self.accumulator.resolve(search_available=True))

    def test_unavailable_channel_resolves_to_not_configured(self):
        """渠道不可用時工具直接返回錯誤、不記錄，計數必須是 None。"""
        from src.agent.tools.search_tools import _handle_search_stock_news

        service = _StubSearchService(available=False)
        self._install_service(service)

        _handle_search_stock_news("600519", "测试标的")

        self.assertIsNone(self.accumulator.resolve(search_available=False))

    def test_available_channel_never_searched_reports_zero_hit_not_missing_channel(self):
        """渠道可用但 Agent 一次都沒搜：仍是「沒拿到新聞」，不能謊稱未配置渠道。"""
        self.assertEqual(0, self.accumulator.resolve(search_available=True))

    def test_tool_threads_accumulate_into_the_parent_scope(self):
        """工具在線程池中執行，累加必須對 pipeline 可見。

        src/agent/runner.py 用 contextvars.copy_context() + pool.submit(ctx.run, ...)
        提交工具調用。ContextVar 裡必須是可變累加器對象，換成不可變值父線程就讀不到。
        """
        import contextvars
        from concurrent.futures import ThreadPoolExecutor

        record = self.news_evidence.record_news_evidence
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = []
            for count in (2, 0, 5):
                ctx = contextvars.copy_context()
                futures.append(pool.submit(ctx.run, record, count))
            for future in futures:
                future.result()

        self.assertEqual(7, self.accumulator.resolve(search_available=True))

    def test_recording_outside_a_scope_is_ignored(self):
        """報告頁的後續資訊檢索等場景不得影響本次分析的披露判定。"""
        token = self.news_evidence.activate_news_evidence_scope()
        outer = self.news_evidence.get_current_news_evidence()
        self.news_evidence.reset_news_evidence_scope(token)

        self.news_evidence.record_news_evidence(99)

        self.assertEqual(0, outer.resolve(search_available=True))


class NewsEvidenceSourcesTestCase(unittest.TestCase):
    """披露斷言的是「結論有沒有用到新聞面證據」，不是「搜索命中了幾條」。

    `news_context` 由三路來源拼成，只有實時檢索會產生計數：

    1. 實時多維檢索 —— 更新 news_result_count
    2. 社交情緒（美股）—— 不更新計數
    3. 本地已落庫的資訊池 —— 不更新計數

    只看計數就會把後兩路參與的分析誤報成「未納入新聞面證據」
    （review OR-COR-2e4b9d61 點名了第 3 路；第 2 路是同一缺陷類，一併鎖住）。
    """

    def _result(self, *, count, evidence):
        return _make_result(news_result_count=count, news_evidence_present=evidence)

    def test_local_intel_without_search_channel_is_not_reported_as_missing(self):
        """本地資訊池已進入分析輸入，即使沒配搜索渠道也不能說未納入新聞證據。"""
        report = NotificationService.generate_daily_report(
            _make_service(),
            [self._result(count=None, evidence=True)],
            report_date="2026-08-20",
        )
        self.assertNotIn(NO_CHANNEL_DISCLOSURE, report)
        self.assertNotIn(ZERO_HIT_DISCLOSURE, report)

    def test_social_sentiment_without_search_hits_is_not_reported_as_missing(self):
        """社交情緒同樣進入 news_context，零命中也不能否認已用證據。"""
        report = NotificationService.generate_daily_report(
            _make_service(),
            [self._result(count=0, evidence=True)],
            report_date="2026-08-20",
        )
        self.assertNotIn(ZERO_HIT_DISCLOSURE, report)
        self.assertNotIn(NO_CHANNEL_DISCLOSURE, report)

    def test_no_evidence_at_all_still_discloses_with_the_right_reason(self):
        """真的沒有任何證據時，原有兩種原因文案必須照舊。"""
        no_channel = NotificationService.generate_daily_report(
            _make_service(),
            [self._result(count=None, evidence=False)],
            report_date="2026-08-20",
        )
        zero_hit = NotificationService.generate_daily_report(
            _make_service(),
            [self._result(count=0, evidence=False)],
            report_date="2026-08-20",
        )
        self.assertIn(NO_CHANNEL_DISCLOSURE, no_channel)
        self.assertIn(ZERO_HIT_DISCLOSURE, zero_hit)

    def test_evidence_helper_registers_sources_one_by_one(self):
        from src.services.empty_news import news_evidence_present

        # 真實命中數 / 社交情緒 / 本地資訊池，任一為真即算有證據
        self.assertTrue(news_evidence_present(4, None, None))
        self.assertTrue(news_evidence_present(0, "reddit 讨论……", None))
        self.assertTrue(news_evidence_present(0, None, "## 本地资讯证据池"))
        self.assertFalse(news_evidence_present(0, None, None))
        self.assertFalse(news_evidence_present(0, "", "   \n\t "))
        self.assertFalse(news_evidence_present(None, None, None))

    def test_zero_hit_placeholder_report_is_not_mistaken_for_evidence(self):
        """零命中時 format_intel_report 仍吐佔位文本，絕不能被當成證據。

        這是真實反例（review OR-COR-8f4c2d1b）：`format_intel_report()` 即使所有
        維度都失敗，也會輸出「【XX 情報搜索結果】」標題和每個維度的「未找到相關
        信息」，整段永遠非空。曾經的實現把整段 news_context 傳進判定函數，於是
        「搜了但一條沒拿到」被翻成「有證據」，恰好吞掉本 PR 要補的那條披露。
        這裡用真實函數產出反例，不用 mock。
        """
        from src.search_service import SearchService
        from src.services.empty_news import news_evidence_present

        class _FailedResponse:
            success = False
            results = []
            provider = "stub"

        service = SearchService.__new__(SearchService)
        placeholder = SearchService.format_intel_report(
            service,
            {"latest_news": _FailedResponse(), "risk_check": _FailedResponse()},
            "测试标的",
        )

        # 前提：這段佔位文本確實非空，否則這條反例就失去意義
        self.assertTrue(placeholder.strip())
        self.assertIn("未找到相關信息", placeholder)

        # 按來源登記：實時 0 條、無社交、無本地資訊池 —— 必須判定為沒有證據
        self.assertFalse(news_evidence_present(0, None, None))

        # 端到端：這種情況報告必須出現零命中披露
        report = NotificationService.generate_daily_report(
            _make_service(),
            [_make_result(news_result_count=0, news_evidence_present=False)],
            report_date="2026-08-21",
        )
        self.assertIn(ZERO_HIT_DISCLOSURE, report)

    def test_stored_record_round_trips_the_evidence_flag(self):
        from src.services.empty_news import (
            empty_news_disclosure_from_stored,
            persisted_news_evidence_present,
        )

        stored = self._result(count=None, evidence=True).to_dict()
        self.assertIn("news_evidence_present", stored)
        self.assertTrue(persisted_news_evidence_present(stored, None))
        self.assertIsNone(empty_news_disclosure_from_stored(stored, None, "zh"))

    def test_legacy_record_without_the_flag_keeps_its_original_behaviour(self):
        """舊記錄沒有該字段時按計數推斷，不追溯改變當時的報告表現。"""
        from src.services.empty_news import persisted_news_evidence_present

        self.assertTrue(persisted_news_evidence_present({"news_result_count": 4}, 4))
        self.assertFalse(persisted_news_evidence_present({"news_result_count": 0}, 0))

    def test_pipeline_registers_sources_and_never_passes_the_whole_context(self):
        """兩條 pipeline 路徑都必須按來源登記，且都不許傳拼好的整段 news_context。

        源碼斷言：誰把整段 news_context 交回判定函數，本用例就會失敗——那正是
        零命中佔位文本冒充證據的入口。
        """
        from pathlib import Path

        src = (Path(__file__).resolve().parents[1] / "src" / "core" / "pipeline.py").read_text(
            encoding="utf-8"
        )
        code_only = "\n".join(
            line for line in src.splitlines() if not line.strip().startswith("#")
        )

        calls = code_only.count("result.news_evidence_present = news_evidence_present(")
        self.assertEqual(2, calls, "普通路徑與 Agent 路徑各要有一次登記")

        # 三路來源都要出現在登記參數裡
        self.assertIn("social_evidence_context", code_only)
        self.assertIn("persisted_intelligence_context", code_only)

        # 整段 news_context 不許再被交給判定函數
        self.assertNotIn("news_evidence_present(\n                        news_context", code_only)
        self.assertNotIn("news_evidence_present(news_context", code_only)
        self.assertNotIn('news_evidence_present(\n                    initial_context.get("news_context")', code_only)


if __name__ == "__main__":
    unittest.main()
