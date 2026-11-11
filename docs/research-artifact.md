# ResearchArtifact 結構化研究產物

`ResearchArtifact` 是報告的結構化版本，用於後續 Dashboard、個股研究頁、監控中心、自選股和 Copilot 複用同一份研究結論。

## 目標

首版解決三個問題：

- 把報告結論沉澱為 `thesis`，而不是隻依賴 Markdown。
- 每份結構化報告必須帶 `invalidation_conditions`，明確什麼時候需要推翻或重新評估。
- 證據項統一帶 `freshness` 與 `quality_level`，讓頁面能展示數據新鮮度和可信度。

## 字段

頂層結構：

- `schema_version`：固定為 `research-artifact-v1`。
- `artifact_id`：穩定產物 id，優先使用 `report:<source_report_id>`；尚未持久化時使用 `report:<stock_code>:<query_id>`，避免批量分析中多個股票共享 query id 造成碰撞；無 query id 時回退為 `report:<stock_code>`。
- `source_report_id`：歷史報告主鍵。
- `source_query_id`：分析任務 query id。
- `created_at`：報告創建時間。
- `subject`：標的。
- `thesis`：結構化觀點。
- `evidence`：證據列表。
- `invalidation_conditions`：失效條件，至少一條。
- `next_actions`：下一步動作。
- `data_quality`：輸入質量摘要。
- `metadata`：低敏擴展字段。

## Thesis

`thesis` 包含：

- `direction`：`bullish` / `bearish` / `neutral` / `unknown`。
- `summary`：核心觀點。
- `confidence`：由情緒分換算的置信度。
- `score`：原始情緒分。
- `action` / `action_label`：結構化建議動作。
- `reasons`：支持理由。
- `risks`：主要風險。

## Evidence

`evidence` 包含：

- `source_type`：例如 `analysis_context`、`news`、`fundamental`、`market_structure`。
- `freshness`：`fresh` / `stale` / `unknown`。
- `quality_level`：`good` / `usable` / `limited` / `poor` / `unknown`。
- `source`、`as_of`、`url`、`metadata` 等低敏擴展字段。

時間與新鮮度邊界：

- `as_of` 僅來自顯式 `provider_timestamp`，保留上游時區；不會用報告創建時間或抓取時間代替行情觀測時間。
- `metadata.context_timestamp` 保留 context block 的原始時間語義，`metadata.fetched_at` 單獨記錄抓取時間。兩者都不證明數據是最新的。
- 上游明確 `stale` 時保留 `stale`；僅有 `available`、`fallback`、`partial`、`estimated` 或 `ok` 時，freshness 為 `unknown`，質量狀態仍按原邏輯計算。沒有統一 TTL，也不把股票交易日規則套用於 24/7 市場。
- 舊報告沒有時間字段時繼續兼容。當前適配器不根據讀取時的時鐘重新判斷歷史證據，也不凍結完整證據快照。

首版適配器會從 `analysis_context_pack_overview.blocks`、新聞摘要、財報、分紅和市場結構中提取證據。

## Invalidation

每份 `ResearchArtifact` 必須包含至少一條 `invalidation_conditions`。

首版默認來源：

- `strategy.stop_loss` 生成價格失效條件。
- `strategy.take_profit` 生成止盈複核條件。
- 數據質量限制生成 `data_quality` 失效條件。
- 新聞缺失披露生成 `evidence` 失效條件。
- 如果沒有顯式條件，生成 `manual:thesis_reassessment` 兜底複核條件。

## 兼容邊界

`AnalysisReport` 新增可選字段：

```text
structured_report?: ResearchArtifact | null
```

舊報告可以繼續不返回該字段；Web 類型和後端 schema 都按可選字段處理。

當前 Stock Profile API 會從歷史詳情動態構建該產物；報告生成時凍結並持久化完整 `structured_report` 仍是後續範圍。

## 實現入口

後端：

- Schema：`api/v1/schemas/research_artifact.py`
- Helper：`src/services/research_artifact_service.py`
- 測試：`tests/test_research_artifact_service.py`

Web：

- 類型：`apps/dsa-web/src/types/researchArtifact.ts`
- `AnalysisReport.structuredReport`：可選消費入口

## 後續接入

1. 報告生成鏈路在持久化時寫入 `structured_report`。
2. 個股研究頁直接讀取 `thesis`、`evidence` 和 `invalidation_conditions`。
3. 監控中心把失效條件轉成可編輯規則。
4. Dashboard 的 What Changed 可以比較兩份 `ResearchArtifact` 的 thesis 與 evidence 差異。
