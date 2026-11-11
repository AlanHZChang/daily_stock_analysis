# -*- coding: utf-8 -*-
"""
===================================
分析相關模型
===================================

職責：
1. 定義分析請求和響應模型
2. 定義任務狀態模型
3. 定義異步任務隊列相關模型
"""

from typing import Optional, List, Any, Literal
from enum import Enum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from src.utils.analysis_metadata import SELECTION_SOURCE_PATTERN
from src.utils.market_review_region import normalize_market_review_region_strict


class TaskStatusEnum(str, Enum):
    """任務狀態枚舉"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"


AnalysisPhase = Literal["auto", "premarket", "intraday", "postmarket"]


class AnalyzeRequest(BaseModel):
    """Analysis request parameters"""
    
    stock_code: Optional[str] = Field(
        None, 
        description="單隻股票代碼", 
        json_schema_extra={"example": "600519"},
    )
    stock_codes: Optional[List[str]] = Field(
        None, 
        description="多隻股票代碼（與 stock_code 二选一）",
        json_schema_extra={"example": ["600519", "000858"]},
    )
    report_type: str = Field(
        "detailed",
        description="報告類型：simple(精簡) / detailed(完整) / full(完整) / brief(簡潔)",
        pattern="^(simple|detailed|full|brief)$",
    )
    force_refresh: bool = Field(
        False,
        description="是否強制刷新（忽略緩存）"
    )
    async_mode: bool = Field(
        False,
        description="是否使用異步模式"
    )
    analysis_phase: AnalysisPhase = Field(
        "auto",
        description="分析階段覆蓋：auto(自動推斷) / premarket(盤前) / intraday(盤中) / postmarket(盤後)",
    )
    stock_name: Optional[str] = Field(
        None,
        description="用户選中的股票名稱（自動補全時提供）",
        json_schema_extra={"example": "贵州茅台"},
    )
    original_query: Optional[str] = Field(
        None,
        description="用户原始输入（如茅台、gzmt、600519）",
        json_schema_extra={"example": "茅台"},
    )
    selection_source: Optional[str] = Field(
        None,
        description="股票選擇來源：manual(手動輸入) | autocomplete(自動補全) | import(導入) | image(圖片識別)",
        pattern=SELECTION_SOURCE_PATTERN,
        json_schema_extra={"example": "autocomplete"},
    )
    notify: bool = Field(
        True,
        description="是否發送推送通知（Telegram/企業微信等）"
    )
    report_language: Optional[Literal["zh", "en", "ko"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="本次分析报告輸出語言；未傳時使用全局 REPORT_LANGUAGE",
    )
    skills: Optional[List[str]] = Field(
        None,
        validation_alias=AliasChoices("skills", "strategies"),
        description="本次分析使用的策略 skill ID 列表；兼容 legacy strategies 字段",
        json_schema_extra={"example": ["bull_trend", "growth_quality"]},
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "report_type": "detailed",
            "force_refresh": False,
            "async_mode": False,
            "analysis_phase": "auto",
            "stock_name": "贵州茅台",
            "original_query": "茅台",
            "selection_source": "autocomplete",
            "notify": True,
            "report_language": "zh",
            "skills": ["bull_trend"]
        }
    })


class MarketReviewRequest(BaseModel):
    """Market review trigger parameters."""

    send_notification: bool = Field(
        True,
        description="是否在大盘复盘完成後發送推送通知",
    )
    report_language: Optional[Literal["zh", "en", "ko"]] = Field(
        None,
        validation_alias=AliasChoices("report_language", "reportLanguage"),
        description="本次大盘复盘報告輸出語言；未傳時使用全局 REPORT_LANGUAGE",
    )
    region: Optional[str] = Field(
        None,
        min_length=1,
        max_length=64,
        description=(
            "本次大盘复盘市場覆蓋。合法 token 為 cn、hk、us、jp、kr、both；"
            "both 只能單獨使用，其餘 token 可用逗號組合。輸入會忽略大小寫和 token 兩側空格、"
            "去重並按 cn,hk,us,jp,kr 排序；空值、空 token、未知 token、both 混用或超过 "
            "64 個字符會整體返回 4xx，不會部分執行。未傳時使用運行時全局 MARKET_REVIEW_REGION。"
        ),
        json_schema_extra={
            "example": "cn,us",
            "examples": ["cn", "jp,kr", "both"],
        },
    )

    @field_validator("region")
    @classmethod
    def normalize_region(cls, value: Optional[str]) -> Optional[str]:
        """Strictly validate request input and return its canonical ordering."""
        if value is None:
            return None
        return normalize_market_review_region_strict(value)


class MarketReviewAccepted(BaseModel):
    """Market review background task accepted response."""

    status: str = Field("accepted", description="提交状态")
    message: str = Field(..., description="提示信息")
    send_notification: bool = Field(..., description="是否發送通知")
    region: str = Field(
        ...,
        description="本次任務實際執行的 canonical 市場範圍",
        examples=["us", "jp,kr"],
    )
    trace_id: Optional[str] = Field(
        None,
        description="本次後臺任務的诊断 trace ID",
    )
    task_id: Optional[str] = Field(
        None,
        description="任務 ID（僅當任務實際提交時返回）",
    )


class AnalysisResultResponse(BaseModel):
    """分析結果響應模型"""
    
    query_id: str = Field(..., description="分析记录唯一标识")
    trace_id: Optional[str] = Field(None, description="诊断 trace ID")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    report: Optional[Any] = Field(None, description="分析报告")
    diagnostic_summary: Optional[Any] = Field(None, description="运行诊断摘要")
    created_at: str = Field(..., description="創建時間")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query_id": "abc123def456",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "report": {
                "summary": {
                    "sentiment_score": 75,
                    "operation_advice": "持有"
                }
            },
            "created_at": "2024-01-01T12:00:00"
        }
    })


class TaskAccepted(BaseModel):
    """異步任務接受響應"""
    
    task_id: str = Field(..., description="任務 ID，用於查詢狀態")
    trace_id: Optional[str] = Field(None, description="诊断 trace ID")
    status: str = Field(
        ..., 
        description="任务状态",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="提示信息")
    analysis_phase: AnalysisPhase = Field("auto", description="請求的分析階段")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "pending",
            "message": "Analysis task accepted",
            "analysis_phase": "auto"
        }
    })


class BatchTaskAcceptedItem(BaseModel):
    """批量異步任務中的單個成功提交項。"""

    task_id: str = Field(..., description="任務 ID，用於查詢狀態")
    trace_id: Optional[str] = Field(None, description="诊断 trace ID")
    stock_code: str = Field(..., description="股票代码")
    status: str = Field(
        ...,
        description="任务状态",
        pattern="^(pending|processing)$"
    )
    message: Optional[str] = Field(None, description="提示信息")
    analysis_phase: AnalysisPhase = Field("auto", description="請求的分析階段")
    asset_type: Optional[Literal["stock", "index"]] = Field(
        None,
        description="parser 來源的可選資產類型（stock/index）；由已提交的 analysis_target 透傳，舊客戶端可缺省",
    )

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "stock_code": "600519",
            "status": "pending",
            "message": "分析任務已加入隊列: 600519",
            "analysis_phase": "auto"
        }
    })


class BatchDuplicateTaskItem(BaseModel):
    """批量異步任務中的重複提交項。"""

    stock_code: str = Field(..., description="股票代码")
    existing_task_id: str = Field(..., description="已存在的任務 ID")
    message: str = Field(..., description="錯誤信息")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "existing_task_id": "task_existing_123",
            "message": "股票 600519 正在分析中 (task_id: task_existing_123)"
        }
    })


class RejectedTaskItem(BaseModel):
    """批量異步任務中被明確拒絕的單個目標項（如未登記 CSI 指數）。"""

    stock_code: str = Field(..., description="被拒絕的目標代碼")
    message: str = Field(..., description="拒絕原因")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "930956.CSI",
            "message": "unregistered CSI index: '930956.CSI' is not in the index registry",
        }
    })


class BatchTaskAcceptedResponse(BaseModel):
    """批量異步任務接受響應。"""

    accepted: List[BatchTaskAcceptedItem] = Field(default_factory=list, description="成功提交的任務列表")
    duplicates: List[BatchDuplicateTaskItem] = Field(default_factory=list, description="重複而跳過的任務列表")
    rejected: Optional[List[RejectedTaskItem]] = Field(
        None,
        description="批量中被明確拒絕的目標列表（如未登記 CSI 指数），僅在異步批量請求中返回",
    )
    message: str = Field(..., description="彙總信息")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "accepted": [
                {
                    "task_id": "task_abc123",
                    "stock_code": "600519",
                    "status": "pending",
                    "message": "分析任務已加入隊列: 600519",
                    "analysis_phase": "auto"
                }
            ],
            "duplicates": [
                {
                    "stock_code": "000858",
                    "existing_task_id": "task_existing_456",
                    "message": "股票 000858 正在分析中 (task_id: task_existing_456)"
                }
            ],
            "message": "已提交 1 個任務，1 個重複跳過"
        }
    })


class TaskStatus(BaseModel):
    """Task status model"""
    
    task_id: str = Field(..., description="任務 ID")
    trace_id: Optional[str] = Field(None, description="诊断 trace ID")
    status: TaskStatusEnum = Field(
        ..., 
        description="任务状态",
    )
    progress: Optional[int] = Field(
        None, 
        description="進度百分比 (0-100)",
        ge=0,
        le=100
    )
    result: Optional[AnalysisResultResponse] = Field(
        None, 
        description="分析結果（僅在 completed 時存在）"
    )
    market_review_report: Optional[str] = Field(
        None,
        description="大盘复盘任務返回的報告文本（僅大盘复盘任務）",
    )
    market_review_payload: Optional[Any] = Field(
        None,
        description="Structured market-review payload for API/Web consumers.",
    )
    region: Optional[str] = Field(
        None,
        description="大盘复盘任務實際執行的 canonical 市場範圍",
    )
    error: Optional[str] = Field(
        None, 
        description="錯誤信息（僅在 failed 時存在）"
    )
    stock_name: Optional[str] = Field(None, description="股票名称")
    original_query: Optional[str] = Field(None, description="用户原始输入")
    selection_source: Optional[str] = Field(
        None,
        description="選擇來源",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: Optional[AnalysisPhase] = Field(
        None,
        description="請求的分析階段；無持久化字段的歷史 DB fallback 可能為空",
    )
    skills: Optional[List[str]] = Field(None, description="本次任務使用的策略 skill ID 列表")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "task_abc123",
            "status": "completed",
            "progress": 100,
            "result": None,
            "market_review_report": None,
            "error": None,
            "stock_name": "贵州茅台",
            "original_query": "茅台",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskInfo(BaseModel):
    """
    Task details model

    Used for task list and SSE event delivery
    """
    
    task_id: str = Field(..., description="任務 ID")
    trace_id: Optional[str] = Field(None, description="诊断 trace ID")
    stock_code: str = Field(..., description="股票代码")
    stock_name: Optional[str] = Field(None, description="股票名称")
    status: TaskStatusEnum = Field(..., description="任务状态")
    progress: int = Field(0, description="進度百分比 (0-100)", ge=0, le=100)
    message: Optional[str] = Field(None, description="狀態消息")
    report_type: str = Field("detailed", description="報告類型")
    created_at: str = Field(..., description="創建時間")
    started_at: Optional[str] = Field(None, description="開始執行時間")
    completed_at: Optional[str] = Field(None, description="完成時間")
    error: Optional[str] = Field(None, description="錯誤信息（僅在 failed 時存在）")
    original_query: Optional[str] = Field(None, description="用户原始输入")
    selection_source: Optional[str] = Field(
        None,
        description="選擇來源",
        pattern=SELECTION_SOURCE_PATTERN,
    )
    analysis_phase: AnalysisPhase = Field("auto", description="請求的分析階段")
    skills: Optional[List[str]] = Field(None, description="本次任務使用的策略 skill ID 列表")
    region: Optional[str] = Field(
        None,
        description="大盘复盘任務實際執行的 canonical 市場範圍",
    )
    asset_type: Optional[Literal["stock", "index"]] = Field(
        None,
        description="parser 來源的可選資產類型（stock/index）；由已提交的 analysis_target 透傳，舊客戶端可缺省",
    )
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "task_id": "abc123def456",
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "status": "processing",
            "progress": 50,
            "message": "正在分析中...",
            "report_type": "detailed",
            "created_at": "2026-02-05T10:30:00",
            "started_at": "2026-02-05T10:30:01",
            "completed_at": None,
            "error": None,
            "original_query": "茅台",
            "selection_source": "autocomplete",
            "analysis_phase": "auto",
            "skills": ["bull_trend"]
        }
    })


class TaskListResponse(BaseModel):
    """任務列表響應模型"""
    
    total: int = Field(..., description="任務總數")
    pending: int = Field(..., description="等待中的任務數")
    processing: int = Field(..., description="處理中的任務數")
    tasks: List[TaskInfo] = Field(..., description="任务列表")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "total": 3,
            "pending": 1,
            "processing": 2,
            "tasks": []
        }
    })


class DuplicateTaskErrorResponse(BaseModel):
    """重複任務錯誤響應模型"""
    
    error: str = Field("duplicate_task", description="錯誤類型")
    message: str = Field(..., description="錯誤信息")
    stock_code: str = Field(..., description="股票代码")
    existing_task_id: str = Field(..., description="已存在的任務 ID")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "duplicate_task",
            "message": "股票 600519 正在分析中",
            "stock_code": "600519",
            "existing_task_id": "abc123def456"
        }
    })
