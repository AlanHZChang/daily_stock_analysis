# 運行診斷與數據可靠性 1.0（Phase 3）

本文檔記錄 #1391 Phase 3 的交付範圍：在不新增配置的前提下，補齊運行診斷可見性並將歷史排障信息回填到後端上下文快照，便於自部署環境快速定位異常。

## 本輪範圍

- 歷史報告詳情新增默認摺疊的「運行診斷 / 數據可靠性」區域；#1523 後 Web 展示標題調整為「運行診斷 / 運行狀態」，歷史階段標題不變。
- 任務面板對進行中任務展示默認摺疊的 trace 信息，便於和後端日誌、SSE、歷史報告診斷串聯。
- 歷史報告通過只讀接口拉取診斷摘要：

```http
GET /api/v1/history/{record_id}/diagnostics
```

- 同步分析響應若已經帶有 `diagnostic_summary`，前端可直接展示，不額外請求歷史接口。
- 診斷面板支持複製後端生成的脫敏 `copy_text`，用於 issue 或部署排障。
- 分析鏈路在保存歷史後會補齊任務/Provider/LLM/通知診斷到 `context_snapshot.diagnostics`，歷史診斷接口統一聚合為用戶可讀摘要。
- 首頁運行流面板複用同一 RunFlowSnapshot 契約展示 active task、completed report 與大盤覆盤；active task 通過任務 SSE 的可選增量事件實時追加事件流，完成或斷線後再 refetch 快照保證最終一致。

## 運行流實時增量

運行流增量不新增獨立 SSE endpoint，繼續複用：

```http
GET /api/v1/analysis/tasks/stream
```

兼容契約：

- 事件類型仍為 `task_progress`。
- 原有 task payload 字段保持不變。
- 當本次進度更新來自運行診斷時，可選追加 `flow_event` 字段；舊客戶端忽略該字段即可。
- `flow_event` 使用與 `RunFlowSnapshot.events[]` 相同的脫敏事件結構：`id`、`timestamp`、`severity`、`type`、`node_id`、`title`、`message`、`metadata`。
- active task 可追加 `provider_run_started` / `llm_run_started` 實時事件；這些事件只用於運行中的 running 卡片展示，完成後由同 `node_id` 的 `provider_run` / `llm_run` 結果事件覆蓋狀態，歷史診斷仍以最終結果為準。
- 後端 TaskQueue 只為每個 active task 保留最近 N 條運行流事件，避免內存無限增長；完整歷史仍以 `context_snapshot.diagnostics` 和歷史 RunFlowSnapshot 為準。

示例：

```json
{
  "task_id": "3f87...",
  "trace_id": "3f87...",
  "stock_code": "600519",
  "status": "processing",
  "progress": 64,
  "message": "LLM 正在生成分析結果",
  "flow_event": {
    "id": "flow_0002",
    "timestamp": "2026-06-08T22:30:24",
    "severity": "success",
    "type": "llm_run",
    "node_id": "llm_analysis_1",
    "title": "LLM 成功",
    "message": "LLM deepseek-chat 成功"
  }
}
```

運行診斷記錄函數會在 provider、LLM、歷史保存、通知記錄成功寫入內存診斷後 fail-open 觸發 event sink。sink 失敗只記錄 warning，不改變分析、保存或通知的成功/失敗判定。

新聞情報搜索也納入同一 provider 診斷語義：`SearchService.search_stock_news()` 會以 `data_type=news_search` 記錄 Tavily、SearXNG、Bocha、Brave 等搜索 provider 的嘗試、過濾後結果數、緩存命中和失敗原因。多個搜索 provider 連續嘗試時，Web 運行流主圖默認聚合為一個“新聞輿情”節點，卡片展示 provider 鏈路與狀態，節點詳情展示成功/失敗次數、fallback / retry 次數；需要排障時可展開該聚合節點查看單次 provider 嘗試。

