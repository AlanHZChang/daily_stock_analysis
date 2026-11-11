# Grok Bot 集成說明

本文說明 [daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)（DSA）如何對接 **2026-08-11** 上線的 [Grok Bot](https://x.ai/bot)（xAI 的 AI teammate 產品，不是普通 Grok 聊天）。

不新增 API、環境變量、provider 或運行時分支。Grok Bot 只消費現有 REST / Skill 契約。

## 先分清兩條路徑

| 路徑 | 是什麼 | 怎麼配 | 不是什麼 |
| --- | --- | --- | --- |
| **Grok 當分析模型** | LiteLLM 直連 `xai/*`，DSA 用 Grok 寫報告 | `XAI_API_KEY` + `LITELLM_MODEL=xai/<官方模型ID>`，見 [LLM 配置指南](LLM_CONFIG_GUIDE.md) | 不是 Grok Bot 產品 |
| **Grok Bot 當隊友** | 帶持久雲電腦、Skills、Routines、MCP/Connectors、computer use 的 teammate | Bot 調 DSA 已部署的 HTTP API，或在其電腦上跑 `python main.py` | 不要把 Bot 配成 `LITELLM_MODEL` |

兩條路徑可以同時用：DSA 用 `xai/grok-*` 做分析，Grok Bot 再來讀報告 / `DecisionSignal`。

## 推薦對接順序

1. 先讓 DSA API 長期可訪問：`python main.py --serve-only` 或 Docker。GitHub Actions 只做定時任務，不長期暴露 API。
2. 在 Grok Bot 裡放一條 Skill（可直接改 [openclaw Skill](openclaw-skill-integration.md) 的 `SKILL.md` 示例，或用 [`docs/examples/grok_bot/SKILL.md`](examples/grok_bot/SKILL.md)）。
3. 需要盤中盯盤 / 早報時，用 Bot Routine 調 `DecisionSignal` 查詢，而不是反覆跑完整分析。
4. 只有 Bot 已經能穩定調通 HTTP 之後，才考慮把同一組接口掛到 MCP Connector。本倉庫 **P0 不提供 MCP server**。

## Skill：觸發個股分析

與 openclaw 相同的主入口。Bot / Routine **默認 `async_mode: true`**：

```http
POST {DSA_BASE_URL}/api/v1/analysis/analyze
Content-Type: application/json

{
  "stock_code": "600519",
  "report_type": "detailed",
  "force_refresh": true,
  "async_mode": true
}
```

- 異步：返回 202 + `task_id`，再 `GET /api/v1/analysis/status/{task_id}` 直到 `status: completed`。完成報告在 `result.report`（`TaskStatus.result` 是 `AnalysisResultResponse`），不要讀響應根上的 `report`。
- 不要在同步超時後改發異步重跑。同步超時後服務端 `_handle_sync_analysis` 仍會繼續跑且不進 `TaskQueue`，再發 `async_mode: true` 會繞過隊列去重，造成重複 LLM 費用與推送。
- 僅當 HTTP 超時 ≥300 秒且用戶在等單次結果時，才用 `async_mode: false`。同步響應的報告在根級 `report`。
- 健康檢查：`GET /api/health`。
- 問股 Agent（需 `AGENT_MODE=true`）：`POST /api/v1/agent/chat`。

結果讀取約定（與 openclaw Skill 一致，避免平行字段）：

- 自由文本：`report.summary.operation_advice`、`trend_prediction`、`analysis_summary`（異步前綴 `result.`）
- 結構化動作：可選 `action` / `action_label`（八態 `buy|add|hold|reduce|sell|watch|avoid|alert`）
- 舊歷史缺字段時回退 `operation_advice`；舊三態統計仍以 `decision_type` 為準

Grok Bot Skill 正文見 [`docs/examples/grok_bot/SKILL.md`](examples/grok_bot/SKILL.md)，也可複用 [openclaw Skill](openclaw-skill-integration.md) 示例。環境變量統一為 `DSA_BASE_URL`。

## Skill：大盤覆盤

`POST {DSA_BASE_URL}/api/v1/analysis/market-review` 固定返回 202 接受體 + `task_id`，不是覆盤正文。請求體可傳 `send_notification`、`region`。

輪詢 `GET /api/v1/analysis/status/{task_id}` 直到 `status: completed`，從 `TaskStatus` 頂層讀 `market_review_report` 或 `market_review_payload`（不在 `result.report`）。

## Routine：消費 DecisionSignal

不要讓 Routine 每次都重跑分析。公開查詢口：

| 用途 | 接口 |
| --- | --- |
| 某股最新 active 信號 | `GET /api/v1/decision-signals/latest/{stock_code}` |
| 分頁篩選 | `GET /api/v1/decision-signals` |
| 後驗統計 | `GET /api/v1/decision-signals/outcomes/stats` |
| 有用 / 無用反饋 | `GET/PUT /api/v1/decision-signals/{signal_id}/feedback` |

字段與生命週期見 [DecisionSignal 專題](decision-signals.md)。`DecisionSignal` 只記錄建議，不執行下單或調倉。

需要給 Bot 低敏上下文時，用 [AnalysisContextPack](analysis-context-pack.md) 的公開 overview，不要把完整 `context_snapshot` 塞進 Skill 提示詞。

## MCP / Connector / computer use

- **MCP**：把上表 REST 包成 tool 即可（`analyze_stock`、`get_latest_signal`、`market_review`）。本倉庫暫不內置 MCP server，以免和 FastAPI 契約雙源漂移。
- **Connectors**：Grok Bot 可登錄飛書 / 郵件等；DSA 自己的通知渠道仍走 `.env` 裡已有的 webhook，不必經 Bot 轉發。
- **Computer use**：僅當 Bot 的雲電腦裡已經 clone 並配好 `.env` 時，才適合跑 `python main.py --stocks 600519,AAPL` 或 `python main.py --market-review`。默認仍推薦 HTTP，便於鑑權、超時和異步任務。

## 認證

默認 DSA API 無需認證。若 `ADMIN_AUTH_ENABLED=true`，當前只支持登錄後的 Cookie，**不支持 Bearer Token**。Grok Bot 若只能帶 `Authorization: Bearer`，先保持 API 不鑑權並限制監聽網段，或在反代層做獨立鑑權；不要把 `XAI_API_KEY` 當成 DSA API 的鑑權密鑰。

## 明確不做的事

- 不把 Grok Bot 註冊成 LiteLLM managed channel。
- 不新增 `GROK_BOT_*` 環境變量。
- 不復制一套平行 `DecisionSignal` / `AnalysisContextPack` schema。
- 不在本頁承諾某個 `grok-*` 型號在當前 `litellm` 約束內一定可用。型號以 [xAI 文檔](https://docs.x.ai/docs) 為準，並用 `python scripts/check_env.py --llm` 實測。

## 最小驗收

1. DSA：`python scripts/check_env.py --config`；若走 xAI 模型再跑 `python scripts/check_env.py --llm`。
2. `GET {DSA_BASE_URL}/api/health` 成功。
3. Bot Skill 對一隻真實代碼（如 `AAPL` 或 `600519`）拿到 `operation_advice` 或 `action`（異步路徑從 `result.report` 讀）。
4. 大盤覆盤能從 status 拿到 `market_review_report` 或 `market_review_payload`，而不是隻拿到 202 accepted。
5. Routine 能讀到 `GET /api/v1/decision-signals/latest/{stock_code}` 的 JSON，而無需重跑分析。
