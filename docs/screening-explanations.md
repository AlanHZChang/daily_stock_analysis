# 選股解釋契約

選股候選同時返回 `why_selected`、`why_now` 和 `explanation_quality`。解釋由後端在候選歸一化和 DSA 數據補充完成後生成，Web 逐條展示 text、source 和 quality；分組綜合質量只作摘要，不取代條目來源。Web 不再根據 `change_pct`、`amount` 或 LLM 字段自行猜測。

## 字段

每條 explanation item 包含：

- `code`：穩定原因代碼，例如 `selection_reason`、`top_factors`、`news`、`quote_change_pct`、`awaiting_evidence`。
- `text`：用戶可見說明。
- `source`：`screening`、`realtime_quote`、新聞來源、事件來源或 `llm`。
- `quality`：`observed`、`inferred` 或 `unknown`。
- `value`：可選數值；真實 `0` 必須原樣保留。

`explanation_quality.why_selected/why_now` 彙總為 `ok`、`partial` 或 `unknown`。

## Why Selected

確定性本地解釋優先使用 screening reason 和當前策略實際參與評分的因子；零權重或未配置的因子既不會進入缺省 `selection_reason`，也不會被寫成“核心因子”，兩處展示順序都按“因子分數 × 策略權重”的真實貢獻排列。`risk_summary` / `risk_level` 始終保留在獨立風險展示，不會在缺少 reason 時提升為 `selection_reason`；行業標籤也不會單獨冒充入選依據。缺少 reason 和可核驗加權因子時只確認“已進入當前選股候選結果”，不會把可能經過 LLM 排序、組合約束或後處理調整的最終名次誤寫成“確定性篩選排名”。來自 `post_analysis_summaries` 的 DSA/外部 analyzer 摘要保留 `post_analyzer:<name>` 來源並標記為 inferred，不冒充本地 observed；即使候選同時已有顯式 `reason` / `ranking_reason`，後分析摘要也會作為 `post_analysis_summary` 一併返回。去重身份為 `(text, source, quality)`：同一來源和質量的相同文案只保留一次，不同來源或質量即使文案相同也分別保留。顯式 reason 若只是後分析摘要的別名，不憑空增加 screening/observed 來源。純本地確定性 `scorecard` 摘要保持 observed，但只要 scorecard 消費了 `llm_confidence`、`llm_catalysts` 或 `llm_risks`，其解釋質量就保持 inferred。LLM ranking 的 `reason` 與 `thesis` 都是合法獨立解釋入口，即使僅返回 thesis 也保留為 llm/inferred；兩者內容不同則同時保留，相同則按上述身份去重。歸一化 raw 包裝對象時先合併響應字段，再判斷 scorecard 是否消費了外層 LLM 輸入。即使 LLM 未配置、超時或返回無效結構，候選仍至少返回入選結果說明；LLM 不是本地解釋的前置條件。

後分析器省略摘要、返回 `null` 或空白摘要時，若 `post_analysis_status` 為 `completed` 且 `post_analysis_score_deltas` 是有限非零數值，Why Selected 返回 `post_analysis_score_delta` 條目，說明分析器已完成、評分調整值以及未提供摘要；`value` 保留帶符號的分差，來源仍為 `post_analyzer:<name>`，質量沿用該分析器摘要的規則。該條目只說明評分影響，不推測調分依據。有摘要時沿用摘要條目，不重複追加調分說明；失敗、跳過、零分差或無有效分差時不生成此類條目。歸一化、服務響應和歷史持久化保留狀態、分差及生成的解釋，不改變原評分與重排行為。

## Why Now

時點解釋只使用帶來源的證據：DSA 新聞、事件，以及 `dsa_context.quote` 中明確存在的實時行情字段。新聞與事件都必須帶可解析的 `published_date`，且發佈時間在最近 30 天內；解析複用 SearchService 已支持的 ISO、RFC 2822、中文日期、Unix timestamp 和相對日期格式。缺日期或過期的新聞/事件不標記為 observed，包括複用已補充候選上下文而未重新搜索的路徑。候選頂層的 `change_pct=0` 或 `amount=0` 不能單獨證明數據真實存在，因為舊數據源可能用 0 表示缺失；沒有 quote provenance 時返回 `awaiting_evidence`，不會寫成“當前漲跌幅 0%”。

當 `dsa_context.quote.change_pct` 明確存在且為 `0` 時，它是合法平盤數據，返回 `value=0` 和 `quality=observed`。LLM catalyst 可作為 `inferred` 補充，但不能冒充觀測事實。
若 quote 標記 `is_stale`/`price_stale`，或質量為 partial/unavailable/stale/missing/fetch_failed，則其中數值不進入 Why Now observed；沒有其他新鮮證據時返回 `awaiting_evidence`。