運行流拓撲的數據來源泳道優先按節點開始時間排序；provider / LLM 節點若只有完成時間和耗時，會以 `ended_at - duration_ms` 推導 `started_at`，並在卡片上展示開始時間。無可用時間的節點保留原展示順序作為兜底。主圖表達“入口 -> 數據來源 -> ContextPack -> LLM -> 保存/通知”的流程結構；完整排障細節保留在事件流、節點詳情和聚合節點展開態中。

Web 運行流主圖使用前端內部展示模型，不改變後端 `RunFlowSnapshot` 契約：

- provider attempts 按 `metadata.data_type` 聚合為數據來源節點，例如實時行情、日線數據、新聞輿情。
- `context_block_*` 節點默認摺疊進 `ContextPack` 詳情，避免與 provider attempts 在數據來源泳道混排。
- 點擊聚合節點可在詳情區查看 attempts 表格；點擊“展開嘗試”後，當前聚合組的子 provider 節點會回到拓撲中。
- 事件流仍展示完整事件；事件關聯節點會映射到當前可見節點，摺疊時指向聚合節點，展開時指向具體 attempt。
- 拓撲連線使用多連接點策略：橫向主流程走左右端口，同泳道上下關係走底部到頂部，fallback / retry 繼續使用文字標籤與虛線樣式表達。

## 運行流 API

```http
GET /api/v1/analysis/tasks/{task_id}/flow
GET /api/v1/history/{record_id}/flow
```

- 兩個接口返回同一 `RunFlowSnapshot` 契約。
- active task 缺少 diagnostics 時返回 skeleton flow，不偽造 provider / LLM 事件。
- active task 若已有 recent `flow_event`，snapshot 會返回這些真實事件，並可根據事件中的節點元數據補出臨時節點。
- completed history 優先從 `context_snapshot.diagnostics` 與 `analysis_context_pack_overview` 構建完整拓撲。
- 大盤覆盤歷史記錄使用 `code=MARKET`、`report_type=market_review`，同樣走 `/history/{record_id}/flow` 與 Web 運行流面板，不提供單獨 UI 分叉。
- `cancel_requested` 與 `cancelled` 是合法運行流狀態；用戶取消不應映射為 `failed`。

## 運行流視圖

運行流視圖是在運行診斷摘要之上的可視化排障入口，用於串聯一次分析從觸發、數據獲取、ContextPack 組裝、LLM 生成到保存/通知的大致鏈路。它不替代診斷摘要的 `copy_text`，而是把同一批脫敏診斷證據組織為節點、連線、事件和摘要指標，方便從 Web 首頁快速定位異常或降級環節。

後端提供兩個只讀快照接口：

```http
GET /api/v1/analysis/tasks/{task_id}/flow
GET /api/v1/history/{record_id}/flow
```

- `tasks/{task_id}/flow` 面向活躍任務。任務仍在內存隊列中時優先返回當前任務快照；任務已完成時可按同一 `task_id/query_id` 嘗試讀取歷史診斷。缺少診斷時返回 skeleton flow，不偽造 provider、LLM 或通知事件。
- `history/{record_id}/flow` 面向歷史報告，支持歷史記錄主鍵 ID 或可解析的 `query_id`。普通個股分析與 `MARKET/market_review` 大盤覆盤複用同一 `RunFlowSnapshot` 契約。
- 同一頁面觸發個股分析時，個股流程可按需生成或複用當日大盤上下文；這不是獨立的個股分析步驟，而是 Prompt 背景生成。後臺會用獨立 `market_context_*` query_id 與 `scope=daily_market_context` 保存該大盤上下文，避免與個股報告共用 query_id。
- 為兼容早期已寫入的混合診斷，運行流會在讀取歷史時按報告類型做低風險過濾：`MARKET/market_review` 記錄隱藏個股行情、日線、技術、基本面與籌碼 provider 節點；個股記錄隱藏首次個股行情前的大盤新聞搜索，以及首次個股 LLM 前的大盤保存/通知節點。
- 通知跳過或未配置時允許 `attempts=0`，運行流展示為 skipped，不再因 Pydantic 校驗失敗導致 `/flow` 返回 500。
- 快照頂層包含 `summary`、`lanes`、`nodes`、`edges`、`events` 和 `generated_at`。節點狀態使用 `pending/running/success/failed/degraded/fallback/timeout/cancel_requested/cancelled/skipped/unknown`，其中用戶取消類狀態不會被映射成 `failed`。
- 舊歷史、缺失 `context_snapshot.diagnostics` 或證據不足時，後端返回 `unknown` 或 skeleton 節點；Web 端按空/未知狀態展示，不影響報告詳情讀取。

