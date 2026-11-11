---
name: daily-stock-analysis
description: 調用 daily_stock_analysis API 做股票分析。當用戶說「分析茅臺」「analyze AAPL」「幫我看看 600519」或要大盤覆盤時使用。優先用股票代碼。
---

# daily_stock_analysis

本 Skill 供 Grok Bot（2026-08-11 AI teammate）使用。通過 HTTP 調用已部署的 DSA，不要把 Bot 配成 LiteLLM provider。

需要環境變量 `DSA_BASE_URL`（DSA API 根地址，無尾斜槓）。

## 何時使用

- 分析單隻或多隻股票
- 查詢某股最新 DecisionSignal（早報 / 盯盤 Routine）
- 大盤覆盤

## 工作流程

1. 提取股票代碼：A股 6 位（`600519`）、港股 `hk00700`、美股 `AAPL`、臺股 `.TW` / `.TWO`。只有中文名時先提示用戶給代碼，或使用常見映射（茅臺 → `600519`）。
2. 需要完整分析時 POST `{DSA_BASE_URL}/api/v1/analysis/analyze`。**Routine 或預計超過 Bot HTTP 超時的分析，從一開始用異步**，不要先同步再改發異步：同步超時後服務端 `_handle_sync_analysis` 仍會繼續跑且不進 `TaskQueue`，再發 `async_mode: true` 會繞過隊列去重，重複計費和推送。

```json
{
  "stock_code": "<code>",
  "report_type": "detailed",
  "force_refresh": true,
  "async_mode": true
}
```

返回 202 + `task_id` 後輪詢 `GET {DSA_BASE_URL}/api/v1/analysis/status/{task_id}`，直到 `status: completed`。完成報告在 `result.report`，不要讀響應根上的 `report`。

僅當 Bot HTTP 超時 ≥300 秒、且用戶在等單次同步結果時，才用 `async_mode: false`。同步超時後不要改發異步重跑；先查詢該股是否已有進行中任務（409 / status），或讀最新 DecisionSignal。

3. 只需最新建議、不要重跑分析時：`GET {DSA_BASE_URL}/api/v1/decision-signals/latest/{stock_code}`。
4. 大盤覆盤：`POST {DSA_BASE_URL}/api/v1/analysis/market-review` 固定返回 202 + `task_id`，不是覆盤正文。輪詢同一條 status 接口，完成後讀頂層 `market_review_report` 或 `market_review_payload`（不在 `result.report`）。
5. 健康檢查失敗先 `GET {DSA_BASE_URL}/api/health`。

## 如何呈現結果

- 同步分析：`report.summary.operation_advice`、`trend_prediction`、`analysis_summary`
- 異步分析：`result.report.summary.operation_advice`、`result.report.summary.trend_prediction`、`result.report.summary.analysis_summary`
- 結構化動作：`action` / `action_label`（`buy|add|hold|reduce|sell|watch|avoid|alert`）；異步時在 `result.report.summary`
- 計劃：同步 `report.strategy.ideal_buy` / `stop_loss` / `take_profit`；異步 `result.report.strategy.*`
- 大盤覆盤：`market_review_report`（文本）或 `market_review_payload`（結構化）
- 缺字段時回退 `operation_advice`；舊三態統計仍看 `decision_type`
- DecisionSignal 只展示建議，不下單、不調倉

## 錯誤

| 狀態 | 處理 |
| --- | --- |
| 連接失敗 | 檢查 DSA 是否在跑、`DSA_BASE_URL` 是否正確 |
| 400 | 檢查 `stock_code` |
| 409 | 該股正在分析，查已有 `existing_task_id` 的 status；不要另開一條分析 |
| 500 | 看 DSA 日誌；確認 `LITELLM_MODEL` 與對應 Key（含可選 `XAI_API_KEY`） |

若 `ADMIN_AUTH_ENABLED=true`，當前 API 只認 Cookie，不認 Bearer。不要把 `XAI_API_KEY` 當作 DSA API 密鑰。
