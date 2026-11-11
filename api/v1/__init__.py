# -*- coding: utf-8 -*-
"""
===================================
API v1 模塊初始化
===================================

職責：
1. 延遲導出 v1 版本 API 的路由，避免 schema import 觸發整棵 endpoint 導入樹
"""

from typing import Any

__all__ = ["api_v1_router"]


def __getattr__(name: str) -> Any:
    if name != "api_v1_router":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from api.v1.router import router

    return router
