# AnalysisContextPack：P0 盤點、P1/P2 契約、P3 Runtime Consumption、P4 可見性、P5 數據質量、#1386 P6 聯動與 #1389 P6 遷移回滾

本頁是 Issue #1389 的專題文檔，用於記錄當前 DSA 分析上下文的真實來源、消費路徑、字段狀態邊界，以及 `AnalysisContextPack` 內部契約、builder、運行態消費、低敏可見性、數據質量評分、告警/持倉/歷史/回測聯動、遷移和回滾邊界。P0 負責現狀盤點和契約邊界；P1 只新增內部 schema/envelope、block catalog、類型約定和脫敏序列化；P2 只從 pipeline 已有 artifacts 組裝 pack；P3 只把低敏摘要接入普通分析和 Agent 初始 Prompt；P4 只把低敏 overview 接入歷史詳情、同步分析響應、completed task status 和 Web 報告頁；P5 在同一 `PACK_VERSION = "1.0"` 內補齊數據質量評分、`fetch_failed` 狀態、Prompt 數據限制和 overview 低敏展示；#1386 P6 複用同一公開 overview 做告警、持倉、歷史、回測和通知聯動，並在手動持倉分析時加入可選輔助 `portfolio` block；#1389 P6 只補齊文檔、配置可見性、遷移和回滾說明，不新增 pack runtime、pack feature flag、DB migration 或 schema 版本。

## 術語與邊界

當前倉庫裡有多種名為 context / snapshot 的數據面，P0 必須先消歧，避免把現有運行時結構誤寫成未來 pack。

| 術語 | 當前含義 | 當前主要消費方 | P0 邊界 |
| --- | --- | --- | --- |
| `storage.get_analysis_context()` | `src/storage.py` 中從數據庫最近兩天 OHLCV 生成的技術面簡上下文，包含 `today`、`yesterday`、`volume_change_ratio`、`price_change_ratio`、`ma_status` 等。當前實現接收 `target_date`，但實際仍取最新兩天數據。 | 普通分析主鏈路、Agent 工具 `get_analysis_context` | 記錄為歷史技術面輸入來源，不把它直接等同於未來 pack。 |
| `enhanced_context` | 普通分析中由 `src/core/pipeline.py` 基於 DB 簡上下文、實時行情、籌碼、趨勢、基本面和語言信息增強後的 prompt 上下文。 | `src/analyzer.py` prompt 渲染、`_build_context_snapshot()` | 記錄當前 prompt 輸入面；P0 不改變字段名或結構。 |
| `analysis_history.context_snapshot` | 分析完成後寫入歷史表的持久化快照。普通分析通常包含 `enhanced_context`、`news_content`、`realtime_quote_raw`、`chip_distribution_raw`；Agent 路徑保存 `initial_context`。 | 歷史詳情、同步 analysis/status 響應、回測、部分基本面 fallback 展示 | 記錄為持久化消費面；必須保留 `context_snapshot.enhanced_context.date` 兼容。 |
| Agent executor message context | `AgentExecutor._build_user_message()` 注入首輪用戶消息的上下文，適用於 `AGENT_ARCH=single` 路徑，目前包含股票代碼、報告類型、輸出語言、`realtime_quote`、`chip_distribution`、`news_context`。 | 單 Agent 首輪 LLM 消息 | 記錄當前首輪可見字段；P0 不補 runtime 注入。 |
| Agent orchestrator `AgentContext` | `AgentOrchestrator._build_context()` 寫入多 Agent 共享上下文，適用於 `AGENT_ARCH=multi` 路徑，可預注入 `realtime_quote`、`daily_history`、`chip_distribution`、`trend_result`、`news_context`。 | Technical / Intel / Risk / Decision 多 Agent 鏈路 | 記錄為 orchestrator 內部共享數據面；不預注入 `fundamental_context`，`trend_result` 是否存在取決於 caller 是否傳入。 |

## P0 範圍與非目標

P0 的目標是讓後續 P1/P2/P3 可以基於真實倉庫邊界設計 `AnalysisContextPack`，而不是提前改造運行時。

- P0 覆蓋普通分析、Agent、告警、持倉、回測、歷史、通知七條路徑的上下文盤點。
- P0 固定字段質量狀態詞；P1 已新增 `AnalysisContextPack` 內部 schema，但仍不新增 builder、不接入 runtime、不公開完整 pack。
- P0 不新增 builder，不新增配置項，不新增數據庫字段，不改變 API、報告、歷史或通知 payload。
- P0 不接入 runtime，不改 `src/` 分析、Agent、告警、持倉、回測或通知邏輯。
- P0 不 pack 化 `market_review`、`market_light` 或大盤紅綠燈專題快照；這些只作為歷史快照中的其他 `report_kind` / 專題消費邊界記錄。
- P0 當時不把 `fetch_failed` 加入字段質量狀態詞；P5 已在同一 1.0 umbrella 內追加該狀態，用於明確區分“不支持”和“本次抓取失敗”。
- P0 不在 README 擴寫實現細節；本頁作為專題文檔，由 `docs/INDEX.md` / `docs/INDEX_EN.md` 入口發現。

## P1 內部契約

P1 落地 `src/schemas/analysis_context_pack.py`，只定義內部 schema/envelope，方便 P2 builder 和 P3 runtime 消費時複用同一結構。P1 不填充運行時數據、不新增 fetcher、不改變 Prompt、不寫入 history/task/report metadata，也不把完整 pack 暴露到 API、Web、Bot、Desktop 或通知。

P1 schema 包含：

- `PACK_VERSION = "1.0"`，並通過 `AnalysisContextPack.pack_version` 標記契約版本。
- `ContextFieldStatus`：P1 首版只允許 `available`、`missing`、`not_supported`、`fallback`、`stale`、`estimated`、`partial`；P5 已追加 `fetch_failed`，表示字段或數據塊本次抓取明確失敗，不代表整次分析失敗。
- `AnalysisSubject`：頂層身份槽，只包含 `code`、`stock_name`、`market`；`exchange`、`currency`、`industry` 留給後續擴展，P2 builder 不擴 P1 schema，也不重複新增 `identity` block。
- `AnalysisContextItem`：字段級輸入項，包含 `status`、`value`、`source`、`timestamp`、`fallback_from`、`missing_reason`、`warnings`、`metadata`。
- `AnalysisContextBlock`：數據塊級分組，包含 `status`、`items`、`source`、`timestamp`、`warnings`、`metadata`，其中 `items` 是 `Dict[str, AnalysisContextItem]`。
- `DataQuality`：P1 只保留 `warnings` 與 `metadata` 容器；P5 已追加 `overall_score`、`level`、`block_scores`、`limitations`，仍保持低敏，不承載 raw payload。
- `AnalysisContextPack`：頂層 envelope，包含 `pack_version`、`subject`、`phase`、`blocks`、`data_quality`、`metadata`、`created_at`。

