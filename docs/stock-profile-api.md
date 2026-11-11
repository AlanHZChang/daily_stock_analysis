# 個股研究聚合 API

本文檔說明 Issue #2279 的後端契約階段。目標是讓後續 `/stocks/:code` 工作臺通過單一端點消費數據，而不是在瀏覽器併發拼裝行情、歷史、報告、資訊、持倉和監控接口。

## 端點

`GET /api/v1/stocks/{stock_code}/profile?history_days=60`

端點先把輸入統一為 canonical code。實時行情、歷史和報告鏈使用 canonical code；對可能由舊入口按別名持久化的 intelligence 與 monitor 記錄，讀取時會展開倉庫既有等價代碼集合並按 ID 去重：

- A 股：`SH600519`、`600519.SH` 等收斂為 `600519`。入口已經顯式攜帶 `SH` / `SZ` / `BJ` 時，後續報告、資訊和監控別名展開會持續保留該市場身份；即使股票索引存在同形日韓代碼，也不會重新按裸數字推斷為其他市場。顯式交易所與代碼規則衝突（如 `600519.SZ`）時返回 400，不會剝離交易所後查詢另一標的。
- 日股：`7203.T` 保留 Yahoo canonical suffix，並返回 `market=jp`。
- 韓股：`005930.KS`、`035720.KQ` 保留 Yahoo canonical suffix，並返回 `market=kr`；股票索引唯一識別出的舊裸代碼也沿用解析後的韓國市場身份。緩存持倉中的舊裸六位韓股在 market 已明確為 `kr` 時按解析身份與檔案 suffix 的數字主體比較，不會再次按無 market 的 A 股規則解釋。
- 臺股：profile 入口接受 4–6 位 `.TW` / `.TWO` Yahoo suffix（包括六位 ETF），並返回 `market=tw`。市場限定的資訊查詢兼容舊裸數字 scope，但 `global` 查詢繼續排除該歧義別名；緩存持倉已明確 `market=tw` 時，舊裸代碼按同市場數字主體與檔案匹配。
- 港股：`00700`、`00700.HK`、`HK00700` 收斂為 `HK00700`；緩存持倉已明確 `market=hk` 時，`700` 等舊短格式也會補零後參與身份比較。
- 美股 ticker 統一為裸大寫形式，例如 `aapl`、`AAPL.US` 都收斂為 `AAPL`；持久化讀取仍查詢裸 ticker 與 `.US` 等價別名。

響應包含 `quote`、`history`、`research`、`intelligence`、`portfolio`、`monitors` 六個獨立塊，以及頂層 `evidence_quality` 彙總。每個塊的 `status` 只允許：

| 狀態 | 語義 |
| --- | --- |
| `fresh` | 本次請求成功取得可用數據；不代表所有外部來源具有同一時區或刷新頻率 |
| `partial` | 核心信息仍可用，但存在明確限制，例如只有報告列表、缺少詳情，或持倉關係只來自緩存 |
| `unavailable` | 本次沒有可用數據；原因以穩定的 `limitations` code 返回，不暴露原始異常或密鑰 |

任一可選塊失敗不會讓其他塊消失。例如 quote 失敗時，歷史報告、結構化 ResearchArtifact、symbol intelligence 和監控規則仍可返回；最新報告詳情失敗時，`research.recent_reports` 仍保留，`structured_report` 為 `null` 並標記 `latest_report_detail_unavailable`。

## 數據來源與邊界

- quote/history：複用 `StockService`，不新增數據獲取器。
- research：複用 `HistoryService` 和 #2291 的 `ResearchArtifact` builder。報告查詢把檔案入口已經解析出的 market hint 傳到 `HistoryService` 的候選生成層：只保留能在無提示解析時仍確認屬於當前市場的裸數字別名；例如 `600519` 可繼續兼容 A 股舊記錄，`005930` 可兼容已唯一登記為韓股的舊報告，而與韓股同形的顯式 A 股 `SZ000660` 不會查詢裸 `000660`。日韓臺查詢保留交易所後綴及其他已確認同市場的舊裸數字代碼，但不展開可能命中其他市場歷史記錄的別名；市場限定後候選為空時直接返回空分頁，不會退化成無過濾查詢。artifact 同時複用歷史詳情的上下文、raw result 和獨立基本面快照 fallback，保留財報、分紅與市場結構專項證據及其 source count。
- service 導入邊界：`api.v1` 的 router 改為延遲導出，因此 `StockProfileService -> ResearchArtifact schema` 不會反向觸發全部 API endpoints。CLI、獨立腳本和單元測試可在沒有預先導入 `api.app` 的情況下直接導入 profile service。
- intelligence：複用 `IntelligenceService` 的 symbol scope 查詢，併兼容 canonical、交易所前後綴、港股前後綴、混合大小寫及日韓臺市場限定的裸數字歷史別名；無法無提示解析回當前市場的歧義裸碼不會進入 `global` 查詢。查詢別名按 casefold identity 去重，由 repository 的 symbol-only 不區分大小寫過濾兼容歷史大小寫，避免重複 count/select。任一別名/市場查詢失敗時塊保持 partial limitation，即使其餘查詢成功但為空，也不誤報為已確認無資訊。
- portfolio：只讀 `PortfolioRepository.list_cached_position_identities()`，並使用每條緩存持倉自己的 market 解析舊裸代碼；只有 market 與檔案身份一致時才算持有。不為了打開個股頁觸發實時估值或寫 snapshot，所以狀態固定為 `partial` 幷包含 `cached_positions_only`。
- monitors：複用 `AlertService.list_rules()`，以不區分大小寫的 symbol 過濾分頁彙總並去重 canonical code 及等價歷史別名下的 `single_symbol` 規則。由於現有告警目標沒有獨立 market 字段，日韓臺檔案不會查詢可能與 A/HK 同形的裸數字別名，避免跨市場規則誤歸屬。

本階段不新增 Web 路由/頁面、不接線 Home/Watchlist/Screening/Portfolio/Report 入口，也不包含日曆事件。後續 Web PR 必須消費本端點並分別渲染塊狀態；不得重新恢復多請求頁面聚合。日曆事件在 #2307 契約合入後再作為獨立塊擴展。

## 回滾

Revert 本 PR 即可移除 profile schema、service、endpoint、測試和文檔。沒有數據庫遷移、配置變更或數據清理步驟。
