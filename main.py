# -*- coding: utf-8 -*-
"""
===================================
A股自選股智能分析系統 - 主調度程序
===================================

職責：
1. 協調各模塊完成股票分析流程
2. 實現低併發的線程池調度
3. 全局異常處理，確保單股失敗不影響整體
4. 提供命令行入口

使用方式：
    python main.py              # 正常運行
    python main.py --debug      # 調試模式
    python main.py --dry-run    # 僅獲取數據不分析

交易理念（已融入分析）：
- 嚴進策略：不追高，乖離率 > 5% 不買入
- 趨勢交易：只做 MA5>MA10>MA20 多頭排列
- 效率優先：關注籌碼集中度好的股票
- 買點偏好：縮量回踩 MA5/MA10 支撐
"""
from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from dotenv import dotenv_values
from src.config import setup_env

_INITIAL_PROCESS_ENV = dict(os.environ)
setup_env()

# 代理配置 - 通過 USE_PROXY 環境變量控制，默認關閉
# GitHub Actions 環境自動跳過代理配置
if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
    # 本地開發環境，啟用代理（可在 .env 中配置 PROXY_HOST 和 PROXY_PORT）
    proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
    proxy_port = os.getenv("PROXY_PORT", "10809")
    proxy_url = f"http://{proxy_host}:{proxy_port}"
    os.environ["http_proxy"] = proxy_url
    os.environ["https_proxy"] = proxy_url

_packaged_import_probe = os.getenv("DSA_PACKAGED_IMPORT_PROBE")
if _packaged_import_probe:
    import importlib
    import sys

    try:
        probe_module = importlib.import_module(_packaged_import_probe)
        if _packaged_import_probe == "py_mini_racer":
            # Importing the Python wrapper does not load V8 or its data files.
            # Exercise the installed runtime to detect missing/mismatched assets.
            engine = probe_module.MiniRacer()
            try:
                if engine.eval("1 + 1") != 2:
                    raise RuntimeError("MiniRacer JavaScript evaluation failed")
            finally:
                close = getattr(engine, "close", None)
                if callable(close):
                    close()
        elif _packaged_import_probe == "src.agent.factory":
            # Build the agent tool registry so tool modules that read package
            # data at import time (e.g. the FXMacroData operation catalogue)
            # are exercised in the frozen artifact.
            registry = probe_module.get_tool_registry()
            if not any(name.startswith("fxmacrodata_") for name in registry.list_names()):
                raise RuntimeError("FXMacroData tools are missing from the agent tool registry")
    except Exception as exc:
        print(
            f"ERROR: packaged runtime probe failed for {_packaged_import_probe}: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"OK: packaged import succeeded for {_packaged_import_probe}")
    sys.exit(0)

import argparse
import logging
import sys
import time
import uuid
from datetime import date, datetime, timezone, timedelta

from src.webui_frontend import prepare_webui_frontend_assets
from src.config import get_config, Config
from src.logging_config import setup_logging
from src.brokers.futu.portfolio import FutuPortfolioError
from src.core.analysis_run_marker import (
    record_analysis_run_marker,
    should_skip_startup_immediate_run,
)
from data_provider.base import canonical_stock_code
from src.services.stock_list_parser import (
    AnalysisTarget,
    ParseStatus,
    parse_analysis_target,
    split_stock_list,
)
from src.services.stock_code_utils import resolve_index_stock_code_for_analysis


logger = logging.getLogger(__name__)
_RUNTIME_ENV_FILE_KEYS = set()
_PUBLIC_BIND_HOSTS = frozenset({"0.0.0.0", "::", "[::]", "*"})
_LAST_ANALYSIS_FAILURE_REASON: Optional[str] = None


def _get_active_env_path() -> Path:
    env_file = os.getenv("ENV_FILE")
    if env_file:
        return Path(env_file)
    return Path(__file__).resolve().parent / ".env"


def _is_public_bind_host(host: str) -> bool:
    return (host or "").strip().lower() in _PUBLIC_BIND_HOSTS


def _warn_if_public_webui_without_auth(host: str) -> None:
    if not _is_public_bind_host(host):
        return

    from src.auth import is_auth_enabled

    if is_auth_enabled():
        return
    logger.warning(
        "WEBUI_HOST=%s binds the Web UI to a public interface while "
        "ADMIN_AUTH_ENABLED=false. Keep this service behind a trusted network "
        "boundary or enable admin authentication before exposing it.",
        host,
    )


def _resolve_web_service_bind(args: argparse.Namespace, config: Config) -> Tuple[str, int]:
    """Resolve the effective Web/API bind address from CLI first, then config."""
    host = args.host if args.host is not None else (config.webui_host or "127.0.0.1")
    port = args.port if args.port is not None else config.webui_port
    return host, port


def _read_active_env_values() -> Optional[Dict[str, str]]:
    env_path = _get_active_env_path()
    if not env_path.exists():
        return {}

    try:
        values = dotenv_values(env_path)
    except Exception as exc:  # pragma: no cover - defensive branch
        logger.warning("讀取配置文件 %s 失敗，繼續沿用当前環境變量: %s", env_path, exc)
        return None

    return {
        str(key): "" if value is None else str(value)
        for key, value in values.items()
        if key is not None
    }


_ACTIVE_ENV_FILE_VALUES = _read_active_env_values() or {}
_RUNTIME_ENV_FILE_KEYS = {
    key for key in _ACTIVE_ENV_FILE_VALUES
    if key not in _INITIAL_PROCESS_ENV
}

# setup_env() already ran at import time above.
_env_bootstrapped = True


def _bootstrap_environment() -> None:
    """Load .env and apply optional local proxy settings.

    Guarded to be idempotent so it can safely be called from lazy-import
    paths used by API / bot consumers.
    """
    global _env_bootstrapped
    if _env_bootstrapped:
        return

    from src.config import setup_env

    setup_env()

    if os.getenv("GITHUB_ACTIONS") != "true" and os.getenv("USE_PROXY", "false").lower() == "true":
        proxy_host = os.getenv("PROXY_HOST", "127.0.0.1")
        proxy_port = os.getenv("PROXY_PORT", "10809")
        proxy_url = f"http://{proxy_host}:{proxy_port}"
        os.environ["http_proxy"] = proxy_url
        os.environ["https_proxy"] = proxy_url

    _env_bootstrapped = True


def _setup_bootstrap_logging(debug: bool = False) -> None:
    """Initialize stderr-only logging before config is loaded.

    File handlers are deferred until ``config.log_dir`` is known (via the
    subsequent ``setup_logging()`` call) so that healthy runs never create
    log files in a hard-coded directory.
    """
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    root.setLevel(level)
    if not any(
        isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) is sys.stderr
        for h in root.handlers
    ):
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(level)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(handler)


def _setup_runtime_logging(log_dir: str, debug: bool = False) -> bool:
    """Switch to configured logging, falling back to console on file I/O errors."""
    try:
        setup_logging(log_prefix="stock_analysis", debug=debug, log_dir=log_dir)
        return True
    except OSError as exc:
        logger.warning(
            "文件日誌初始化失敗，已降级為控制檯日誌輸出；日誌目錄 %r 当前不可寫或不可創建: %s。"
            "官方 Docker 鏡像啟動入口會自動修復默認掛載目錄權限；若仍失敗，"
            "請檢查是否使用了 --user、只讀掛載、rootless Docker 或 NFS 等限制寫入的環境。",
            log_dir,
            exc,
        )
        return False


def _get_stock_analysis_pipeline():
    """Lazily import StockAnalysisPipeline for external consumers.

    Also ensures env/proxy bootstrap has run so that API / bot consumers
    that never call ``main()`` still get ``USE_PROXY`` applied.
    """
    _bootstrap_environment()
    from src.core.pipeline import StockAnalysisPipeline as _Pipeline

    return _Pipeline


class _LazyPipelineDescriptor:
    """Descriptor that resolves StockAnalysisPipeline on first attribute access."""

    _resolved = None

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, objtype=None):
        if self._resolved is None:
            self._resolved = _get_stock_analysis_pipeline()
        return self._resolved


class _ModuleExports:
    StockAnalysisPipeline = _LazyPipelineDescriptor()


_exports = _ModuleExports()


def __getattr__(name: str):
    if name == "StockAnalysisPipeline":
        return _exports.StockAnalysisPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _reload_env_file_values_preserving_overrides() -> None:
    """Refresh `.env`-managed env vars without clobbering process env overrides."""
    global _RUNTIME_ENV_FILE_KEYS

    latest_values = _read_active_env_values()
    if latest_values is None:
        return

    managed_keys = {
        key for key in latest_values
        if key not in _INITIAL_PROCESS_ENV
    }

    for key in _RUNTIME_ENV_FILE_KEYS - managed_keys:
        os.environ.pop(key, None)

    for key in managed_keys:
        os.environ[key] = latest_values[key]

    _RUNTIME_ENV_FILE_KEYS = managed_keys