時間字段約定：

- `AnalysisContextPack.created_at` 使用 `datetime`，由 `model_dump(mode="json")` 輸出 ISO 8601 字符串。
- `AnalysisContextItem.timestamp` 與 `AnalysisContextBlock.timestamp` 使用 `Optional[str]`，約定為 ISO 8601 datetime 字符串；P1 schema 在構造時校驗該格式，date-only、自然語言時間或斜槓分隔日期會被拒絕；P2 builder 複用現有 artifact 時間戳時不做強制二次轉換。

狀態語義：

- `block.status` 表示整塊可用性。
- `item.status` 表示字段級質量。
- P1 不實現 `item.status` 到 `block.status` 的自動聚合推導。

P1 Block Catalog：

| block key | P1 語義 | P1 邊界 |
| --- | --- | --- |
| `quote` | 實時行情和報價相關輸入 | 只定義可表達位置，不抓取或填充數據。 |
| `daily_bars` | 完整日線窗口和最近完整日線日期 | P1 不判斷 partial bar。 |
| `technical` | 技術指標、量價結構和形態 | P1 不生成指標。 |
| `fundamentals` | 估值、成長、盈利、財報和股東回報 | P1 不新增基本面 fetcher。 |
| `news` | 新聞、公告、輿情和催化事件輸入 | P1 不改變新聞搜索。 |
| `portfolio` | 是否持倉、賬戶摘要、成本、數量、倉位和 stale 摘要 | P1 不納入交易流水、現金流水或完整賬戶隱私數據。 |
| `chip` / `capital_flow` | 籌碼、資金流和主力行為 | 後續擴展鍵，P1 只允許契約表達。 |
| `events` / `market_context` | 風險事件、市場寬度、指數、板塊和熱點環境 | 後續擴展鍵，不把 `market_review` / `market_light` 作為首版單股 pack。 |

`phase` 字段只接收 #1386 `MarketPhaseContext.to_dict()` 產物，保持 `Dict[str, Any]`，不重新定義 phase enum 或 phase 子模型。

脫敏邊界：

- `AnalysisContextPack.to_safe_dict()` 先執行 `model_dump(mode="json")`，再調用 `redact_sensitive_mapping()`。
- `redact_sensitive_mapping()` 只做 dict/list 的 key-based 遞歸脫敏，命中 `api_key`、`access_token`、`refresh_token`、`authorization_header`、`webhook_url`、`password`、`cookie`、`secret`、`token`、`sendkey`、`license_key` 等敏感鍵或短語時把值替換為 `[REDACTED]`。
- P1 不掃描普通字符串值，不做 URL 正則脫敏，不把 `data_api` 或裸 `api` / `key` 當作敏感命中，避免把本契約擴展成通用 secrets engine。

## P2 Builder 契約

P2 新增 `AnalysisContextBuilder`，但首版只做 assembler：從普通分析 pipeline 已經拿到的 artifacts 組裝內部 `AnalysisContextPack`。Issue 驗收項裡的“複用現有數據源”在本 slice 中解釋為複用 pipeline 已 fetch 的 `realtime_quote`、`base_context`、`enhanced_context`、`trend_result`、`chip_data`、`fundamental_context`、`news_context` 等 artifacts；builder 本身 zero-fetch，不調用 DB、fetcher、SearchService、Agent 工具或具體 provider。

P2 輸入契約使用 `PipelineAnalysisArtifacts`：`code`、`stock_name`、`market`、`phase`、`base_context`、`enhanced_context`、`realtime_quote`、`trend_result`、`chip_data`、`fundamental_context`、`news_context`、`news_result_count`、`metadata`。單股 `build()` 與批量 `build_batch()` 複用同一結構，避免 P3 runtime 接入時再次改簽名。

P2 block 組裝邊界：

- `subject` 仍只寫 `code`、`stock_name`、`market` 三字段，不擴 `AnalysisSubject`。
- `phase` 只接收傳入的 `MarketPhaseContext.to_dict()` 產物，不從 `enhanced_context` 反推。
- `quote` 從 `realtime_quote` 組裝；缺失為 `missing`；`source=fallback` 或顯式 `fallback_from` 映射為 `fallback`，但 `source` 保留真實成功源；`fallback_from` 只在 artifact/metadata 顯式提供時填寫，否則只記錄穩定 warning code，不偽造 provider 鏈。
- `quote` 會透傳 #1386 P3 的 `fetched_at`、`provider_timestamp`、`is_stale`、`stale_seconds`、`fallback_from`。狀態優先級固定為 `STALE > FALLBACK > AVAILABLE`：`is_stale=True`、`price_stale`、`quote_stale`、`quote_stale_seconds` 等顯式 marker 標為 `stale`；`stale_seconds` 且 `is_stale=False` 只是元數據，不單獨推斷 stale。builder 只映射上游 artifact，不做質量評分。
- `daily_bars` 只表達完整日線窗口，優先讀 `base_context.today`、`base_context.yesterday`、`base_context.date`、`base_context.data_missing`；date-only 放入 `value` 或 `metadata`，不寫入 `timestamp`。
- `enhanced_context.today` 上的 `is_partial_bar`、`is_estimated`、`estimated_fields` 優先進入 `technical`；缺失時仍兼容 `enhanced_context.today.data_source` 為 `realtime:*` 的舊 heuristic。partial/estimated 只進入 `technical`，`daily_bars` 不承載 partial/estimated，warning 使用 `intraday_realtime_overlay`。
- `technical` 優先複用 `trend_result.to_dict()`；無 trend artifact 時為 `missing`。
- `chip` 複用 `chip_data.to_dict()`；無 chip artifact 默認 `missing`，只有輸入 metadata/artifact 明確 not_supported 時才標 `not_supported`。
- `fundamentals` 只讀 `fundamental_context` 參數；`ok` 映射為 `available`，`not_supported` 映射為 `not_supported`，`partial` 映射為 `partial`，P5 後 `failed` 映射為 `fetch_failed` + 穩定 reason code `fundamental_pipeline_failed`；不寫入 `errors[]` 原文。
- `news` 非空白字符串為 `available`，空白或缺失為 `missing`；`news_result_count` 寫入 pack metadata。