Web 入口：

- 首頁活躍任務卡片提供運行流入口，打開抽屜後按 `task_id` 拉取任務快照。
- 歷史報告摘要和運行診斷區域提供運行流入口，打開抽屜後按歷史記錄 ID 拉取歷史快照。
- 面板展示摘要、基礎拓撲、事件流和節點詳情；複雜拓撲聚合、實時增量事件和佈局 polish 會在後續階段繼續收斂。

脫敏與兼容邊界：

- 運行流只讀取既有任務信息、歷史結果和 `context_snapshot.diagnostics` 中的低敏診斷字段，不新增配置項、不改數據庫結構、不遷移舊歷史。
- `model`、`provider`、`fallback_model` 僅用於展示實際診斷到的調用信息；不參與模型選擇、請求路由、Base URL 解析或配置保存。
- `metadata`、錯誤信息和本地路徑會經過後端裁剪與脫敏，避免暴露 API key、token、cookie、webhook、prompt/raw response、代理頭和本地絕對路徑。
- 回滾時可移除 Web 入口和查詢路徑；後端新增只讀快照接口不改變原有分析、歷史、通知或診斷摘要接口的成功/失敗語義。

## 狀態文案

總體狀態：

- `normal`：正常
- `degraded`：部分降級
- `failed`：失敗
- `unknown`：未知

組件狀態：

- `ok`：正常
- `degraded`：最近失敗後已降級
- `failed`：失敗
- `unknown`：未知
- `not_configured`：未配置
- `skipped`：已跳過

## 交互邊界

- 診斷區域默認摺疊，避免擠佔報告主要內容。
- 首屏只展示總體狀態、首要原因和必要 trace 信息。
- 組件狀態與高級 JSON 字段放在展開區域內；高級字段再二級摺疊，避免信息過載。
- 舊報告、接口失敗或證據不足時顯示 `unknown`，不影響報告閱讀。

## 兼容性邊界

- 本輪不新增 `.env` 配置項，不修改數據庫結構，不引入數據遷移。
- Web 只消費 Phase 1/2 已追加的可選字段和只讀診斷接口；後端補齊 `src/core/pipeline.py`、`src/services/run_diagnostics.py`、`src/storage.py` 與 `src/services/history_service.py` 的診斷持久化與刷新邏輯，並通過 `api/v1/endpoints/history.py` 提供可讀端點。
- 後端變更範圍包含任務編排、歷史保存後補寫、歷史診斷查詢與通知結果診斷記錄；這些鏈路只追加 `context_snapshot.diagnostics` 診斷快照和摘要，不改變分析主流程、通知發送成敗語義或歷史報告主體字段。
- 複製文本由後端生成並脫敏；前端只負責展示和複製。
- Desktop 複用 Web 構建產物，未單獨改動 Electron 主進程或打包腳本。
- 運行時配置/模型/provider/base_url 兼容語義不調整：除診斷持久化鏈路外，不改 provider 優先級、LiteLLM 路由、運行時清理與配置回退邏輯。
- 舊歷史與舊配置兼容規則不變：歷史診斷查詢新增可選字段不影響既有歷史查詢響應解析；回退方式為移除本輪展示與相關前端查詢路徑，或按現有指南恢復模型和配置。
- 回滾策略：優先回退前端展示與查詢入口；若需完全隔離新增鏈路，可回滾本輪 PR（回退後保留歷史記錄原有響應，新增診斷端點不再在 Web 中展示）。