## 當前階段邊界

本階段只完成 API explanation 和 Web 展示。Issue #2282 中的策略 metadata 擴充、結果行 action、run history diff、export/backtest 等仍是後續範圍。

## 回滾

移除 explanation 生成、Web 字段/卡片和對應測試即可回滾；原候選字段與 screening 排序流程保持兼容。

## 瀏覽器驗收

`cd apps/dsa-web && npx playwright test --config playwright.fixture.config.ts` 使用固定 API fixture 渲染真實頁面，不依賴後端服務或密鑰。CI 的 `web-gate` 安裝 Chromium、執行驗收，並將截圖上傳為 `web-ui-evidence-<head SHA>` artifact（保留 30 天）；截圖不提交到倉庫。該驗收驗證頁面交互和展示，不代表實時 provider/LLM 可用性。

## 舊版歷史兼容

打開或自動恢復舊版已持久化運行時，若候選缺少 `why_selected` 但保留 `reason`、`llm_thesis` 或後分析摘要，Web 在解釋卡片保留所有不同的“歷史摘要（來源未記錄）”，來源為 `legacy_result`、質量為 `unknown`。不會用當前策略權重重新解釋舊因子，也不會把舊行情或頂層佔位 0 當作當前 observed 證據。已有 explanation 數組優先使用；兼容展示不回寫數據庫、不修改歷史記錄。

## 驗收矩陣

- 接受的 ranker 響應：reason-only、thesis-only、reason+thesis、同文案 reason/thesis、risk-only。
- 歸一化：plain Pick、raw 包裝字段、重複歸一化後 provenance 保持一致。
- 後分析：顯式 reason 與每個 analyzer 共存；真實 scorecard、DSA 和 external_http 調分並重排後，排名理由與已完成的 analyzer 摘要仍分別保留；external_http 無摘要的正負調分與重排保留通用來源說明，服務響應與歷史記錄一致；同文案不同來源不丟失 inferred；本地 scorecard 與消費 LLM 輸入的 scorecard 分別分類。
- 傳輸/持久化：同步 screen、異步 task、history 的前端映射保留條目；screen 保存和 history_detail 讀取逐項一致。
- 頁面：混合來源逐條標註，綜合 partial 不覆蓋單條 observed/inferred；舊歷史來源 unknown；真實 0 與缺失值分離。

### 預補充證據刷新

後排名補充與 Why Now 使用相同的可用性判斷：新聞和事件必須有來源、非空標題/摘要，且發佈時間在 30 天窗口內。僅當兩類緩存均可用時跳過補充；過期、無日期或缺來源/正文的一類會單獨刷新，另一類有效緩存和已有行情/基本面繼續複用。刷新失敗保留降級告警，不把舊新聞提升為 observed；候選數上限和原搜索超時保持不變。

標題和摘要分別去除首尾空白後取值；標題缺失或僅含空白時使用有效摘要。緩存判斷與 Why Now 展示覆用同一正文取值，避免空白標題遮蔽摘要並觸發不必要的刷新。

迴歸驗證覆蓋真實 `screen()` 入口、搜索響應歸一化及 `history_detail()` 讀取：頂層或上下文中的過期/無日期新聞與事件觸發單類刷新，新證據以 observed 寫入響應和歷史；兩類緩存均有效時跳過補充並保留已有告警。

### 無理由模型排序

成功接受的 LLM 排序結果即使省略 reason/thesis（包括僅 risk、僅 code 的合法響應），仍以 llm/inferred 顯示“模型已參與排序（未提供入選理由）”，整體 Why Selected 為 partial；真實 0 分仍算模型輸入。風險文本只保留在風險區，失敗後回退的純因子結果不添加模型參與項。

迴歸驗證使用雙候選實際重排，覆蓋缺省分數、零分及 risk-only 響應；重排後每個候選的本地加權因子保持 observed，模型參與項保持 inferred，重複歸一化後綜合質量仍為 partial。

### 瀏覽器測試入口隔離

`npm run test:smoke` 使用默認 `playwright.config.ts`，明確排除 `e2e/fixtures/`；未設置 `DSA_WEB_SMOKE_PASSWORD` 時繼續跳過需要登錄的 smoke，不啟動後端/Web 服務。選股的 5 個 API mock fixture 僅通過 `npx playwright test --config playwright.fixture.config.ts` 運行，該配置獨立啟動 Web 服務，不需要密碼或後端。CI 同時執行無密碼默認入口與專用 fixture 入口，避免僅專用配置通過掩蓋默認入口迴歸。