P2 不組裝 `portfolio`、`events`、`market_context`，也不把 `capital_flow` 拆成獨立 block；首版只把它保留在 fundamentals 的 coverage/source chain metadata 中。P2 當時也不改變 Prompt、不讓普通分析或 Agent runtime 消費 pack、不寫入 history/task/report metadata、不暴露完整 pack 到 API/Web/Bot/Desktop/通知；P5 只在現有 builder 上追加低敏評分、`fetch_failed` 細分和 Prompt 限制，不新增 fetcher。

## P3 Runtime Consumption

P3 在 P2 `AnalysisContextBuilder` 之後接入運行態消費，但消費面限定為低敏 `analysis_context_pack_summary`。`StockAnalysisPipeline` 是 summary 的唯一生產者：在普通分析路徑和 Agent 路徑內完成 `PipelineAnalysisArtifacts` -> `AnalysisContextBuilder.build()` -> `format_analysis_context_pack_prompt_section()`，下游 analyzer、single-agent、multi-agent 只接收 summary 字符串，不自行構造完整 pack，也不讀取 `AnalysisContextPack.to_safe_dict()` 的 block item 原始值。

普通分析 Prompt 的順序固定為：基礎信息 -> #1386 `market_phase_context` 渲染區塊 -> `analysis_context_pack_summary` -> 技術面、實時行情、新聞等既有區塊。`analysis_context_pack_summary` 只包含 subject、`pack_version`、block `status` / `source` / `warnings` / `missing_reason`、`metadata.news_result_count`、`data_quality.warnings` 和 P5 低敏數據限制，不得輸出 `news.content`、`trend_result`、`chip`、`fundamental_context` 等原始 payload。

Agent 路徑同樣只傳 summary。`AgentExecutor._build_user_message()` 在 market phase 段之後、pre-fetched JSON 之前插入 summary；`AgentOrchestrator._build_context()` 只把 summary 放入 `ctx.meta["analysis_context_pack_summary"]`，禁止寫入 `ctx.data`；`BaseAgent._build_messages()` 在 market phase user message 之後、`_inject_cached_data()` 之前插入 summary。Agent 路徑會在 `_ensure_agent_history()` 預取後讀取一次 `storage.get_analysis_context()` 作為 `daily_bars` 的低敏狀態來源，讀取失敗或無可用上下文時才標記 `daily_bars_missing`，該讀取 fail-open 且不把日線原始 payload 寫入 Agent runtime context。Agent 首輪沒有複用普通分析新聞檢索，`news` block 為 `missing` 是當前 P3 的預期狀態。

P3 當時不持久化完整 pack，不新增 API/Web/Bot/Desktop 字段，不改變報告 JSON schema，不把 summary 寫入 `analysis_history.context_snapshot`、task status 或 report metadata；history snapshot 和 diagnostic snapshot 會剝離 `market_phase_context`、`analysis_context_pack`、`analysis_context_pack_summary` 等 runtime prompt key。P4 在此基礎上新增低敏 overview，可見性只覆蓋歷史詳情、同步分析響應、completed task status 和 Web 報告頁；P5 繼續複用 summary 消費路徑，不改 LLM 輸出 JSON schema。Agent 工具級 pack cache 複用仍是後續工作。

## #1381 Daily Market Context

#1381 在 AnalysisContextPack 之外新增一個小型每日大盤環境摘要通道，避免把 `market_review` / `market_light` 直接 pack 化。`DAILY_MARKET_CONTEXT_ENABLED` 默認開啟；當 `MARKET_REVIEW_ENABLED=true` 且 `DAILY_MARKET_CONTEXT_ENABLED=true` 時，`StockAnalysisPipeline` 會按個股市場（`cn` / `hk` / `us`）加載當日大盤上下文：優先複用 `analysis_history(code=MARKET, report_type=market_review)` 中同日同市場記錄；沒有同日記錄時才調用 `run_market_review(..., return_structured=True, send_notification=False)` 生成本次上下文，且通過進程內 cache 避免同一 Pipeline 重複生成，並在 CLI/定時任務併發路徑上通過 market review lock 串行化生成。`DAILY_MARKET_CONTEXT_ENABLED=false` 只關閉個股分析的低敏摘要注入與保守護欄，不關閉大盤覆盤本身。