### 結構化檢測澄清

本輪 review 的結構化檢測命中了外部模型/API 兼容和運行時配置遷移風險；複核後結論如下：

- 模型名/provider/Base URL：本輪不新增、不替換、不重排任何模型名、provider、Base URL、channel 或 fallback 默認值，也不改變 `LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`LITELLM_FALLBACK_MODELS`、`OPENAI_*`、`GEMINI_*`、`ANTHROPIC_*`、`DEEPSEEK_*` 的解析優先級。
- SDK/依賴默認值：本輪不修改 `requirements.txt`、`package.json` 依賴約束或 LiteLLM/OpenAI-compatible 調用默認參數；外部來源仍以 `docs/llm-providers.md` 和 `docs/LLM_CONFIG_GUIDE*.md` 中已記錄的官方文檔與當前鎖定依賴說明為準。
- 保存前清理/配置遷移：本輪不觸發 `.env`、Web 設置頁 channel、桌面端用戶數據目錄、Docker 運行時配置文件或歷史舊配置的遷移、清理、刪除、回寫策略變更。
- 本輪實際運行時改動只把既有分析 trace、provider/LLM/通知結果和脫敏錯誤摘要寫入 `context_snapshot.diagnostics`，並通過歷史只讀接口和 Web 默認摺疊面板展示；診斷記錄失敗按 fail-open 處理，不改變分析或通知的成功/失敗判定。
- 因此本次屬於結構化檢測誤報/文檔澄清；無新增官方來源、舊配置遷移步驟或 provider 回退路徑需要執行。若需回退，按本節回滾策略移除診斷展示/查詢入口即可，模型與運行時配置恢復路徑不變。

## 兼容性迴歸與驗證（PR 合併前關鍵證據）

- 後端迴歸覆蓋：
  - `tests/test_pipeline_market_phase_context.py`
  - `tests/test_realtime_types.py`
  - `tests/test_scheduler_background.py`
  - `tests/test_analysis_api_contract.py`（子集：診斷上下文入出參/狀態查詢契約）
  - `tests/test_analysis_history.py`（子集：歷史 API 與持久化鏈路）
- 覆蓋關係：API 合約由 `tests/test_analysis_api_contract.py` 與 `tests/test_analysis_history.py` 覆蓋；任務編排、歷史保存和 `context_snapshot.diagnostics` 由 `tests/test_pipeline_market_phase_context.py` 覆蓋；通知路徑通過 `./scripts/ci_gate.sh` 中的既有通知迴歸與導入檢查兜底。
- 迴歸命令（PR 合併前至少確認全部通過）：

```bash
./scripts/ci_gate.sh
python -m pytest tests/test_realtime_types.py tests/test_scheduler_background.py tests/test_pipeline_market_phase_context.py tests/test_analysis_api_contract.py tests/test_analysis_history.py
cd apps/dsa-web && npm run lint && npm run build
```

## 驗證建議

```bash
cd apps/dsa-web
npm run lint
npm run build
```

可補充執行（非阻斷）：

```bash
cd apps/dsa-web
npm test -- --run src/components/report/__tests__/ReportDiagnostics.test.tsx src/components/tasks/__tests__/TaskPanel.test.tsx src/hooks/__tests__/useTaskStream.test.tsx
```

可補充確定性腳本校驗：

```bash
python -m py_compile api/v1/endpoints/analysis.py api/v1/endpoints/history.py api/v1/schemas/analysis.py api/v1/schemas/history.py src/core/pipeline.py src/services/run_diagnostics.py src/storage.py
```

## 回滾

最小回滾方式：revert Phase 3 PR。由於本輪為可選字段與可讀接口增強，回滾後後端歷史快照與已落庫數據保留，Web 不再展示診斷面板與 trace 診斷入口。