def parse_arguments() -> argparse.Namespace:
    """解析命令行參數"""
    parser = argparse.ArgumentParser(
        description='A股自選股智能分析系統',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python main.py                    # 正常運行
  python main.py --debug            # 調試模式
  python main.py --dry-run          # 僅獲取數據，不進行 AI 分析
  python main.py --stocks 600519,000001  # 指定分析特定股票
  python main.py --stocks sh000016,000300.CSI,930955.CSI  # 指定分析已登記指数（sh/sz 前綴或 .CSI alias）
  python main.py --portfolio futu   # 使用 Futu 真實正股持倉（覆蓋 --stocks）
  python main.py --no-notify        # 不發送推送通知
  python main.py --check-notify     # 檢查通知配置，不發送通知
  python main.py --single-notify    # 啟用單股推送模式（每分析完一隻立即推送）
  python main.py --schedule         # 啟用定時任務模式
  python main.py --market-review    # 僅運行大盘复盘
  python main.py --etf-rotation     # ETF 轮动：最新信號 + 規則回測報告
        '''
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='啟用調試模式，輸出詳細日誌'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='僅獲取數據，不進行 AI 分析'
    )

    parser.add_argument(
        '--stocks',
        type=str,
        help='指定要分析的股票代碼，逗號分隔（覆蓋配置文件）；支持已登記指数：sh/sz 前綴（如 sh000016）或 .CSI alias（如 000300.CSI、930955.CSI）'
    )

    parser.add_argument(
        '--portfolio',
        type=str.lower,
        choices=('futu',),
        help='使用券商真實持倉作為股票列表；当前支持 futu，並覆蓋 --stocks/STOCK_LIST'
    )

    parser.add_argument(
        '--no-notify',
        action='store_true',
        help='不發送推送通知'
    )

    parser.add_argument(
        '--check-notify',
        action='store_true',
        help='只讀檢查通知渠道配置，不發送通知'
    )

    parser.add_argument(
        '--single-notify',
        action='store_true',
        help='啟用單股推送模式：每分析完一隻股票立即推送，而不是彙總推送'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='併發線程數（默認使用配置值）'
    )

    parser.add_argument(
        '--schedule',
        action='store_true',
        help='啟用定時任務模式，每日定時執行'
    )

    parser.add_argument(
        '--no-run-immediately',
        action='store_true',
        help='定時任務啟動時不立即執行一次'
    )

    parser.add_argument(
        '--market-review',
        action='store_true',
        help='僅運行大盘复盘分析'
    )

    parser.add_argument(
        '--no-market-review',
        action='store_true',
        help='跳過大盘复盘分析'
    )

    parser.add_argument(
        '--force-run',
        action='store_true',
        help='跳過交易日檢查，強制執行全量分析（Issue #373）'
    )

    parser.add_argument(
        '--webui',
        action='store_true',
        help='啟動 Web 管理界面'
    )

    parser.add_argument(
        '--webui-only',
        action='store_true',
        help='僅啟動 Web 服務，不執行自動分析'
    )

    parser.add_argument(
        '--serve',
        action='store_true',
        help='啟動 FastAPI 後端服務（同時執行分析任務）'
    )

    parser.add_argument(
        '--serve-only',
        action='store_true',
        help='僅啟動 FastAPI 後端服務，不自動執行分析'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='FastAPI 服務端口（默認使用 WEBUI_PORT，未配置時為 8000）'
    )

    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='FastAPI 服務監聽地址（默認使用 WEBUI_HOST，未配置時為 127.0.0.1）'
    )

    parser.add_argument(
        '--no-context-snapshot',
        action='store_true',
        help='不保存分析上下文快照'
    )

    # === Backtest ===
    parser.add_argument(
        '--backtest',
        action='store_true',
        help='運行回測（對歷史分析結果進行評估）'
    )

    parser.add_argument(
        '--backtest-code',
        type=str,
        default=None,
        help='僅回測指定股票代碼'
    )

    parser.add_argument(
        '--backtest-days',
        type=int,
        default=None,
        help='回測評估窗口（交易日數，默認使用配置）'
    )

    parser.add_argument(
        '--backtest-force',
        action='store_true',
        help='強制回測（即使已有回測結果也重新計算）'
    )

    # === ETF Rotation ===
    parser.add_argument(
        '--etf-rotation',
        action='store_true',
        help='運行 ETF 轮动：輸出最新調倉信號與規則回測報告（不调用 LLM，配置見 ETF_ROTATION_*）'
    )

    return parser.parse_args()


def _startup_config_warnings(config: Config, args: argparse.Namespace) -> List[str]:
    """Return startup config messages, minus those this invocation already resolves."""
    resolved_issues = set()
    if getattr(args, "stocks", None) or getattr(args, "portfolio", None):
        resolved_issues.add(
            ("STOCK_LIST", "未配置 STOCK_LIST。请设置至少一个股票代码，例如：600519,hk00700,AAPL。")
        )
    if getattr(args, "no_notify", False):
        # 該 field 是“未配置任何通知渠道”這一條告警的歸屬字段
        resolved_issues.add(("WECHAT_WEBHOOK_URL", "未配置通知渠道，将不发送推送通知"))
    return [
        issue.message
        for issue in config.validate_structured()
        if not any(
            issue.field == field and issue.message == message
            for field, message in resolved_issues
        )
    ]


def _compute_trading_day_filter(
    config: Config,
    args: argparse.Namespace,
    stock_codes: List[str],
) -> Tuple[List[str], Optional[str], bool]:
    """
    Compute filtered stock list and effective market review region (Issue #373).

    Returns:
        (filtered_codes, effective_region, should_skip_all)
        - effective_region None = use config default (check disabled)
        - effective_region '' = all relevant markets closed, skip market review
        - should_skip_all: skip entire run when no stocks and no market review to run
    """
    force_run = getattr(args, 'force_run', False)
    if force_run or not getattr(config, 'trading_day_check_enabled', True):
        return (stock_codes, None, False)

    from src.core.trading_calendar import (
        get_market_for_stock,
        get_open_markets_today,
        compute_effective_region,
    )

    open_markets = get_open_markets_today()
    filtered_codes = []
    for code in stock_codes:
        mkt = get_market_for_stock(code)
        if mkt is None:
            # 指數 code（如 sh000016/csi930955/930955.CSI）的 get_market_for_stock
            # 返回 None，若直接 fail-open 保留，A 股休市日指數不會被過濾，破壞
            # per-stock 交易日契約。對市場未知的 code 用 parse_analysis_target
            # 判型，已登記指數按 market=cn 參與 CN 交易日過濾；仍未知的非指數
            # code 繼續 fail-open 保留。
            target = parse_analysis_target(code)
            if target.asset_type == ParseStatus.INDEX:
                mkt = "cn"
        if mkt in open_markets or mkt is None:
            filtered_codes.append(code)

    if config.market_review_enabled and not getattr(args, 'no_market_review', False):
        effective_region = compute_effective_region(
            getattr(config, 'market_review_region', 'cn') or 'cn', open_markets
        )
    else:
        effective_region = None

    should_skip_all = (not filtered_codes) and (effective_region or '') == ''
    return (filtered_codes, effective_region, should_skip_all)


def _classify_stock_list_tokens(
    tokens: List[str],
    *,
    entry_label: str,
) -> Optional[Tuple[List[str], List[AnalysisTarget]]]:
    """Classify stock-list tokens into aligned ``(stock_codes, analysis_targets)``.

    Shared by the one-shot ``--stocks`` entry and the GitHub Actions
    ``STOCK_LIST`` entry: explicit index tokens resolve through
    ``parse_analysis_target`` and keep their index canonical, while every
    other token keeps the legacy ``resolve_index_stock_code_for_analysis``
    path. ``unsupported`` tokens (e.g. an unregistered ``.CSI``) reject the
    whole run up-front with an explicit error — provider calls are never
    reached for any token in the batch. Returns ``None`` after logging the
    rejection, so callers exit without running analysis.
    """
    targets = [parse_analysis_target(t) for t in tokens]
    unsupported = [
        (token, target.unsupported_reason or "unsupported target")
        for token, target in zip(tokens, targets)
        if target.asset_type == ParseStatus.UNSUPPORTED
    ]
    if unsupported:
        token, reason = unsupported[0]
        logger.error(
            "%s 包含不支持的目標 %r：%s；本輪不執行任何分析。",
            entry_label,
            token,
            reason,
        )
        return None
    stock_codes = [
        t.canonical_id
        if t.asset_type == ParseStatus.INDEX
        else resolve_index_stock_code_for_analysis(raw)
        for t, raw in zip(targets, tokens)
    ]
    return stock_codes, targets


def _run_market_review_with_shared_lock(
    config: Config,
    run_market_review_func: Callable[..., Any],
    **kwargs: Any,
) -> Any:
    from src.core.market_review_lock import (
        release_market_review_lock,
        try_acquire_market_review_lock,
    )

    lock_token = try_acquire_market_review_lock(config)
    if lock_token is None:
        logger.warning("大盘复盘正在執行中，跳過本次大盘复盘")
        return None

    try:
        params = dict(kwargs)
        params.setdefault("config", config)
        return run_market_review_func(**params)
    finally:
        release_market_review_lock(lock_token)


def _is_multi_market_region(region: str) -> bool:
    normalized = str(region or "").strip().lower()
    if not normalized:
        return False
    if normalized == "both":
        return True
    parts = {item.strip() for item in normalized.split(",") if item.strip()}
    return len(parts) > 1


def _refresh_stock_index_cache_for_analysis(config: Config) -> None:
    """Best-effort stock-index refresh for CLI/scheduled analysis paths."""
    try:
        from src.services.stock_index_remote_service import (
            refresh_remote_stock_index_cache,
            settings_from_config,
        )

        result = refresh_remote_stock_index_cache(settings_from_config(config))
        if result.refreshed:
            logger.info("[stock-index] 分析前已刷新股票索引緩存: %s", result.cache_path)
        elif result.error:
            logger.debug("[stock-index] 分析前刷新未完成，繼續使用本地索引: %s", result.error)
    except Exception as exc:  # noqa: BLE001 - stock index freshness must not block analysis.
        logger.warning("[stock-index] 分析前刷新股票索引失敗，繼續執行分析: %s", exc)


def _resolve_portfolio_stock_codes(args: argparse.Namespace) -> Optional[List[str]]:
    """Resolve an optional broker portfolio into the analysis stock list."""
    portfolio = str(getattr(args, "portfolio", "") or "").strip().lower()
    if not portfolio:
        return None
    if portfolio != "futu":  # argparse prevents this for CLI callers; keep API callers safe.
        raise ValueError(f"不支持的 portfolio: {portfolio}")

    from src.brokers.futu.portfolio import load_futu_stock_codes

    stock_codes = [
        canonical_stock_code(code)
        for code in load_futu_stock_codes()
        if (code or "").strip()
    ]
    logger.info("portfolio=futu 已覆蓋 stocks/STOCK_LIST，使用 %d 只真實正股", len(stock_codes))
    return stock_codes


def _resolve_gate_expected_stock_codes(
    config: Config,
    args: argparse.Namespace,
    *,
    stock_codes: Optional[List[str]] = None,
) -> Tuple[Optional[List[str]], Optional[str]]:
    """Resolve the startup dedup gate's expected list like the run entry.

    Mirrors ``run_full_analysis``' real target resolution (Futu portfolio
    first, then the ``STOCK_LIST`` .env hot-reload, then the trading-day
    filter) so the skip decision uses what THIS startup would actually
    analyze instead of a possibly stale ``config.stock_list`` snapshot
    (second-round review blockers OR-COR-e59aed48 / OR-COR-c4971c31).

    The result is a snapshot taken at gate time: if the portfolio or the
    .env watchlist changes strictly after this resolution but before the
    run re-resolves them, the gate may miss that and a new target waits
    for the next scheduled run. The drift direction still never skips a
    run that would cover more than recorded (fail-open), and the residual
    race window is a single task invocation.

    Returns ``(expected_codes, fail_open_reason)``:

    - Portfolio mode: the trading-day-filtered live position codes. An
      empty filtered list (no positions / no open market) can never prove
      coverage, so it returns a fail-open reason instead — the run itself
      decides downstream, the gate never skips on it.
    - Non-portfolio mode: mirrors the run's refresh condition verbatim
      (``stock_codes is None`` on the schedule path; the refresh is
      idempotent on the same config object the run reuses) and keeps the
      existing semantics for an empty config watchlist (pure-review dedup).
    - Any resolution failure fails open too: ``None`` expected codes plus a
      reason string for the gate log. Never miss a run outranks never
      re-run.
    """
    try:
        portfolio_stock_codes = _resolve_portfolio_stock_codes(args)
        if portfolio_stock_codes is not None:
            filtered_codes, _, _ = _compute_trading_day_filter(
                config, args, portfolio_stock_codes
            )
            if not filtered_codes:
                return (None, "portfolio mode resolved no tradable targets")
            return (filtered_codes, None)

        # Issue #529: keep this condition verbatim-identical to
        # run_full_analysis — hot-reload STOCK_LIST from .env before a
        # config-list run. The gate and the run share the same config
        # object, so this refresh converges to what the run would do anyway.
        if stock_codes is None:
            config.refresh_stock_list()
        effective_codes = (
            stock_codes
            if stock_codes is not None
            else getattr(config, "stock_list", None) or []
        )
        filtered_codes, _, _ = _compute_trading_day_filter(
            config, args, effective_codes
        )
        return (filtered_codes, None)
    except Exception as exc:  # noqa: BLE001 - the gate must never block a run
        return (None, f"target resolution failed: {exc}")


def _prime_daily_market_context(
    config: Config,
    pipeline: Any,
    *,
    region: str,
    no_market_review: bool,
    allow_generate: bool,
    force_refresh: bool = False,
    target_date: Optional[date] = None,
    return_full_report: bool = False,
    require_current_query_match: bool = False,
) -> Union[str, Tuple[str, str]]:
    """Load/reuse the run's market context, avoiding unbounded background generation."""
    if no_market_review or not region:
        return ("", "") if return_full_report else ""

    from src.services.daily_market_context import DailyMarketContextService

    if not _is_multi_market_region(region):
        service = getattr(pipeline, "_daily_market_context_service", None)
        if service is None:
            service = DailyMarketContextService(db_manager=pipeline.db)
            pipeline._daily_market_context_service = service
    else:
        service = DailyMarketContextService(db_manager=pipeline.db)

    get_context_kwargs = {
        "region": region,
        "config": config,
        "notifier": pipeline.notifier,
        "analyzer": pipeline.analyzer,
        "search_service": pipeline.search_service,
        "force_refresh": force_refresh,
        "allow_generate": allow_generate,
        "persist_market_review_history": False,
        "target_date": target_date,
        "require_query_id_match": require_current_query_match,
    }
    current_query_id = getattr(pipeline, "query_id", None)
    if isinstance(current_query_id, str) and current_query_id.strip():
        get_context_kwargs["current_query_id"] = current_query_id

    context = service.get_context(**get_context_kwargs)
    if context is None:
        return ("", "") if return_full_report else ""

    # Runtime context generation is preload-only and must not replace the full
    # market review run, except the query-scoped fallback after that run fails.
    if context.source != "analysis_history" and not (
        require_current_query_match and context.source == "market_review_runtime"
    ):
        return ("", "") if return_full_report else ""

    summary = str(getattr(context, "summary", ""))
    full_report = str(getattr(context, "full_report", "") or "")
    if return_full_report:
        return summary, full_report
    return summary


def _can_reuse_market_context_for_review(summary: str, region: str) -> bool:
    if not summary:
        return False
    normalized = str(region or "").strip().lower()
    if normalized == "both":
        return False
    parts = {item.strip() for item in normalized.split(",") if item.strip()}
    return len(parts) <= 1


def _resolve_daily_market_context_market(market: str, normalized_region: str) -> str:
    if "," not in normalized_region:
        return market
    parts = [item.strip() for item in normalized_region.split(",") if item.strip()]
    if parts and all(item in {"jp", "kr"} for item in parts):
        return parts[0]
    return market


def _resolve_daily_market_context_target_date(
    region: str,
    current_time: datetime,
) -> date:
    normalized_region = str(region or "cn").strip().lower()
    market = normalized_region if normalized_region in {"cn", "hk", "us", "jp", "kr"} else "cn"

    from src.core.trading_calendar import get_effective_trading_date

    return get_effective_trading_date(
        _resolve_daily_market_context_market(market, normalized_region),
        current_time=current_time,
    )


def _market_review_report_text(review_result: Any) -> str:
    if review_result is None:
        return ""
    report = getattr(review_result, "report", None)
    if isinstance(report, str):
        return report
    return review_result if isinstance(review_result, str) else ""


def _save_reused_market_review_report(
    notifier: Any,
    market_report: str,
    *,
    config: Config,
    trigger_source: str,
    region: str,
) -> None:
    body = str(market_report or "").strip()
    if not body:
        return
    title = (
        "# 🎯 Market Review"
        if str(getattr(config, "report_language", "zh")).strip().lower() == "en"
        else "# 🎯 大盘复盘"
    )
    if not any(body.startswith(item) for item in ("# 🎯 大盘复盘", "# 🎯 Market Review")):
        body = f"{title}\n\n{body}"
    try:
        date_str = datetime.now().strftime('%Y%m%d')
        report_filename = f"market_review_{date_str}.md"
        filepath = notifier.save_report_to_file(body, report_filename)
        logger.info(
            "[MarketReview] component=market_review action=save_reused_report "
            "trigger_source=%s region=%s path=%s",
            trigger_source,
            region,
            filepath,
        )
    except Exception as exc:
        logger.warning("複用大盘上下文保存大盘复盘報告失敗: %s", exc)


def _run_auto_backtest(config: Config) -> None:
    """Run the independently configured auto-backtest without failing analysis."""

    try:
        if not getattr(config, 'backtest_enabled', False):
            return

        from src.services.backtest_service import BacktestService

        logger.info("開始自動回測...")
        service = BacktestService()
        stats = service.run_backtest(
            force=False,
            eval_window_days=getattr(config, 'backtest_eval_window_days', 10),
            min_age_days=getattr(config, 'backtest_min_age_days', 14),
            limit=200,
        )
        logger.info(
            f"自動回測完成: processed={stats.get('processed')} "
            f"saved={stats.get('saved')} completed={stats.get('completed')} "
            f"insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
        )
    except Exception as exc:
        logger.warning(f"自動回測失敗（已忽略）: {exc}")


def _all_stock_targets_succeeded(
    stock_codes: Optional[List[str]],
    results: List[Any],
) -> bool:
    """Return True only when every requested stock target produced a result.

    ``StockAnalysisPipeline.run`` returns just the successful results, so
    run completeness is "every requested code shows up in the results".
    Both sides normalize to ``str(code)`` — exactly the normalization the
    run marker's ``stock_codes`` field uses — and order/duplicates are
    ignored. An empty target list is a vacuous success (pure-review
    deployments keep their same-day dedup). Market-review completeness is
    deliberately NOT part of this check: a failing review must never
    resurrect the restart loop the dedup gate fixes (the daily run
    backfills it).
    """
    try:
        requested = {str(code) for code in (stock_codes or [])}
        produced = {
            str(getattr(result, "code", "")) for result in (results or [])
        }
        return requested.issubset(produced)
    except Exception:  # pragma: no cover - defensive: a bookkeeping error
        # must never break the analysis run; not recording the marker just
        # makes the next startup re-run (fail-open).
        return False


def run_full_analysis(
    config: Config,
    args: argparse.Namespace,
    stock_codes: Optional[List[str]] = None,
    *,
    raise_errors: bool = False,
    analysis_targets: Optional[List[AnalysisTarget]] = None,
    refresh_watchlist: bool = True,
) -> bool:
    """
    執行完整的分析流程（個股 + 大盤覆盤）

    這是定時任務調用的主函數。Futu 持倉解析失敗始終傳播給調用方；
    ``raise_errors`` 只控制持倉解析成功後的分析流程異常語義。
    ``analysis_targets`` 與 ``stock_codes`` 對齊，攜帶結構化分析目標
    （指數目標用於推導 market=cn 與能力矩陣）。
    ``refresh_watchlist=False`` 僅用於已原子認領的定時快照，避免認領後再次熱更新。
    """
    # Capture the entry-level stock list for the run-marker scope: the local
    # ``stock_codes`` variable is later replaced by the trading-day filter and
    # Futu positions, so it must never feed the dedup decision (the marker
    # fingerprint always comes from config.stock_list on both sides).
    entry_stock_codes = stock_codes
    # Portfolio resolution is its own CLI contract boundary. A broker import
    # failure must reach the one-shot caller, while all later work keeps the
    # existing run_full_analysis return-value semantics.
    portfolio_stock_codes = _resolve_portfolio_stock_codes(args)
    portfolio_is_empty = portfolio_stock_codes == []
    market_review_requested = (
        getattr(config, 'market_review_enabled', False)
        and not getattr(args, 'no_market_review', False)
    )
    if portfolio_is_empty and not market_review_requested:
        logger.info(
            "真實賬戶中無符合條件的 Futu 持倉，"
            "本輪跳過个股分析和大盘复盘。"
        )
        _run_auto_backtest(config)
        return True

    # Import pipeline modules outside the broad try/except so that import-time
    # failures propagate to the caller instead of being silently swallowed.
    from src.core.market_review import run_market_review
    from src.core.pipeline import StockAnalysisPipeline

    global _LAST_ANALYSIS_FAILURE_REASON
    _LAST_ANALYSIS_FAILURE_REASON = None

    def _return_with_auto_backtest(result: bool) -> bool:
        _run_auto_backtest(config)
        return result

    try:
        _refresh_stock_index_cache_for_analysis(config)
        if portfolio_stock_codes is not None:
            stock_codes = portfolio_stock_codes
            analysis_targets = None

        # Issue #529: Hot-reload STOCK_LIST from .env on each scheduled run
        if stock_codes is None and portfolio_stock_codes is None and refresh_watchlist:
            config.refresh_stock_list()

        using_config_stock_list = stock_codes is None and portfolio_stock_codes is None
        effective_codes = stock_codes if stock_codes is not None else config.stock_list
        # Fail fast on an empty persisted watchlist before trading-day filtering.
        # Otherwise should_skip=True would mask the configuration error as success.
        if (
            not getattr(args, "dry_run", False)
            and using_config_stock_list
            and not effective_codes
            and not market_review_requested
        ):
            _LAST_ANALYSIS_FAILURE_REASON = "empty_stock_list"
            logger.error(
                "本輪分析未生成報告：STOCK_LIST 為空，且未啟用大盘复盘。"
            )
            return _return_with_auto_backtest(False)

        # Issue #373: Trading day filter (per-stock, per-market)
        filtered_codes, effective_region, should_skip = _compute_trading_day_filter(
            config, args, effective_codes
        )
        if should_skip:
            if portfolio_is_empty:
                logger.info(
                    "真實賬戶中無符合條件的 Futu 持倉，"
                    "本輪无需執行个股分析或大盘复盘，跳過執行。"
                )
            else:
                logger.info(
                    "今日所有相關市場均為非交易日，跳過執行。"
                    "可使用 --force-run 強制執行。"
                )
            return True
        if set(filtered_codes) != set(effective_codes):
            skipped = set(effective_codes) - set(filtered_codes)
            logger.info("今日休市股票已跳過: %s", skipped)
        if analysis_targets is not None:
            if len(analysis_targets) != len(effective_codes):
                raise ValueError("analysis_targets must align with stock_codes")
            remaining_pairs = list(zip(effective_codes, analysis_targets))
            filtered_targets = []
            for filtered_code in filtered_codes:
                for index, (code, target) in enumerate(remaining_pairs):
                    if code == filtered_code:
                        filtered_targets.append(target)
                        remaining_pairs.pop(index)
                        break
            analysis_targets = filtered_targets
        stock_codes = filtered_codes
        skip_futu_stock_analysis = (
            portfolio_stock_codes is not None and not stock_codes
        )

        # 命令行參數 --single-notify 覆蓋配置（#55）
        if getattr(args, 'single_notify', False):
            config.single_stock_notify = True

        # Issue #190: 個股與大盤覆盤合併推送
        merge_notification = (
            getattr(config, 'merge_email_notification', False)
            and config.market_review_enabled
            and not getattr(args, 'no_market_review', False)
            and not config.single_stock_notify
        )

        # 創建調度器
        save_context_snapshot = None
        if getattr(args, 'no_context_snapshot', False):
            save_context_snapshot = False
        query_id = uuid.uuid4().hex
        market_review_region = (
            effective_region
            if effective_region is not None
            else (getattr(config, 'market_review_region', 'cn') or 'cn')
        )
        should_run_market_review = (
            config.market_review_enabled
            and not args.no_market_review
            and (market_review_region or '') != ''
        )
        if (
            not getattr(args, "dry_run", False)
            and not stock_codes
            and using_config_stock_list
            and not should_run_market_review
        ):
            _LAST_ANALYSIS_FAILURE_REASON = "empty_stock_list"
            logger.error(
                "本輪分析未生成報告：STOCK_LIST 為空，且未啟用大盘复盘。"
            )
            return _return_with_auto_backtest(False)
        should_use_daily_market_context = (
            should_run_market_review
            and getattr(config, 'daily_market_context_enabled', True)
        )
        analysis_reference_time = datetime.now(timezone.utc)
        daily_market_context_target_date = None
        if should_use_daily_market_context:
            daily_market_context_target_date = _resolve_daily_market_context_target_date(
                market_review_region,
                analysis_reference_time,
            )
        market_report = ""
        market_context_summary = ""
        market_context_full_report = ""
        market_context_generated_during_stock = False
        pipeline = StockAnalysisPipeline(
            config=config,
            max_workers=args.workers,
            query_id=query_id,
            query_source="cli",
            save_context_snapshot=save_context_snapshot,
            daily_market_context_enabled=should_use_daily_market_context,
            daily_market_context_allow_generate=should_use_daily_market_context,
        )
        if should_use_daily_market_context:
            # Prompt-side context can reuse historical summaries, while full-merge
            # content must avoid silently reusing unrelated historical reports.
            _prime_daily_market_context(
                config,
                pipeline=pipeline,
                region=market_review_region,
                no_market_review=args.no_market_review,
                allow_generate=False,
                target_date=daily_market_context_target_date,
                return_full_report=False,
            )
            (
                market_context_summary,
                market_context_full_report,
            ) = _prime_daily_market_context(
                config,
                pipeline=pipeline,
                region=market_review_region,
                no_market_review=args.no_market_review,
                allow_generate=False,
                target_date=daily_market_context_target_date,
                return_full_report=True,
                require_current_query_match=True,
            )

        # 1. 運行個股分析
        if skip_futu_stock_analysis:
            if portfolio_is_empty:
                logger.info("真實賬戶中無符合條件的 Futu 持倉，跳過个股分析。")
            else:
                logger.info("Futu 持倉經交易日過濾後無可分析股票，跳過个股分析。")
            results = []
        else:
            results = pipeline.run(
                stock_codes=stock_codes,
                dry_run=args.dry_run,
                send_notification=not args.no_notify,
                merge_notification=merge_notification,
                current_time=analysis_reference_time,
                analysis_targets=analysis_targets,
            )

        if should_use_daily_market_context and not market_context_summary:
            (
                market_context_summary,
                market_context_full_report,
            ) = _prime_daily_market_context(
                config,
                pipeline=pipeline,
                region=market_review_region,
                no_market_review=args.no_market_review,
                allow_generate=False,
                target_date=daily_market_context_target_date,
                return_full_report=True,
                require_current_query_match=True,
            )
            market_context_generated_during_stock = bool(market_context_summary)

        # Issue #128: 分析間隔 - 在個股分析和大盤分析之間添加延遲
        analysis_delay = getattr(config, 'analysis_delay', 0)

        # 2. 運行大盤覆盤（如果啟用且不是僅個股模式）
        if should_run_market_review:
            schedule_mode = bool(
                getattr(args, 'schedule', False)
                or getattr(config, 'schedule_enabled', False)
            )
            review_trigger_source = "schedule" if schedule_mode else "cli"
            can_reuse_market_context = (
                _can_reuse_market_context_for_review(
                    market_context_summary,
                    market_review_region,
                )
                if should_use_daily_market_context
                else False
            )

            can_skip_market_review = (
                (merge_notification or market_context_generated_during_stock)
                and can_reuse_market_context
                and bool(market_context_full_report or market_context_summary)
            )
            if can_skip_market_review:
                market_report = market_context_full_report or market_context_summary
                logger.info(
                    "覆盤上下文可複用，跳過重複大盘复盘並複用上下文內容。"
                )
                _save_reused_market_review_report(
                    pipeline.notifier,
                    market_report,
                    config=config,
                    trigger_source=review_trigger_source,
                    region=market_review_region,
                )
                if (
                    market_context_generated_during_stock
                    and not merge_notification
                    and not args.no_notify
                    and pipeline.notifier.is_available()
                ):
                    if pipeline.notifier.send(
                        f"# 📈 大盘复盘\n\n{market_report}",
                        email_send_to_all=True,
                        route_type="report",
                    ):
                        logger.info("複用本輪大盘上下文推送大盘复盘成功")
                    else:
                        logger.warning("複用本輪大盘上下文推送大盘复盘失敗")

            review_result = None
            if not can_skip_market_review:
                if analysis_delay > 0:
                    logger.info(f"等待 {analysis_delay} 秒後執行大盘复盘（避免API限流）...")
                    time.sleep(analysis_delay)

                review_result = _run_market_review_with_shared_lock(
                    config,
                    run_market_review,
                    notifier=pipeline.notifier,
                    analyzer=pipeline.analyzer,
                    search_service=pipeline.search_service,
                    send_notification=not args.no_notify,
                    merge_notification=merge_notification,
                    override_region=market_review_region,
                    query_id=query_id,
                    trigger_source=review_trigger_source,
                )
                # 如果覆盤仍未執行成功，再做一次複用歷史/緩存讀取（防止與併發運行競態）。
                if not review_result and should_use_daily_market_context:
                    (
                        market_context_summary,
                        market_context_full_report,
                    ) = _prime_daily_market_context(
                        config,
                        pipeline=pipeline,
                        region=market_review_region,
                        no_market_review=args.no_market_review,
                        allow_generate=False,
                        target_date=daily_market_context_target_date,
                        return_full_report=True,
                        require_current_query_match=True,
                    )
                    can_reuse_market_context = _can_reuse_market_context_for_review(
                        market_context_summary,
                        market_review_region,
                    )
                elif not review_result:
                    can_reuse_market_context = False

            # 如果有結果，賦值給 market_report 用於後續飛書文檔生成
            if review_result:
                market_report = _market_review_report_text(review_result)
            elif can_reuse_market_context:
                market_report = market_context_full_report or market_context_summary

        expected_stock_report = (
            not getattr(args, "dry_run", False)
            and bool(stock_codes)
            and not skip_futu_stock_analysis
        )
        deferred_failure_result = None
        if expected_stock_report and results and not getattr(
            pipeline, "_last_local_report_path", None
        ):
            _LAST_ANALYSIS_FAILURE_REASON = "report_save_failed"
            save_error = getattr(pipeline, "_last_local_report_error", None) or "unknown error"
            logger.error(
                "本輪分析已生成个股結果，但彙總報告保存失敗，未生成本地報告文件: %s",
                save_error,
            )
            deferred_failure_result = False
        expected_market_report = (
            not getattr(args, "dry_run", False)
            and should_run_market_review
        )
        if (expected_stock_report or expected_market_report) and not results and not market_report:
            _LAST_ANALYSIS_FAILURE_REASON = "no_report"
            logger.error(
                "本輪分析未生成任何報告：預期的个股分析或大盘复盘均未產出結果。"
            )
            return _return_with_auto_backtest(False)

        # Issue #190: 合併推送（個股+大盤覆盤）
        if merge_notification and (results or market_report) and not args.no_notify:
            parts = []
            if market_report:
                parts.append(f"# 📈 大盘复盘\n\n{market_report}")
            if results:
                dashboard_content = pipeline.notifier.generate_aggregate_report(
                    results,
                    getattr(config, 'report_type', 'simple'),
                )
                parts.append(f"# 🚀 个股决策仪表盘\n\n{dashboard_content}")
            if parts:
                combined_content = "\n\n---\n\n".join(parts)
                if pipeline.notifier.is_available():
                    if pipeline.notifier.send(combined_content, email_send_to_all=True, route_type="report"):
                        logger.info("已合併推送（个股+大盘复盘）")
                    else:
                        logger.warning("合併推送失敗")

        # 輸出摘要
        if results:
            logger.info("\n===== 分析結果摘要 =====")
            for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
                emoji = r.get_emoji()
                logger.info(
                    f"{emoji} {r.name}({r.code}): {r.operation_advice} | "
                    f"评分 {r.sentiment_score} | {r.trend_prediction}"
                )

        logger.info("\n任務執行完成")

        # === 新增：生成飛書雲文檔 ===
        try:
            from src.feishu_doc import FeishuDocManager

            feishu_doc = FeishuDocManager()
            if feishu_doc.is_configured() and (results or market_report):
                logger.info("正在創建飛書雲文檔...")

                # 1. 準備標題 "01-01 13:01大盤覆盤"
                tz_cn = timezone(timedelta(hours=8))
                now = datetime.now(tz_cn)
                doc_title = f"{now.strftime('%Y-%m-%d %H:%M')} 大盘复盘"

                # 2. 準備內容 (拼接個股分析和大盤覆盤)
                full_content = ""

                # 添加大盤覆盤內容（如果有）
                if market_report:
                    full_content += f"# 📈 大盘复盘\n\n{market_report}\n\n---\n\n"

                # 添加個股決策儀表盤（使用 NotificationService 生成，按 report_type 分支）
                if results:
                    dashboard_content = pipeline.notifier.generate_aggregate_report(
                        results,
                        getattr(config, 'report_type', 'simple'),
                    )
                    full_content += f"# 🚀 个股决策仪表盘\n\n{dashboard_content}"

                # 3. 創建文檔
                doc_url = feishu_doc.create_daily_doc(doc_title, full_content)
                if doc_url:
                    logger.info(f"飛書雲文檔創建成功: {doc_url}")
                    # 可選：將文檔鏈接也推送到群裡
                    if not args.no_notify:
                        pipeline.notifier.send(
                            f"[{now.strftime('%Y-%m-%d %H:%M')}] 覆盤文檔創建成功: {doc_url}",
                            route_type="report",
                        )

        except Exception as e:
            logger.error(f"飛書文檔生成失敗: {e}")

        final_result = (
            deferred_failure_result
            if deferred_failure_result is not None
            else True
        )
        # Startup daily dedup bookkeeping: only a genuinely successful AND
        # complete run records the marker — every requested stock target
        # must have produced a result (pipeline.run returns just the
        # successes, so partial failures shrink ``results``). Skip paths,
        # failures and partial-failure rounds must not record, otherwise a
        # restart would wrongly dedup away the missing stocks. The scope
        # reflects the entry-level stock list; the covered ``stock_codes``
        # are written verbatim (str(code), same normalization as the
        # completeness check); the stock-list fingerprint stays an
        # observability field computed inside the marker module.
        if (
            final_result is True
            and _all_stock_targets_succeeded(stock_codes, results)
            and not getattr(args, "dry_run", False)
        ):
            record_analysis_run_marker(
                config,
                scope="subset" if entry_stock_codes is not None else "full",
                stock_codes=stock_codes,
                market_review_requested=market_review_requested,
                market_review_completed=(
                    bool(market_report) if market_review_requested else None
                ),
                args=args,
            )
        return _return_with_auto_backtest(final_result)

    except Exception as e:
        if _LAST_ANALYSIS_FAILURE_REASON is None:
            _LAST_ANALYSIS_FAILURE_REASON = "runtime_error"
        logger.exception(f"分析流程執行失敗: {e}")
        if raise_errors:
            raise
        return False


def run_scheduled_analysis(
    config: Config,
    args: argparse.Namespace,
    stock_codes: Optional[List[str]] = None,
) -> bool:
    """Run scheduled analysis with failures propagated to the scheduler."""
    scheduled_for = getattr(args, "_scheduled_for", None)
    if scheduled_for is None:
        return run_full_analysis(config, args, stock_codes, raise_errors=True)

    from src.services.scheduled_analysis_claim import run_claimed_scheduled_analysis

    return run_claimed_scheduled_analysis(
        config, args, scheduled_for,
        lambda snapshot: run_full_analysis(
            snapshot, args, stock_codes, raise_errors=True, refresh_watchlist=False,
        ),
    )


def _run_analysis_with_runtime_scheduler_lock(
    config: Config,
    args: argparse.Namespace,
    stock_codes: Optional[List[str]] = None,
    analysis_targets: Optional[List[AnalysisTarget]] = None,
) -> bool:
    from src.services.runtime_scheduler import run_with_global_analysis_lock

    task_result: Dict[str, bool] = {"ok": True}

    def _locked_task_runner(
        locked_config: Config,
        locked_args: argparse.Namespace,
        locked_stock_codes: Optional[List[str]] = None,
    ) -> bool:
        if analysis_targets is None:
            result = run_full_analysis(locked_config, locked_args, locked_stock_codes)
        else:
            result = run_full_analysis(
                locked_config,
                locked_args,
                locked_stock_codes,
                analysis_targets=analysis_targets,
            )
        task_result["ok"] = bool(result)
        return task_result["ok"]

    # Keep startup/triggered analysis in sync with API runtime scheduler and
    # run-now entrypoint. Blocking is expected here because startup paths should
    # wait for an in-flight job before returning a response.
    lock_acquired = run_with_global_analysis_lock(
        task_runner=_locked_task_runner,
        config=config,
        args=args,
        stock_codes=stock_codes,
        blocking=True,
    )
    return bool(lock_acquired and task_result["ok"])


def start_api_server(host: str, port: int, config: Config) -> None:
    """
    在後臺線程啟動 FastAPI 服務

    Args:
        host: 監聽地址
        port: 監聽端口
        config: 配置對象
    """
    import socket
    import threading
    import uvicorn

    probe = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError as exc:
        raise RuntimeError(f"FastAPI port is not available: {host}:{port}") from exc
    finally:
        probe.close()

    level_name = (config.log_level or "INFO").lower()
    use_config_signal_handlers = True
    uvicorn_kwargs = {
        "host": host,
        "port": port,
        "log_level": level_name,
        "log_config": None,
    }
    # Import the ASGI app object in the calling thread instead of handing uvicorn
    # the "api.app:app" import string. With the string, uvicorn imports the app
    # lazily inside the server thread, and that import (litellm + the full app
    # tree, ~10s+ on constrained hosts) runs inside the startup probe window
    # below, tripping the 3.0s timeout and causing a restart loop on slower
    # machines. Importing first keeps the heavy work out of the probe window;
    # genuine import failures still surface immediately to the caller.
    from api.app import app as fastapi_app
    from api.middlewares.security_guard import uvicorn_proxy_kwargs

    uvicorn_kwargs.update(uvicorn_proxy_kwargs())

    try:
        uvicorn_config = uvicorn.Config(
            fastapi_app,
            install_signal_handlers=False,
            **uvicorn_kwargs,
        )
    except TypeError:
        # Older uvicorn versions do not accept install_signal_handlers in
        # Config; fall back and only disable signal handling via Server attribute
        # when it's a boolean flag.
        use_config_signal_handlers = False
        uvicorn_config = uvicorn.Config(
            fastapi_app,
            **uvicorn_kwargs,
        )
    uvicorn_server = uvicorn.Server(config=uvicorn_config)
    if not use_config_signal_handlers:
        install_signal_handlers = getattr(uvicorn_server, "install_signal_handlers", None)
        if isinstance(install_signal_handlers, bool):
            uvicorn_server.install_signal_handlers = False

    startup_error: list[BaseException] = []

    def run_server():
        try:
            uvicorn_server.run()
        except Exception as exc:  # noqa: BLE001 - surface startup issues to caller promptly
            startup_error.append(exc)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    timeout_seconds = 3.0
    wait_deadline = time.time() + timeout_seconds
    while time.time() < wait_deadline:
        if startup_error:
            raise RuntimeError(
                f"FastAPI server failed to start: {host}:{port}; {startup_error[0]}"
            )
        if uvicorn_server.started:
            logger.info(f"FastAPI 服務已啟動: http://{host}:{port}")
            return
        if not thread.is_alive():
            break
        time.sleep(0.05)

    if startup_error:
        raise RuntimeError(f"FastAPI server failed to start: {host}:{port}; {startup_error[0]}")
    if uvicorn_server.started:
        logger.info(f"FastAPI 服務已啟動: http://{host}:{port}")
        return
    if not thread.is_alive():
        raise RuntimeError(f"FastAPI 服務器啟動後立即退出: {host}:{port}")

    raise RuntimeError(f"FastAPI 服務在 {timeout_seconds:.1f}s 內未完成啟動: {host}:{port}")


def _is_truthy_env(var_name: str, default: str = "true") -> bool:
    """Parse common truthy / falsy environment values."""
    value = os.getenv(var_name, default).strip().lower()
    return value not in {"0", "false", "no", "off"}


def start_bot_stream_clients(config: Config) -> None:
    """Start bot stream clients when enabled in config."""
    # 啟動釘釘 Stream 客戶端
    if config.dingtalk_stream_enabled:
        try:
            from bot.platforms import start_dingtalk_stream_background, DINGTALK_STREAM_AVAILABLE
            if DINGTALK_STREAM_AVAILABLE:
                if start_dingtalk_stream_background():
                    logger.info("[Main] Dingtalk Stream client started in background.")
                else:
                    logger.warning("[Main] Dingtalk Stream client failed to start.")
            else:
                logger.warning("[Main] Dingtalk Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install dingtalk-stream")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Dingtalk Stream client: {exc}")

    # 啟動飛書 Stream 客戶端
    if getattr(config, 'feishu_stream_enabled', False):
        try:
            from bot.platforms import start_feishu_stream_background, FEISHU_SDK_AVAILABLE
            if FEISHU_SDK_AVAILABLE:
                if start_feishu_stream_background():
                    logger.info("[Main] Feishu Stream client started in background.")
                else:
                    logger.warning("[Main] Feishu Stream client failed to start.")
            else:
                logger.warning("[Main] Feishu Stream enabled but SDK is missing.")
                logger.warning("[Main] Run: pip install lark-oapi")
        except Exception as exc:
            logger.error(f"[Main] Failed to start Feishu Stream client: {exc}")


def _resolve_scheduled_stock_codes(stock_codes: Optional[List[str]]) -> Optional[List[str]]:
    """Scheduled runs should always read the latest persisted watchlist."""
    if stock_codes is not None:
        logger.warning(
            "定時模式下檢測到 --stocks 參數；計劃執行將忽略啟動時股票快照，並在每次運行前重新讀取最新的 STOCK_LIST。"
        )
    return None


def _skips_stock_entry(args: argparse.Namespace, config: Config) -> bool:
    """Whether the active mode consumes a stock list at all.

    Modes that do not analyze the watchlist must not parse/classify
    ``--stocks``/``STOCK_LIST`` tokens nor refresh the stock-index registry
    before the mode dispatch, otherwise an unsupported index token would
    wrongly block a run that never consumes it. Covered modes:
    ``--backtest``, ``--market-review``, ``--etf-rotation``, ``--serve-only``/``--webui-only``,
    ``--portfolio`` (any value) and ``--schedule``/``config.schedule_enabled``.
    ``--serve`` (not serve-only) and plain one-shot runs still consume the
    stock list and stay outside the guard. The webui-only flag is read
    directly here because the webui -> serve mapping happens only later in
    ``main()``.
    """
    return bool(
        getattr(args, "backtest", False)
        or getattr(args, "etf_rotation", False)
        or getattr(args, "market_review", False)
        or getattr(args, "serve_only", False)
        or getattr(args, "webui_only", False)
        or bool(getattr(args, "portfolio", None))
        or getattr(args, "schedule", False)
        or getattr(config, "schedule_enabled", False)
    )


def _reload_runtime_config() -> Config:
    """Reload config from the latest persisted `.env` values for scheduled runs."""
    _reload_env_file_values_preserving_overrides()
    Config.reset_instance()
    new_config = get_config()

    # Drop the module-level ToolRegistry so the next
    # ``build_agent_executor`` / ``build_agent_chat_executor`` call rebuilds
    # it against the freshly-loaded Config and picks up new
    # ``AGENT_*_TOOL_TIMEOUT_S`` overrides (Issue #1890). Wrap in try/except
    # so a future runtime reset helper cannot crash scheduled-job bootstrap.
    try:
        from src.agent.factory import reset_tool_registry

        reset_tool_registry()
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("Failed to reset tool registry during config reload: %s", exc)

    return new_config


def _build_schedule_time_provider(default_schedule_time: str):
    """Read the latest schedule time directly from the active config file.

    Fallback order:
    1. Process-level env override (set before launch) → honour it.
    2. Persisted config file value (written by WebUI) → use it.
    3. Documented system default ``"18:00"`` → always fall back here so
       that clearing SCHEDULE_TIME in WebUI correctly resets the schedule.
    """
    from src.core.config_manager import ConfigManager

    _SYSTEM_DEFAULT_SCHEDULE_TIME = "18:00"
    manager = ConfigManager()

    def _provider() -> str:
        if "SCHEDULE_TIME" in _INITIAL_PROCESS_ENV:
            return os.getenv("SCHEDULE_TIME", default_schedule_time)

        config_map = manager.read_config_map()
        schedule_time = (config_map.get("SCHEDULE_TIME", "") or "").strip()
        if schedule_time:
            return schedule_time
        return _SYSTEM_DEFAULT_SCHEDULE_TIME

    return _provider


def _build_schedule_times_provider(default_schedule_time: str):
    """Read the latest SCHEDULE_TIMES with SCHEDULE_TIME fallback."""
    from src.core.config_manager import ConfigManager
    from src.scheduler import normalize_schedule_times

    _SYSTEM_DEFAULT_SCHEDULE_TIME = "18:00"
    manager = ConfigManager()

    def _provider():
        if "SCHEDULE_TIMES" in _INITIAL_PROCESS_ENV:
            return normalize_schedule_times(
                os.getenv("SCHEDULE_TIMES", ""),
                fallback_time=os.getenv("SCHEDULE_TIME", default_schedule_time),
            )
        if "SCHEDULE_TIME" in _INITIAL_PROCESS_ENV:
            return normalize_schedule_times(
                os.getenv("SCHEDULE_TIMES", ""),
                fallback_time=os.getenv("SCHEDULE_TIME", default_schedule_time),
            )

        config_map = manager.read_config_map()
        schedule_time = (config_map.get("SCHEDULE_TIME", "") or "").strip() or _SYSTEM_DEFAULT_SCHEDULE_TIME
        return normalize_schedule_times(
            config_map.get("SCHEDULE_TIMES", ""),
            fallback_time=schedule_time,
        )

    return _provider


def main() -> int:
    """
    主入口函數

    Returns:
        退出碼（0 表示成功）
    """
    # 解析命令行參數
    args = parse_arguments()

    # 在配置加載前先初始化 bootstrap 日誌，確保早期失敗也能落盤
    try:
        _setup_bootstrap_logging(debug=args.debug)
    except Exception as exc:
        logging.basicConfig(
            level=logging.DEBUG if getattr(args, "debug", False) else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            stream=sys.stderr,
        )
        logger.warning("Bootstrap 日誌初始化失敗，已回退到 stderr: %s", exc)

    # 加載配置（在 bootstrap logging 之後執行，確保異常有日誌）
    try:
        config = get_config()
    except Exception as exc:
        logger.exception("加載配置失敗: %s", exc)
        return 1

    # 配置日誌（輸出到控制檯和文件）
    try:
        _setup_runtime_logging(config.log_dir, debug=args.debug)
    except Exception as exc:
        logger.exception("切换到配置日誌目錄失敗: %s", exc)
        return 1

    logger.info("=" * 60)
    logger.info("A股自選股智能分析系統 啟動")
    logger.info(f"運行時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 驗證配置
    for warning in _startup_config_warnings(config, args):
        logger.warning(warning)

    if getattr(args, "check_notify", False):
        from src.services.notification_diagnostics import (
            format_notification_diagnostics,
            run_notification_diagnostics,
        )

        result = run_notification_diagnostics(config)
        print(format_notification_diagnostics(result))
        return 0 if result.ok else 1

    # 解析股票列表（統一為大寫 Issue #355）
    # Story 1.5: 一次性 --stocks 入口使用 parse_analysis_target 構造結構化
    # AnalysisTarget 列表，指數目標（sh/sz/csi 前綴與 .CSI alias）在入口即保留
    # 身份語義；unsupported 目標（如未登記 .CSI）在入口明確拒絕，不進入 provider。
    # 不消費個股列表的模式（回測/大盤覆盤/僅服務/portfolio/定時）整體跳過
    # 分類與索引刷新（_skips_stock_entry），避免無關壞 token 攔截模式主體。
    _skip_stock_entry = _skips_stock_entry(args, config)
    if args.stocks and getattr(args, "portfolio", None):
        logger.info("同時指定了 --portfolio；實際分析時 portfolio 將覆蓋 --stocks")
    stock_codes = None
    analysis_targets = None
    if args.stocks and not _skip_stock_entry:
        # 在解析 --stocks 前先 best-effort 刷新股票索引註冊表，保證首次運行能吃到
        # 刷新後的 alias/身份；失敗/超時/禁用不阻斷分析。僅 --stocks 入口需要，
        # 其他模式由 run_full_analysis 內的既有刷新覆蓋。
        _refresh_stock_index_cache_for_analysis(config)
        tokens = [c for c in split_stock_list(args.stocks) if (c or "").strip()]
        resolved = _classify_stock_list_tokens(tokens, entry_label="--stocks")
        if resolved is None:
            return 1
        stock_codes, analysis_targets = resolved
        logger.info(f"使用命令行指定的股票列表: {stock_codes}")
    elif (
        os.getenv("GITHUB_ACTIONS") == "true"
        and not _skip_stock_entry
    ):
        # 每日工作流（GITHUB_ACTIONS=true）無參數運行 `python main.py`（full 或
        # stocks-only 模式）：把 STOCK_LIST token 分類為與一次性 --stocks 等價的
        # 結構化 target，顯式指數 token 進入指數路徑、個股 token 保持既有路徑。
        # 不消費個股列表的模式由 _skips_stock_entry 整體跳過（不刷新不分類），
        # 本地默認路徑不在本入口構造 target。
        raw_value = config.stock_list or []
        raw_tokens = (
            split_stock_list(raw_value)
            if isinstance(raw_value, str)
            else [str(c).strip() for c in raw_value if str(c or "").strip()]
        )
        raw_tokens = [c for c in raw_tokens if (c or "").strip()]
        if raw_tokens:
            _refresh_stock_index_cache_for_analysis(config)
            resolved = _classify_stock_list_tokens(
                raw_tokens, entry_label="GitHub Actions STOCK_LIST"
            )
            if resolved is None:
                return 1
            stock_codes, analysis_targets = resolved
            logger.info(f"GitHub Actions 默認 STOCK_LIST: {stock_codes}")

    # === 處理 --webui / --webui-only 參數，映射到 --serve / --serve-only ===
    if args.webui:
        args.serve = True
    if args.webui_only:
        args.serve_only = True

    # 兼容舊版 WEBUI_ENABLED 環境變量
    if config.webui_enabled and not (args.serve or args.serve_only):
        args.serve = True

    # === 啟動 Web 服務 (如果啟用) ===
    start_serve = (args.serve or args.serve_only) and os.getenv("GITHUB_ACTIONS") != "true"

    if start_serve:
        args.host, args.port = _resolve_web_service_bind(args, config)
        _warn_if_public_webui_without_auth(args.host)

    bot_clients_started = False
    if start_serve:
        from src.services.runtime_scheduler import (
            CLI_SCHEDULER_OWNER_ENV,
            RUNTIME_SCHEDULER_ARGS_ENV,
            RUNTIME_SCHEDULER_FORCE_ENABLED_ENV,
            RUNTIME_SCHEDULER_RUN_IMMEDIATELY_ENV,
            RUNTIME_SCHEDULER_SUPPRESS_START_ENV,
        )

        # The API runtime scheduler owns schedules once the Web/API service starts.
        # This keeps Web settings, status, and run-now actions attached to the real
        # scheduler instead of a separate CLI loop.
        os.environ.pop(CLI_SCHEDULER_OWNER_ENV, None)
        os.environ.pop(RUNTIME_SCHEDULER_SUPPRESS_START_ENV, None)
        runtime_schedule_requested = args.schedule or config.schedule_enabled
        if args.schedule:
            os.environ[RUNTIME_SCHEDULER_FORCE_ENABLED_ENV] = "true"
        else:
            os.environ.pop(RUNTIME_SCHEDULER_FORCE_ENABLED_ENV, None)
        if runtime_schedule_requested:
            # ``--serve-only`` must restore persisted schedules, but it must not
            # turn service/Desktop startup into an immediate analysis run.
            runtime_run_immediately = (
                False if args.serve_only else config.schedule_run_immediately
            )
            if getattr(args, 'no_run_immediately', False):
                runtime_run_immediately = False
            os.environ[RUNTIME_SCHEDULER_RUN_IMMEDIATELY_ENV] = (
                "true" if runtime_run_immediately else "false"
            )
        else:
            os.environ.pop(RUNTIME_SCHEDULER_RUN_IMMEDIATELY_ENV, None)
        runtime_scheduler_args = {
            "no_notify": bool(getattr(args, "no_notify", False)),
            "no_market_review": bool(getattr(args, "no_market_review", False)),
            "dry_run": bool(getattr(args, "dry_run", False)),
            "force_run": bool(getattr(args, "force_run", False)),
            "single_notify": bool(getattr(args, "single_notify", False)),
            "no_context_snapshot": bool(getattr(args, "no_context_snapshot", False)),
            "workers": getattr(args, "workers", None),
        }
        if getattr(args, "portfolio", None):
            runtime_scheduler_args["portfolio"] = args.portfolio
        os.environ[RUNTIME_SCHEDULER_ARGS_ENV] = json.dumps(runtime_scheduler_args)
        if not prepare_webui_frontend_assets():
            logger.warning("前端靜態資源未就緒，繼續啟動 FastAPI 服務（Web 頁面可能不可用）")
        try:
            start_api_server(host=args.host, port=args.port, config=config)
            bot_clients_started = True
        except Exception as e:
            logger.error(f"啟動 FastAPI 服務失敗: {e}")
            if args.serve_only:
                return 1
            start_serve = False

    if bot_clients_started:
        start_bot_stream_clients(config)

    # === 僅 Web 服務模式：不自動執行分析 ===
    if args.serve_only:
        logger.info("模式: 僅 Web 服務")
        logger.info(f"Web 服務運行中: http://{args.host}:{args.port}")
        logger.info("通過 /api/v1/analysis/analyze 接口觸發分析")
        logger.info(f"API 文檔: http://{args.host}:{args.port}/docs")
        logger.info("按 Ctrl+C 退出...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n用户中斷，程序退出")
        return 0

    try:
        # 模式0: 回測
        if getattr(args, 'backtest', False):
            logger.info("模式: 回測")
            from src.services.backtest_service import BacktestService

            service = BacktestService()
            stats = service.run_backtest(
                code=getattr(args, 'backtest_code', None),
                force=getattr(args, 'backtest_force', False),
                eval_window_days=getattr(args, 'backtest_days', None),
            )
            logger.info(
                f"回測完成: processed={stats.get('processed')} saved={stats.get('saved')} "
                f"completed={stats.get('completed')} insufficient={stats.get('insufficient')} errors={stats.get('errors')}"
            )
            return 0

        # 模式0.5: ETF 輪動（規則化，不調用 LLM）
        if getattr(args, 'etf_rotation', False):
            logger.info("模式: ETF 轮动")
            from src.services.etf_rotation_service import run_etf_rotation

            report = run_etf_rotation(config, send_notification=not args.no_notify)
            logger.info(
                "ETF 轮动完成: as_of=%s target=%s failed=%s",
                f"{report.as_of:%Y-%m-%d}", report.target_weights, list(report.failed_codes),
            )
            return 0

        # 模式1: 僅大盤覆盤
        if args.market_review:
            from src.core.market_review import run_market_review
            from src.core.market_review_runtime import build_market_review_runtime

            # Issue #373: Trading day check for market-review-only mode.
            # Do NOT use _compute_trading_day_filter here: that helper checks
            # config.market_review_enabled, which would wrongly block an
            # explicit --market-review invocation when the flag is disabled.
            effective_region = None
            if not getattr(args, 'force_run', False) and getattr(config, 'trading_day_check_enabled', True):
                from src.core.trading_calendar import get_open_markets_today, compute_effective_region as _compute_region
                open_markets = get_open_markets_today()
                effective_region = _compute_region(
                    getattr(config, 'market_review_region', 'cn') or 'cn', open_markets
                )
                if effective_region == '':
                    logger.info("今日大盘复盘相關市場均為非交易日，跳過執行。可使用 --force-run 強制執行。")
                    return 0

            logger.info("模式: 僅大盘复盘")
            notifier, analyzer, search_service = build_market_review_runtime(config)

            market_review_result = _run_market_review_with_shared_lock(
                config,
                run_market_review,
                notifier=notifier,
                analyzer=analyzer,
                search_service=search_service,
                send_notification=not args.no_notify,
                override_region=effective_region,
                trigger_source="cli",
            )
            return 0 if market_review_result else 1

        # 模式2: 定時任務模式
        if args.schedule or config.schedule_enabled:
            if start_serve:
                # 模式2 + Web 服務：此路徑來自 --schedule/--webui/--serve 與
                # config.schedule_enabled 的組合（均已入 guard），由 API runtime
                # scheduler 接管；--serve-only 已在上面 serve_only 分支返回。
                logger.info("模式: Web/API runtime scheduler")
                logger.info(f"Web 服務運行中: http://{args.host}:{args.port}")
                logger.info("Web/API runtime scheduler 已接管定時任務，保存設置會作用於当前進程")
                logger.info("按 Ctrl+C 退出...")
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    logger.info("\n用户中斷，程序退出")
                return 0

            logger.info("模式: 定時任務")
            logger.info(f"每日執行時間: {config.schedule_time}")

            # Determine whether to run immediately:
            # Command line arg --no-run-immediately overrides config if present.
            # Otherwise use config (defaults to True).
            should_run_immediately = config.schedule_run_immediately
            if getattr(args, 'no_run_immediately', False):
                should_run_immediately = False

            logger.info(f"啟動時立即執行: {should_run_immediately}")

            from src.scheduler import run_with_schedule
            scheduled_stock_codes = _resolve_scheduled_stock_codes(args.stocks or None)
            schedule_time_provider = _build_schedule_time_provider(config.schedule_time)
            schedule_times_provider = _build_schedule_times_provider(config.schedule_time)

            # Startup daily dedup gate (src/core/analysis_run_marker.py):
            # only the startup-immediate invocation consults the gate; the
            # daily scheduled invocations never do. --force-run bypasses the
            # gate entirely (explicit request for an immediate full run,
            # mirroring the trading-day skip override). The flag is consumed
            # by the first task call whatever its outcome. Fail-open by design.
            startup_gate_active = should_run_immediately

            def scheduled_task(scheduled_for=None):
                nonlocal startup_gate_active
                gated, startup_gate_active = startup_gate_active, False
                runtime_config = _reload_runtime_config()
                force_run = getattr(args, "force_run", False)
                if (
                    gated
                    and not force_run
                    and getattr(runtime_config, "schedule_startup_dedup", True)
                ):
                    # Expected list = what THIS startup would actually
                    # analyze, resolved through the same real target chain
                    # as run_full_analysis (Futu portfolio first, .env
                    # hot-reload second, trading-day filter last; schema 2
                    # coverage gate). Only used for the skip decision; the
                    # run below still applies its own filter. A resolution
                    # failure or an empty portfolio resolution comes back
                    # as a fail-open reason instead of an expected list —
                    # the gate then never skips.
                    expected_codes, fail_open_reason = (
                        _resolve_gate_expected_stock_codes(
                            runtime_config,
                            args,
                            stock_codes=scheduled_stock_codes,
                        )
                    )
                    if fail_open_reason is not None:
                        logger.info(
                            "啟動立即執行去重檢查 fail-open(%s)，照常執行分析",
                            fail_open_reason,
                        )
                    else:
                        decision = should_skip_startup_immediate_run(
                            runtime_config,
                            expected_stock_codes=expected_codes,
                        )
                        if decision.skip:
                            logger.info(
                                "啟動立即執行已跳過:當日全量分析已完成(%s)",
                                decision.reason,
                            )
                            return
                        logger.info(
                            "啟動立即執行去重檢查通過:%s", decision.reason
                        )
                elif gated and force_run:
                    logger.info("--force-run 指定,跳過啟動去重檢查")
                if scheduled_for is None:
                    result = run_full_analysis(runtime_config, args, scheduled_stock_codes)
                else:
                    from src.services.scheduled_analysis_claim import ScheduledAnalysisSkipped

                    scheduled_args = argparse.Namespace(**vars(args))
                    scheduled_args._scheduled_for = scheduled_for
                    try:
                        result = run_scheduled_analysis(runtime_config, scheduled_args, scheduled_stock_codes)
                    except ScheduledAnalysisSkipped:
                        logger.info("Scheduled analysis already claimed; skipping occurrence %s", scheduled_for)
                        return

                if result is False:
                    reason = _LAST_ANALYSIS_FAILURE_REASON or "unknown"
                    raise RuntimeError(
                        f"scheduled analysis reported failure: {reason}"
                    )

            background_tasks = []
            if getattr(config, 'agent_event_monitor_enabled', False):
                from src.services.alert_worker import AlertWorker

                interval_minutes = max(1, getattr(config, 'agent_event_monitor_interval_minutes', 5))
                alert_worker = AlertWorker(config_provider=_reload_runtime_config)

                def event_monitor_task():
                    stats = alert_worker.run_once()
                    triggered_count = stats.get("triggered", 0)
                    if triggered_count:
                        logger.info("[EventMonitor] 本輪觸發 %d 條提醒", triggered_count)

                background_tasks.append({
                    "task": event_monitor_task,
                    "interval_seconds": interval_minutes * 60,
                    "run_immediately": True,
                    "name": "agent_event_monitor",
                })

            schedule_kwargs = {
                "task": scheduled_task,
                "schedule_time": config.schedule_time,
                "run_immediately": should_run_immediately,
                "background_tasks": background_tasks,
                "schedule_time_provider": schedule_time_provider,
                "pass_scheduled_for": True,
            }
            if hasattr(config, "schedule_times"):
                schedule_kwargs["schedule_times"] = config.schedule_times
                schedule_kwargs["schedule_times_provider"] = schedule_times_provider
            run_with_schedule(**schedule_kwargs)
            return 0

        # 模式3: 正常單次運行
        if config.run_immediately:
            try:
                analysis_ok = _run_analysis_with_runtime_scheduler_lock(
                    config, args, stock_codes, analysis_targets
                )
            except FutuPortfolioError as exc:
                if not start_serve:
                    raise
                logger.exception(
                    "Futu 持倉導入失敗，Web/API 服務繼續運行: %s",
                    exc,
                )
            else:
                if analysis_ok is False:
                    if start_serve:
                        logger.error("啟動時分析執行失敗，Web/API 服務繼續運行。")
                    elif _LAST_ANALYSIS_FAILURE_REASON in {
                        "no_report",
                        "empty_stock_list",
                        "report_save_failed",
                    }:
                        return 1
        else:
            logger.info("配置為不立即運行分析 (RUN_IMMEDIATELY=false)")

        logger.info("\n程序執行完成")

        # 如果啟用了服務且是非定時任務模式，保持程序運行
        keep_running = start_serve and not (args.schedule or config.schedule_enabled)
        if keep_running:
            logger.info("API 服務運行中 (按 Ctrl+C 退出)...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

        return 0

    except KeyboardInterrupt:
        logger.info("\n用户中斷，程序退出")
        return 130

    except Exception as e:
        logger.exception(f"程序執行失敗: {e}")
        return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