**Background：**`#1381` 聚焦單股分析的當日大盤上下文複用與回退控制，不改變現有日內階段、日報或狀態建模架構。該段與 `docs/CHANGELOG.md` [Unreleased] 的 #1381 條目保持一致，可作為本輪變更說明的收斂邊界。
**Scope（本輪實現範圍）：**`#1381` 僅覆蓋後端 runtime 的大盤上下文注入、當日/目標交易日複用控制與保守護欄；不包含獨立 API、Web 階段結果獨立展示、四階段日報結構化持久化或新增日報狀態表。涉及主要入口為 `main.py`（調度與 `--no-market-review`）、`src/core/pipeline.py`、`src/core/market_review.py`、`src/services/daily_market_context.py`、`src/analyzer.py`、`src/analysis_context_pack_overview.py`、`src/agent/executor.py`、`src/agent/orchestrator.py`、`src/agent/agents/base_agent.py`、`src/daily_market_context_guardrail.py`；Web 側僅同步 `DAILY_MARKET_CONTEXT_ENABLED` 設置項文案/幫助，不新增階段結果展示。
**驗收閉環邊界：**本 PR 僅對應 `#1381` 的 runtime 接入與護欄子目標；除非獨立 API、Web 階段展示、四階段日報持久化和日報狀態表已在後續變更中落地並驗證，否則不得把 Issue #1381 標記為完整驗收通過。
**Acceptance Criteria（驗收邊界）：**本輪僅按 runtime 與配置入口驗收，不納入 PR 過程中的 API/Web UI 獨立階段展示驗收。當前驗收路徑限制為 `tests/test_main_schedule_mode.py`、`tests/test_pipeline_daily_market_context.py`、`tests/test_daily_market_context.py`、`tests/test_daily_market_context_guardrail.py`、`tests/test_agent_executor.py`、`tests/test_config_env_compat.py`、`tests/test_config_registry.py` 和 `apps/dsa-web/tests/system_config_i18n.test.ts`。重點覆蓋項為：`--no-market-review` 禁止觸發大盤覆盤生成、`DAILY_MARKET_CONTEXT_ENABLED=false` 關閉個股上下文注入但保留大盤覆盤、單次 schedule 複用同一 `target_date`、多市場上下文加載（`cn,us`）、`daily_market_context` 只在同一次分析主鏈路注入一次、普通分析與 Agent 路徑應用護欄且不洩漏原始 `market_review_payload`。
**Compatibility/Risk（兼容與風險）：**`#1381` 不改變 `provider/model/base_url`、默認模型或配置清理/回填/遷移語義；不新增數據庫或運行時配置表變更。`main.py::_bootstrap_environment`、`src/core/pipeline.py`、`src/analyzer.py`、`src/agent/executor.py`、`src/agent/orchestrator.py`、`src/agent/agents/base_agent.py`、`src/services/daily_market_context.py`、`src/daily_market_context_guardrail.py` 只在既有讀取鏈路消費 LLM 與市場覆盤上下文，不新增 `SystemConfig` 保存或回寫分支。官方兼容依據沿用 `LiteLLM OpenAI-compatible` 與 `OpenAI Chat Completion`（見後文“兼容性證據與核驗邊界”）；回滾方式為常規發佈回滾（撤銷相關提交），如必要可配合重啟並清理 `env_file` / `--env-file` / 進程級同名環境覆蓋項，恢復用戶歷史持久化配置。
**兼容性證據與核驗邊界：**本輪僅複用既有 LLM 配置鏈路讀取配置，不新增 `.env` 寫入分支，不新增配置遷移/清理/回寫入口。官方依據沿用：`LiteLLM OpenAI-compatible` <https://docs.litellm.ai/docs/providers/openai_compatible>、`OpenAI Chat Completion` <https://platform.openai.com/docs/api-reference/chat/create>；版本約束見 `requirements.txt`（`litellm`、`openai`）當前窗口。可回溯代碼路徑：`main.py::_bootstrap_environment`、`src/analyzer.py::_init_litellm`、`src/agent/agents/base_agent.py::_get_analyzer_config`（僅讀取）、`src/agent/executor.py`、`src/agent/orchestrator.py`、`src/core/pipeline.py`、`src/services/daily_market_context.py`、`src/daily_market_context_guardrail.py`。迴歸核驗點為 `tests/test_config_env_compat.py`、`tests/test_config_registry.py`、`tests/test_system_config_service.py`、`tests/test_system_config_api.py`、`tests/test_llm_channel_config.py`、`tests/test_market_review_runtime.py`。

普通分析與 Agent 分析只接收低敏字段：`daily_market_context`（region、trade_date、summary、risk_tags、source、可選 position_cap）和 `daily_market_context_summary` Prompt 段，不傳遞完整 `market_review_payload`、原始新聞、密鑰或通知配置。普通分析 Prompt 在市場階段段落後、技術面數據前插入大盤摘要；Agent 單體與多 Agent 路徑在 market phase 後、pre-fetched 數據前插入同一摘要。Agent 自由聊天只在調用方已經提供 `daily_market_context` / `daily_market_context_summary` 時注入，不為每次聊天自動觸發大盤覆盤。

結果後處理新增保守大盤環境護欄：當摘要或標籤顯示 `high_risk`、`market_cooling`、`conservative`、`low_position_cap`，且處於保守/高風險語境下時，模型給出 `buy` 決策（含“立即買入/追高/激進加倉”等買入類建議）會被軟化為觀望或小倉等待確認，並把高置信度降為中等。該護欄只修改當次 `AnalysisResult` 與 dashboard 中的低敏限制說明，不新增數據庫表或 API 字段。回滾方式為撤銷 #1381 相關服務、Prompt 注入和 guardrail 代碼，既有大盤覆盤歷史記錄保持兼容。

## P4 歷史記錄、任務狀態與 Web 可見性

P4 把 P3 已構建的 `AnalysisContextPack` 投影為公共低敏 `analysis_context_pack_overview`。該 overview 由專用 renderer 生成，公共 API 不允許直接返回 `AnalysisContextPack.to_safe_dict()` 或完整 pack dump。renderer 只輸出白名單字段：`pack_version`、`created_at`、`subject.code` / `stock_name` / `market`、數據塊 `key` / `label` / `status` / `source` / `warnings` / `missing_reasons`、按 block status 計數的 `counts`、頂層 `data_quality.warnings` 和 `metadata.trigger_source` / `metadata.news_result_count`。P5 在同一 overview 上追加 `data_quality` 低敏對象，不重複頂層 `warnings`。

overview 不輸出 `blocks.*.items`、`items.value`、`news.content`、`trend_result`、`chip`、`fundamental_context` 原始 payload，也不輸出 `api_key`、`token`、`cookie`、`webhook_url`、`password`、`secret`、`authorization`、`sendkey`、`license_key` 等敏感鍵或值。

P4 持久化面只在 `analysis_history.context_snapshot` 頂層寫入 `analysis_context_pack_overview`。運行態 prompt 字段仍會從 `enhanced_context` 和 history snapshot 中剝離：`market_phase_context`、`analysis_context_pack`、`analysis_context_pack_summary` 不進入公開歷史詳情或任務狀態。`SAVE_CONTEXT_SNAPSHOT=false` 時不持久化整份 `analysis_history.context_snapshot`，因此也不會落庫 overview、`market_phase_summary`、`enhanced_context` 或 raw snapshot 字段；舊記錄或缺少 overview 的記錄繼續返回空字段，不影響歷史詳情讀取。

公共 overview block 可追加 `timestamp`、`provider_timestamp`、`fetched_at`：僅透傳可解析的 ISO 8601 datetime，保留時區和原始值；不從任意 item 猜測整個 block 的時間，不暴露其他 metadata。`timestamp` 可能來自抓取時間，不能當作觀測時間或新鮮度證明；`provider_timestamp` 與 `fetched_at` 分別保留來源觀測時間和抓取時間。舊 overview 缺少字段時仍可讀取。

