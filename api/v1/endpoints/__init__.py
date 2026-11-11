# -*- coding: utf-8 -*-
"""
===================================
API v1 Endpoints 模塊初始化
===================================

職責：
1. 聲明所有 endpoint 路由模塊
"""

from api.v1.endpoints import (
    health,
    analysis,
    history,
    stocks,
    backtest,
    data,
    system_config,
    auth,
    agent,
    usage,
    portfolio,
    alerts,
    decision_signals,
    screening,
)
__all__ = [
    "health",
    "analysis",
    "history",
    "stocks",
    "backtest",
    "data",
    "system_config",
    "auth",
    "agent",
    "usage",
    "portfolio",
    "alerts",
    "decision_signals",
    "screening",
]
