# -*- coding: utf-8 -*-
"""ETF rotation service: load ETF closes, run the rule-based rotation and
render a Markdown report (latest signal + backtest + parameter sweep).

The strategy itself lives in ``src.core.etf_rotation``; this module only
handles data loading, report rendering and optional notification.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
import logging
import math
from typing import Callable, Dict, List, Optional, Sequence

import pandas as pd

from src.core.etf_rotation import (
    CASH,
    DAYS_PER_YEAR,
    BacktestResult,
    RotationParams,
    MAX_FORWARD_FILL_DAYS,
    annual_returns,
    compute_metrics,
    holdings_to_weights,
    is_rebalance_day,
    latest_ranking,
    parameter_sweep,
    run_backtest,
    select_holdings,
)

logger = logging.getLogger(__name__)

RECENT_TRADES_LIMIT = 10
CASH_LABEL = "現金"
# History starting this long after the requested start is flagged as truncated.
TRUNCATED_HISTORY_TOLERANCE_DAYS = 30
# ETF daily limits are 10%/20%; larger moves are almost always split/adjustment artifacts.
SUSPICIOUS_DAILY_MOVE = 0.25
MAX_LISTED_JUMPS = 3
# Shorter backtests make annualised figures meaningless; only the signal is shown.
MIN_BACKTEST_YEARS = 1.0
CALENDAR_MARKET = "cn"

NextSessionFn = Callable[[date], Optional[date]]


@dataclass
class LoadedPrices:
    closes: pd.DataFrame
    requested_start: date
    failed: Dict[str, str] = field(default_factory=dict)
    sources: Dict[str, str] = field(default_factory=dict)


@dataclass
class RotationReport:
    markdown: str
    as_of: Optional[pd.Timestamp] = None
    target_weights: Dict[str, float] = field(default_factory=dict)
    failed_codes: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)


def params_from_config(config) -> RotationParams:
    return RotationParams(
        lookback_days=config.etf_rotation_lookback_days,
        rebalance=config.etf_rotation_rebalance,
        top_n=config.etf_rotation_top_n,
        switch_buffer_pct=config.etf_rotation_switch_buffer_pct,
        cost_bps=config.etf_rotation_cost_bps,
    )


def _close_series(code: str, df: Optional[pd.DataFrame], end_day: date) -> pd.Series:
    if df is None or df.empty:
        raise ValueError("empty daily data")
    missing = sorted({"date", "close"} - set(df.columns))
    if missing:
        raise ValueError(f"daily data missing columns: {missing}")
    closes = pd.to_numeric(df["close"], errors="coerce")
    closes = closes.replace([math.inf, -math.inf], math.nan).where(closes > 0)
    closes.index = pd.DatetimeIndex(pd.to_datetime(df["date"])).tz_localize(None).normalize()
    closes = closes[~closes.index.duplicated(keep="last")].sort_index()
    kept = closes.loc[: pd.Timestamp(end_day)]
    if len(kept) < len(closes):
        logger.info("[ETF輪動] %s 丟棄 %s 之後的 %d 根未收盤 K 線", code, end_day, len(closes) - len(kept))
    if not kept.notna().any():
        raise ValueError("no valid close prices")
    return kept


def load_closes(
    fetcher_manager,
    codes: Sequence[str],
    years: int,
    end: Optional[date] = None,
) -> LoadedPrices:
    """Fetch daily closes per code; failures are returned, not swallowed.

    Bars after ``end`` (e.g. an unfinished intraday bar) are dropped. Reindex
    against actual A-share sessions through ``end``; missing quotes stay NaN.
    An unavailable historical calendar raises rather than inventing sessions.
    """
    end_day = end or date.today()
    start_day = end_day - timedelta(days=int(years * 365.25))
    series: Dict[str, pd.Series] = {}
    failed: Dict[str, str] = {}
    sources: Dict[str, str] = {}

    from data_provider.base import DataFetcherManager, _is_etf_code

    # Keep the existing priority/fallback manager, but give this consumer a
    # request-local list whose ETF paths explicitly request forward adjustment.
    # Never change the shared manager or quietly use raw-price fallback sources.
    adjusted_manager = None
    if isinstance(fetcher_manager, DataFetcherManager):
        eligible = [
            fetcher for fetcher in fetcher_manager._get_fetchers_snapshot()
            if fetcher.name in {"EfinanceFetcher", "AkshareFetcher", "BaostockFetcher"}
            or (fetcher.name == "TickFlowFetcher" and fetcher.kline_adjust == "forward")
        ]
        if eligible:
            adjusted_manager = DataFetcherManager(fetchers=eligible)

    for code in codes:
        try:
            if isinstance(fetcher_manager, DataFetcherManager):
                if not _is_etf_code(code):
                    raise ValueError("rotation requires an A-share ETF code")
                if adjusted_manager is None:
                    raise ValueError("no forward-adjusted ETF data source available")
            manager = adjusted_manager or fetcher_manager
            df, source = manager.get_daily_data(
                code,
                start_date=start_day.isoformat(),
                end_date=end_day.isoformat(),
            )
            close_series = _close_series(code, df, end_day)
            if adjusted_manager is None and df.attrs.get("price_adjustment") != "forward":
                raise ValueError("daily source does not confirm forward-adjusted prices")
            series[code] = close_series
        except Exception as exc:  # fetch errors and malformed frames alike
            failed[code] = str(exc) or type(exc).__name__
            logger.warning("[ETF輪動] %s 日線不可用: %s", code, failed[code])
            continue
        sources[code] = source
        logger.info("[ETF輪動] %s 獲取 %d 條日線 (來源: %s)", code, len(series[code]), source)

    frame = pd.DataFrame(series).sort_index() if series else pd.DataFrame()
    if not frame.empty:
        from src.core.trading_calendar import get_trading_dates

        sessions = get_trading_dates(CALENDAR_MARKET, frame.index[0].date(), end_day)
        if sessions is None:
            raise ValueError("A-share trading calendar unavailable for ETF rotation history")
        # Keep sessions even when every source omits the date; otherwise missing
        # execution days become delayed trades and missing Fridays shift signals.
        frame = frame.reindex(sessions)
    return LoadedPrices(closes=frame, requested_start=start_day, failed=failed, sources=sources)


def data_quality_warnings(loaded: LoadedPrices) -> List[str]:
    """Surface data issues that silently distort a backtest."""
    warnings: List[str] = [
        f"{code} 數據獲取失敗，已從本次計算中剔除（{reason[:60]}）"
        for code, reason in loaded.failed.items()
    ]
    limit = pd.Timestamp(loaded.requested_start) + pd.Timedelta(days=TRUNCATED_HISTORY_TOLERANCE_DAYS)
    for code in loaded.closes.columns:
        series = loaded.closes[code].dropna()
        if series.empty:
            continue
        missing = loaded.closes[code].isna() & loaded.closes[code].notna().cummax()
        longest_gap = int(missing.groupby((~missing).cumsum()).sum().max())
        if longest_gap:
            warnings.append(
                f"{code} 上市後行情缺失，最長連續 {longest_gap} 根；缺報價日不成交，"
                "持倉按最後報價估值，恢復報價時計入完整損益"
            )
            if longest_gap > MAX_FORWARD_FILL_DAYS:
                warnings.append(f"{code} 行情缺口超過 {MAX_FORWARD_FILL_DAYS} 根，動量信號在缺口期間不可用")
        if series.index[0] > limit:
            warnings.append(
                f"{code} 歷史起點為 {series.index[0]:%Y-%m-%d}（請求 {loaded.requested_start:%Y-%m-%d}），"
                "可能是上市較晚，或回退數據源只返回了部分歷史，回測區間會相應縮短"
            )
        moves = series.pct_change(fill_method=None)
        jumps = moves[moves.abs() > SUSPICIOUS_DAILY_MOVE]
        if not jumps.empty:
            listed = "、".join(f"{d:%Y-%m-%d} {v * 100:+.0f}%" for d, v in jumps.head(MAX_LISTED_JUMPS).items())
            warnings.append(f"{code} 存在異常單日漲跌（{listed}），疑似拆分或復權缺失，回測結果可能失真")
    distinct = sorted(set(loaded.sources.values()))
    if len(distinct) > 1:
        detail = "、".join(f"{code}:{src}" for code, src in loaded.sources.items())
        warnings.append(f"數據來自多個數據源（{detail}），復權口徑可能不一致")
    return warnings


def _resolve_names(fetcher_manager, codes: Sequence[str]) -> Dict[str, str]:
    names: Dict[str, str] = {CASH: CASH_LABEL}
    for code in codes:
        try:
            name = fetcher_manager.get_stock_name(code, allow_realtime=False)
        except Exception as exc:
            logger.debug("[ETF輪動] %s 名稱獲取失敗: %s", code, exc)
            name = None
        names[code] = name or code
    return names


def _pct(value: float, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value * 100:.{digits}f}%"


def _num(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return f"{value:.2f}"


def _label(code: str, names: Dict[str, str]) -> str:
    name = names.get(code, code)
    return name if name == code else f"{name}({code})"


def _weights_text(weights: Dict[str, float], names: Dict[str, str]) -> str:
    if not weights:
        return CASH_LABEL
    ordered = sorted(weights.items(), key=lambda kv: kv[1], reverse=True)
    return " + ".join(f"{_label(c, names)} {w * 100:.0f}%" for c, w in ordered)


def _signal_conclusion(changed: bool, rebalance_day: Optional[bool], rebalance: str) -> str:
    if rebalance_day:
        return "**需要調倉**，下一交易日收盤按目標持倉執行" if changed else "維持不變"
    period = "本周" if rebalance == "weekly" else "本月"
    outlook = "屆時需要調倉" if changed else "屆時維持不變"
    reason = "今天不是調倉日" if rebalance_day is False else "交易日曆不可用，無法確認今天是否為調倉日"
    return f"{reason}，目標持倉僅供參考，正式信號以{period}最後一個交易日收盤為準；按當前排名{outlook}"


def _render_signal(
    as_of: pd.Timestamp,
    ranking: pd.Series,
    current: Dict[str, float],
    target: Dict[str, float],
    conclusion: str,
    names: Dict[str, str],
) -> List[str]:
    lines = [
        f"## 最新信號（基於 {as_of:%Y-%m-%d} 收盤）",
        "",
        f"- 當前規則持倉：{_weights_text(current, names)}",
        f"- 最新收盤目標：{_weights_text(target, names)}",
        f"- 結論：{conclusion}",
        "",
        "| 排名 | 标的 | 动量 | 是否合格 |",
        "| --- | --- | --- | --- |",
    ]
    for rank, (code, score) in enumerate(ranking.items(), start=1):
        eligible = "是" if pd.notna(score) and score > 0 else "否"
        lines.append(f"| {rank} | {_label(code, names)} | {_pct(score)} | {eligible} |")
    return lines


def _render_metrics(result: BacktestResult) -> List[str]:
    strat = compute_metrics(result.equity)
    bench = compute_metrics(result.benchmark_equity)
    start, end = result.equity.index[0], result.equity.index[-1]
    rows = [
        ("累计收益", "total_return", _pct),
        ("年化收益", "cagr", _pct),
        ("年化波动", "ann_vol", _pct),
        ("夏普比率", "sharpe", _num),
        ("最大回撤", "max_drawdown", _pct),
        ("Calmar", "calmar", _num),
    ]
    lines = [
        f"## 回測表現（{start:%Y-%m-%d} ~ {end:%Y-%m-%d}，已扣交易成本）",
        "",
        "| 指标 | 轮动策略 | 风险池等权持有 |",
        "| --- | --- | --- |",
    ]
    lines += [f"| {title} | {fmt(strat[key])} | {fmt(bench[key])} |" for title, key, fmt in rows]
    lines.append(f"| 調倉次數 | {len(result.trades)} | - |")
    return lines


def _render_annual(result: BacktestResult) -> List[str]:
    strat = annual_returns(result.equity)
    bench = annual_returns(result.benchmark_equity)
    lines = ["## 分年度收益", "", "| 年份 | 轮动策略 | 等权持有 | 差值 |", "| --- | --- | --- | --- |"]
    for year in strat.index:
        s, b = strat[year], bench.get(year, math.nan)
        lines.append(f"| {year} | {_pct(s)} | {_pct(b)} | {_pct(s - b)} |")
    return lines


def _render_sweep(rows, current_lookback: int) -> List[str]:
    if not rows:
        return []
    lines = [
        "## 参数平原检验（仅改变动量窗口，统一评估区间）",
        "",
        "| 动量窗口 | 年化收益 | 最大回撤 | 夏普 |",
        "| --- | --- | --- | --- |",
    ]
    for lookback, m in rows:
        mark = " ⬅ 當前" if lookback == current_lookback else ""
        lines.append(f"| {lookback}{mark} | {_pct(m['cagr'])} | {_pct(m['max_drawdown'])} | {_num(m['sharpe'])} |")
    lines += ["", "> 相邻窗口的表现应当接近；如果只有个别窗口表现好，说明结果大概率是过拟合。"]
    return lines


def _render_trades(result: BacktestResult, names: Dict[str, str]) -> List[str]:
    if not result.trades:
        return []
    lines = ["## 近期调仓记录", "", "| 信号日 | 执行日 | 调出 | 调入 |", "| --- | --- | --- | --- |"]
    for trade in result.trades[-RECENT_TRADES_LIMIT:][::-1]:
        lines.append(
            f"| {trade.signal_date:%Y-%m-%d} | {trade.exec_date:%Y-%m-%d} | "
            f"{_weights_text(trade.from_weights, names)} | {_weights_text(trade.to_weights, names)} |"
        )
    return lines


def _render_rules(params: RotationParams, safe_asset: Optional[str], names: Dict[str, str]) -> List[str]:
    period = "每週最後一個交易日" if params.rebalance == "weekly" else "每月最後一個交易日"
    defensive = _label(safe_asset, names) if safe_asset else CASH_LABEL
    return [
        "## 规则说明",
        "",
        f"- {period}收盤計算 {params.lookback_days} 日動量，下一交易日收盤執行",
        f"- 持有動量最強且為正的前 {params.top_n} 只，每隻 {100 / params.top_n:.0f}%；空出的倉位切到 {defensive}",
        f"- 已持有標的在合格且落後幅度不超過 {params.switch_buffer_pct:g}% 時繼續持有",
        f"- 交易成本按單邊 {params.cost_bps:g} bp 乘以換手率扣除",
        "- 对比基准为风险池等权持有（日再平衡、不扣成本），与策略同从首次建仓日起算",
        "",
        "> 规则化的回测结果不代表未来收益，不构成投资建议。趋势策略在震荡市会反复止损，在急涨行情中会反应滞后。",
    ]


def build_report(
    closes: pd.DataFrame,
    risk_assets: Sequence[str],
    safe_asset: Optional[str],
    params: RotationParams,
    names: Dict[str, str],
    warnings: Sequence[str] = (),
    next_session: Optional[NextSessionFn] = None,
) -> RotationReport:
    """Render the report; ``next_session`` resolves the trading day after a date."""
    risk = [c for c in risk_assets if c in closes.columns]
    result = run_backtest(closes, risk, safe_asset, params)
    as_of, ranking = latest_ranking(closes, risk, params)
    safe_close = closes.loc[as_of, safe_asset] if safe_asset and safe_asset in closes.columns else math.nan
    usable_safe = safe_asset if pd.notna(safe_close) and math.isfinite(safe_close) and safe_close > 0 else None
    target_holdings = select_holdings(ranking, result.final_holdings, params)
    target = holdings_to_weights(target_holdings, params.top_n, usable_safe)
    # Compare holdings, not weights: live weights drift away from the exact 1/top_n split.
    changed = set(target) != set(result.final_weights)
    following = next_session(as_of.date()) if next_session else None
    rebalance_day = is_rebalance_day(as_of, pd.Timestamp(following), params.rebalance) if following else None

    notes = list(warnings)
    if safe_asset and not usable_safe:
        notes.append(f"防守資產 {safe_asset} 不可用，防守倉位按現金（收益為 0）計算")
    start, end = result.equity.index[0], result.equity.index[-1]
    has_backtest = (end - start).days / DAYS_PER_YEAR >= MIN_BACKTEST_YEARS
    if has_backtest:
        sweep = parameter_sweep(closes, risk, safe_asset, params, min_years=MIN_BACKTEST_YEARS)
    else:
        sweep = []
        notes.append(
            f"可回測區間僅 {start:%Y-%m-%d} ~ {end:%Y-%m-%d}，不足 {MIN_BACKTEST_YEARS:g} 年，"
            "已省略回測表現、分年度收益、參數平原檢驗和調倉記錄，只給出最新信號"
        )

    lines = [f"# ETF 輪動信號 {as_of:%Y-%m-%d}", ""]
    if notes:
        lines += ["## ⚠️ 数据告警", ""] + [f"- {note}" for note in notes] + [""]
    conclusion = _signal_conclusion(changed, rebalance_day, params.rebalance)
    backtest_blocks = (
        (_render_metrics(result), _render_annual(result), _render_sweep(sweep, params.lookback_days),
         _render_trades(result, names))
        if has_backtest else ()
    )
    for block in (
        _render_signal(as_of, ranking, result.final_weights, target, conclusion, names),
        *backtest_blocks,
        _render_rules(params, usable_safe, names),
    ):
        if block:
            lines += block + [""]

    return RotationReport(
        markdown="\n".join(lines).rstrip() + "\n",
        as_of=as_of,
        target_weights=target,
        warnings=notes,
    )


def _deliver(report: RotationReport, send_notification: bool, notifier) -> None:
    """Save and push the report; failures are logged, never raised."""
    try:
        if notifier is None:
            from src.notification import NotificationService

            notifier = NotificationService()
    except Exception as exc:
        logger.warning("[ETF輪動] 通知服務初始化失敗，報告未保存也未推送: %s\n%s", exc, report.markdown)
        return

    filename = f"etf_rotation_{report.as_of:%Y%m%d}.md"
    try:
        path = notifier.save_report_to_file(report.markdown, filename)
        logger.info("[ETF輪動] 報告已保存: %s", path)
    except Exception as exc:
        logger.warning("[ETF輪動] 報告保存失敗: %s\n%s", exc, report.markdown)

    if not send_notification:
        return
    try:
        if not notifier.is_available():
            logger.info("[ETF輪動] 未配置通知渠道，跳過推送")
        elif not notifier.send(report.markdown, route_type="report"):
            logger.warning("[ETF輪動] 通知推送失敗")
    except Exception as exc:
        logger.warning("[ETF輪動] 通知推送異常: %s", exc)


def run_etf_rotation(
    config,
    send_notification: bool = True,
    fetcher_manager=None,
    notifier=None,
    end: Optional[date] = None,
    next_session: Optional[NextSessionFn] = None,
) -> RotationReport:
    """CLI entry: fetch data, build report, save it, optionally push it.

    ``end`` defaults to the latest completed A-share session, so an intraday
    run never treats the unfinished bar as a close.
    """
    from src.core.trading_calendar import get_effective_trading_date, get_next_trading_date

    pool = [c for c in config.etf_rotation_pool if c]
    if not pool:
        raise ValueError("ETF_ROTATION_POOL 為空，請至少配置一隻 ETF")
    safe_asset = config.etf_rotation_safe_asset or None
    params = params_from_config(config)

    if fetcher_manager is None:
        from data_provider import DataFetcherManager

        fetcher_manager = DataFetcherManager()

    codes = pool + ([safe_asset] if safe_asset and safe_asset not in pool else [])
    end_day = end or get_effective_trading_date(CALENDAR_MARKET)
    if next_session is None:
        def next_session(day: date) -> Optional[date]:
            return get_next_trading_date(CALENDAR_MARKET, day)

    loaded = load_closes(fetcher_manager, codes, config.etf_rotation_backtest_years, end=end_day)
    risk = [c for c in pool if c in loaded.closes.columns]
    if not risk:
        raise RuntimeError(f"ETF 輪動池全部數據獲取失敗: {loaded.failed}")

    names = _resolve_names(fetcher_manager, codes)
    warnings = data_quality_warnings(loaded)
    for warning in warnings:
        logger.warning("[ETF輪動] %s", warning)
    report = replace(
        build_report(loaded.closes, risk, safe_asset, params, names, warnings, next_session=next_session),
        failed_codes=dict(loaded.failed),
    )

    _deliver(report, send_notification, notifier)
    return report