公共 API 字段固定為 `report.details.analysis_context_pack_overview`，Web 端經深度 camelCase 後讀取 `analysisContextPackOverview`。接線麵包括：

- `GET /api/v1/history/{record_id}` 歷史詳情。
- 同步 `POST /api/v1/analysis/analyze` 返回的 `AnalysisResultResponse.report.details`，但 overview 依賴已持久化的 `analysis_history.context_snapshot`；`SAVE_CONTEXT_SNAPSHOT=false` 時，新記錄不保證返回 overview。
- completed `GET /api/v1/analysis/status/{task_id}`，包括內存隊列 enrichment 和 DB completed fallback。

API 返回給 Web 的 `details.context_snapshot` 會通過 `sanitize_context_snapshot_for_api()` 剝離頂層 `analysis_context_pack_overview`，避免 raw snapshot 面板重複展示或被當作完整上下文導出；overview 只從 `extract_analysis_context_pack_overview()` 單獨取出。Agent 路徑與普通分析路徑寫入同一 overview 形狀，Agent 無新聞計數時 `metadata.news_result_count` 可為空。

P4 Web 展示只在報告詳情頁渲染 `AnalysisContextSummary`，位置在策略點位和資訊之後、運行診斷之前；該區域默認摺疊，摺疊頭部展示可用數、缺失數、非零的其他狀態計數和觸發來源，展開後的每個數據塊只展示狀態、來源、告警和說明。來源為空時顯示“未記錄輸入來源”；說明行把已知缺失原因翻譯為原因、對本次分析的影響和簡短處理建議，並在括號中保留診斷碼，未知原因則按 block 狀態提供通用建議。`fallback`、`stale`、`estimated`、`partial` 等沒有缺失原因的降級狀態也在同一說明行解釋，不新增處理、範圍或證據字段。報告頁相關資訊由獨立接口加載，其有無不能通過 overview 的 `metadata.news_result_count` 推斷；資訊區只說明自身是報告頁補充資訊，輸入數據塊只說明新聞是否進入本次 LLM 分析，避免把兩套數據範圍混為同一結果集。展開區仍展示狀態計數和新聞結果數。P5 後摺疊頭部還會展示質量分/等級，展開後展示 `limitations` 和 `fetch_failed` 狀態。無 overview 時不渲染佔位。在 #1386 P4b 中，Web 會在同一報告詳情頁展示 `report.meta.market_phase_summary` 階段標籤，並繼續複用該低敏數據質量摘要；不擴大完整 pack、Prompt summary、raw payload 或 snapshot 內部字段的公開面。P4/P5 不覆蓋 pending/processing TaskPanel 的 AnalysisContextPack 數據質量摘要或 SSE 進行中 overview 可見性，不改通知摘要、Bot/Desktop 專屬展示或 `market_review` overview。

## P5 數據質量評分與 Prompt 數據限制

P5 在不升級 `PACK_VERSION`、不新增 fetcher、不新增配置項、不做歷史遷移的前提下補齊三件事：內部低敏數據質量評分、跨模型通用的 Prompt 數據限制區塊，以及既有 `analysis_context_pack_overview` 的低敏可見性擴展。#1389 P5 仍不改變 LLM 輸出 JSON schema，也不做後處理強制改寫；#1386 P5 會消費這裡的低敏輸入質量，在報告 `dashboard.phase_decision` 中輸出盤中動作字段與質量護欄結果。

狀態契約新增 `fetch_failed`，用於“當前字段或數據塊本次抓取明確失敗”。首版只在已有 artifact 明確失敗時使用，例如 `fundamental_context.status == "failed"`；空新聞、未配置搜索、無實時 quote artifact 或 chip 缺失仍保持既有 `missing` / `not_supported` 語義，避免把未啟用能力誤報成抓取失敗。`fetch_failed` 不代表整次分析失敗。

`DataQuality` 追加以下低敏字段，並保留舊 `warnings` / `metadata`：

- `overall_score: Optional[int]`：0-100 總分。
- `level: Optional["good"|"usable"|"limited"|"poor"]`：`>=85 good`、`>=70 usable`、`>=55 limited`，否則 `poor`。
- `block_scores: Dict[str, int]`：固定六塊的狀態分。
- `limitations: List[str]`：最多 5 條穩定限制說明，使用 `block: status` 形式。

評分只計算固定六塊，不隨輔助塊缺失重歸一化，未來新增 block 不自動影響總分。權重固定為 `quote=25`、`daily_bars=25`、`technical=25`、`news=10`、`fundamentals=10`、`chip=5`；狀態分固定為 `available=100`、`partial=75`、`estimated=75`、`not_supported=70`、`fallback=65`、`stale=50`、`missing=35`、`fetch_failed=25`。總分公式為 `round(sum(block_score * weight) / 100)`。

`limitations` 優先列出核心塊 `quote` / `daily_bars` / `technical` 的 `stale`、`fallback`、`missing`、`fetch_failed`、`partial`、`estimated`；其次列出輔助塊 `news` / `fundamentals` / `chip` 的 `fetch_failed`、`fallback`、`stale`。輔助塊單純缺失不進入限制列表，避免把新聞缺失、未配置搜索或不支持能力解釋成利好/利空。

Prompt 數據限制只在 `format_analysis_context_pack_prompt_section()` 內渲染，緊跟 pack summary，因此普通分析、single Agent 和 multi-agent 複用同一消費路徑。中文輸出 `數據限制`，英文輸出 `Data Limitations`；只有真實 score 存在時才輸出評分行。若 `quote`、`daily_bars` 或 `technical` 為 degraded 狀態，Prompt 明確要求最終 JSON 的 `confidence_level` 不得為 `高` / `High`。Prompt 繼續只使用 status/source/warnings/missing_reason/低敏評分，不輸出 raw payload、新聞正文、趨勢原始值、secret、token 或 webhook。

#1386 P2-full 在 P5 score/limitations 之後、confidence/safety 之前追加最小的 `phase × degraded data` 交叉約束：當 `AnalysisContextPack.phase` 來自合法 `MarketPhaseContext`，且 `quote`、`daily_bars` 或 `technical` 存在 degraded 狀態時，Prompt 只補充當前階段下數據質量如何限制盤中判斷、開盤計劃或保守分析；它不替代 P5 的 confidence/safety 規則，也不復述 `market_phase_context` 的 phase-only 文案。`pack.phase` 缺失、非 dict 或包含非法 phase 時 fail-open，僅保留 P5 通用數據限制。

