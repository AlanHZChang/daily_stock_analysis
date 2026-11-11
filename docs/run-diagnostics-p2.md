# 運行診斷與數據可靠性 1.0（Phase 2）

本文檔記錄 #1391 Phase 2 的後端落地範圍：基於 Phase 1 的 `trace_id` 與 provider run 記錄，生成用戶可讀的運行診斷摘要，並提供可複製的脫敏排障文本。

## 本輪範圍

- 新增 `RunDiagnosticSummary` 聚合邏輯，輸出總體狀態：
  - `normal` / 正常
  - `degraded` / 部分降級
  - `failed` / 失敗
  - `unknown` / 未知
- 摘要覆蓋以下關鍵鏈路：
  - 實時行情
  - 日線數據
  - 新聞搜索
  - LLM
  - 通知
  - 歷史保存
- `AnalysisService` 同步/異步任務結果追加可選 `diagnostic_summary`。
- 新增歷史報告診斷 API：

```http
GET /api/v1/history/{record_id}/diagnostics
```

`record_id` 支持歷史記錄主鍵 ID 或 `query_id`，返回診斷摘要與 `copy_text`。

## 複製排障信息

`copy_text` 是面向 issue/排障的純文本，包含：

- `trace_id`
- `query_id`
- `stock_code`
- `trigger_source`
- 總體 `data_status`
- 實時行情、日線、新聞、LLM、通知、歷史保存的簡短狀態
- 首要原因

生成前會複用運行診斷脫敏規則，避免輸出 token、API key、Authorization、Cookie、webhook URL、郵箱密碼、代理憑據等敏感信息。

## 兼容性邊界

- 本輪不新增配置項，不改變數據源優先級，不改變 fallback 策略。
- 本輪不改變任何 LLM/provider/Base URL/配置遷移語義，僅新增歷史快照中的診斷字段與查詢接口。
- API 只追加可選字段和新增只讀接口；舊客戶端可忽略。
- 舊報告沒有 `context_snapshot.diagnostics` 時返回 `unknown`，不報錯。
- 通知診斷在當前任務上下文中記錄；歷史報告如果保存時尚無通知證據，會在摘要中顯示通知結果未知。
- 診斷摘要生成失敗不得影響報告讀取或分析主流程。

### 結構化檢測告警澄清

- 自動化檢測命中的“模型/provider/base URL 兼容風險”來源是：`src/agent/factory.py` 新增了 `agent_max_steps` 與 `agent_orchestrator_timeout_s` 的 **數字安全兜底**（`_coerce_config_int`），因此掃描可能將其誤識別為配置敏感路徑；該命中屬於測試與路由保護觸發，不是運行時配置或兼容語義變更。
- 當數值配置存在非法值時，系統會記錄 `warning` 到 `src.agent.factory` 日誌（示例：`[AgentFactory] Invalid value for agent_max_steps...`），並回退到默認值；日誌用於定位“參數未生效”類問題，與模型/provider/base URL 兼容性獨立。
- 本輪確認無靜默遷移/清空/改寫：
  - `src/core/pipeline.py` 與 `src/services/analysis_service.py` 僅新增診斷記錄，不修改 `Config` 中任何 `litellm_model`、`agent_litellm_model`、`openai_base_url` 或 channel `LLM_*` 字段。
  - `src/agent/factory.py` 的 `_coerce_config_int` 只在構建執行參數時計算 `max_steps` 與 `timeout_seconds`，並且不寫回到 `config` 對象；`litellm_model`、`agent_litellm_model`、`openai_base_url` 原值在構造鏈路中完整透傳。
  - 本輪不觸發 `Config` 的運行時清理、持久化回寫或遷移流程，因此不存在寫回導致運行時配置被重寫的風險。
- 迴歸驗證：`tests/test_agent_pipeline.py::TestAgentConfig::test_build_agent_executor_does_not_mutate_llm_route_config` 與 `tests/test_agent_pipeline.py::TestAgentConfig::test_build_agent_executor_multi_arch_does_not_mutate_llm_route_config` 明確斷言上述字段在 `build_agent_executor` 後保持原值。
- 回退路徑：如需恢復到舊行為，移除本輪相關提交；或將 `diag_*` 字段從 `context_snapshot`/`RunDiagnosticSummary` 的反序列化鏈路中移除。主鏈路與模型/provider 配置無需額外遷移或修復。

## 驗證建議

```bash
python -m pytest tests/test_run_diagnostics_p2.py tests/test_run_diagnostics_p1.py
python -m py_compile src/services/run_diagnostics.py src/services/history_service.py api/v1/endpoints/history.py api/v1/schemas/history.py
```
