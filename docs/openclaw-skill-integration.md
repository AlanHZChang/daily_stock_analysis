# openclaw Skill 集成指南

本文檔說明如何通過 [openclaw](https://github.com/openclaw/openclaw) Skill 調用 daily_stock_analysis 的 REST API，實現在 openclaw 對話中觸發股票分析的能力。

## 概述

- **集成方式**：openclaw Skill 通過 HTTP 調用 daily_stock_analysis（DSA）REST API
- **適用場景**：已部署 DSA API 服務，希望在 openclaw 對話中觸發分析（如「幫我分析茅臺」「analyze AAPL」）
- **同類消費方**：2026-08-11 上線的 [Grok Bot](https://x.ai/bot)（Skills / Routines / MCP / computer use）走同一套 REST 契約，不要另起平行 API。見 [Grok Bot 集成](grok-bot-integration.md)。

## 前置條件

1. **daily_stock_analysis 必須已運行**：執行 `python main.py --serve-only` 或通過 Docker 部署，使 API 長期可用
2. **openclaw 需具備 HTTP 調用能力**：如 `system.run` 執行 curl，或內置 HTTP 工具（如 api-tester 等）
3. **說明**：GitHub Actions 僅做定時任務，不長期暴露 API，需本地或 Docker 運行 DSA

## 核心 API 參考

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/v1/analysis/analyze` | POST | 觸發分析（主入口） |
| `/api/v1/analysis/status/{task_id}` | GET | 異步任務狀態 |
| `/api/v1/agent/chat` | POST | Agent 策略問股（需 `AGENT_MODE=true`） |
| `/api/health` | GET | 健康檢查 |

### 觸發分析請求體

```json
{
  "stock_code": "600519",
  "report_type": "detailed",
  "force_refresh": true,
  "async_mode": false
}
```

- `stock_code`：股票代碼（必填）
- `report_type`：`simple` | `detailed` | `brief`
- `force_refresh`：布爾值，是否強制刷新（忽略緩存）
- `async_mode`：布爾值，`false` 時同步返回，`true` 時返回 202 + `task_id` 需輪詢

**注意**：`force_refresh`、`async_mode` 為布爾類型，非字符串。

### 響應示例（同步模式）

```json
{
  "query_id": "abc123def456",
  "stock_code": "600519",
  "stock_name": "贵州茅台",
  "report": {
    "summary": {
      "analysis_summary": "...",
      "operation_advice": "持有",
      "action": "hold",
      "action_label": "持有",
      "trend_prediction": "看多",
      "sentiment_score": 75
    },
    "strategy": {
      "ideal_buy": "1850",
      "stop_loss": "1780",
      "take_profit": "1950"
    }
  },
  "created_at": "2026-03-13T10:00:00"
}
```

## 重要限制與說明

- **僅支持股票代碼**：API 不接受中文名稱（如「茅臺」），需在 Skill 側解析或提示用戶提供代碼（如 600519、AAPL）
- **同步模式耗時**：`async_mode: false` 時，單次分析約 2–5 分鐘，需確保 openclaw 或 HTTP 客戶端超時足夠
- **異步模式**：`async_mode: true` 返回 202 + `task_id`，需輪詢 `GET /api/v1/analysis/status/{task_id}` 直至 `status: completed`

## 股票代碼格式

| 類型 | 格式 | 示例 |
|------|------|------|
| A股 | 6位數字 | `600519`、`000001`、`300750` |
| 北交所 | 8/4/92 開頭 6 位，支持 `BJ` 前綴或 `.BJ` 後綴 | `920748`、`BJ920493`、`920493.BJ` |
| 港股 | hk + 5位數字 | `hk00700`、`hk09988` |
| 美股 | 1-5 字母（可選 .X 後綴） | `AAPL`、`TSLA`、`BRK.B` |
| 美股指數 | SPX/DJI/IXIC 等 | `SPX`、`DJI`、`NASDAQ`、`VIX` |

## 配置方式

在 `~/.openclaw/openclaw.json` 中配置：

```json
{
  "skills": {
    "entries": {
      "daily-stock-analysis": {
        "enabled": true,
        "env": {
          "DSA_BASE_URL": "http://localhost:8000"
        }
      }
    }
  }
}
```

- 本地部署：`http://localhost:8000` 或 `http://127.0.0.1:8000`
- 遠程部署：替換為實際 URL
- **建議**：`DSA_BASE_URL` 勿以 `/` 結尾

## 錯誤響應格式

| 狀態碼 | error 字段 | 說明 |
|--------|-------------|------|
| 400 | `validation_error` | 參數錯誤（如缺少 stock_code） |
| 409 | `duplicate_task` | 該股票正在分析中，拒絕重複提交 |
| 500 | `internal_error` / `analysis_failed` | 分析過程發生錯誤 |

## 完整 SKILL.md 示例

將以下內容保存到 `~/.openclaw/skills/daily-stock-analysis/SKILL.md`：

```markdown
---
name: daily-stock-analysis
description: 調用 daily_stock_analysis API 進行股票智能分析。當用戶詢問「分析茅臺」「analyze AAPL」「幫我看看 600519」等時使用。僅支持股票代碼，不支持中文名稱。
metadata:
  {"openclaw": {"requires": {"env": ["DSA_BASE_URL"]}, "primaryEnv": "DSA_BASE_URL"}}
---

## 觸發條件

當用戶請求分析某隻股票時（如「分析茅臺」「analyze AAPL」「幫我看看 600519」），使用本 Skill。

## 工作流程

1. **提取股票代碼**：從用戶消息中識別股票代碼（如 600519、AAPL、hk00700）。若用戶僅提供中文名稱（如「茅臺」），需提示用戶提供股票代碼，或使用常見映射（茅臺→600519）。
2. **調用 API**：向 `{DSA_BASE_URL}/api/v1/analysis/analyze` 發送 POST 請求，請求體：
   ```json
   {"stock_code": "<提取的代碼>", "report_type": "detailed", "force_refresh": true, "async_mode": false, "skills": ["bull_trend"]}
   ```
   > `skills` 為可選策略 ID 數組；歷史字段 `strategies` 仍保留兼容，建議優先使用 `skills`。
3. **等待響應**：同步模式下分析約需 2–5 分鐘，請確保 HTTP 客戶端超時足夠（建議 ≥300 秒）。
4. **解析結果**：從響應的 `report.summary` 中提取 `operation_advice`、`trend_prediction`、`analysis_summary`，從 `report.strategy` 中提取 `ideal_buy`、`stop_loss`、`take_profit`，以簡潔格式呈現給用戶。外部集成可繼續只讀取自由文本 `operation_advice`；若需要結構化展示，可優先讀取可選的 `action` / `action_label`（八態：`buy|add|hold|reduce|sell|watch|avoid|alert`）。舊歷史缺字段時可回退到 `operation_advice` 文本展示，但該回退不等價於穩定 API action；舊三態統計口徑仍以 `decision_type` 為準。
5. **錯誤處理**：
   - 連接失敗：提示檢查 DSA 是否運行、DSA_BASE_URL 是否正確
   - 400：檢查 stock_code 格式
   - 409：該股票正在分析中，可稍後重試或查詢任務狀態
   - 500：提示查看 DSA 日誌排查

## 股票代碼格式

- A股：6位數字（600519、000001）
- 北交所：8/4/92 開頭 6 位，支持 BJ 前綴或 .BJ 後綴（920748、BJ920493、920493.BJ）
- 港股：hk + 5位數字（hk00700）
- 美股：1–5 字母（AAPL、TSLA、BRK.B）
- 美股指數：SPX、DJI、IXIC 等
```

## Agent 策略問股（可選）

若 daily_stock_analysis 已啟用 `AGENT_MODE=true`，可調用 Agent 策略問股接口，支持多輪對話與多種策略（纏論、均線金叉等）：

```bash
# 將 {DSA_BASE_URL} 替換為實際配置的 API 地址（如 http://localhost:8000）
curl -X POST {DSA_BASE_URL}/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "用纏論分析 600519", "session_id": "optional-session-id"}'
```

響應包含 `content`（分析結論）和 `session_id`（用於多輪對話）。

## 故障排查

| 現象 | 可能原因 | 處理建議 |
|------|----------|----------|
| 連接失敗 | DSA 未運行、端口錯誤、防火牆 | 確認 `python main.py --serve-only` 已啟動，檢查 `DSA_BASE_URL` |
| 400 錯誤 | stock_code 格式錯誤或缺失 | 檢查代碼格式（見上文表格），確保請求體包含 `stock_code` |
| 500 錯誤 | AI 配置、數據源、網絡問題 | 查看 DSA 日誌，確認 `LITELLM_MODEL` 與對應 Key（如 `GEMINI_API_KEY` / `XAI_API_KEY`）已配置 |
| Agent 400 | Agent 模式未啟用 | 在 DSA 的 `.env` 中設置 `AGENT_MODE=true` |
| 分析超時 | 同步模式等待時間過長 | 增加 HTTP 客戶端超時，或改用 `async_mode: true` 輪詢狀態 |

## 認證說明

默認情況下 DSA API 無需認證。若在 `.env` 中啟用了 `ADMIN_AUTH_ENABLED=true`，則需在 Skill 調用時攜帶登錄後獲得的 Cookie，具體方式取決於 openclaw 的 HTTP 工具能力（當前 API 僅支持 Cookie 認證，不支持 Bearer Token）。