overview 只擴展現有公開面：`analysis_context_pack_overview.data_quality` 白名單包含 `overall_score`、`level`、`block_scores`、`limitations`，不重複公開 `warnings`。`render_analysis_context_pack_overview()` 與 `extract_analysis_context_pack_overview()` / persisted sanitizer 都會清洗該對象；舊 overview 缺少 `data_quality` 時仍正常讀取。`details.context_snapshot` 繼續剝離頂層 `analysis_context_pack_overview`，不公開完整 pack。

## P6 告警、持倉、歷史和回測聯動

#1386 P6 不新增 pack 版本，也不把完整 pack 暴露到更多公共面。它只複用 P4/P5 已定義的 `analysis_context_pack_overview` 和 #1386 已定義的 `market_phase_summary`：

- 告警觸發記錄仍寫入現有 `alert_triggers.diagnostics` 文本字段；當 diagnostics 可 JSON 化時，worker 會合並 `analysis_visibility.analysis_context_pack_overview`，來源只允許 evaluator 已帶 overview 或最近 30 天曆史 snapshot。舊純文本 diagnostics 不被覆蓋，API 派生字段為空且 source 為 `legacy_text`。
- 持倉手動分析通過 API 構造低敏 `portfolio_context` 並傳入 pipeline；builder 會在 pack 中加入可選 `portfolio` block。該 block 只包含賬戶 ID/name、symbol、market、currency、quantity、avg cost、total cost、unrealized PnL、price source/provider/date/stale/available 和 cost method，不包含交易流水、現金流水、新聞正文、Prompt、密鑰或 webhook。
- `portfolio` block 是輔助塊，`metadata={"auxiliary": true, "quality_weighted": false}`，不改變 P5 固定六塊 `quote`、`daily_bars`、`technical`、`news`、`fundamentals`、`chip` 的權重、總分或 limitations 口徑。
- `portfolio_context` 只在任務執行內部透傳；`TaskInfo.to_dict()`、任務列表、SSE `task_created/task_started/task_completed/task_failed/task_progress` payload 不暴露該對象。
- 歷史列表、單股歷史、StockBar 和回測結果只讀取 `context_snapshot` 頂層的公開 `market_phase_summary`；舊記錄、`SAVE_CONTEXT_SNAPSHOT=false` 或解析失敗返回 `null` / `unknown`，不失敗。
- 回測 phase filter 只基於公開 summary 做 bucket：`premarket` 保持 premarket，`intraday|lunch_break|closing_auction` 歸入 intraday，`postmarket` 保持 postmarket，`non_trading|missing|invalid` 歸入 unknown。帶 phase 過濾時 repository 先按 SQL 條件批量讀取結果和 snapshot，服務層 bucket 後再分頁和統計，避免 API 層分頁後臨時過濾。
- 通知摘要只消費 `market_phase_summary` 與 `analysis_context_pack_overview.data_quality`，輸出階段、trigger source、partial-bar warning、質量等級和前兩條 limitations；不輸出 raw pack、`analysis_context_pack_summary` Prompt 字符串、新聞正文或持倉敏感細節。

## P6 文檔、遷移與回滾

P6 不改變 P1-P5 的運行時行為，只把已經落地的契約、可見性、配置、遷移和回滾邊界寫成穩定文檔。它不新增 pack enable/disable feature flag，不升級 `PACK_VERSION = "1.0"`，不新增 API 參數，不改變報告 JSON schema，也不做數據庫遷移。

四個數據面必須分開理解：

| 數據面 | 位置 | 可見性 | P6 邊界 |
| --- | --- | --- | --- |
| 內部完整 pack | `AnalysisContextPack` / `AnalysisContextBuilder` 產物 | 僅內部運行態使用 | 不作為公共 API，不寫入歷史，不承諾外部穩定 wire contract。 |
| LLM 低敏摘要 | `analysis_context_pack_summary` | 普通分析、single Agent、multi-agent Prompt | 只包含 subject、pack version、block status/source/warnings/missing reason、新聞結果數和數據限制；不包含 `items.value`、新聞正文、趨勢/籌碼/基本面 raw payload、secret、token 或 webhook。 |
| 公共低敏 overview | `report.details.analysis_context_pack_overview` | 歷史詳情、同步分析響應、completed task status、Web 報告頁 | 只輸出白名單字段和 `data_quality` 低敏評分；不輸出完整 pack、Prompt summary 或 raw payload。 |
| 歷史上下文快照 | `analysis_history.context_snapshot` | 持久化後供歷史/API/Web/診斷讀取 | `details.context_snapshot` 經 `sanitize_context_snapshot_for_api()` 剝離 `analysis_context_pack_overview` 和 `market_phase_summary`，避免 raw 面板重複公開穩定摘要。 |

摘要可見性矩陣：

| 消費面 | 暴露內容 | 不暴露內容 |
| --- | --- | --- |
| LLM Prompt | `analysis_context_pack_summary` 低敏狀態摘要和數據限制 | 完整 pack、`items.value`、新聞正文、趨勢/籌碼/基本面 raw payload、secret/token/webhook |
| `GET /api/v1/history/{record_id}` | `report.details.analysis_context_pack_overview` | 完整 pack、Prompt summary、raw `analysis_context_pack_overview` duplicate |
| 同步 `POST /api/v1/analysis/analyze` | `report.details.analysis_context_pack_overview`，前提是本次歷史已持久化 `analysis_history.context_snapshot` | 完整 pack、Prompt summary |
| completed `GET /api/v1/analysis/status/{task_id}` | `status.result.report.details.analysis_context_pack_overview` | 完整 pack、Prompt summary |
| Web 報告頁 | 默認摺疊的 `AnalysisContextSummary`，展示 block 狀態、來源、告警、包含影響/建議/診斷碼的說明、質量分和限制 | 完整 pack、raw payload、Prompt summary、報告頁獨立加載的資訊結果狀態 |
| raw `details.context_snapshot` | 剝離後的歷史快照 | 頂層 `analysis_context_pack_overview`、`market_phase_summary` |
| 通知、Bot、Desktop 專屬展示 | P6 不新增專屬展示 | 完整 pack、Prompt summary、raw payload |

字段質量狀態全集保持為 `available`、`missing`、`not_supported`、`fallback`、`stale`、`estimated`、`partial`、`fetch_failed`。這些狀態解釋輸入數據質量，不表示分析任務、告警、回測或通知投遞本身成功或失敗。

脫敏邊界：

- 完整 `AnalysisContextPack` 不進入公共 API、Web、通知、Bot 或 Desktop 專屬展示。
- `AnalysisContextPack.to_safe_dict()` 只作為內部安全序列化 helper；公共 overview 仍必須通過 `render_analysis_context_pack_overview()` 投影。
- `analysis_context_pack_summary` 與 overview 都不得輸出 `items.value`、新聞正文、`trend_result`、`chip`、`fundamental_context` 原始 payload、API key、token、cookie、完整 webhook URL、郵箱密碼、secret、authorization、sendkey 或 license key。
- 已持久化 overview 再讀取時必須經過 `extract_analysis_context_pack_overview()` / persisted sanitizer；API 透明度面板必須繼續通過 `sanitize_context_snapshot_for_api()` 剝離頂層穩定摘要。

遷移邊界：

- P6 不做 DB migration；舊歷史記錄缺少 `analysis_context_pack_overview` 或 `data_quality` 時返回空字段，報告仍正常讀取。
- `SAVE_CONTEXT_SNAPSHOT=true` 是默認行為，會繼續把 `analysis_history.context_snapshot` 作為歷史透明度和診斷來源持久化。
- `SAVE_CONTEXT_SNAPSHOT=false` 或 CLI `--no-context-snapshot` 會停止持久化整份 `analysis_history.context_snapshot`；換言之，新歷史不持久化整份 `analysis_history.context_snapshot`，包括 `enhanced_context`、`market_phase_summary`、`analysis_context_pack_overview`、`diagnostics`、`realtime_quote_raw` 和其他 raw snapshot 字段。
- 關閉持久化不影響當次 `AnalysisContextPack` 構建、`analysis_context_pack_summary` 注入 Prompt，也不影響內存中的 `result.diagnostic_context_snapshot`。

回滾方式：

| 手段 | 作用 | 不能做什麼 |
| --- | --- | --- |
| 發佈或代碼回滾 P3-P5 相關改動 | 移除 pack prompt summary、overview 和數據質量接入 | - |
| `SAVE_CONTEXT_SNAPSHOT=false` 或 `--no-context-snapshot` | 停止保存新的歷史 `context_snapshot`，從而不再從新歷史公開 overview / phase summary / raw snapshot | 不能關閉當次 pack 構建或 LLM Prompt 中的低敏 summary |
| 運行時 pack 總開關 | 當前不存在 | 不能通過 env 一鍵關閉 P3-P5 pack 接入；需要代碼回滾或後續單獨設計 |

## 字段質量狀態

未來 pack 的字段質量狀態在 P0 先固定七詞；P5 在同一 1.0 umbrella 內追加 `fetch_failed`。它們描述字段或數據塊的質量，不描述業務流程是否成功。

| 狀態 | 含義 | 示例邊界 |
| --- | --- | --- |
| `available` | 字段存在，來源和時間戳可解釋，當前路徑可正常使用。 | 實時行情返回價格和來源；歷史 K 線窗口滿足計算需求。 |
| `missing` | 當前路徑需要該字段，但實際未取到或為空。 | DB 無最近日線，普通分析進入 `data_missing` 結果。 |
| `not_supported` | 當前市場、數據源或路徑不支持該字段，不應誤報為錯誤。 | 某些市場無籌碼分佈或資金流。 |
| `fallback` | 首選來源不可用，使用了備用來源或舊路徑。 | 持倉價格從實時行情 fallback 到歷史收盤價。 |
| `stale` | 字段存在，但時間新鮮度不足。 | 持倉估值中的 `price_stale` / `fx_stale`。 |
| `estimated` | 字段是估算值，不應當作完整事實。 | 盤中用實時價補今日 bar 後生成技術估計。 |
| `partial` | 數據塊部分可用、部分缺失。 | 大盤紅綠燈 `data_quality=partial` 或工具返回 `partial_cache`。 |
| `fetch_failed` | 當前路徑確認嘗試過抓取，但本次抓取失敗。 | `fundamental_context.status == "failed"` 映射為基本面 block 抓取失敗。 |

## 現有狀態映射

當前倉庫已有不少狀態詞。P0 只建立映射或不映射關係，避免後續把業務結果狀態混入字段質量枚舉。

| 現有詞或字段 | 當前位置 | 建議關係 | 說明 |
| --- | --- | --- | --- |
| `data_missing` | 普通分析缺歷史數據結果 | 可映射到 `missing` | 這是核心輸入缺失，不是業務成功狀態。 |
| `cache_hit` / `partial_cache` | Agent 歷史數據工具 | `partial_cache` 可映射到 `partial` | `cache_hit` 是來源/緩存元數據，不是質量狀態。 |
| `source` / `data_source` / `realtime_source` | 數據源、告警、上下文快照 | 不映射 | 這些是來源元數據，應與字段質量狀態並列保存。 |
| `price_source=missing` | 持倉快照 | 可映射到 `missing` | 表示估值價格不可用。 |
| `price_stale` / `fx_stale` | 持倉快照 | 可映射到 `stale` | 保留原字段作為業務元數據。 |
| `triggered` / `skipped` / `degraded` / `failed` | 告警評估與記錄 | 不映射 | 這是規則評估或記錄結果，不是字段級質量狀態。 |
| `insufficient_data` / `completed` / `error` | 回測服務 | 不映射 | 這是回測執行狀態；可在 pack 摘要中解釋觸發原因。 |
| `sent` / `no_channel` / `partial_failed` / `all_failed` | 通知發送 | 不映射 | 這是通知投遞結果，不能反推分析輸入質量。 |
| `data_quality=ok/partial/unavailable` | 大盤紅綠燈 | `partial` 可映射，`unavailable` 視字段場景映射到 `missing` 或 `not_supported` | P0 不把大盤紅綠燈納入首版單股 pack。 |
| `fetch_failed` | 數據質量細分 | P5 映射為 `fetch_failed` | 只在已有 artifact 明確失敗時使用，不代表整次分析失敗。 |

## 七路徑盤點

### 普通分析

普通分析主鏈路在 `src/core/pipeline.py` 中組裝輸入：先讀取 `storage.get_analysis_context()`，再按可用性補充實時行情、籌碼、趨勢分析、新聞、基本面和報告語言，最後交給 `src/analyzer.py` 渲染 prompt。當前重複點主要是實時字段同時存在於 `enhanced_context.realtime`、`realtime_quote_raw` 和報告 meta；命名上存在 `source`、`data_source`、`realtime_source` 等多種來源字段。

首版 pack 可從普通分析路徑抽取單股核心身份、行情、日線、技術、新聞、基本面和數據質量摘要；P0 不改變 `_enhance_context()`、`_build_context_snapshot()` 或 analyzer prompt。

### Agent

Agent 有三層需要分開記錄的數據面。`src/core/pipeline.py` 的 Agent 路徑會構造 `initial_context`，固定包含 `fundamental_context`，並在可用時加入 `trend_result`，最終作為 Agent 路徑的 `context_snapshot` 持久化。`AgentExecutor._build_user_message()` 只適用於 `AGENT_ARCH=single`，首輪消息只顯式注入 `realtime_quote`、`chip_distribution`、`news_context` 等已取上下文，不顯式注入 `fundamental_context` 或 `trend_result`。`AgentOrchestrator._build_context()` 適用於 `AGENT_ARCH=multi`，可預注入 `realtime_quote`、`daily_history`、`chip_distribution`、`trend_result`、`news_context`，這些進入 `AgentContext` 的字段會作為 pre-fetched data 注入 stage agent 消息；但 orchestrator 不預注入 `fundamental_context`。`trend_result` 不是天然存在，取決於 caller 是否傳入。

Agent 工具還會獨立調用 `get_realtime_quote`、`get_daily_history`、`get_chip_distribution`、`get_analysis_context`、`get_stock_info` 等工具，容易與普通分析前置獲取產生重複請求。當前 pack 生成只在 Agent 歷史預取後複用 `storage.get_analysis_context()` 的日線可用性狀態，不復用或暴露完整工具級 pack cache；P5 再決定是否做更深的數據質量評分與工具緩存複用。

### 告警

告警鏈路在 `src/services/alert_worker.py` 中評估規則、記錄觸發歷史並分發通知，具體字段語義見 [實時告警中心](alerts.md)。告警狀態如 `triggered`、`skipped`、`degraded`、`failed` 是規則評估或記錄狀態，不能直接寫入字段質量枚舉。

首版 pack 不把告警規則評估作為輸入數據塊；告警後續只消費 pack 的字段質量摘要，例如核心行情是否 fallback、是否 stale、是否 partial。

### 持倉

持倉快照在 `src/services/portfolio_service.py` 中聚合賬戶、倉位、成本、價格、匯率和風險輸入，API 輸出結構在 `api/v1/schemas/portfolio.py`。當前已有 `price_source`、`price_provider`、`price_date`、`price_stale`、`price_available`、`fx_stale` 等字段。

首版 pack 可記錄“是否持倉、賬戶摘要、成本、數量、倉位、浮盈浮虧、價格/匯率 stale 摘要”，但不納入交易流水、現金流水、公司行動或完整賬戶隱私數據。

### 回測

回測服務在 `src/services/backtest_service.py` 和 `src/repositories/backtest_repo.py` 中消費歷史分析記錄與日線數據。現有 `parse_analysis_date_from_snapshot()` 依賴 `analysis_history.context_snapshot.enhanced_context.date` 解析分析日期。

P0 必須把 `enhanced_context.date` 標為兼容邊界。後續 pack 可以新增更清晰的日期字段，但不能無遷移地刪除或改名當前歷史快照中的日期位置。

### 歷史

歷史詳情在 `src/services/history_service.py`、`api/v1/endpoints/history.py`、`api/v1/schemas/history.py` 中返回 `raw_result`、`news_content`、`context_snapshot` 等字段。同步 analysis/status 響應也會在 `api/v1/endpoints/analysis.py` 中讀取 `context_snapshot.enhanced_context`、`realtime_quote_raw` 和基本面 fallback。

P0 只記錄歷史消費面。完整 pack 不應默認公開到歷史詳情或公共 API；後續 P4 如需展示，應優先暴露摘要、來源和降級說明。

### 通知

通知鏈路在 `src/notification.py` 中消費 `AnalysisResult`、dashboard、market snapshot、data_sources 等輸出，並記錄 `sent`、`no_channel`、`partial_failed`、`all_failed` 等投遞狀態；渠道配置與邊界見 [通知能力基線](notifications.md)。

通知不是事實數據層，不能把投遞失敗誤寫成輸入質量失敗。後續只應在必要時消費 pack 摘要，例如“實時行情已降級”“基本面缺失”“新聞源不足”。

## 源碼錨點

| 域 | 錨點 |
| --- | --- |
| 普通分析 | `src/core/pipeline.py`, `src/storage.py`, `src/analyzer.py` |
| Agent | `src/agent/orchestrator.py`, `src/agent/executor.py`, `src/agent/tools/data_tools.py` |
| 告警 | `src/services/alert_worker.py`, `docs/alerts.md` |
| 持倉 | `src/services/portfolio_service.py`, `api/v1/schemas/portfolio.py` |
| 回測 | `src/services/backtest_service.py`, `src/repositories/backtest_repo.py` |
| 歷史 | `src/services/history_service.py`, `api/v1/endpoints/history.py`, `api/v1/endpoints/analysis.py`, `api/v1/schemas/history.py` |
| 通知 | `src/notification.py`, `docs/notifications.md` |

## 兼容與安全邊界

- `analysis_history.context_snapshot.enhanced_context.date` 是當前回測日期解析兼容點，P1/P2 不能在沒有遷移的情況下破壞。
- 完整 pack 不默認公開到歷史、API、Web 或通知；P4/P5 只公開 `analysis_context_pack_overview` 低敏摘要、來源、fallback、stale、missing reason、block status count 和 `data_quality` 低敏評分。
- pack、日誌、歷史快照和 API 響應不得記錄 API key、token、cookie、完整 webhook URL、郵箱密碼、私有環境變量或其他密鑰。
- `source`、`timestamp`、`fallback`、`stale`、`partial` 等質量元數據只用於解釋輸入限制，不用於阻斷分析；除非現有核心路徑本來就是 fail-fast。
- #1386 的盤前 / 盤中 phase 感知是後續 `phase` / `data_quality` 字段的重要背景；P0 只記錄關係，不接入 runtime。
