# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

> For user-friendly release highlights, see the [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases) page.

## [Unreleased]

- [改进] 將全儲存庫的中文文案、註解及文件統一為繁體中文，同步調整顯示文案的測試預期；保留資料欄位、訊號值、解析標記及外部介面契約，維持程式邏輯不變。

- [改进] 將 `src/` 的簡體中文註解、說明、日誌與顯示文案轉為繁體中文；保留參與解析、比對、列舉、資料欄位及外部查詢的原始字串，以維持既有邏輯與相容性。

- [文档] 恢復 README、部署指南及模型/搜索配置表中的 Anspire 可點擊鏈接並保留推廣碼，繼續作為 SerpAPI 後的可選搜索服務。

- [改进] 下線 Anspire 合作宣傳及專屬額度說明，移除 README 推薦入口，調整配置示例和渠道展示順序；新聞搜索順序調整至 SerpAPI 之後，保留原推廣碼鏈接、已有 Key 和模型渠道兼容。

- [修复] Agent 工具消息內容與工具調用參數序列化不再透傳 NaN/±Infinity：`LLMToolAdapter._convert_messages` 序列化前將非有限浮點遞歸歸一化為 `null`，並以 `allow_nan=False` 輸出嚴格 RFC 8259 JSON，避免 LiteLLM 以 `"NaN" is not valid JSON` 拒絕請求（#2471）。

- [修复] 啟動日誌不再對 `--stocks` / `--portfolio` / `--no-notify` 已覆蓋的配置項告警；單一日線數據源失敗（含 Eastmoney 股票與 ETF 請求）降為 WARNING，普通股票及 A 股指數全部日線數據源失敗仍為 ERROR；LLM 返回與調試日誌顯示實際響應模型（含流式響應），依據實際調用路由標註回退，避免將別名、供應商前綴和日期版本差異誤報為回退
- [文档] 修正 DeepSeek 默認模型說明，明確 Gemini API 與 Vertex AI 的模型生命週期及驗證邊界。
- [修复] 深度研究合成階段預算增至受剩餘整體預算限制的 120 秒；階段/provider 超時保留階段、實際耗時與原始原因，研究 API 不再誤報整體預算耗盡或清零已知 token 用量（#2475）。

- [改进] 更新默認模型：Gemini 主模型 `gemini-3.6-flash`、備用 `gemini-3.5-flash-lite`，選股默認同步；OpenAI 默認 `gpt-6.1-sol`（選股與 PR 審查兜底同步，不再回落到 `gpt-4o-mini`）；僅配置 `DEEPSEEK_API_KEY` 時默認 `deepseek-v4-flash`。未顯式配置模型的用戶將自動切換，顯式配置不受影響
- [修复] GPT-6 系列請求時省略 `temperature`，與 GPT-5 / o 系列一致，避免服務端拒絕非默認採樣參數
- [修复] Anthropic 已退役 `claude-3-5-sonnet-20241022` / `claude-3-7-sonnet-20250219`：GitHub Actions 默認 `ANTHROPIC_MODEL` 與 LiteLLM 配置示例改為 `claude-sonnet-4-6`。該模型默認不啟用 thinking，仍接受 `temperature` 與指定 `tool_choice`，現有請求參數與 Agent 工具往返無需調整；已通過 `ANTHROPIC_MODEL` Variable / Secret 顯式配置舊模型的用戶需手動更新。
- [修复] 依賴鎖定 `akshare<1.20.0`，避免上游目錄與 HTTP 層重構導致 CI 與桌面打包失敗；Python 3.10 新裝限制 `litellm<1.98.0`，修復 `NotRequired` 導入錯誤
- [修复] 自選及其他無關配置保存不再被已有 LLM 渠道或模型錯誤阻斷，模型相關修改仍校驗完整依賴；僅更新自選時保留運行時單例與容器環境覆蓋，並補齊增刪、刪空和校驗迴歸。凡本次保存會啟用 Agent 路徑的，同樣校驗完整模型依賴：切到 LiteLLM Agent 後端（`AGENT_BACKEND` / `AGENT_GENERATION_BACKEND` 解析為 litellm）、開啟 Agent 分析（`AGENT_MODE=true`）、或配置了非 `all` 的 `AGENT_SKILLS`——後兩者走普通分析的 Agent 分支，自帶 `LLMToolAdapter`，不受 `AGENT_BACKEND` 決定。僅關閉 `AGENT_MODE`、將 `AGENT_SKILLS` 設為 `all` 或空值、以及無關鍵保存仍不受 LLM 配置影響；顯式保存或導入已退役的 `codex_app_server` 仍被拒絕。
- [改进] 移除實驗性 Codex App Server 問股後端及專屬探針、取消與啟動鏈；舊配置明確提示退役並可主動修正，保留默認 LiteLLM、會話接受事務及獨立 Codex CLI 報告。
- [修复] Agent 狀態面板在缺少可用主模型時顯示中英文配置指引，保留技術錯誤碼；配置指南明確區分已移除後端與歷史 Gate 記錄。
- [chore] Default new MiniMax channels to MiniMax-M3.1-Flash and MiniMax-M3, filter older text recommendations while retaining saved/custom models, and refresh fallback pricing.

<!-- 新條目格式：- [類型] 描述（類型取值：新功能/改进/修复/文档/测试/chore）-->
<!-- 每條獨立一行追加到本段末尾，無需分類標題，合併時衝突最小 -->
- [新功能] 新增可選的 fastapi-guard 安全中間件（`GUARD_ENABLED=true`，默認關閉）：按 IP 限流、IP 白/黑名單、請求特徵攔截與掃描器自動封禁，與登錄失敗限流疊加；客戶端 IP 取值與 `TRUST_X_FORWARDED_FOR` 保持一致，啟用後內置啟動入口的 Uvicorn 代理頭處理只信任同一組代理，默認不掃描請求體，詳見 `docs/full-guide.md`。
- [修复] Telegram 推送按 UTF-16 長度判斷與分段，修復含大量 emoji 的報告超出 4096 限制導致發送失敗的問題。

- [新功能] 定時模式啟動立即執行的當日去重（`SCHEDULE_STARTUP_DEDUP`，默認開啟）：`python main.py --schedule` 在 `SCHEDULE_RUN_IMMEDIATELY=true` 觸發啟動補跑前檢查標記文件（位於 `DATABASE_PATH` 所在目錄，默認 `data/analysis_run_state.json`），當天已有成功且覆蓋當前應分析清單的全量分析（日期 + scope=full + 覆蓋面子集判定）則跳過，否則照常補跑；每日定時任務與手動/API/GitHub Actions 觸發永不去重；標記缺失、損壞、schema 未知或覆蓋不全一律 fail-open 執行（絕不漏跑）；大盤覆盤完成度僅記錄、不參與判定（覆盤補齊由每日定時任務覆蓋）；設 `SCHEDULE_STARTUP_DEDUP=false` 可回到此前"每次容器重啟都全量重跑"的行為；`--force-run` 可繞過啟動去重檢查（明確要求立即全量分析）。
- [修复] Web 設置-數據源 中 Futu OpenD 地址/端口、妙想（MX_API）API Key 與妙想數據源優先級四項缺失中文文案，回退顯示英文標題與說明的問題。
- [修复] 港股實時數據源優先級（`FUTU_HK_REALTIME_SOURCE_PRIORITY`）的中文名稱與說明改由前端維護，後端註冊表恢復英文文案，英文界面不再顯示中文。
- [改进] Web 設置-數據源 配置項排序收斂：通用配置置頂（股票索引遠程更新、盤中實時技術面、啟用實時行情、啟用籌碼分佈分析、實時數據源優先級、新聞最大時效、新聞策略窗口檔位、BIAS 閾值），同一廠商的配置項連續排列（TickFlow、Futu、妙想、SearXNG 等），廠商之間的相對順序保持不變。
- [修复] 收緊定時模式啟動去重：僅當全部應分析標的都成功時才記錄當日標記（部分失敗或全敗、即使大盤覆盤成功也不得記錄，避免重啟漏跑）；跳過判定改為覆蓋面子集校驗並升版 schema 2（v1 舊標記一律 fail-open 重跑一次以升級），`SCHEDULE_STARTUP_DEDUP` 進程環境變量與 .env 值不同時以進程為準（與 `SCHEDULE_RUN_IMMEDIATELY` 同權）。
- [修复] 定時模式啟動去重檢查的預期清單改為與運行入口一致的真實目標解析鏈（Futu 持倉優先、其次 .env 熱更新 `STOCK_LIST`、再按交易日過濾）：`--portfolio futu` 新增持倉、純持倉部署自選為空、以及進程 env 啟動後 .env 熱更新三類場景不再誤跳過；持倉解析失敗或解析為空一律 fail-open 照常執行（絕不漏跑），非持倉空清單保持既有當日去重語義。

- [文档] 文檔中心補充 `market-support.md` 入口，與 README / 完整指南的市場支持鏈接保持一致。
- [修复] 美股社交輿情 Reddit 個股端點切換至現行 Adanos 契約 `/reddit/stocks/v1/stock/{ticker}`（舊 `/reddit/stocks/v1/report/{ticker}` 已下線、固定 404，導致 Reddit 段落始終顯示無數據）；適配官方契約 200+`found=false` 無數據語義：`get_social_context` 在證據登記前將空報告歸一化為平臺無數據，三源全空返回 `None` 且不再誤置 `news_evidence_present`（X/Polymarket 有數據時貢獻保留）；mention 正文按 `text_snippet`→`text`→`title` 回退，日線情緒 `sentiment_score` 優先且保留真實零值，舊字段 `avg_sentiment` 兼容回退（#2448）。
- [修复] Futu OpenD 未運行或協議未就緒時，FutuFetcher 改為異步連接並最多等待 5 秒，失敗後關閉連接、只記錄一條警告並在 5 分鐘內跳過 Futu，港股請求回退到其他數據源，不再因 SDK 同步構造無限重連而卡住整輪分析（#2447）。
- [改进] 持倉風險的板塊集中度按股票代碼在進程內緩存所屬板塊 24 小時（僅緩存成功結果），重複打開或刷新持倉頁時不再對每隻 A 股持倉重新經過數據源限速請求；此前多隻持倉時每次加載風險模塊都要等待數十秒，容易觸發前端 30 秒超時降級（Refs #1945）。
- [修复] 大盤 Market Light 評分和中英文指數均值排除 VIX 波動率漲跌幅，保留原始行情展示；僅有 VIX 時指數維度標為不可用，告警沿用跳過語義（#2472）。

- [改进] Agent 軌跡評估增加獨立股票範圍診斷與干擾股票樣例，區分越界請求、運行時攔截和無法判定調用，支持多股對比及階段明細，不改變原指標或退出碼。

## [3.33.0] - 2026-10-15

### 發佈亮點

- feat: 問股討論對象由服務端保存，刷新、重開及 Bot/Web 交替使用可恢復；修復完整股票名稱被內部短別名誤判的問題。
- feat: 新增規則化 ETF 雙動量輪動，提供最新調倉信號、扣成本回測、年度對比及數據質量告警，無需 LLM。
- feat: Web 新增只讀數據中心和持倉風險與暴露看板，自選股列表提供“變化 / 狀態 / 下一步”提示。
- feat: 選股提供帶來源與質量狀態的入選理由和時點證據，補齊新聞事件，並修復日線新鮮度、交易日期及緩存降級判斷。
- feat: 簡化 Modelflare 單 Key 配置，補充已合入的 Requesty 渠道、妙想籌碼與資金流數據及 FXMacroData 宏觀工具。
- fix: 修復基本面與資金流解析、科創板成交量單位、重複定時派發和桌面 MiniRacer 資源打包；調度超時可推送已完成的部分結果。

### 新功能

- 問股由服務端保存已確認的主討論對象，刷新、重開和會話切換可恢復；Bot/Web 交替問股共享已確認對象，保留股票/指數、跨市場身份及嚴格工具範圍（#2397、#2406）。
- 新增 `python main.py --etf-rotation` 規則化 ETF 雙動量輪動，輸出最新調倉信號、扣成本回測、分年度對比、參數平原檢驗和數據質量告警；不調用 LLM，配置與數據邊界見 [ETF 輪動](etf-rotation.md)（#2376）。
- Web 新增只讀數據中心，展示 Provider 能力、數據集質量和運行時優先級，不展示 API Key 或原始配置值；短窗口中的導航列表可滾動，並保留主題、語言與退出控件（#2304）。
- Web 持倉頁新增風險與暴露看板，聚合個股/行業集中度、回撤、止損、AI 信號、價格質量、市場及幣種暴露（#2297）。
- 選股候選新增後端生成的 Why Selected / Why Now 解釋、來源與質量狀態；保留模型 reason/thesis 和逐條 provenance，區分真實零值與缺失佔位值，舊歷史不重新評分或回寫（#2305）。
- 新增 `/api/v1/screening/screen/check`，對調用方提供的單條快照解釋策略硬過濾條件、閾值、當前值及通過/失敗/缺失狀態，不抓取行情、不調用模型、不改變既有選股結果（#2382）。
- 新增單票決策信號覆盤只讀接口 `GET /api/v1/decision-signals/stocks/{stock_code}/review`，返回樣本量、命中率、常見 miss 原因和置信度調整方向；啟用 `AGENT_MEMORY_ENABLED` 時作為獨立記憶段注入，樣本不足或數據質量弱時僅供觀察（#2331）。
- 新增妙想補充數據源 `MX_APIKEY` / `MX_PRIORITY`，用於籌碼分佈和個股資金流降級，接入 Web 配置與每日 Actions；不提供日線能力，調用受剩餘階段預算和跨實例非阻塞准入約束（#2387、#2388）。
- Agent 新增 FXMacroData 官方宏觀數據工具，USD 基礎數據無需密鑰；每日 Actions 映射可選 `FXMACRODATA_API_KEY`，Windows/macOS 凍結產物收集操作目錄並校驗工具註冊（#2336）。
- 新增 Requesty 聚合網關預設，補齊 Web、環境示例、Actions 的 `LLM_REQUESTY_*` 映射與配置說明；模型發現返回的 vendor/model ID 保留 OpenAI-compatible 網關路由（#2367）。

### 改進

- Modelflare 支持只配置 `MODELFLARE_KEY`，後端、Web、選股及 Actions 自動識別渠道並補齊默認地址和模型；單渠道未聲明模型時可複用主模型與 OpenAI 備用模型，否則使用默認模型，顯式 YAML、模型列表和多渠道規則保持優先（#2403）。
- 模型設置預覽、連接測試及保存失敗時顯示具體字段與修正提示；Modelflare 預設提供條件註冊鏈接和說明，同步簡化三語 README 贊助區並使用對應語言橫幅（#2403、#2407）。
- Web 自選股新增“變化 / 狀態 / 下一步”信號，結合今日分析、歷史報告、運行任務和詳情狀態提示操作；“僅未分析”排除運行中任務，兼容股票/指數身份（#2293）。
- Web 始終保留選股導航，未開啟時提供開啟提示；狀態加載失敗可重試，不誤報功能未開啟，也不自動啟用或提交任務（#2392）。
- 選股 LLM 重排前按候選上限補充新聞與事件，保留來源、發佈時間和檢索時間，隔離不可信資料與排序指令；長度預算包含 system 消息和重試提示，同次運行復用查詢，缺失/失敗不視為無風險（#2390）。
- 研究與搜索證據保留來源觀測和實際檢索完成時間，在歸一化、時效過濾、排序及緩存中持續傳遞；緩存命中不刷新檢索時間，沒有明確時效證據時保持 unknown（#2381、#2390）。
- 新增意圖解析器基礎模塊，支持二維任務組、多意圖解析、跨市場候選消歧、LLM 兜底及確認狀態簿記；本版本尚未將其接入 Web SSE 執行入口（#2385）。
- Multi-Agent 軌跡評估增加階段快照、階段本地工具指標、局部/累計步數及完成/失敗/跳過狀態；頂層步數由階段快照累計，單 Agent 既有指標保持兼容（#2351）。

### 修復

- 問股將完整註冊名稱視為一個標的，避免“長電科技”中的“長電”或“京東方A”中的代碼片段觸發錯誤澄清；獨立別名、跨市場同名和名稱/代碼真正衝突仍沿用確認規則（#2406）。
- 問股實時請求與舊歷史恢復共用對象決策，正確處理明確切股、重複輸入、普通追問、比較、否定、條件句及引用；工具和緩存保留股票/指數及跨市場身份，防止同碼誤讀與模型名稱改變新聞目標（#2397）。
- 問股接受事務統一保存消息、顯式 Skill 和對象狀態，校驗會話實例、版本及用戶錨點；遲到列表、摘要或回覆不覆蓋新狀態，比較或執行失敗不改寫已確認對象，顯式空 Skill 保留默認執行語義（#2397）。
- 嚴格回測按已驗證身份和關聯分析來源查詢，兼容正常 CN 寫入器的數字鍵及同身份存儲別名，保持跨市場隔離、總數與分頁一致性（#2397）。
- Codex 問股向最終請求傳遞當前交易 Skill 指令，保留會話繼承、顯式清空及默認技能語義；能力邊界限定於三個已保存數據工具，缺失數據或能力時明確披露（#2371）。
- ETF 輪動按真實 A 股交易日曆保留全池缺報價日及尾部缺口，防止調倉順延或信號提前；缺價不虛構成交，報價恢復後計入完整持倉損益，防守資產不可買入時保留現金；日曆不可用時停止計算，主回測與參數掃描共用前復權行情（#2376）。
- 選股日線核驗交易日期、有效收盤價及收盤時段，拒絕休市/未來日期、非法日期與盤前佔位行情；緩存使用持久化獲取時間，無時區舊時間回退文件 mtime，避免跨時區或桌面恢復誤判新鮮度（#2389）。
- 選股全源陳舊時優先保留最新合法日線，同日保留來源優先級；比較 DSA、備用來源及文件緩存，不以陳舊/非法結果覆蓋 last-good，完整傳遞各來源錯誤和健康狀態以參與質量評分（#2389）。
- 選股來源僅在行情通過日期驗證後記錄成功，非法響應參與既有熔斷和恢復；yfinance 按美東日期推進排他的 end 邊界，避免收盤後漏取當日 K 線（#2389）。
- 選股響應和歷史保留當次實際因子權重（含零值），無候選時也不使用策略目錄原始或後續變更權重補填；入選解釋仍只消費正權重（#2389）。
- 選股時點證據與預補充共用時效和來源校驗，按新聞/事件分別刷新無效緩存，有效摘要可用於 Why Now；失敗保持 unknown 和告警，無理由或僅 thesis 的 LLM 結果仍保留 inferred 標記、真實重排與風險說明（#2390、#2305）。
- 選股後分析器完成非零調分卻未給出有效摘要時，仍保留來源、質量、完成狀態及分差；模型理由、本地因子和各後分析來源可同時保存在響應與歷史中（#2305）。
- Web 設置保護普通配置、模型渠道及調度未保存草稿，重置/成功導入清理舊草稿，保存及導入期間防止編輯與離開競態；登錄後保留安全站內目標及 query/hash，首次引導可滾動聚焦 `STOCK_LIST`（#2386、#2399）。
- 持倉看板缺價、過期匯率、異常估值或行業分類覆蓋不足時保持不可用，不展示誤導的集中度、權重或餅圖；兼容舍入後的零權重尾行，並正確聚合混合幣種和零市值賬戶（#2297）。
- 妙想按明確金額指標選表選列並規範列表型 nameMap，避免價格/佔比被當成資金流金額；缺失值保留在交易日窗口中，超時任務結束前抑制重複請求，避免排隊消耗額度（#2387、#2388）。
- AkShare 基本面、資金流及龍虎榜超時後按操作跨管理器抑制重複後臺請求；大盤統計降級調用使用可終止子進程超時，診斷耗時按實際等待記錄，避免線程拒絕或超時虛報完整預算（#2345、#2372、#2380）。
- 基本面按明確報告期與目標股票讀取業績預告、快報、機構持股和十大股東，修正市場代碼；財務寬表按最新報告期與真實指標解析，補齊新浪收入/利潤增長、ROE、經營現金流別名，不跨報告期補值或把空結果標成功（#2362、#2370、#2373）。
- yfinance 財報同比按日期匹配去年同季度，缺同期時回退 info 同比，避免固定行偏移把更早季度誤當作去年同期（#2365）。
- 騰訊科創板（688/689）日線成交量按“股”保留，不再統一乘以 100；存量數據修正要求見下方升級注意事項（#2360，Fixes #2350）。
- `REPORT_LANGUAGE=en` 使用完整英文 system/user 模板，`ko` 複用英文骨架並保留韓文指令；JSON 鍵名、枚舉和解析契約保持不變，中文模板不變（#2368）。
- CLI 與 Web/API 每日調度共享 SQLite 計劃時刻認領，避免同一數據庫上的併發或錯峰重複派發；不同時間/分析範圍及手動補跑獨立執行，認領後失敗不會自動重派（#2379）。
- Web/API 調度硬超時後記錄已完成/待完成摘要，並可推送已落庫的部分結果；默認通知行為及關閉方式見下方（#2338）。
- 告警列表披露有效環境規則和去重後數量，明確頁面刪除/禁用不停止環境規則；來源統計只讀且請求內複用，不查實時行情或改寫持倉快照；規則變更後的刷新保留當前篩選和分頁（#2374、#2378）。
- Windows/macOS 桌面後端完整收集 MiniRacer 原生運行文件並實際執行 JavaScript 檢查；macOS 補齊選股策略 YAML 資源及 Bash 參數構造校驗（#2361、#2384）。
- 智能導入兼容帶 UTF-8 BOM 的 CSV 與剪貼板文本，避免表頭誤判或有效代碼丟失；默認 Web smoke 排除獨立 fixture，避免錯誤收集需特定環境的用例（#2333、#2390）。

### 升級注意事項

- **默認行為變化**：Web/API 調度硬超時後，`DSA_TIMEOUT_PARTIAL_NOTIFY` 默認開啟，可能新增部分完成通知；設為 `false` 可關閉。該能力不保證通知送達，也不會自動重試已認領的整輪任務。
- **歷史行情**：科創板成交量修復不自動重寫已有數據；修正舊記錄時須限定 `data_source = 'TencentFetcher'` 及受影響的 688/689 股票，不能統一調整其他來源或市場。
- **會話升級與回滾**：升級前備份數據庫及配置；回滾時先停止新後端，保留新增可空列與數據庫版本默認值，不刪列或重建數據庫，避免舊新寫入後端並行。舊版寫入後再次升級需重新確認討論對象，已有消息及 Skill 保留，詳見 [問股事件與回滾邊界](agent-stream-events.md#rollback)。
- **功能範圍**：新意圖解析器仍為基礎模塊，尚未接入 Web SSE 執行入口；CLI 啟動分析行為保持現狀。ETF 輪動及可選數據/模型渠道按各自配置啟用。

### 測試與文檔

- 補充真實索引下完整名稱、HTTP/SSE、會話恢復與重複確認迴歸；意圖解析器覆蓋任務切分、確認消費、LLM 結果校驗及狀態簿記。
- 補充選股新鮮度、備用來源、緩存、檢索時間、真實重排及響應/歷史一致性驗證，保留風險與缺失數據反例。
- 告警來源和頁面交互採用無後臺、無密鑰的確定性瀏覽器驗收，CI 保存桌面與窄屏證據；修復名稱解析冷啟動併發測試競態。
- 同步模型、數據源、ETF 輪動、數據中心、問股升級/回滾及桌面指南，更新三語贊助說明和 SerpAPI 鏈接，修復文檔錨點。

## [3.32.0] - 2026-09-06

### 發佈亮點

- feat: 已登記 A 股指數貫通 Web/API、Bot、CLI 與 GitHub Actions 分析入口，註冊表擴展至 33 項，並統一指數身份、任務去重、歷史與 Chat 上下文。
- feat: 新增個股研究聚合 API、ResearchArtifact 結構化研究產物，以及數據源能力與數據集質量只讀接口。
- feat: 完善 Futu OpenD 港股數據源接入，新增 Web Chat 分詞基礎模塊與 Agent 軌跡評估入口。
- feat: 自建 SearXNG 搜索超時可配置，Tavily 改用 basic 搜索以降低 credit 消耗。
- fix: 定時分析採用獨立進程與硬超時保護，選股結果支持歷史恢復，桌面端增加全局更新入口，並修復 Linux/Docker 分享圖中韓文字體缺失。
- fix: 收斂 LiteLLM 兼容版本窗口，更新 Web/桌面依賴，並修復美股數據源優先級與股票名稱歸一問題。

### 變更明細

- [修复] 入口分類的模式邊界修復（PR3 review）：不消費個股列表的模式（`--backtest`/`--market-review`/`--serve-only`/`--webui-only`/`--portfolio`/`--schedule`/`config.schedule_enabled`）在模式分發前整體跳過 `--stocks` 與 GitHub Actions `STOCK_LIST` 的分類與索引刷新，未登記 `.CSI` 等壞 token 不再攔截這些模式（此前 `GITHUB_ACTIONS=true` 下 `--backtest`、`--portfolio futu`、`--schedule` 配壞 watchlist 會在進入模式主體前被整批拒絕）；`--schedule --stocks` 的"警告後忽略啟動快照"語義保留；`--stocks` 與 GitHub Actions 入口的指數分類與整批拒絕契約不迴歸，文檔同步把指數自選股配置收窄為僅這兩類入口（本地 `.env`/Docker 無參數默認運行保持股票語義，分析指數請配 `--stocks`）。
- [新功能] 指數註冊表新增國證糧食（`sz399365`）與中證鋼鐵（`csi930606`）：已登記 seed（`scripts/stock_index_seeds/index_registry.csv`）與 bundled 指數清單（`apps/dsa-web/public/stocks.index.json`）由 31 項擴展到 33 項，已登記指數的 `sh`/`sz`/`csi` 前綴與 `.SH`/`.SZ`/`.CSI` 顯式形態均可作為自選股指數目標；ETF 與美股指數不進 CN 註冊表，路由語義不變。
- [文档] 中英 full-guide 新增「指數自選股配置」小節：說明已登記指數前綴/顯式後綴規則、未登記 `.CSI` 整批拒絕、裸碼不自動提升為指數、NDX 等美股指數裸碼即正確路由、ETF 走股票路徑，並同步補充 README / DEPLOY 的 `STOCK_LIST` 提示；修正 full-guide 中已過期的「已登記 5 個滬深指數」表述。
- [新功能] GitHub Actions 每日工作流支持已登記指數入口：`GITHUB_ACTIONS=true` 下無參數 `python main.py` 把 `STOCK_LIST` 按與一次性 `--stocks` 相同的判型規則分類為結構化 target（顯式指數 token 進入指數路徑、個股 token 保持既有 legacy 路徑），指數與個股同批覆用同一 Pipeline，不新增第二條能力矩陣；本地與 `--schedule` 熱刷新默認路徑不在入口構造 target，語義不變。
- [修复] `main.py --stocks` 對未登記 `.CSI` 目標在入口明確報錯並整批拒絕本輪運行（此前被靜默按股票 token 交給 provider），拒絕發生在任何 provider 請求之前，與 API 層"provider 調用前明確拒絕"的邊界對齊；CLI/Actions 整批拒絕與 API 異步批量僅拒絕該目標的差異已在文檔中說明。
- [测试] 新增 Bot 指數入口 transport-independent 在線 E2E smoke（`scripts/smoke_bot_index_entry.py`）：worker 子進程經真實 `CommandDispatcher.dispatch_async` 提交併在同進程輪詢 `TaskService` 貫穿到 `StockAnalysisPipeline`，父進程只負責 deadline、進程樹清理（Windows `taskkill /T /F`、POSIX 殺進程組）與退出碼（0=成功/1=失敗/124=超時），輸出單行 `E2E_EVENT {json}` 事件（`phase=submitted|completed|failed|timeout`）；smoke 覆蓋 `SH.000016`/`上证50`/`930955.CSI` 矩陣，期望 code/name 取腳本內置權威映射（不信任響應/結果自報身份，提交 code mismatch 輸出含期望值與實際值的顯式錯誤並攜帶結構化實際 `stock_code`，dispatcher 路由錯誤也失敗），矩陣外 target 與非正 `--timeout` 在提交與 spawn 之前即被拒絕（退出碼 2），completed 須 exact canonical code、exact 註冊名稱且 `analysis_summary`/`operation_advice`/`trend_prediction` 非空（僅空白視為空），失敗或結果不完整即非零退出；超時清理進程樹（Windows `taskkill /T /F`、POSIX 殺進程組），清理成功輸出 `timeout` 事件並退出 124、清理失敗輸出含清理錯誤的 `failed` 事件並退出 1，不回滾 DB/報告/通知副作用；用戶 Ctrl-C 中止時父進程同樣先清理進程樹，清理成功透傳中斷、清理失敗輸出含清理錯誤的 `failed` 事件並退出 1，絕不靜默吞掉清理失敗；worker 意外異常輸出 `failed` 事件並退出 1（stderr 保留異常證據，`KeyboardInterrupt` 不按普通失敗處理），父進程將 worker 任意其他退出碼歸一化為 1（運行時契約只暴露 0/1/124）；父進程以內部 `--worker` flag 顯式拉起子進程（不依賴環境變量，防外部預置繞過硬超時）；不 mock 在線依賴、不 dry-run、不修 transport，不加入離線 gate。
- [新功能] Bot `/analyze` 支持已登記指數入口：顯式代碼（`sh000016`）、CSI alias（`930955.CSI` 收斂為 `csi930955`）與註冊中文名（`上证50`）均可提交，指數以結構化 `AnalysisTarget` 經 `TaskService` 貫穿到 Pipeline `process_single_stock`（`sh000016` 不再被改寫為 `SH000016`）；註冊名稱查詢獨立於 parser identity alias（中文名不進入 `find_by_explicit_key`/`parse_analysis_target`），同名歧義返回明確錯誤並要求顯式代碼，未登記 CSI 與未知名稱返回明確錯誤且不提交任務；個股代碼（A/HK/US）保持既有 legacy code 路徑不變，股票名稱輸入（如 `贵州茅台`）由本次 Bot 入口新暴露——複用既有名稱解析器（`resolve_name_to_code`）解析後提交 legacy code，不攜帶結構化 target；提交成功響應在 `BotResponse.extra` 暴露內部任務 identity（`task_id`/`stock_code`）供在線驗收等內部流程使用，文本與錯誤路徑不變、平臺適配器可忽略 `extra`。
- [新功能] 新增最小 Agent 軌跡評估入口 `evals/agent_trajectory/`(Refs #1956):純函數指標層只消費真實 `tool_calls_log + AgentResult`,凍結最小指標契約(工具命中、冗餘/緩存、失敗/重試、總步數/max_steps),`run_eval.py` 經 `build_agent_executor` 真實執行並輸出文本摘要 + 結構化 JSON 報告;評估為 reporter 非 gate,零 `src/` 改動

- [修复] 將 litellm 依賴窗口上界收斂到 `<1.99.0`：1.99.0 起把 `prompt_cache_key` 透傳給 OpenAI provider，破壞 provider 緩存測試對不透傳行為的既有斷言（CI backend-tests 3/3 與 backend-gate 失敗）；保留歷史最低版本與 `!=1.82.7`/`!=1.82.8` 事故排除，同時同步更新各 LLM 兼容文檔中寫死的依賴約束表述，避免文檔與 requirements.txt 漂移

- [新功能] 新增 `SEARXNG_TIMEOUT_SECONDS` 配置自建 SearXNG 單次搜索超時（默認 10 秒），已接線全部 SearchService 構造入口（含題材搜索子進程重建）與默認 GitHub Actions 工作流

- [修复] 美股日線路由現按各數據源當前優先級排序，單項 `*_PRIORITY` 配置（如 `YFINANCE_PRIORITY=0`）對美股即時生效；指數固定首選與 Longbridge preferred 語義保持不變

- [新功能] 新增個股研究聚合 API，以統一 canonical code 返回行情、歷史、研究產物、資訊、緩存持倉關係和監控規則，並對每個塊獨立標記 fresh/partial/unavailable。
- [修复] 個股研究聚合拒絕交易所衝突的股票身份，在市場限定後無歷史候選時保持空結果，兼容市場限定裸碼與混合大小寫舊數據，並從獨立基本面快照補齊 ResearchArtifact 的財報與分紅證據。

- [新功能] 支持通過 `main.py --stocks` 一次性分析已登記板塊指數，自動使用指數適用的數據與分析能力，並保持報告、歷史和決策信號兼容。
- [修复] `main.py --stocks` 在解析股票列表前先 best-effort 刷新股票索引註冊表，保證首次運行能吃到刷新後的指數 alias/身份；刷新失敗、超時或禁用不阻斷分析。
- [修复] 交易日過濾對市場未知的指數 code（如 `sh000016`/`csi930955`/`930955.CSI`）按 `market=cn` 參與 A 股休市過濾，避免休市日指數被 fail-open 保留；市場仍未知的非指數 code 繼續保留。
- [修复] 指數分析將實際命中的日線數據源歸因保存到歷史記錄，並由 Dashboard/Brief aggregate 報告展示；來源無效時保持原有輸出。
- [文档] 在中英繁 README 頂部關聯 DSA arXiv 論文，並新增 `CITATION.cff` 統一項目引用信息。
- [新功能] 新增數據源能力與數據集質量只讀契約，提供 `/api/v1/data/overview` 和 `/api/v1/data/capabilities`，為大盤看板、數據中心、個股詳情和自選 2.0 統一暴露 provider capability、dataset quality 和 source priority。
- [修复] 統一美股指數實時行情與數據能力概覽為 YFinance-only 路由，避免 YFinance 失敗後誤用 Longbridge fallback。
- [改进] PR CI 增加文檔路徑檢測：僅修改普通文檔、非治理 Markdown 或 LICENSE 時跳過後端測試分片、Docker、Web 與桌面打包，保留輕量治理和門禁彙總；契約文檔、靜態 API 規格與測試 fixture 仍執行後端迴歸。
- [新功能] 新增 ResearchArtifact 結構化研究產物契約，在 `AnalysisReport.structured_report` 中承載 Thesis、Evidence、Invalidation Conditions、Next Actions 和 Data Quality，並提供從現有報告生成結構化產物的後端 helper 與 Web 類型。
- [修复] 同步 ResearchArtifact 與 `AnalysisReport.structured_report` 到靜態 OpenAPI，避免公開 API 規格與運行時契約漂移。
- [修复] Linux/Docker 分享圖補齊 Noto CJK 字體與中韓文字體棧，避免 PNG 只顯示數字和英文、中文或韓文內容消失。
- [修复] 股票名稱歸一：AkShare 部分名稱帶無意義內嵌空格（“五 糧 液”、“萬  科Ａ”）與全角寬度拼寫（“京東方Ａ” 的全角 Ａ），統一經 `_normalize_stock_name()` 做 NFKC 寬度歸一 + 去空白（原 `_compact_stock_name` 僅去空白）：本地映射初值、`_build_name_map_from_df()` 構建與 `extend_AkShare()` 合併、磁盤緩存加載三個入庫口（含歸一後為空的條目守衛）與 `resolver_name_to_code_list()` / `is_known_stock_name()` / `resolve_name_to_code()` 三個查詢入口同源歸一；消除空格/全角拼寫與本地無空格半角拼寫比較不相等造成的假性改名別名，源形態輸入（帶空格/全角）與常規拼寫同樣可解析，覆蓋 `/analyze` API、按名稱導入與 Bot 文本解析等全部調用路徑；全角拼寫此前與分詞管道 NFKC 歸一後的半角輸入（“京東方A”）永不相等——全名精確匹配落空且會被更短庫內名誤切出錯誤實體（“京東”），歸一後半角/全角輸入產出一致、展示名統一為歸一拼寫；磁盤緩存中的歷史未歸一數據（帶空格/全角）經合併與加載入口自動歸一，無需遷移。
- [新功能] Web Chat 意圖識別層新增分詞模塊：`web_intent_tokenizer` 六步管道（多股票全名實體掃描 → 標點/空白切分 → 代碼形提取 → 市場關鍵詞 → 無歧義關鍵詞 → 殘存 gap 多策略 DFS 匹配）把用戶消息切分為攜帶語義標籤的 Token 序列；配套 `web_intent_types` 數據字典（Token 結構、Market 枚舉、21 個語義 tag、clean/extend 雙詞池與正則機器）。核心原則"寧可不做，不可做錯"：Step 1~5 只做精確匹配，Step 6 要求整段 TAG 全覆蓋（交叉驗證）才產出，未覆蓋片段保持空 tag 交下游 LLM 兜底；代碼形 token 辨認為 `stock_code`（附 code/name/market 三元組）/ `wrong_{market}_code` / `unknown_{market}_code` 三態，token 層代碼拼寫統一 canonical 歸一（a=6 位裸數字、hk=HK+5 位、us=大寫 ticker）。意圖枚舉與意圖識別結果隨後續 `web_intent_resolver` PR 引入。新增 183 個分詞單元測試。
- [新功能] 完善 Futu OpenD 港股數據源接入：系統設置支持 OpenD 地址、端口和港股實時數據源優先級，保留 Longbridge、AkShare、YFinance fallback。
- [测试] 增加 Futu 配置 schema、港股實時路由和 fallback 契約覆蓋。

- [新功能] 建立唯一、可生成、可校驗、可降級的指數身份註冊表：由 `scripts/stock_index_seeds/index_registry.csv` 的 31 項 manifest 確定性合併進 `apps/dsa-web/public/stocks.index.json`，運行時唯一真源為 JSON 中通過校驗的 `active=true`/`assetType=index` 行，移除 `stock_list_parser` 的 5 項硬編碼白名單；支持 `--index-only` 生成與字節穩定輸出。
- [新功能] 補齊顯式 SH/SZ/CSI 指數 alias 收斂與 CSI 身份：`sh000300`/`000300.SH`/`sz399300`/`399300.SZ`/`000300.CSI` 均解析到 `sh000300`，`csi930955`/`930955.CSI` 解析到 `csi930955`；未登記 `.CSI` 輸入返回 `unsupported`；裸數字恆為 stock 並僅通過 `matched_index` 暴露歧義。
- [新功能] 數據管理器按 SH/SZ/CSI 支持矩陣映射 provider symbol：CSI 僅 AkShare 支持（`csi{code}`），Tencent/TickFlow/Yahoo 返回空 symbol 並記錄 `unsupported` provider-run，不觸發指數健康熔斷。
- [改进] 存儲層 `_derive_canonical_id` 統一為 parser 推導（裸碼=stock、顯式指數=index），並新增冪等分批修復歷史裸碼錯誤 canonical 串桶（`000001`/`000016`/`000688`/`930955` 等），顯式指數行與正確 stock 行不受影響，registry 為空時修復 no-op。
- [改进] Web loader 完整解壓含 index 的共享 payload，但在返回給 autocomplete/popular/group 消費面前過濾 `assetType=index`，股票與 ETF 行為保持不變。
- [测试] 為生成器、loader、parser、provider 路由、存儲修復與 Web 門檻補充 TDD 迴歸錨點。
- [修复] PR #2267 review 收斂 CSI 顯式身份：將 `csi` prefix（canonical）與 `.CSI` suffix（顯式 alias）在 parser/build/runtime 規範化器中分離，未登記顯式 `csiNNNNNN`/`NNNNNN.CSI` 一律返回 `unsupported`（不再落入美股或猜測 SH/SZ），並防止未登記 `csi000300` 被等價成已登記 `000300.CSI` alias；存儲 `_derive_canonical_id` 對 unsupported 輸入返回 NULL，避免進入持久化 canonical 桶。
- [修复] 在 seed、build entry 與 runtime candidate 三層嚴格校驗 alias 唯一性與整數 popularity：NFKC/casefold 等價 alias 跨條目衝突被拒絕（無靜默覆蓋），非負整數之外（小數/布爾/負值/字符串）popularity 一律拒絕，整數 `100` 保持有效。
- [修复] 收斂已登記 CSI 顯式身份在 resolver、任務去重鍵與歷史候選中的分裂：`csi930955`/`930955.CSI`/`CSI930955` 統一解析為 parser canonical `csi930955`，未登記 `csi930956`/`930956.CSI` 保持既有降級語義；`is_code_like()`、REST/watchlist 輸入邊界與完整 Pipeline 透傳不變。
- [修复] 阻止任意更新的非 bundled 指數候選（含 legacy `static` 子集）在 remote 缺失/損壞時以 active-index 子集覆蓋 bundled baseline：所有非 bundled 候選必須為 bundled active-index canonical 集合的合法超集，否則回退 bundled 並記錄 WARNING。
- [新功能] 桌面端全局右上角增加更新入口，與設置頁共用更新狀態；普通瀏覽器 WebUI 不展示，且不會在掛載時重複觸發後臺檢查。
- [修复] 桌面端右上角更新入口與設置頁共用檢查中狀態，避免一側檢查時另一側仍可重複觸發 GitHub Releases 檢查；主進程手動檢查路徑同步增加 in-flight 防重。
- [新功能] Web 自動補全與搜索放行已登記指數（註冊中文名/`sh`/`sz` 前綴/`csi`/`.CSI` 顯式形式均可檢索與提交），熱門候選仍僅股票；`/analyze` API 對顯式指數輸入構造結構化 `AnalysisTarget`（INDEX 用 `canonical_id` 去重，與同碼個股互不折疊，CSI alias 收斂），未登記 CSI 單請求返回明確 4xx、異步批量僅該目標進入響應 `rejected` 列表；指數 target 經任務隊列貫穿到 Pipeline `process_single_stock`，`DecisionSignal` 以 `market_override="cn"` 落庫並有真實分支測試。
- [修复] `/analyze` 在解析前按 strip 後非空原始 token 數限制 50 上限，rejected/duplicate token 也計入，防止用拒絕或重複 token 繞過批量上限；以唯一 `is_single = len(stock_codes) == 1 and not rejected_entries` 統一驅動 metadata、409 與單任務 202，duplicate+rejected 混合批次不再誤返 legacy 409（單 duplicate 仍 409、部分 rejected 仍 202、全 rejected 仍 400）。
- [新功能] 報告 meta 補充可選 `asset_type`（`stock`/`index`），由後端 canonical code 經 `parse_analysis_target` 生成權威類型；指數報告在 Web 報告頁與 Chat 自選入口隱藏 stock-only 自選操作，裸同碼股票（如 `000016`）保持股票行為，market review 與舊客戶端可缺省。
- [修复] Web 批量分析把 accepted/duplicates/rejected 三類計入確認數，含 rejected 的完整 chunk 繼續提交下一 chunk 而非誤報 incomplete，最終以 warning 展示拒絕數量與首個拒絕原因（中英文文案）。
- [修复] 歷史篩選/刪除/計數與 stock-bar 對已登記指數按 parser canonical 身份隔離：`sh000016`/`SH000016`/`000016.SH` 等顯式形態互相可達（lowercase canonical + uppercase legacy canonical + 顯式 alias），但永遠不命中同碼裸股票，裸碼查詢也不會命中指數記錄；同一指數多條顯式形態舊記錄在 `/history/stocks` 合併為一行並計數全部形態，無記錄刪除仍返回 `deleted=0`。SH/SZ/CSI 共用同一 parser 分支，股票 alias、港股與海外市場行為不變。歷史列表、歷史詳情與 stock-bar 對已登記指數（含舊 uppercase/顯式 alias 持久化記錄，如 `SZ399300`、`000300.CSI`）的 API `stock_code` 一律輸出 parser canonical（`sh000300`/`csi930955`）。
- [改进] 任務列表/SSE 事件、歷史列表項與 stock-bar 項追加可選 `asset_type`（`stock`/`index`）：任務側從已提交的 `analysis_target` 透傳（不重新猜測），歷史與 stock-bar 側由持久化 `record.code` 經 `parse_analysis_target` 生成；舊客戶端與 market review 可缺省，字段可選追加不破壞既有契約。
- [修复] Web 首頁與自選工作區改用資產感知身份鍵：任務/報告/歷史的 `assetType` 優先，且被後端保證為 parser canonical 的代碼只做**大小寫摺疊**（`SH000016`→`sh000016`），禁止再用前綴/後綴正則猜 canonical（否則 `000300.CSI` 會被誤猜成 `csi000300`、`sz399300` 被誤當成獨立 canonical，違反註冊表唯一判型真源）；僅 watchlist 原始字符串缺少類型時，才用已加載 `stocks.index.json` 的 `assetType=index` 行 canonical/display/顯式 alias 精確命中（不先 normalize、不用前綴正則猜測；加載期間禁用批量分析，加載失敗或請求超過 10 秒時按既有股票語義 fail-open）；行選中、active task 與完成自動選中按資產類型分桶，`sh000016` 指數行與 `000016` 股票行狀態獨立，完成後自動選中正確 canonical 指數報告。
- [修复] Chat 消息恢復、發送與報告追問對顯式 SH/SZ/CSI 已登記指數統一按註冊表 canonical 判型並覆蓋默認 LiteLLM 與 Codex：所有 Chat 後端首幀加載 registry，加載期間延遲 URL/歷史恢復並禁用發送，settle 後 `sh000016`/`sz399001`/`000016.SH`/`930955.CSI`/`csi930955` 只產出一個 lowercase canonical；後端 `resolve_stock_scope`、工具守衛與 cache key 複用 parser `INDEX` 身份，保持指數與裸同碼股票隔離；未登記、空 registry 或加載失敗時維持既有股票 fail-open，絕不按前綴猜指數。
- [修复] 選股結果持久化恢復：選股頁新增歷史記錄區塊，任務完成後保留 run_id，刷新頁面可從歷史 API 恢復上次選股結果（此前刷新後結果丟失）。
- [修复] Web/API runtime scheduler 使用跨平臺獨立進程執行分析，並在默認 45 分鐘硬超時或服務停止後清理進程樹；停止返回後不再派發新的自動任務，避免一次卡死阻斷後續調度。
- [改进] Tavily 搜索深度由 `advanced` 調整為 `basic`，降低搜索 credit 消耗（#2314）。
- [修复] Web 的 axios 依賴升級至 `^1.18.0`，桌面端通過 override 固定 js-yaml 為 `4.3.1`，納入依賴安全更新（#2256、#2254）。

## [3.31.0] - 2026-08-23

### 發佈亮點

- feat: Agent 工具調用新增按類別和單工具配置的超時契約，並補齊防重試、協作取消、併發預算與熱重載一致性。
- feat: 股票名稱解析、`canonical_id` 雙寫和 A 股指數多數據源路由共同完善股票身份與行情降級鏈路。
- improve: 新聞檢索為空時在報告中如實披露證據邊界，Anspire 默認覆蓋全球區域，公共 SearXNG 實例改為顯式啟用。
- fix: 定時任務恢復、無報告失敗反饋、通知發送和大盤覆盤歷史/診斷信息進一步收斂，減少靜默失敗與誤導展示。
- security: 桌面端升級 `builder-util-runtime`，修復 CVE-2026-54673 涉及的重定向憑據頭信息洩露風險。
- docs: 增加 xAI Grok 的 LiteLLM 配置示例、Grok Bot 集成說明與可複用 Skill。

### 變更明細

- [修复] 大盤覆盤歷史列表與詳情統一展示持久化短摘要；舊記錄缺少摘要時從完整 Markdown 生成無內部標記的純文本節選。
- [修复] 大盤覆盤按實際執行的生成後端和模型記錄診斷，避免 Codex CLI 或 fallback 被誤顯示為配置模型。
- [修复] 已配置釘釘 Webhook 時不再誤報“未配置通知渠道”；釘釘 Stream 仍僅用於交互，不作為定時靜態推送渠道。
- [修复] WebUI/API/Desktop 以 `--serve-only` 重啟後會恢復已啟用的定時任務，同時保持啟動時不立即執行分析；通知路由示例補充釘釘 Webhook 渠道。
- [改进] AIHubMix 註冊與引流鏈接統一使用 inferera.com，改善中國大陸網絡直連體驗。
- [修复] 單股推送模式在未配置通知渠道時仍會落盤本地個股報告；CLI 啟動分析若因空股票列表、個股結果全失敗或本地報告保存失敗而未生成報告，會顯式返回失敗並記錄原因。
- [修复] 合併推送模式下即使個股彙總報告落盤失敗，仍會先發送已有的合併通知；僅啟用大盤覆盤但最終未生成任何覆盤內容時，分析任務會顯式返回失敗。
- [修复] SearXNG 公共實例發現的默認值由啟用改為關閉：公共實例普遍存在限流、下線或不返回 JSON 的情況，默認開啟會讓未配置搜索 key 的用戶每次分析多耗 30~60 秒且新聞面最終為空。運行時默認值、配置模板、中英文檔與工作流診斷同步調整；顯式設為 true 的用戶行為不變。
- [改进] 新聞檢索未執行或零命中時，報告中如實標註結論未納入新聞面證據：零命中與「未配置搜索渠道」使用各自獨立的文案，覆蓋日報 / dashboard / brief / 個股 / 企業微信與模板渲染的詳細與摘要分支、歷史報告與分享導出、報告詳情 API 與 Web 報告詳情頁，並按 `zh` / `en` / `ko` 分別本地化。此前該情況下消息面章節直接消失，讀者無從區分「確實沒有新聞」與「檢索靜默失敗」。披露以本次分析實際收到的消息面證據為準，涵蓋實時檢索、社交情緒與本地已落庫的資訊池三路來源；搜索命中數僅用於在確無證據時說明原因（未配置渠道 / 檢索零命中），避免把已用到本地或社交證據的分析誤報成「未納入新聞面證據」。Agent 模式的命中數取自 Agent 實際消費的搜索工具結果，而非分析結束後為持久化情報而補打的查詢。

- [新功能] Agent 工具調用支持按類別（data/search/analysis/action/market）配置默認超時，並允許單工具聲明 `timeout_seconds`；有效超時按 first-wins 優先級解析（顯式 per-run `tool_call_timeout_seconds` > 單工具顯式 `timeout_seconds` > 類別默認 > 無限制），剩餘 wall-clock 預算僅作不可突破的外層 cap，超時後返回結構化 `{"timeout": true}` 錯誤（標記 `retriable: false` 並寫入 `non_retriable_tool_results` 防重試重複執行）供 Agent 繼續執行而非中斷循環（fixes #1890）。
- [修复] Agent 工具註冊表（`src/agent/factory.get_tool_registry`）由模塊級緩存改為按「類別超時映射的值」比對失效，規避 CPython 回收對象後地址複用（`id(config)` 相同）導致配置 reload 後的 `Config` 被誤判為未變、沿用過期超時的真 bug；新增 `_coerce_config_timeout` 類型白名單，使調用方傳入 `MagicMock` / 缺屬性 stub / 髒字符串（如 `float(MagicMock())` 靜默得到 1.0）時降級為「無類別限制」而非崩潰或強加 1 秒超時；`build_agent_executor(config)` / `build_agent_chat_executor(config)` 現已把調用方 `config` 透傳給 `get_tool_registry(config)`（不再無參調用凍結首構 registry）；`main._reload_runtime_config` 與 `SystemConfigService._reload_runtime_singletons`（及 `update()`→`reload_now` 路徑）在配置熱重載時調用 `reset_tool_registry()` 強制重建；迴歸測試補充「傳入新 config 後 registry 重建」「reload 後新超時應生效」及「builder 透傳 config」三類場景（#1890 的 review follow-up，閉環 OR-COM-dd1e8fa7 / OR-COM-bff42110）
- [修复] Agent 工具超時 review 閉環（fixes #1890 的 4 個 blocker）：超時解析由 min 契約改為 first-wins（顯式 per-run `tool_call_timeout_seconds` > 單工具 `ToolDefinition.timeout_seconds` > 類別默認 > 無限制，剩餘 wall-clock 預算只作不可突破的外層 cap；research 路徑不再傳 `tool_call_timeout_seconds` 以免覆蓋類別限制）；超時結果標記 `retriable: false` 並寫入 `non_retriable_tool_results` 阻斷 LLM 同調用重試重入，且超時觸發時為仍在後臺運行的 handler 武裝協作取消信號（`is_tool_cancellation_requested()` 與既有 `check_tool_execution()` 檢查點均響應，handler 從不輪詢則行為不變），作為 review 要求的「handler 內協作取消」緩解，規避 Python 線程無法 force-stop 導致的重複執行與副作用；`_coerce_config_timeout` 對 `inf`/`nan`/負數降級為「無限制」，根絕 `future.result(timeout=inf)` 觸發 `OverflowError`；`get_tool_registry` / `reset_tool_registry` 加 `threading.Lock` 雙檢鎖，且重建後返回本次構建的局部 registry（而非全局緩存），消除併發重建競態與跨調用超時串擾；`@tool` 裝飾器將 `ToolPolicy.timeout_seconds` 摺疊進 `ToolDefinition` 單一來源；統一單/並行工具超時包裝（單一 executor + deadline 驅動的 wait loop，消除並行路徑嵌套 executor 與線程翻倍，duration 精確到各工具自身超時值），並新增快慢工具混合並行迴歸；同步 `docs/full-guide_EN.md` 的超時環境變量文檔；測試覆蓋 first-wins、non-retriable、協作取消接線、finite 校驗、緩存線程安全與快慢混合並行。
- [修复] 按最新 review 複核收斂 3 處正確性問題（OR-COM-7f3d3f5b / 3d6b61f8 / a1e8b0c2）：`BaseAgent._filtered_registry()` 攜帶源 registry 的類別超時映射（工具子集仍生效類別上限，不再繞過 #1890 類別超時）；並行批次 >5 時排隊調用的 per-tool 超時自 worker 實際開始起算（不再提交即燒預算導致對未啟動調用的假超時）；`get_tool_registry()` 緩存命中快路徑在鎖內讀取一致對（消除與 `reset_tool_registry()` 競態返回 `None` 或錯配 registry）。新增對應迴歸測試。
- [新功能] 股票名稱解析引擎重構增強：新增 `resolver_name_to_code_list()` 公開 API，返回按市場排序（A 股→港股→美股）的 `Stock` 候選列表（最多 5 個），新增 `US_stock_code_match()` 匹配美股 ticker（1~5 位字母且僅限本地庫已存在代碼，避免 hello/open 等英文詞誤判為股票）；AkShare 全量 A 股數據經冪等 `extend_AkShare()` 合併進全局 `stockDB`（30 分鐘緩存 + 失敗 5 分鐘退避 + Future 單飛：TTL 過期 stale-while-revalidate 零等待、冷啟動等待上界由拉取超時推導（拉取經子進程封頂 25s）、worker 先清賬喚醒等待者再做日誌/落盤（finally 兜底 BaseException）、成功拉取落盤 `data/cache` 跨重啟複用，非中文輸入跳過網絡擴展），匹配策略升級為「精確→子串（≥2 漢字）→拼音子串（≥5 字母）→difflib 模糊（0.8，單字誤寫 0.7 兜底）」；`resolve_name_to_code()` 保持既有本地優先語義（本地精確命中零網絡，調用方離線低延遲契約不變），跨市場候選能力由 `resolver_name_to_code_list()` 獨立提供；解析全鏈路線程安全（`stockDB` 讀寫加鎖、名稱/拼音索引隨庫變更自動失效），新增 40 個單元測試覆蓋精確/跨市場排序/子串/拼音/模糊/冪等擴展/失敗退避/多候選場景。
- [改进] `StockDaily` 表新增可空 `canonical_id` 列並支持雙寫（Expand-Contract PR2，issue #2207）：自愈式遷移冪等加列 + 普通索引 `ix_stock_daily_canonical_id`，存量行與 `save_daily_data` 未顯式傳參時均經 index-aware 推導（裸指數碼命中註冊表時統一到指數 `canonical_id`，避免同一指數按輸入形態分裂到不同桶——例如裸 `000300` 與顯式 `sh000300` 現在都收斂到 `sh000300`，而非裸碼被推導為 `sz000300`），推導失敗寫 NULL 降級；讀路徑仍用 `code` 列，`(code, date)` 唯一約束保留不變。顯式登記契約漂移：PRD Glossary/FR-1/DD-3 與架構 AD-1/AD-7 中 canonical_id 的點分格式描述（`000016.SH`）已被 Phase 1 已合入代碼的前綴格式（`sh000016`）取代，本變更遵循代碼，PRD/架構文檔的同步修正留待後續 PR 統一收斂。
- [新功能] 當前註冊表已識別的 5 個滬深 A 股指數以顯式市場輸入按 canonical 身份路由：名稱優先使用註冊表並以 Tencent、AkShare、TickFlow 兜底，日線固定使用 Tencent、AkShare、TickFlow、yfinance 多源降級鏈，不讀取普通 A 股日 K 的 `*_PRIORITY` 配置；裸代碼仍按股票處理，並隔離同碼股票名稱緩存。
- [修复] Anspire 搜索默認切換為全球區域模式（`region_mode=2`），使海外股票新聞檢索能夠覆蓋境外信息。
- [修复] 桌面端將 `builder-util-runtime` 升級至 9.7.0，修復 CVE-2026-54673 涉及的 HTTP 重定向憑據頭信息洩露風險。
- [文档] 增加 xAI Grok 的 LiteLLM 配置示例、Grok Bot 集成指南和異步分析 Skill，明確分析模型與 AI teammate 兩類接入邊界。
- [测试] 固定 yfinance 股息 TTM 與單股報告文件名的時間夾具，消除跨日期和合並後時間基準衝突造成的 CI 波動。

## [3.30.0] - 2026-08-09

### 發佈亮點

- feat: LLM 渠道新增顯式 Chat Completions / Responses API Surface，統一連接測試、分析、選股、圖片識別與狀態診斷的協議路由。
- feat: Agent Chat 按會話持久化 Skill 選擇，刷新和切換會話後可恢復，並完整保留省略、顯式空列表與非空選擇三態。
- feat: Electron 桌面端恢復歷史報告、市場覆盤和完整報告分享圖；未配置自定義品牌時，統一使用隨包二維碼與默認“小紅書@霸天土小豆”賬號文案。
- feat: 新增單條分析目標解析契約，收緊交易所後綴、指數別名及美股代碼的規範化邊界。
- fix: 修復移動端側欄滾動、自選股詳情狀態、長通知標題分片及 Lark 國際域名等用戶可見穩定性問題。
- improve: 後端 CI 按測試文件分成三個 runner 並行執行，並收緊 Web 共享資產與跨層契約的門禁範圍。

### 新功能

- LLM 渠道支持顯式選擇 Chat Completions 或 Responses API Surface，兼容 Responses-only 模型，並讓連接測試、主分析、選股、圖片識別和狀態診斷複用統一路由契約。
- Agent Chat 將 Skill 選擇按會話持久化，刷新或切換會話後恢復；歷史會話繼續保留運行時默認，非法 Skill 請求不會誤清空已有選擇。
- Electron 桌面端複用安裝包自帶 Chromium，為歷史個股報告、市場覆盤和完整報告生成 PNG 分享圖；Web 與桌面端統一使用隨包分發的小紅書二維碼。
- `STOCK_LIST` 新增 `parse_analysis_target()` 單條目解析契約，並對外暴露可注入的指數註冊表及解析結果類型。

### 改進

- 優化首頁側欄任務面板和自選股工作區，支持摺疊任務摘要、自選股直接打開最新詳情，並壓縮頭部操作以釋放列表空間。
- 後端 CI 按完整測試文件拆分為三個 runner 並行執行，由統一 `backend-gate` 彙總結果；繼續保留穩定的離線測試語義並降低全局狀態競態風險。

### 修復

- 固定分享圖小紅書二維碼下方的賬號文案格式為“小紅書@暱稱”，未配置自定義暱稱時默認顯示“小紅書@霸天土小豆”；不再渲染數字 ID，歷史 ID 配置不會改變分享圖模板。
- 修復首頁移動端歷史、自選和今日列表無法穩定縱向觸摸滾動的問題，同時保持桌面端卡片裁剪行為。
- 長通知包含一級 Markdown 標題時按對應標題邊界正確分片，避免錯誤遞歸耗盡長度預算並中斷髮送。
- 收斂自選股詳情與今日狀態語義：刷新和查詢期間不再開放過期報告，失敗時不會將舊歷史誤標為今日分析，並限制逐股票 fallback 併發及取消失效批次。
- 收斂 Responses 渠道的協議、provider、route alias 與 wire-model 契約，拒絕協議不匹配、同名 alias 混用 Surface 及非法歷史配置。
- 飛書交互機器人在 `FEISHU_DOMAIN=lark` 時讓 Stream 長連接和消息回覆統一使用 Lark 國際版 API 域名，避免連接國內域名後返回 `Incorrect domain name`。
- 顯式交易所後綴、畸形混合 alias、dotted-prefix 及外盤半顯式後綴的非法輸入不再靜默改寫或降級為錯誤市場。
- `us` 前綴保持大小寫不敏感，但 ticker base 必須滿足規範的大寫美股代碼形態；非法小寫、標點或數字輸入直接返回 `unsupported`。
- 帶 `.US` 後綴的規範美股代碼不再因前兩字符碰撞 `sh`、`hk`、`bj` 或 `us` 前綴而被錯誤拆分。

### 測試

- 非 Web 改動默認執行完整後端門禁；純 Web、共享 public 資產、渠道模板和設置幫助的過濾語義補充迴歸測試，Docker 構建繼續按實際輸入過濾。

### 文檔

- FAQ 補充 macOS 桌面應用被 Gatekeeper quarantine 阻止啟動時，對受信任安裝包進行臨時放行的步驟。

## [3.29.0] - 2026-08-02

### 發佈亮點

- feat: 將參考 AlphaSift 實現的選股核心與策略正式納入 DSA，新增選股運行歷史、數據源歷史和候選深度分析鏈路。
- feat: 新增 1080px 個股決策卡與高密度市場覆盤分享圖，支持 Web 原生分享和下載回退。
- feat: 新增 Skill Opinion Outcome 計算、表現統計與基於真實樣本的有界運行時權重。
- improve: 優化選股快照複用、熱點按需加載、多源併發和候選輪換，縮短長流程等待並提升結果多樣性。
- fix: 加固關閉認證、短憑證診斷脫敏、CI 超時取證和桌面凍結包啟動鏈路。
- fix: 修復 Longbridge 量比、股票代碼窗口解析、選股後置重排及分享圖交互等穩定性問題。

### 新功能

- SkillAggregator 基於獨立滿足 30 條 evaluated 門檻的真實 Skill Outcome bucket，使用 Beta 先驗收縮、unable 懲罰和多週期證據加權生成有界運行時權重；缺失、低樣本或異常統計保持中性。
- 選股結果按 `run_id` 持久化到 DSA 數據庫，新增運行歷史和數據源歷史 API，接入公告事件上下文及其搜索緩存，並支持將候選連同篩選策略映射的 skill 交給單股深度分析。
- 新增按 skill、horizon 與 outcome engine version 獨立聚合的只讀 Skill Opinion 表現統計；少於 30 條 evaluated 樣本時僅返回觀察性計數，不輸出表現指標或調整運行時權重。
- 新增按 individual SkillAgent 自身 signal、版本化 engine 與本地已存同源日線窗口計算並持久化 `skill_opinion_outcomes` 的核心服務。

### 改進

- 選中熱點後先展示榜單已有摘要和核心股，後臺再補充完整詳情，並將單次熱點源等待上限收緊為 8 秒。
- 熱點成分股並行獲取東方財富與同花順數據，並按固定數據源優先級合併；真實供應商調用增加限流、可終止 timeout、併發槽和 worker 回收，題材詳情可按需複用 DSA 原生搜索服務補充安全且帶鏈接的近期消息。
- 精簡選股頁面的重複說明，將任務標識、快照統計和排序診斷摺疊到運行詳情。
- 將參考 AlphaSift 實現的選股核心與策略正式納入 DSA，統一使用 `ScreeningService`、`SCREENING_ENABLED` 和 `/api/v1/screening`，並保留 Apache-2.0 歸因與來源版本記錄。
- Web 選股使用瀏覽器匿名種子與運行 ID 在最終評分後的有界近分池中生成每次運行的候選組合；本地評分覆蓋完整短名單，遠程分析繼續遵守數量上限，硬過濾、風險否決和得分保持不變。
- 熱點榜單刷新與選股長流程解除雙向串行等待，熱點詳情改為選中後按需加載；選股默認複用 5 分鐘內且數據源優先級一致的成功全市場快照，並展示快照、候選上下文、LLM 重排、最終評分和新聞事件增強階段。
- 圖片報告改用獨立的 1080px 個股決策卡和高密度市場覆盤卡，優先從結構化 payload 精確填充數據並保留 Markdown 回退；小紅書賬號與二維碼支持關閉或替換，Web 支持原生分享與下載回退。

### 修復

- Web 分享圖在按需生成完成後通過第二次用戶點擊同步打開系統分享，避免首次異步生成使原生分享退化為下載。
- Web 分享圖改為用戶點擊“分享”後才按需生成，不再在報告加載時自動請求。
- 移除基礎設置選股卡片中仍跳轉到“數據源”的過期“查看配置項”按鈕，並將 `SCREENING_ENABLED` 及 Web 選股功能開關歸入“基礎設置”。
- `scripts/ci_gate.sh` 的離線測試增加單測 timeout 與 faulthandler 取證，並同步 Docker 發佈流程的 CI 依賴，避免無 traceback 卡住或發佈門禁缺少 `pytest-timeout`。
- 選股策略欄穩定展示完整中文策略列表，並保留自定義策略 ID 入口。
- 選股熱點詳情統一使用中文業務文案，不再顯示內部類名、字段名和原始數據源錯誤。
- 刷新熱點榜單並保留當前題材時同步繞過詳情緩存重拉該題材，避免新榜單繼續搭配舊路線與成分股。
- 選股尾部輪換以分析器輸入順序為權威並保留並列分候選順序；熱點消息增強、共享緩存 owner、全局併發容量和新聞搜索 deadline 統一收斂。
- Outcome 候選按上次嘗試時間公平調度，避免持續新增的缺失 key 使舊 `pending` outcome 永久得不到重試。
- 選股主模型返回空內容、非 JSON 或低覆蓋結構時繼續嘗試備用模型；全部失敗時明確展示確定性因子排序狀態，且不把 `reasoning_content` 當作最終結果。
- 選股日線增強改用請求級 DSA-first fetcher 注入，多個後置分析器按最新分數逐級重排，遠程分析狀態跟隨實際提交候選，避免重疊請求洩漏 wrapper 或改寫未提交候選。
- 統一等價股票代碼的本地日線候選與同源窗口解析；衝突滬深交易所代碼不再降級匹配裸碼，回測僅接受快照或交易日曆確認的起點。
- 關閉認證時強制再次校驗當前管理員密碼，命中 rate limit 時返回 429，前端在當前密碼缺失時阻止提交併顯示內聯提示（#1970）。
- 本地 CLI 的 `stdout_preview` / `stderr_preview` 按環境變量、JSON、YAML/日誌標量與 URL 的獨立契約脫敏短憑證，避免 API key、secret 或 token 進入診斷（refs #1784）。
- PyInstaller 凍結包在 NLTK 3.10 導入保護下誤判內置 `_internal` 標準庫時不再啟動失敗；Windows/macOS 打包腳本統一接入兼容 runtime hook。
- 分享圖按字段合併歷史結構化數據與 Markdown，多市場逐區域複用持久化 payload，隱藏不可用市場燈號維度並保留配色方案；中英韓模板跟隨報告語言，原生分享失敗時自動回退下載。
- 飛書文件報告在寫入或上傳前清理隱藏的市場 metadata；桌面運行時默認隱藏未隨包提供 renderer 的 Web 分享按鈕。
- `redact_diagnostic_text()` 的命令替換掃描不再吞掉尾隨非敏感診斷字段，並統一 `export FOO=$(...)` 與 `FOO=$(...)` 的脫敏行為。
- Longbridge 量比改用 adaptive keyword args 調用 `history_candlesticks_by_offset`，兼容 0.2.74 與 4.x SDK 參數順序（fixes #2100）。

## [3.28.0] - 2026-07-26

### 發佈亮點

- feat: Multi-Agent 多策略綜合支持分層 deliberation、mediator/self-review、revision projection 與 multi-round，並統一最終動作和解釋契約。
- feat: AI 建議頁新增按決策風格分組的歷史表現，specialist opinion 樣本可持久化並用於後驗評估。
- feat: 新增 `--portfolio futu`，可只讀導入 Futu OpenD 真實賬戶的滬深 A 股、港股和美股 LONG 正股持倉。
- feat: Web 首頁與 API 支持按單個或多個市場臨時觸發大盤覆盤，不修改全局配置。
- feat: Tushare 支持通過 `TUSHARE_HTTP_URL` 接入自建網關或兼容鏡像。
- fix: 改進港股行情路由與緩存、外股英文新聞匹配、數據源兜底順序及桌面端發包穩定性。

### 新功能

- Multi-Agent 多策略綜合新增受控 deliberation v0、可注入 mediator/self-review v1-v2、只讀 revision projection v3 與 multi-round v4；增強層相對上一層 baseline 只能保持或繼續 softened，不覆蓋權威最終信號。
- `specialist` 模式最多選擇 4 個策略專家，並通過 `AGENT_SKILL_CONCURRENCY` 控制 1–4 個 worker 併發；worker 繼承主管線凍結的 target date 等上下文，單個 skill 失敗不阻斷其它策略或最終決策。
- Multi-Agent 報告按八態用戶 action 追蹤 Pipeline 最終調整，排除非法 Agent 意見；僅在 canonical action 可唯一解析時生成 explanation 與 DecisionSignal，並以同一個 `final_action` 統一最終動作契約。
- specialist 在分析歷史保存成功後持久化版本化、低敏且冪等的有效 opinion 樣本，為後續後驗評估提供真實數據；本階段不計算 outcome、不統計表現、不調整權重。
- AI 建議頁新增決策風格歷史表現，按每個分組獨立的 30 個已完成樣本門檻展示命中、區間漲跌、無法評估和最大不利波動，並保持舊統計接口兼容。
- 新增 `--portfolio futu`，只讀導入 Futu OpenD 真實賬戶的滬深 A 股、港股和美股 LONG 正股持倉作為分析列表。
- Web 首頁與 `POST /api/v1/analysis/market-review` 支持用嚴格校驗的 `region` 臨時選擇單個或多個覆盤市場；一次性覆蓋不讀寫全局配置，並貫穿任務提交、狀態、SSE、結果與歷史記錄。
- Tushare 數據源支持通過 `TUSHARE_HTTP_URL` 自定義接入地址；留空時繼續使用官方默認地址（fixes #1985）。

### 改進

- 暫停 PR Review 的自動觸發，僅保留 `workflow_dispatch` 手動入口，避免輔助評審重複運行及評論權限失敗產生誤導性紅燈；正式 CI 檢查保持不變。
- `.env.example` 與每日分析 workflow 同步映射 `TUSHARE_HTTP_URL`，保持本地和雲端配置入口一致。

### 修復

- 修復外股代碼映射到中文顯示名時英文新聞相關性漏判，統一外股代碼、英文名和別名解析，並對展開後的檢索詞去重（fixes #2026）。
- 特權 `pull_request_target` 流程不再檢出 fork PR head；敏感步驟僅執行主分支可信腳本，PR 元數據與 diff 通過 GitHub API 讀取（fixes #2051）。
- PR Review 事件載荷缺失、不可讀或 JSON 非法時輸出可定位且不洩露載荷的警告，並保留原有降級行為（fixes #2070）。
- 修復 Windows 上 `mimetypes` 冷啟動讀取註冊表導致進程卡死的問題。
- 統一 `DataFetcherManager`、AkShare 與 Longbridge 對 4–5 位裸港股碼的識別，避免 4 位代碼被錯誤路由或靜默失敗（fixes #2091）。
- AkShare 港股實時行情增加 20 分鐘全市場緩存與併發冷啟動 single-flight，熱緩存命中不再等待網絡限速，主接口異常時仍保留新浪備用接口降級（refs #1852）。
- 將 `TencentFetcher` 默認優先級調整為 A 股日 K 數據源的最終兜底，並新增 `TENCENT_PRIORITY` 顯式覆蓋項（refs #2032）。
- Web 設置頁和通知測試入口補齊普通釘釘群機器人配置，支持安全遮罩保存 webhook 與 secret、查看幫助併發送測試通知（refs #1957）。
- Agent Chat 普通與流式接口在請求未指定 `report_language` 時繼承全局 `REPORT_LANGUAGE`，顯式請求值仍優先。
- WebUI 分開展示發佈版本、代碼版本與構建時間，並用構建輸入摘要避免複用時間戳未變化的舊靜態資源（fixes #2093）。
- macOS unsigned 打包顯式禁用 Electron 簽名與 Hardened Runtime，在凍結後端和 electron-builder 階段清理殘缺簽名，並審計原始應用與 DMG 產物；該緩解不替代 Apple Developer 簽名與公證（refs #2075）。

### 文檔

- 修復文檔中的失效相對鏈接。
- [修复] #2026 外股代碼映射到中文顯示名時英文新聞相關性判定漏判：新增同源 STOCK_ENGLISH_NAME_MAP 單一真源、canonicalize_foreign_stock_code 規範化入口與 _foreign_english_query_terms 別名解析，使 AAPL/00700/BABA 等 ticker 即使 stock_name 為中文也能在查詢構建、相關性打分與多維度情報路徑上覆用 canonical 英文名，並補齊 .US/.HK suffix / HK 前綴全形式的歸類與迴歸用例；同時在 _score_news_relevance 對 alias 展開 term 做去重，避免 legal alias 展開短名與顯式 short alias 重複計分。
- [新功能] Tushare 數據源支持通過 `TUSHARE_HTTP_URL` 環境變量自定義接入地址，便於網絡無法直達 `api.tushare.pro` 時切換自建網關或第三方兼容鏡像；留空保持官方默認地址不變（fixes #1985）
- [文档] `.env.example` 與 `.github/workflows/00-daily-analysis.yml` 同步映射 `TUSHARE_HTTP_URL`，避免出現"配置項有但 workflow 漏映射"的半修狀態
- [修复] #2051 PR Review 的特權 `pull_request_target` 流程不再檢出 fork PR head：敏感文件、標籤、報告與 AI 審查統一通過 GitHub API 將 PR 元數據和 diff 作為數據讀取，只執行主分支可信腳本；Python 語法、Flake8、確定性檢查和離線測試繼續由無 secrets 的 `pull_request` CI / `backend-gate` 執行，兼容 `actions/checkout` 新增的 fork checkout 安全保護。
- [修复] 修復 Windows 上 mimetypes 冷啟動時讀取註冊表導致的進程卡死

## [3.27.0] - 2026-07-19

### 發佈亮點

- feat: 新增 Codex App Server single-agent 問股實驗原型，並保持 LiteLLM、Multi Agent、普通報告和定時任務等默認鏈路不變。
- feat: Web AI 建議頁支持保存基於歷史報告快照重算的決策風格信號，補齊去重、續期、失效和可審計 guardrail 語義。
- feat: 引入多策略觀點結構化輸出第一階段契約，覆蓋觀點標準化、基礎衝突檢測、聚合元數據和報告兼容邊界。
- improve: 報告頁明確展示輸入數據狀態、來源、異常影響、處理建議和診斷碼，並區分頁面資訊與本次分析輸入。
- fix: 修復 MiniMax 推理內容汙染最終 JSON、字符串 `<think>` 包裝兼容及多 Agent 風險覆蓋後結論未按最終信號收斂的問題。
- fix: 補齊美股實時行情 PE/PB 估值字段、多市場工具描述和 macOS Gatekeeper 安裝排障說明。

### 新功能

- 新增 #1743 Phase 6 Codex App Server single-agent 問股實驗原型，僅開放三個既有隻讀 Tool Surface 工具；默認 LiteLLM、Multi Agent、Deep Research、普通報告、定時任務與 Phase 1/2 `codex_cli` 路徑保持不變。
- Web AI 建議頁支持確認保存基於歷史報告快照重算的決策風格信號，以 created/existing/refreshed 區分新建、原樣複用和既有記錄續期或維度補齊，並複用 profile-aware 去重與失效語義。
- 多策略觀點結構化輸出第一版新增策略觀點標準化、基礎衝突檢測與聚合 metadata，作為 #1964 的階段性基礎契約；本版本不聲明完成併發執行、完整策略調度 MVP 或前端完整多語言展示。

### 改進

- Codex 設置頁僅檢查配置、命令和所需協議是否允許嘗試，用戶保存後可直接提問；Chat 以服務端 `accepted` 事件提交問題並按實際 backend 停止。
- Web 報告頁輸入數據塊沿用狀態、來源、告警和說明字段，在說明中補充異常影響、處理建議與診斷碼，並區分報告頁資訊和本次分析輸入。
- 更新 Anspire 數據源的項目展示信息，並將 `get_stock_info` 工具說明從 A 股限定修正為覆蓋 A 股、港股和美股。

### 修復

- 修復 MiniMax 分析與渠道 JSON 測試把推理內容和最終文本拼接後導致結果無法解析、無法持久化的問題；字符串響應僅剝離開頭完整的 `<think>` 包裝，並保留 JSON 內容中的同名字面標籤。
- 修正多 Agent 內部 runtime facts 的 timeout 歸因，並讓 risk application 覆蓋後的 dashboard 決策字段及一句話核心結論基於 post-risk signal 完成 finalization。
- 收斂多策略綜合器語義：正確處理 Signal 枚舉、缺失 signal、有效 opinion_count 和 deterministic synthesis，併兼容歷史與外部 dashboard 的寬鬆字段形狀。
- Codex 問股只接受 App Server 明確完成的終態回答，並統一整體時限、累計輸出、事件、工具預算和進程回收邊界。
- `codex_cli` 普通分析顯式固定無人值守批准策略與只讀沙箱，避免新版 Codex 在非交互任務中因請求人工批准而中斷。
- yfinance 美股實時行情補齊 `pe_ratio` 和 `pb_ratio`，供估值分析和下游報告使用。

### 文檔

- 補充 macOS 未簽名、未公證 DMG 被 Gatekeeper 攔截時的架構選擇、安全排查與官方安裝包臨時放行步驟。

## [3.26.1] - 2026-07-12

### 發佈亮點

- feat: Web 首頁新增歷史、自選與今日工作區，支持批量分析、今日覆蓋判斷和評分排行。
- feat: 新增 A 股市場結構與題材主線上下文，並貫通報告、Agent、DecisionSignal 與 Web 展示。
- feat: 飛書支持文件形式推送報告，多 Agent 支持子 Agent 獨立超時鉗位。
- feat: 補齊內部 DSA Tool Surface、DecisionAgent 分歧摘要和 DecisionSignal profile 契約。
- fix: 統一報告動作口徑，修復按股票代碼批量刪除歷史記錄和通知理由靜默截斷問題。
- fix: 改進 Web、桌面端、數據源緩存及發行包資源的穩定性。

### 新功能

- 新增 A 股市場結構與題材主線上下文，並在報告、Agent、DecisionSignal 和 Web 市場位置卡中複用。
- 飛書推送新增文件上傳能力：`FeishuSender.send_feishu_file(file_path)` 通過 App Bot SDK (`im.v1.file.create`) 上傳文件併發送文件消息；Webhook 模式回退為發送文件內容文本；新增 `FEISHU_SEND_AS_FILE=true` 配置開關，開啟後飛書以文件形式發送報告而非文字消息。
- 多 Agent 編排 Pipeline 新增子 Agent 獨立超時鉗位：支持 6 個環境變量為 TechnicalAgent、IntelAgent、RiskAgent、DecisionAgent、PortfolioAgent、SkillAgent 各自配置獨立硬上限，互不擠佔配額；默認 0 表示關閉鉗位。

### 改進

- 為 multi-agent DecisionAgent 增加內部低敏分歧摘要輸入管線，作為 #1904 P1 解釋輸出的前置 plumbing；不改變 public API、dashboard schema 或最終解釋字段。
- GitHub Actions 每日分析工作流補齊 TickFlow 數據源環境變量映射，並收斂 README 數據源穩定性說明到完整指南。
- Web 首頁個股欄新增歷史 / 自選 / 今日切換，保留歷史分析默認視圖，並支持在自選頁一鍵分析全部或僅分析今日未覆蓋股票、在今日頁按評分查看當天分析排行；分塊提交部分失敗時保留已確認計數、停止後續提交併刷新任務列表。
- GitHub Actions 每日分析工作流新增釘釘通知環境變量映射，支持在雲端定時任務中直接使用釘釘機器人。
- `STOCK_LIST` 自選股解析支持中文逗號、頓號、分號、空格和換行等常見粘貼分隔符，運行時、定時熱刷新、CLI `--stocks`、Web 設置保存和自選 API 統一識別，並在寫回時規範為英文逗號。
- 新增 `NEWS_INTEL_AUTO_FETCH_ENABLED` 單開關，開啟後個股分析、Agent 分析和大盤覆盤會 fail-open 自動初始化並刷新 RSS/Atom/NewsNow 本地資訊池。
- Web AI 建議頁新增主股票上下文，複用最近分析和股票索引候選，並改進表現統計零樣本說明。
- DecisionSignal 將 `decision_profile` 升級為正式 nullable 字段，統一 same-profile 查詢、去重、續期和失效語義，並保持 create metadata `null` 兼容與 SQLite 冪等回填診斷。
- 設置頁移動端分類導航改為橫向滾動列表並保證設置內容首屏可見，桌面端保留分類說明並收緊字段佈局層級與間距。
- 新增 #1743 Phase 6a 內部 DSA Tool Surface 契約，統一工具 schema、stock scope fail-closed guard、結構化錯誤、審計摘要和脫敏診斷邊界，並明確外部 AgentBackend 工具能力仍需 wire-level probe 證明。
- `src/services/analysis_service.py` 在 `report` 詳情層新增 `details.raw_result` 回填，補齊與 API/歷史詳情的報告載荷一致性；不改變 provider、model、Base URL 或配置遷移語義。

### 修復

- 按股票代碼刪除歷史記錄時分批清理全部匹配項，並拒絕空白代碼，避免超過 10000 條後殘留記錄或無篩選刪除。
- 市場結構概念排行為空或超時時複用本輪負結果，避免批量個股分析重複請求同一概念排行數據源。
- Windows/macOS 桌面後端打包顯式收集並校驗 AkShare `file_fold/calendar.json`，避免發行包因缺少交易日曆 package data 導致熱點題材和選股日線增強降級。
- 郵件、Telegram 與報告共享的 DecisionSignal 摘要完整展示已脫敏的理由，避免固定 120 字符在句中無提示截斷；Telegram 按最終 Markdown payload 長度安全分片。
- 推送報告、Jinja 報告與歷史 Markdown 導出複用 Web/API 的評分-action 口徑：高分但舊 `operation_advice` 仍為持有且無降級原因時，建議文案與三類統計展示為買入；有明確 guardrail reason 時繼續保留持有/觀望。
- WebUI 啟動時顯式 `--host` / `--port` 不再被 `.env` 中的 `WEBUI_HOST` / `WEBUI_PORT` 覆蓋，未傳 CLI 參數時統一使用解析後的運行時配置。
- Web 首頁今日狀態與排行使用帶時區偏移的歷史時間戳和完整分頁數據，在查詢失敗、跨服務器時區邊界或任務完成刷新時保持安全且準確。
- Web 首頁 stock bar 刷新序列化：併發或亂序返回時僅最新請求可清除 `stockBarRefreshFailed`，避免舊響應覆蓋任務完成後的刷新結果。
- Web 持倉頁首屏快照改用 `include_realtime=false` 快速估值，跳過逐票實時行情預取後先展示持倉列表，避免外部實時行情源變慢時長時間空白等待。
- 修復任務狀態接口重建報告動作字段時把合法情緒分 `0` 當成空值的問題，確保低分報告能按評分口徑糾正為賣出建議。
- 修復 Agent 流式回覆在未收到完成事件就斷開時被顯示為“（無內容）”的問題，改為提示流式響應中斷並保留用戶消息。
- 修復桌面端 `WEBUI_HOST=*` / `WEBUI_HOST=[::]` 會被原樣傳給端口探測和後端啟動導致無法監聽的問題，啟動前分別規範化為 `0.0.0.0` / `::`。

### 文檔

- 在 README 快速開始中補充行情數據源配置說明（`TUSHARE_TOKEN` / Longbridge），明確未配置時仍可使用 AkShare、Baostock、YFinance 等免費兜底源，並同步中英文完整指南。

## [3.25.0] - 2026-07-03

### 發佈亮點

- feat: 新增 `claude_code_cli`、`opencode_cli` generation-only 本地 CLI backend，並補齊生成後端狀態診斷、預覽、冒煙測試 API 和 Web 狀態面板。
- feat: 臺股報告完整接入三大法人資料，覆蓋報告渲染、LLM prompt、TWD 幣別標示、收盤集合競價識別和 fetcher 韌性加固。
- feat: 新增釘釘群機器人通知、韓語報告輸出和 AI 建議決策風格重評估預覽。
- feat: Agent `/chat/stream` 標準化 progress event，新增階段開始/完成、pipeline timeout 和預算跳過語義。
- fix: 修復桌面端 WebUI host/port 綁定、macOS Homebrew CLI PATH 診斷、Discord 長報告分片、AlphaSift 超時、yfinance 分紅解析、A 股回測代碼歸一化等穩定性問題。

### 新功能

- 釘釘群機器人通知支持 `DINGTALK_WEBHOOK_URL` 和 `DINGTALK_SECRET`，並對長文本自動切片以適配 20KB 限制。
- 報告輸出語言新增韓語（`REPORT_LANGUAGE=ko`），覆蓋個股報告、大盤覆盤、Prompt 輸出語言、決策護欄、通知模板標籤與 Web 報告詳情頁文案。
- 新增 `claude_code_cli` 與 `opencode_cli` generation-only 本地 CLI backend，保留 LiteLLM 默認路徑、Agent 工具調用邊界、per-preset extractor、最小 env allowlist 與結構化錯誤。
- 新增生成後端狀態、預覽和冒煙測試 API，以及 Web 生成後端狀態面板，區分輕量檢查與 JSON 冒煙測試，並保持本地 CLI “僅生成、不支持問股工具調用”的邊界。
- Agent `/chat/stream` progress event 新增 `stage_start`、`stage_done`、`pipeline_timeout`、`pipeline_budget_skipped`，補齊階段進度、超時和預算跳過語義。
- 臺股個股報告的 institution 區塊展示 TWSE T86 / TPEx 三大法人原始買賣超淨額，並將三大法人淨買賣超表格注入 LLM 分析 prompt 作為臺股籌碼過濾器。
- 新增 AI 建議決策風格重評估預覽接口與頁面預覽。

### 改進

- 臺股三大法人 fetcher 增加併發緩存防擊穿、TWSE/TPEx 分市場熔斷、TPEx 日期保護和剩餘 stage 預算複用，降低限流、端點故障和冷抓取超時帶來的降級概率。
- AlphaSift 默認依賴 pin 更新到 `9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf`，接入 wrapper 數據源 caller-side timeout、東財直連限速/抖動、策略目錄元數據和防守策略。
- 選股任務狀態輪詢遇到可恢復超時時提示後臺任務仍會自動重試，`.env.example` 補充相關超時調優項。
- 收斂個股分析評分與 DecisionSignal action 口徑，統一 80/60/40/20 分段，並在風控降級時記錄 raw/adjusted score、final action 與原因。
- Web 設置頁左側分類切換時僅在相關分類展示首次啟動檢查和 AlphaSift 輔助卡片，減少跨分類殘留。

### 修復

- 修復 Windows 桌面端啟動後端時固定傳入 `--host 127.0.0.1` 導致 `.env` 中 `WEBUI_HOST=0.0.0.0` 不生效、局域網無法訪問 WebUI 的問題；桌面端仍默認使用 `127.0.0.1`，僅在顯式配置 `WEBUI_HOST` 後按配置綁定。
- 修復桌面端啟動時 `.env` 中 `WEBUI_PORT` 與 Electron 自動選擇端口不一致，導致窗口繼續等待舊端口並連接超時的問題。
- 修復 macOS 桌面端從 Finder/Dock 啟動時後端 PATH 看不到 Homebrew Codex CLI 的問題，並明確 Codex CLI 主分析與 Agent LiteLLM 工具調用分流診斷。
- 修復 Discord 長報告推送按 2000 字符上限分片逐段發送，遇到 429 限流會按 `retry_after`/`Retry-After` 有限重試，避免中途失敗後只收到前半段報告。
- 修復日股、韓股和臺股 `market_phase` 收盤集合競價識別，避免臨近收盤階段仍被標記為普通 `intraday`。
- 修復 A 股個股分析遇到空 `belong_boards` 佔位時不會繼續補查所屬板塊、關聯板塊模塊展示不穩定的問題。
- 修復大盤覆盤在 LLM 標題漂移或正文缺少板塊段時，Web 與推送報告偶發缺少板塊主線的問題。
- 修復 Web 大盤覆盤結構化數據成交額、指數點位、漲跌幅和高/低值格式化，避免浮點長尾或缺失值 `0.00` 直接展示。
- 修復 Web 首頁個股欄在 stock-bar 摘要字段缺失或動作建議無法歸類時隱藏情緒分與建議標識的問題。
- 修復 Web 設置頁定時任務“立即執行一次”後臺線程未傳 `stock_codes` 導致任務崩潰的問題。
- 修復 `opencode_cli` 靜態指令，避免全局 JSON-only 約束影響 `generate_text()` 與大盤覆盤自由文本輸出。
- 修復 yfinance 1.2.x 將 `Ticker.dividends` 返回為單列 DataFrame 時分紅解析被丟棄的問題，恢復 TTM 每股分紅與分紅次數計算。
- 修復臺股財務金額幣別標示，將 TWD 金額標註為“新臺幣”，避免在 A 股語境下誤讀為人民幣。
- 修復回測日線補全將 `605066.SH`、`SS605066`、`SS.605066` 等 A 股等價代碼誤向數據源請求 `SS605066`，導致回測數據不足的問題。

### 文檔

- 新增 Agent `/chat/stream` progress event 契約文檔，說明新增事件字段語義、Web 兼容邊界、驗證方式和回滾方式。
- 同步本地 CLI backend 隱私/部署邊界，明確 local CLI 不是離線模型，Docker/CI/遠端需自行安裝登錄，DSA 不讀取 Claude/OpenCode credential 文件。
- 更新 README 三語入口和市場支持邊界，說明臺股 `.TW` / `.TWO`、三大法人報告區塊、TWD 標註與收盤競價識別能力邊界。

### 測試

- 臺股三大法人 fetcher 新增 live-smoke 腳本與 `@pytest.mark.network` 漂移檢測測試，用於非阻斷 network-smoke 定時任務核對 TWSE T86 / TPEx 核心字段與解析結果。

## [3.24.1] - 2026-06-28

### 修復

- 修正 Longbridge SDK 版本約束為按平臺選擇可安裝版本，避免桌面與 Docker 發佈在 `pip install -r requirements.txt` 時因不存在的 `0.2.75` 版本失敗。

## [3.24.0] - 2026-06-28

### 發佈亮點

- feat: 擴展臺股、日股、韓股市場支持，覆蓋臺股 suffix-only 分析、臺股三大法人資料層、JP/KR 大盤覆盤和跨服務市場枚舉。
- feat: 新增 GenerationBackend 抽象、`codex_cli` 本地 CLI backend、reserved Hermes 本地 HTTP 渠道和 prompt cache capability registry。
- feat: Web/API/Desktop 支持多時間定時推送與 runtime scheduler 熱重建，Web 設置頁補齊首次啟動檢查與定時任務面板。
- feat: 報告鏈路補齊信號歸因、單股信號時間線、概念板塊排行和通知/報告關聯板塊展示。
- fix: 修復 Docker/啟動探針、靜態資源 MIME、回測空結果、組合估值、通知 Markdown、AlphaSift 數據源和測試環境隔離等穩定性問題。

### 新功能

- 新增臺股 suffix-only 個股分析 MVP：`.TW`/`.TWO` 代碼可走 YFinance 日線與近實時行情，並補齊市場識別、交易日曆和 Prompt 能力邊界。
- 臺股 `tw` 納入 DecisionSignal、Portfolio、Intelligence 服務層、API 枚舉和 Web 篩選，避免臺股分析信號被市場歸一化靜默丟棄。
- 新增臺股三大法人資料層 fetcher `TwInstitutionalFetcher`，支持 TWSE/TPEx 來源、日期轉換、單日緩存和 fail-open 退化。
- 大盤覆盤新增 `jp`/`kr` 市場，支持日經225/TOPIX、KOSPI/KOSDAQ 指數覆盤，並擴展 `MARKET_REVIEW_REGION`、交易日過濾和 Web 設置枚舉。
- 新增 GenerationBackend Phase 1 抽象和顯式 opt-in 的 `codex_cli` 本地 CLI generation backend，提供結構化錯誤、fallback、stream 降級和 usage unavailable contract。
- 新增 reserved Hermes 本地 HTTP generation 渠道，提供 JSON generation、no-proxy 本地調用和 saved secret endpoint 綁定。
- 新增 Provider Cache Capability Registry，按 provider、API surface、gateway 與 verification status 建模 prompt cache 能力。
- 支持 `SCHEDULE_TIMES` 多時間定時推送，長運行 Web/API/Desktop 進程保存調度配置後可熱啟停或重建 runtime scheduler。
- 新增信號歸因分析和 Web AI 建議頁單股信號時間線，併為自動生成與歷史回填的 DecisionSignal 寫入默認 `decision_profile` metadata。
- 大盤覆盤、Web 報告頁和通知關聯板塊補齊概念板塊排行與概念信號展示。

### 改進

- TickFlow 擴展為可選 A 股日 K、實時行情、股票列表/名稱數據源，並增加 count、完整性校驗和批量預取緩存保護。
- 硬化 JP/KR/TW suffix 識別、日韓股票種子索引、YFinance 報價/基本面上下文，以及 JP/KR Portfolio 與 Market Light 邊界。
- Web 設置頁新增首次啟動配置檢查卡與定時任務面板，隱藏內部 `SCHEDULE_TIMES` 鍵，並改善重複任務提示的關閉與自動消失體驗。
- Web 歷史報告詳情不再內嵌 AI 建議卡片，結構化決策信號集中到 AI 建議頁，並保留來源報告 ID/URL 參數精確定位。
- `GENERATION_BACKEND=codex_cli` 下普通分析與大盤覆盤不再因缺少 LiteLLM API Key 被誤判不可用，並改用 `--output-last-message` 文件讀取最終響應。
- 本地 CLI backend 對 stdout/stderr 診斷預覽和最終響應實行執行期總量上限，並補齊新增 generation backend 數字配置最大值校驗。
- AlphaSift 默認依賴 pin 更新到 `0a7b9cd59e81718f851890535241bc105d4ddc64`，並默認走 DSA EastMoney 兜底 provider、暴露 source health 診斷。
- Docker Compose 默認內存建議提升到 1G；每日分析 workflow 兼容誤將 `STOCK_LIST` 配到同名 Environment variables 的場景。
- Agent 路徑同步 signal attribution prompt，通知報告摘要不再展開 AI 決策信號明細，完整信號保留在個股詳情與單股報告。

### 修復

- API 異步批量分析共享概念板塊排行緩存，避免同批多股重複拉取全市場概念排行。
- 修復通知 Markdown 表格轉換在空單元格後將後續內容錯配到錯誤表頭的問題。
- 修復 Market Light 區域歸一化拒絕 `jp`/`kr`、日韓歷史列表市場階段摘要誤傳 `analysis_phase` 和默認通知報告缺少 `dashboard.phase_decision` 的問題。
- 固定 Docker 可安裝的 Longbridge SDK 版本為 0.2.75，並修復 Docker 鏡像中 efinance 緩存目錄屬主導致 A 股數據源降級的問題。
- 持倉快照今日估值改為受限併發預取實時價，減少持倉較多時 Web 組合頁面刷新超時。
- Web 首頁重新分析完成後自動切換到同一股票最新報告，並修復 Windows 環境下 Web/Desktop 靜態 JS 資源可能以 `text/plain` 返回導致黑屏的問題。
- 修復 `--serve --schedule` 與 Web/API runtime scheduler 狀態脫節、立即執行忙碌狀態誤提示、重建定時任務重複監聽和啟動參數語義丟失。
- 修復 `main.py --serve-only` 在低配主機上因惰性 import 應用超出 uvicorn 啟動自檢窗口而反覆重啟的問題。
- 修復 Web 回測未傳分析日期範圍、股票代碼未歸一化導致成功響應但結果為空的問題，併為空候選、行情不足和非法後綴提供診斷信息。
- 修復 unsupported `GENERATION_BACKEND` 被當成空響應/模板 fallback、`codex_cli` stdout 重複計入輸出上限和主分析 JSON schema fallback 語義回退的問題。
- Docker 部署中 Web 設置頁保存自定義 Webhook 模板時會轉義 `$content_json` 等佔位符，並在運行時還原，避免 Compose 重新部署展開為空。

### 文檔

- 補齊概念板塊排行字段契約、通知報告行業/概念類型列展示和數據源穩定性與故障處理圖示。
- 補充 JP/KR/TW suffix-only MVP、`MARKET_REVIEW_REGION` 保存/校驗/回退矩陣、Market Light 邊界和 PR 提交流程約束。
- 補充本地 CLI backend 隱私邊界、非離線模型說明、Docker/CI 登錄態限制和 `codex_cli` experimental/limited 狀態。
- 補充回測請求鏈路說明，並同步更新 `docs/full-guide.md` 與 `docs/full-guide_EN.md` 示例。

### 測試

- 新增/更新臺股、JP/KR 大盤覆盤、GenerationBackend、`codex_cli`、Hermes、本地 CLI、runtime scheduler、回測和概念板塊排行相關回歸測試。
- 加強 `tests/test_analysis_api_contract.py`、`tests/test_analysis_history.py` 與 `tests/test_backtest_service.py` 的臨時 `.env` 隔離，避免本地真實 `.env` 汙染系統配置測試。

## [3.23.0] - 2026-06-20

### 發佈亮點

- feat: DecisionSignal 貫通報告提取、Web 展示、反饋/後驗、告警通知和組合風險，AI 建議信號進入可追蹤閉環。
- feat: 新增合規 RSS/Atom 與 NewsNow 資訊源情報池，分析、Agent 和大盤覆盤可 fail-open 複用本地資訊 evidence。
- feat: 新增日本/韓國 suffix-only 個股分析 MVP，支持 `.T`、`.KS`、`.KQ` 標的通過 YFinance 獲取行情與技術上下文。
- feat: 新增 Token 用量監控看板、legacy LLM usage telemetry 和 message stability audit，增強 LLM 調用可觀測性。
- fix: 修復運行流 live 狀態、AlphaSift 緩存/字段兼容、發佈說明診斷和日韓股票輸入/歷史展示等穩定性問題。

### 新功能

- 個股分析歷史成功保存後會從最終報告 best-effort 提取 `DecisionSignal` 決策信號，複用現有信號去重、計劃質量計算和脫敏契約。
- 新增 Web AI 建議頁、持倉頁 latest active 信號摘要、歷史報告信號展示和更完整的信號詳情卡片，展示評分、置信度、價格計劃、催化、風險與失效條件。
- 新增 DecisionSignal 用戶反饋、信號級日線後驗評估、統計 API 與 Web 展示，使用 outcome/feedback sidecar 表並保留主信號表契約。
- 將 DecisionSignal 複用到告警、通知和組合風險：告警觸發關聯 latest active 信號或創建最小 alert 信號，通知追加低敏信號摘要，持倉風險聚合 active sell/reduce/alert 信號並保持 fail-open。
- 新增合規 RSS/Atom 資訊源配置、拉取、去重、入庫、查詢、retention 與基礎安全校驗 API，作為個股/市場資訊情報池基線。
- 資訊源新增 `newsnow` 類型、`NEWSNOW_BASE_URL` 配置和 `/api/v1/intelligence/sources/defaults` 默認源初始化接口，內置財聯社熱門、雪球熱門股票、華爾街見聞快訊、金十數據和格隆匯事件等財經熱點源。
- 個股分析、Agent 分析和大盤覆盤會 fail-open 讀取本地資訊/情報池，並把來源鏈接作為新聞上下文和 evidence 輸入。
- 新增日本/韓國 suffix-only 個股分析 MVP：手輸 `.T` / `.KS` / `.KQ` 代碼可走 YFinance 日線與近實時行情，補充市場識別、交易日曆、Prompt 語義、Web/API 類型和能力邊界文檔。
- 新增 Token 用量監控看板與 `/api/v1/usage/dashboard` 接口，展示 LLM 調用總量、Prompt/Completion 拆分、模型用量、調用類型分佈和最近調用明細。

### 改進

- 為 `DecisionSignal` 補齊默認生命週期、同源窄 relaxed 去重、相反 active 信號自動 invalidated、terminal 狀態不可 PATCH 復活和低敏 market phase hints 提取。
- 補充 Web decision-signals typed API wrapper 與契約隔離測試，並將歷史報告 AI 建議查詢收口到精確報告懶提取。
- DSA 數據源鏈路新增 Tencent 日 K 直連 fetcher、daily source health 短期熔斷，並升級 AlphaSift 默認 pin/runtime bridge。
- 默認啟用 `DAILY_SOURCE=auto`、Sina snapshot 優先級、候選級 quote context 與 LLM ranking timeout/max tokens 邊界。
- 新增 legacy LLM usage provider/cache telemetry、message HMAC 診斷字段和普通個股分析 legacy message stability audit，不改變公開 Usage API、prompt 或 provider 參數。
- 問股頁移動端策略選擇改為默認收起的按鈕入口，展開後仍可多選策略並在發送後自動收起，減少對對話內容的遮擋。

### 修復

- 修復運行流 live SSE 脫敏、後期 LLM/通知卡片重複、數據源聚合卡片過早成功、Web 首頁窄側欄擠壓股票信息，以及個股分析自動生成大盤上下文時運行診斷互相串擾的問題。
- 修復 AlphaSift 熱點題材 EastMoney 瞬斷且無緩存時的空態、桌面更新熱點緩存保留，以及 `leader_stocks` / `stocks` 雙字段兼容問題。
- 修復 Web AI 建議頁篩選/狀態更新分頁、價格計劃單邊入場價展示、持倉 latest 信號刷新、詳情 JSON 安全渲染和卡片交互語義問題。
- 僅允許歷史報告存在明確 `action` 或可解析動作時才觸發決策信號懶回填，避免 `decision_type=hold` 等統計口徑在建議不明確場景誤回填。
- 修復 #1390 P6 DecisionSignal 在組合風險快照語義和默認聚合通知展示中的遺漏。
- 默認禁用 `/api/v1/intelligence/sources/defaults` 新建源，避免公開示例 NewsNow 實例被默認啟用，同時統一 500 響應細節僅入日誌、響應返回通用錯誤信息。
- Web 股票自動補全、輸入校驗、歷史/任務展示和篩選補齊日韓 Yahoo 後綴代碼、常用日韓股票索引與股票池裸碼解析，避免 `000660`、`005930`、`7203.T`、`005930.KS`、`035720.KQ` 等場景崩潰、誤入 A 股語義或歷史分裂展示。
- 日韓個股分析在本地歷史上下文缺失時會用 YFinance 日線兜底構造 K 線與技術指標上下文，避免報告誤稱日股/韓股核心行情和技術數據不可用。
- 發佈說明生成查詢 PR 作者失敗時保留降級並輸出包含 PR 編號和異常類型的 warning，便於排查 token、權限、網絡或 GitHub API 異常。

### 文檔

- README、完整指南和市場支持文檔補充日股/韓股示例（`7203.T`、`005930.KS`），並明確 `.T/.KS/.KQ` 當前為 YFinance-only MVP。
- 新增 DecisionSignal 決策信號專題文檔，補齊字段/API/Web/告警通知/組合風險/後驗評估、脫敏、遷移與回滾說明，並收口 Web i18n 顯示邊界。
- 補充 AlphaSift 遷移與回退邊界：明確 `ALPHASIFT_INSTALL_SPEC` 顯式覆蓋語義、`requirements.txt + DEFAULT_ALPHASIFT_INSTALL_SPEC` 與運行時兼容邊界。
- 補充資訊源基線文檔，說明 `NEWS_INTEL_*` 配置、NewsNow 自建建議、模型/provider/base URL 不變更邊界，以及禁用或移除情報源變量的回退路徑。

### 測試

- 新增/更新 DecisionSignal 服務、提取、反饋/後驗、摘要、文檔、通知、告警、持倉風險、Web 展示和 label 的迴歸覆蓋。
- 新增/更新 RSS/Atom / NewsNow 情報源服務、API、安全校驗、分析接入和配置兼容測試。
- 新增/更新日韓市場識別、股票索引、YFinance 行情兜底、Web 自動補全和輸入校驗測試。
- 新增/更新 LLM usage、運行流、AlphaSift、發佈說明生成和移動端交互相關回歸。


## [3.22.0] - 2026-06-13

### 發佈亮點

- feat: 新增 DecisionSignal 獨立存儲與 API、運行流快照 API 和 Web 運行流視圖，補齊建議動作結構化字段與歷史/回測展示鏈路。
- feat: AlphaSift 熱點題材鏈路升級為新版合約，支持熱點榜單、題材詳情、發酵路線、概念股詳情、緩存與兜底數據源。
- feat: 個股分析默認注入當日大盤環境摘要，並在高風險/退潮環境下軟化激進買入建議。
- fix: 修復問股歷史追問標的上下文、自選股等價代碼匹配、低質量新聞過濾、運行流脫敏與 AlphaSift 熱點詳情展示等穩定性問題。

### 新功能

- 新增獨立 `DecisionSignal` 存儲、Repository、Service 與 `/api/v1/decision-signals` API，支持來源/市場/股票/動作/期限/階段去重、查詢、續期、狀態更新、懶過期、持倉過濾和敏感信息脫敏。
- 新增分析任務與歷史報告運行流快照 API，提供 lanes、nodes、edges、events、summary 等統一契約，並從任務隊列、運行診斷和 AnalysisContextPack overview 構建脫敏數據流/信息流。
- Web 端為活躍任務、歷史報告和大盤覆盤報告補充運行流視圖入口，支持查看運行摘要、拓撲節點、事件流和基礎排障詳情。
- 新增 AlphaSift 熱點題材鏈路：後端提供 `/api/v1/alphasift/hotspots` 與 `/api/v1/alphasift/hotspots/{topic}` API，Web 選股頁新增熱點題材區域並支持發酵路線與概念股查看。

### 改進

- 個股分析新增按當日/市場複用的大盤環境摘要，普通 Pipeline 與 Agent 分析 Prompt 可讀取低敏大盤背景；新增默認開啟的 `DAILY_MARKET_CONTEXT_ENABLED` 配置，用戶仍可顯式關閉。
- 個股分析與歷史/回測展示新增可選八態 `action` / `action_label` 建議動作字段，保留 `operation_advice` 自由文本和 `decision_type=buy|hold|sell` 統計口徑。
- 補充 Web decision-signals typed API wrapper 與契約隔離測試，暫不接入 UI。
- 完善運行時日誌上下文，補充 logger name、觸發來源、市場統計與實時行情預取鏈路狀態，便於排查調度、API、Bot 和數據源降級路徑。
- 持倉管理頁新增持倉賬戶刪除入口，複用現有賬戶軟刪除接口，誤建賬戶會從默認列表、快照、風險、錄入入口和事件列表隱藏且不物理清理歷史流水。
- AlphaSift 依賴鎖定更新到 `d038c52c468543726fc1fd830b53c27d3f09d6da`，併為新版 last-good snapshot、日線歷史、行業/概念 provider cache、hotspot 榜單、題材發酵路線、概念股詳情、上次成功熱點緩存與 post-analysis 元信息補齊 DSA 運行期和 Web 適配。
- AlphaSift 熱點題材讀取默認優先使用上次成功緩存，手動刷新才實時拉取並覆蓋緩存，實時拉取失敗時儘量回退舊緩存。
- AlphaSift 熱點題材區域改為默認摺疊，展開並選中具體題材後再讀取詳情；發酵路線改為帶時間標記的時間線展示，概念股可點擊進入首頁並直接啟動分析。
- AlphaSift 熱點題材數據鏈路複用同一次東方財富板塊異動快照，並從真實漲跌幅、異動次數和高頻個股推導趨勢分、持續分、階段與龍頭樣本。
- AlphaSift 熱點題材刷新在合約層返回少量或缺少關鍵字段時改用 DSA 東方財富板塊異動直連榜單，忽略少於 3 條的本地熱點緩存，並補齊板塊兜底字段。
- AlphaSift 熱點題材卡片改為更緊湊的多列布局，概念股列表改為獨立“分析”按鈕觸發個股分析；詳情優先合併東方財富成分股、同花順解析和板塊異動龍頭兜底並按日聚合發酵時間線。
- AlphaSift 熱點題材詳情新增 DSA 側 30 分鐘磁盤緩存，重複點開同一題材時複用發酵時間線與概念股詳情；題材事件僅展示 AlphaSift 合約時間線、同花順摘要、已配置新聞搜索或東財板塊異動等真實來源。
- AlphaSift 熱點題材消息催化改為摘要展示：配置 LLM 時優先壓縮為一句題材催化摘要，未配置或調用失敗時回退本地短摘要。
- AlphaSift 熱點題材列表新增可選 `include_details` 詳情預取，Web 默認隨熱點列表批量帶回 Top 題材發酵路線與概念股並複用前端內存緩存；新聞催化在 LLM 不可用時改為本地事件歸納。
- 改造 `main.py --webui-only` 啟動行為：若 FastAPI 監聽端口已被佔用，啟動即 fail-fast 拋出明確錯誤並退出。

### 修復

- 問股從歷史報告進入後的追問會持續攜帶當前標的，切回或重載已有會話時可從歷史消息恢復基礎當前標的，並由後端阻斷未明確切換時的錯誤股票工具調用、交易所片段和指標縮寫誤路由。
- 自選股加入和刪除按等價股票代碼匹配港股及大小寫美股變體，避免 `00700`、`HK00700`、`00700.HK` 或 `aapl`、`AAPL` 被誤判為不同標的。
- 收緊建議動作 legacy fallback：否定/迴避表達、中文金融上下文、`buy or sell`、多 guard 歧義文本以及英文複合詞不再誤渲染成 action badge；有結構化 `action` 時回測/歷史趨勢等入口按界面語言顯示 action 標籤。
- 股票新聞與多維情報搜索在相關度排序後新增域名無關的准入過濾，剔除下載/安裝包/應用評分頁及成人/招嫖服務垃圾頁，並在同批已有有效標的/行業候選時移除 `score=0` 背景填充項。
- 修復歷史報告運行流快照在混合時區事件時間戳下返回 500 的問題。
- 修復運行流 live SSE 事件未複用快照層遞歸脫敏規則的問題，避免本地路徑、prompt/raw response、代理頭等敏感診斷字段在 refetch 前短暫暴露。
- AlphaSift 熱點題材默認加載在無緩存且舊適配層缺少 `alphasift.hotspot` 模塊時返回空態，不再一打開選股頁就顯示 AlphaSift 未就緒；手動刷新仍會提示依賴需更新。
- 為 THS 發酵路線補充列名兜底：當 `stock_board_concept_summary_ths` 返回缺列時僅跳過該來源富化，不影響熱點題材詳情 API 返回。
- 桌面發佈打包改用凍結可執行文件運行時探針校驗 `alphasift.dsa_adapter`，避免 macOS PyInstaller 將模塊內嵌進可執行文件時被文件系統/zip 掃描誤判為缺失。
- AlphaSift 熱點題材詳情展示改為優先使用後端融合後的 `route`，避免舊 `timeline` 覆蓋新聞/LLM 摘要；手動刷新熱點榜單時會同步繞過同題材詳情緩存。

### 文檔

- README 與繁中 README 快速開始入口補充視頻教程鏈接，並將桌面客戶端入口文案調整為客戶端配置教程。
- 補充 `docs/alphasift-integration.md`：明確 AlphaSift 鎖定 commit 來源、Hotspot 契約邊界、LLM/LiteLLM 兼容語義與關閉開關下回退路徑。
- 補充 #1381 運行時範圍、兼容邊界、官方語義依據與常規發佈回滾說明。

### 測試

- 覆蓋 #1381 後端 runtime 與兼容核驗：`tests/test_main_schedule_mode.py`、`tests/test_pipeline_daily_market_context.py`、`tests/test_daily_market_context.py`、`tests/test_daily_market_context_guardrail.py`、`tests/test_agent_executor.py`、`tests/test_config_env_compat.py`、`tests/test_config_registry.py` 與 `apps/dsa-web/tests/system_config_i18n.test.ts`。
- 新增/更新 AlphaSift 後端迴歸：`python -m pytest tests/test_alphasift_api.py -q`、`python -m pytest tests/test_docker_entrypoint.py -q`、`python -m pytest tests/test_main_schedule_mode.py -q -k "start_api_server_fails_before_thread_when_port_is_busy"`。

## [3.21.0] - 2026-06-07

### 發佈亮點

- feat: 新增 Web UI 中英文界面語言切換和飛書 App Bot 通知模式，提升多人部署和企業通知場景體驗。
- feat: 大盤覆盤報告、歷史入口和個股欄繼續收口到結構化數據與統一 Markdown/GFM 渲染，Web/API 人工觸發入口不再被交易日 gate 短路。
- feat: AlphaSift 選股鏈路改為可恢復後臺任務，並完善 DSA LLM runtime bridge、默認適配層預置和兼容迴歸。
- fix: 修復英文界面殘留中文、診斷展示、運行時環境變量展示、健康檢查、桌面更新路徑、工作流變量讀取和多處 Web 窄佈局問題。

### 新功能

- WebUI 新增獨立界面語言狀態與中英文切換入口，覆蓋主導航、首頁、登錄、設置頁和通用控件文案；UI 語言與 `report_language` 解耦，不改寫報告語言鏈路。
- 飛書通知新增應用機器人（App Bot）模式，支持通過 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_CHAT_ID` 配置，無需額外創建自定義機器人。
- Web 大盤覆盤報告新增專用展示視圖，歷史入口和首頁即時結果統一使用 Markdown/GFM 渲染並隱藏個股專屬模塊。
- 大盤覆盤新增結構化 `market_review_payload`，Web、歷史詳情和推送統一基於結構化數據渲染，並保留 Markdown 兼容展示。
- 新增默認關閉的 AlphaSift 選股頁籤，通過 `ALPHASIFT_ENABLED` 明確控制，並保留 `/install` 作為顯式修復路徑。

### 改進

- Web/API 大盤覆盤人工觸發入口不再因交易日檢查或相關市場休市而短路跳過；定時任務、GitHub Actions 手動運行和 CLI 默認入口仍保持原交易日 gate。
- AlphaSift Web 選股改為後臺任務提交與狀態輪詢，新增可恢復任務狀態展示，避免外部快照、行情或 LLM 變慢時瀏覽器長請求超時。
- AlphaSift 選股 API 與服務層收斂到 `AlphaSiftService`，endpoint 僅做路由參數接收與錯誤映射。
- AlphaSift 與 DSA 的運行時 LLM 兼容橋接改為調用期注入，保留 `provider/model/base_url/custom headers/fallback` 語義鏈路，不做持久化遷移。
- Web 首頁側欄不再單獨展示大盤覆盤歷史集合，最新大盤覆盤作為 `MARKET` 併入個股欄，按最近分析時間參與排序，並複用個股欄的選擇、刪除、完整報告與歷史趨勢查看能力。
- 多股通知報告將市場階段收斂為總覽下方單行 `市場狀態`，不再在每隻股票摘要下重複展示數據質量和限制詳情。
- API 錯誤響應構造收斂到共享 helper，保持既有錯誤 envelope 形狀並降低 endpoint 重複代碼。
- WebUI 綁定公網地址或 CORS 全開放且未啟用管理員認證時新增運行時 warning；僅增加可觀測性，不阻斷啟動、不改寫配置。
- 數據庫初始化新增 `schema_migrations` baseline 標記表與冪等記錄，用於後續 schema 演進追蹤；不遷移、不清理、不改寫既有業務表數據。
- #1386 P6 複用市場階段與 AnalysisContextPack 公開摘要聯動告警、持倉手動分析、歷史、回測和通知展示，不新增數據庫遷移。

### 修復

- Web 英文界面補齊回測、組合風險與告警規則相關文案本地化，避免英文模式下殘留中文篩選器、按鈕和枚舉標籤。
- 綜合情報搜索中的機構分析與業績預期維度改用 180 天 provider 請求窗口，避免默認短新聞窗口漏掉財報、研報等週期性財經材料。
- Web 個股欄和歷史卡片在窄佈局下不再讓市場階段標籤遮擋股票名稱。
- 問股自由文本追問不再將 TTM、PE、YOY 等金融縮寫誤識別為新股票代碼。
- [修复] GitHub Actions 每日分析工作流讀取 SearXNG 自建實例地址時支持 Variables 優先、Secrets 回退，修復僅配置 Variables 時 URL 不生效的問題。
- Web/桌面端左側導航選中態改用 border 實現，避免藍色豎條指示器溢出側欄邊界；側欄展開寬度 116px -> 136px，新增 rail 緊湊模式。
- Windows 桌面端自動更新安裝目錄不再預先加引號，避免帶空格路徑在自動安裝時觸發“缺少快捷方式 / 找不到 Daily Stock Analysis.exe”的系統彈窗。
- Agent 分析路徑生成 AnalysisContextPack overview 前複用已落庫日線分析上下文，避免日線已抓取成功仍顯示 `daily_bars_missing`。
- 修正大盤覆盤結構化 `breadth` 的可用性判斷：當市場不支持或抓取失敗時不下發 `breadth`，前端展示“暫無數據”，避免誤導性 0 值。
- 大盤覆盤語言行為遵循全局 `report_language`，並在美股中文場景下本地化市場標籤與策略藍圖，避免混入英文策略段落。
- Docker Web 設置頁讀取配置時在活躍 `.env` 文件缺項時回退展示啟動注入的同名環境變量，並補清相關掛載邊界文檔。
- 報告頁運行診斷會區分數據源抓取成功與進入 LLM 分析輸入，相關新聞區標註為報告頁補充/後續檢索資訊，避免與輸入數據塊狀態互相誤讀。
- `/health` 根路徑健康檢查現在始終返回 JSON，避免靜態 Web fallback 吞掉健康探針；`/api/health` 與 `/api/v1/health` 繼續保持兼容。
- `ALPHASIFT_ENABLED` 關閉時不觸發 `alphasift` 運行時注入；開啟後優先複用已配置的 DSA/provider 配置並注入 `LITELLM_*` 與 `LLM_*` 運行時變量。
- 補齊 openai-compatible 場景下 base URL、`extra_headers` 與 `LITELLM_FALLBACK_MODELS` 的兼容路徑與回退鏈驗證。
- 桌面/鏡像打包鏈路保持與運行時一致的 AlphaSift 適配層預置，避免 `pip install` 作為線上修復依賴。

### 文檔

- 明確 Issue #777 UI 語言切換採用倉內 `UiLanguageContext` + `uiText` 實現，持久化 key 為 `dsa.uiLanguage`，並補充對應可視化驗收指引。
- 明確大盤覆盤展示鏈路、結構化 payload、語言行為、交易日 gate 差異和回滾邊界。
- 補充 LLM / LiteLLM 兼容鍵在 Settings 展示與校驗上下文中的回退邊界，說明不改寫、不遷移、不清理用戶現有 provider/model/base URL 持久化配置。
- 補齊 #1602 運行診斷口徑修復覆蓋範圍，說明僅統一輸入與展示口徑，回滾方式為常規發佈回滾。
- 明確 AnalysisContextPack P6 文檔、遷移與回滾邊界，並同步既有 `SAVE_CONTEXT_SNAPSHOT` 到 `.env.example`、配置註冊表、Web 設置幫助和完整指南。
- 補齊 #1386 P7 盤前/盤中/盤後分析的入口、遷移、回滾和用戶可見說明。
- 為 AlphaSift runtime bridge 增加官方兼容依據落點，明確 provider/model/base_url/extra_headers/fallback 與回退邊界。

### 測試

- Web 方向執行 `npm run lint`、`npm run build`、相關 Vitest 和 smoke 命令；未設置 `DSA_WEB_SMOKE_PASSWORD` 時 smoke 用例按設計 skip。
- Web 測試運行時聲明 Node `>=20.19.0 <27` 與 npm `>=10`，並補 localStorage 測試兜底以穩定 Vitest。
- 增補 AlphaSift runtime bridge 與打包腳本靜態驗證，覆蓋 `LLM_CHANNELS`、`LITELLM_FALLBACK_MODELS`、`alphasift.dsa_adapter`、`--collect-all alphasift`。

### chore

- 移除隨 issue / PR 驗收流程誤入庫的截圖資產，並明確一次性截圖證據應保留在 PR 描述、評論、附件或 artifact 中，不作為倉庫文件合入。

## [3.20.0] - 2026-06-03

### 發佈亮點

- feat: 新增 AlphaSift 選股入口、自動安裝與穩定適配層，支持 Web 策略執行、LLM 重排展示和默認關閉的可控啟用。
- feat: 完善個股歷史、自選隊列、市場階段與 AnalysisContextPack 可見性，增強 Web 報告和 API 的結構化上下文能力。
- feat: MiniMax 默認模型升級到 `MiniMax-M3`，並補齊相關價格、預設和測試覆蓋。
- fix: 修復健康檢查、Windows 桌面更新與首次運行編碼、ETF 日線 secid、LLM base_url 校驗和 Agent 日線上下文誤判等穩定性問題。

### 新功能

- 新增默認關閉的 AlphaSift 選股頁籤，通過 `ALPHASIFT_ENABLED` 開啟後經由穩定適配層讀取策略並執行選股。
- Web 首頁左側欄改為個股欄，按股票去重展示，大盤覆盤置頂，點擊個股加載最新報告，支持按代碼變體（.SZ/.SH/.SS）歸一化去重合並。保留全選、批量刪除和刪除確認入口；新增按股票代碼批量刪除 API `DELETE /api/v1/history/by-code/{stock_code}`。
- 報告詳情右側欄新增自選操作入口，支持查看當前股票是否在自選隊列、一鍵加入或移除；大盤覆盤報告不顯示該操作。
- 問股頁面輸入區上方新增自選操作按鈕，用戶發送包含股票代碼的消息後自動顯示加入自選/從自選刪除入口。
- Web 報告頁新增同股歷史趨勢抽屜入口，歷史列表摘要補充趨勢、摘要、模型和分析時行情字段，支持按當前股票查看歷史分析並加載更多。
- AnalysisContextPack P4 低敏 overview 接入歷史詳情、同步分析響應、completed 任務狀態和 Web 報告頁，展示數據塊狀態、來源、缺失原因與降級摘要。
- #1386 P5 為個股分析報告新增 `dashboard.phase_decision` 盤中決策護欄，並在保存歷史前按市場階段與數據質量限制高置信盤中買賣結論。
- #1386 P4a 新增 `analysis_phase=auto|premarket|intraday|postmarket` API 參數，並在異步任務 accepted、內存 status、list、SSE 與分析 pipeline 中透傳請求階段。
- #1386 P4b Web 報告頁新增最終市場階段標籤，任務面板展示請求階段，並複用 AnalysisContextPack 低敏數據質量摘要。
- MiniMax 渠道模型列表升級：新增 `MiniMax-M3` 並作為默認，按官方 OpenAI-compatible 文檔支持 1M 輸入上下文（項目保守註冊為 `<=512K` 價格檔：context_window 512K、`max_tokens` 128K，對應 $0.6/M 輸入、$2.4/M 輸出，>512K 輸入價格檔未建模），保留 `MiniMax-M2.7` 與 `MiniMax-M2.7-highspeed`，並保留 `MiniMax-M2.5` legacy 價格條目以兼容現有用戶配置的成本估算。Web 設置頁 MiniMax 預設模型與價格按 M3 刷新。
- 新增 AnalysisContextPack P1 內部契約與脫敏序列化測試。
- 市場階段低敏摘要接入歷史詳情、同步分析響應和 completed 任務狀態的 report metadata。

### 改進

- 首次運行配置校驗補充缺失 AI Key、空 STOCK_LIST、Telegram/郵件成對字段和 Webhook URL 前綴診斷。
- AlphaSift 選股入口在 Web 側邊欄中移動到“問股”下方，貼近 Agent/研究輔助工作流。
- Docker 鏡像構建階段預置默認 AlphaSift 適配層，與桌面發佈包一樣避免運行期額外安裝。
- AlphaSift 選股改為依賴 `alphasift.dsa_adapter` 的穩定接口，Web 策略列表由 AlphaSift 動態提供，不再在前端硬編碼。
- AlphaSift 選股頁補充 Run ID、快照數、過濾後數量、因子和風險詳情，展開候選時展示真實明細，並暫時僅開放當前支持的 A 股市場。
- Web 設置頁新增 AlphaSift 選股開關卡片，可直接開啟或關閉選股頁籤。
- 開啟 AlphaSift 選股時先切換 `ALPHASIFT_ENABLED` 並檢查適配層可用性，缺失時自動調用受控安裝接口，不再要求用戶額外點擊安裝。
- AlphaSift 已開啟但適配層缺失時，策略列表和選股接口會串行化自動安裝鎖定來源，並強制重裝以覆蓋舊版 `alphasift` 包。
- AlphaSift 選股頁合併重複的快照源 fallback 提示，並保留 AlphaSift 自身的 Tushare 優先快照源邏輯。
- AlphaSift 選股頁在 LLM 重排降級時展示 warning/source error/parse error，並避免把本地因子評分誤顯示為 LLM 判斷。
- Web 設置頁不再把 `ALPHASIFT_ENABLED` 作為普通數據源配置項重複展示，該值僅作為“開啟選股”按鈕背後的持久化狀態。
- AlphaSift 關閉時隱藏 Web 左側“選股”導航入口，避免誤導未開啟用戶。
- 補充 AlphaSift 選股自定義策略顯示邏輯，避免未匹配預設項時誤顯示“均衡多因子”。
- 新增 GET /api/v1/history/stocks 端點按 code 分組返回不重複個股列表；新增 GET /api/v1/stocks/watchlist、POST /api/v1/stocks/watchlist/add、POST /api/v1/stocks/watchlist/remove 端點支持自選隊列增刪查。STOCK_LIST 讀寫保持原樣，不做自動歸一化；add/remove 時歸一化比較判斷等價代碼變體。
- 新增 useWatchlist hook 統一管理自選隊列前端狀態，複用 SystemConfigService 的 STOCK_LIST 配置項實現持久化。
- AnalysisContextPack P5 增加數據質量評分、`fetch_failed` 狀態、Prompt 數據限制區塊和 Web 低敏質量展示。
- #1386 P2-full 在 AnalysisContextPack Prompt 數據限制中追加市場階段與降級數據的交叉約束，並修正中文分析 Prompt 的階段化行情標籤。
- 通知報告默認發送路徑恢復既有渠道兼容轉換與分片邏輯，新增 renderer 能力僅保留為未來擴展基礎。
- 關聯板塊缺少類型數據時改為單行展示板塊名稱，避免生成整列 `N/A` 的板塊表格。
- 優化 Web 報告詳情頁信息層級，將輸入數據塊和運行診斷下移為主體內容後的摺疊輔助信息。
- 盤中分析補齊實時行情獲取時間、provider 時間、stale、fallback 與 partial/estimated 標記，供 AnalysisContextPack 映射輸入數據限制。

### 修復

- Agent 分析路徑生成 AnalysisContextPack overview 前複用已落庫日線分析上下文，避免日線已抓取成功仍顯示 `daily_bars_missing`。
- 註冊 /api/v1/health 路由並加入認證豁免，修復該路徑返回 404 以及開啟 ADMIN_AUTH_ENABLED 後健康探針收到 401 的問題。
- Windows 本地首次運行環境檢查兼容非 UTF-8 控制檯輸出，並將 `requirements.txt` 註釋改為 ASCII 以降低默認代碼頁下的依賴安裝失敗概率。
- AlphaSift DSA 適配層默認開啟 LLM 重排，後端顯式請求 `use_llm=True`，選股頁展示 LLM 分數、判斷、覆蓋率和關注項。
- AlphaSift 嵌入 DSA 時複用 DSA 已解析的 LLM 模型、渠道和密鑰配置，避免 Web 已配置 LLM 但選股 LLM 重排仍因缺少 provider key 降級。
- AlphaSift 選股複用 DSA LLM 路由時過濾未聲明的託管 provider 備選模型，並把已聲明渠道模型補入回退鏈，避免殘留 Gemini fallback 覆蓋可用的 DSA 渠道。
- AlphaSift 默認安裝來源改為鎖定 commit 的受信任 GitHub 地址；桌面模式自動安裝不要求管理員會話，非桌面部署要求管理員認證會話，並繼續限制安裝來源。
- 修復 Web 開啟 AlphaSift 時先安裝後寫配置導致默認關閉狀態無法開啟的問題。
- AlphaSift 狀態與安裝接口不再返回 `install_spec` 明文，僅返回 `install_spec_is_default` 等非敏感狀態字段。
- AlphaSift 狀態探測區分可選依賴缺失與非預期異常，異常場景記錄 warning 並返回非敏感診斷信息。
- 調整 AlphaSift 篩選調用兼容：`screen` 以 `max_results` 為主並支持歷史 `max_output` 關鍵詞，同時允許策略透傳以對齊前端手動策略參數。
- AlphaSift Web 選股請求使用獨立長超時，避免開啟 LLM 重排後被通用 30 秒 API 超時提前中斷。
- 桌面端打包階段預置 AlphaSift 並收集適配層，避免發佈包運行時再要求管理員自動安裝。
- AlphaSift 自動安裝僅在 `status` 診斷為 `missing_module` 時觸發（僅模塊缺失場景）；適配層可導入但運行時異常不再自動 `pip install`，而是返回 `424` 並保留診斷，避免把真實運行時故障掩蓋為重裝。
- 收口 Web 中文界面殘留英文文案與設置頁 help 缺口，回測頁改為中文展示，並讓 Web 設置頁僅展示已註冊且帶說明的配置項。
- Windows 桌面端自動更新靜默安裝時顯式複用當前安裝目錄，避免自定義安裝目錄場景下卸載舊版本文件失敗。
- Windows 安裝器重試舊卸載器時對 `_?=` 安裝目錄參數加引號，修復舊版本安裝在帶空格路徑時返回 2 導致自動更新失敗。
- Windows 桌面端自動更新傳給 NSIS 的 `/D=` 目錄參數在包含空格時自動加引號，避免安裝位置註冊表被截斷。
- 加固 LLM channel base_url 校驗，避免解析差異導致 SSRF 繞過。
- 修正 efinance ETF 日線 Eastmoney secid 路由，避免滬市 ETF 被按深市 quote id 查詢導致日線為空。

### 文檔

- 明確 AlphaSift 與 LiteLLM 兼容邊界：僅橋接 DSA 已聲明 provider/model/base URL 為調用期注入，不對 `.env` 做 provider/model 路由遷移；回退方式為關閉 AlphaSift 並恢復原有 `LITELLM_*`/`LLM_*` 配置。
- 明確 AlphaSift 僅複用 DSA 現有 LLM/LiteLLM 配置語義，不新增 `LITELLM_MODEL`、`OPENAI_MODEL`、`OPENAI_BASE_URL`、`LLM_TIMEOUT_SEC` 等模型語義遷移；失敗提示與回退路徑統一沿用既有系統配置鏈路，僅影響 AlphaSift 選股能力本身。
- 明確 AlphaSift 自動安裝來源鎖定、`missing_module` 與運行時異常行為邊界，以及 LLM/provider/base URL 與自定義通道回退路徑，便於問題溯源與回滾到原有 LLM 配置。
- 明確同股歷史趨勢新增模型字段為歷史快照展示元數據，不影響運行時 LLM Provider/Model/Base URL 路由與配置遷移清理；回退方式為按常規發佈回滾本變更。
- 明確 #1311 的兼容性邊界：渲染層僅消費分析結果 `model_used` 展示字段，未改動 `wechat/slack/feishu/telegram` sender 發送鏈路，不觸發 provider/model/base_url 兼容遷移。
- 明確 AlphaSift 鎖定 commit 的 `alphasift.dsa_adapter` 契約依據，以及當前 DSA API/Web 調用結構的兼容邊界。
- 明確 Settings 頁面對 LLM 配置僅做展示分組與字段歸併，不改寫或觸發 LLM 遷移/回退路徑；兼容現有 `LLM` 配置保存與回退語義。
- 新增 AnalysisContextPack P0 上下文盤點。
- 補齊告警中心 P8 文檔與配置收口說明，明確 legacy JSON、高級規則、Web/API、Docker、GitHub Actions 與 Desktop 邊界。

### 測試

- 同步更新 `llmProviderTemplates`、LiteLLM fallback pricing 與 MiniMax 預設相關單測，斷言新默認模型。
- 補充 ETF 日線數據源路由、輸入變體、fallback 與 MA 字段迴歸覆蓋。

### chore

- 新增通知報告渠道能力畫像、PreparedMessage 與結構感知 Markdown 分片基礎設施，為 #1311 全渠道渲染適配打底。
- 預置企業微信、飛書、Telegram、釘釘、Slack 平臺 renderer 元數據，暫不改變默認推送報告入口和可見版式。

## [3.19.0] - 2026-05-29

### 新功能

- 落地 #1391 Phase 1 運行診斷最小鏈路：任務/SSE 追加 trace_id，並記錄日線與實時行情 ProviderRun 快照。
- 告警中心新增 P7 大盤紅綠燈結構化規則，支持 `market_light_status` 與 `market_light_score_drop` 並複用現有 worker、觸發歷史、通知和冷卻鏈路。
- 落地 #1391 Phase 2 運行診斷摘要：生成用戶可讀 RunDiagnosticSummary，提供歷史報告診斷 API 與脫敏複製文本。
- 落地 #1391 Phase 3 運行診斷可見性：報告詳情和任務面板默認摺疊展示運行狀態、trace 與可複製排障信息；後端通過 `api/v1/history/{record_id}/diagnostics` 與 `context_snapshot.diagnostics` 提供歷史鏈路回填。
- 新增 AnalysisContextPack P1 內部契約與脫敏序列化測試。
- 新增 AnalysisContextPack P2 builder，從普通分析 pipeline 已有 artifacts 組裝內部上下文包。
- 問股新增默認關閉的可見對話上下文壓縮，支持 Web 開關、Agent 高級 preset、滾動摘要和最近輪次原文保護，降低長會話 token 消耗。
- 股票自動補全索引默認支持從 GitHub main 遠程刷新並緩存到本地，Web/CLI 分析入口失敗時自動降級到內置索引，降低摘帽和更名後舊簡稱汙染分析的概率。
- 普通分析與 Agent 運行時 Prompt 接入 AnalysisContextPack 低敏摘要，保持 history/API/Web 輸出兼容。

### 改進

- `scripts/fetch_tushare_stock_list.py` 可對 A 股中帶 `XD`/`XR`/`DR`/`N`/`C` 前綴的名稱進行回填修正，供自動補全刷新流程默認使用。
- Web 路由頁面改為按需加載，降低首包體積並增加路由加載失敗恢復提示。
- Web 完整報告 Markdown 抽屜改為按需加載。
- 新增市場階段推斷基線並明確盤前、盤中、午休、臨近收盤、盤後和非交易日語義。
- 新增運行態市場階段上下文構造與降級測試。
- 設置頁配置幫助階段性補齊 Web 設置頁實際展示/可配置字段的中英雙語文案，覆蓋 Agent、回測、報告、通知路由、系統運行時、AI legacy、數據源和通知高級配置。
- P2-min：LLM Prompt 注入市場階段上下文。

### 修復

- 股票自動補全索引生成缺少 `pypinyin` 時改為直接失敗，避免寫出缺失拼音字段的降級索引。
- 歸一騰訊實時行情成交量為股口徑，避免量能變化倍數被放大並誤導分析報告。
- Docker 默認部署移除 `.env` 單文件掛載，避免 WebUI 保存配置時因 `os.replace` 更新掛載點觸發 `Device or resource busy`。
- 收斂 #1391 Phase 0 A 股代碼歸屬邊界：補齊 `SH`/`SZ` 前綴場景的歸屬一致性，明確 `data_provider/baostock_fetcher.py`、`data_provider/pytdx_fetcher.py`、`data_provider/tushare_fetcher.py` 的本輪修復範圍。
- 修復 `STOCK_LIST` 使用裸 A 股代碼時 Baostock 等數據源 fallback 的內部格式轉換，保持用戶配置繼續使用 6 位股票編號。
- Windows 桌面端自動更新在用戶確認重啟安裝後改為靜默執行安裝器，並在停止內置後端後清理進程引用，降低安裝器提示“每日股票分析無法關閉”的概率。
- macOS 桌面端將運行時配置遷移到用戶數據目錄，並在舊 `.app` 包內文件仍可訪問時遷移 `.env`、數據庫和日誌，避免後續替換升級後重新配置。
- 恢復 Agent/歷史兼容快照中的關聯板塊與板塊聯動字段提取，修復新版首頁報告缺少“板塊聯動”的迴歸問題。
- 修正 Web 設置幫助中 legacy 告警 JSON 字段名與靜默時段投遞語義說明。
- 修復 Web 中文設置頁在數據源、通知、系統與 Agent 區域的配置標題、說明和關鍵下拉選項漏翻問題。
- 修復問股會話切換和首頁任務重連後可能殘留 Agent/分析任務進行中狀態的問題。
- 問股 single-agent 新增 provider-aware trace 分軌，跨輪保留 DeepSeek V4 thinking + tool-call 的 `reasoning_content` 與工具協議材料。
- 為 Akshare 新浪/騰訊 A 股歷史兜底接口增加調用級超時，並補齊 Tushare `605xxx` 滬市代碼路由迴歸測試，避免定時分析因數據源無響應而掛起。
- 將 `exchange-calendars` 依賴下限提升到 `4.13.0`，避免 pandas 3 環境導入交易日曆時因 Timedelta 單位 `T` 失效導致分析失敗。
- 交互式命令（釘釘會話、飛書會話、Telegram）觸發的分析結果只回到來源會話，不再同時廣播到靜態通知渠道。
- 適配 Longbridge OAuth 2.0 認證與 token 緩存恢復，避免新後臺無 Legacy Access Token 時長橋數據源被誤判為未配置。
- Longbridge OAuth 路徑在當前 SDK 不支持 `OAuthBuilder` / `Config.from_oauth` 時明確日誌降級，避免 Linux/Docker 僅可安裝舊 SDK 時構建失敗。
- 兼容 YFinance 日線返回未命名日期索引的場景，避免標準化後缺少 `date` 列導致美股日線 fallback 中斷。

### 文檔

- 新增 #1391 Phase 0 運行診斷契約文檔，明確 trace_id、診斷摘要、關鍵鏈路範圍與脫敏/fail-open/retention 邊界。
- 補齊告警中心 P8 文檔與配置收口說明，明確 legacy JSON、高級規則、Web/API、Docker、GitHub Actions 與 Desktop 邊界。
- 說明本次桌面修復僅覆蓋 Windows NSIS 更新安裝鏈路與後端進程生命週期清理；未改動設置項保存/模型運行時清理語義。移除此前誤入的 `docker/Dockerfile` `npm registry` 變更，恢復部署構建與更新修復的職責隔離。
- 新增 AnalysisContextPack P0 上下文盤點，明確字段質量狀態、現有狀態映射和首版 pack 邊界。
- 明確 #1391 Phase 2 的結構化檢測告警為非配置遷移信號：`agent_max_steps`/`agent_orchestrator_timeout_s` 非法值會 fallback 至默認併產生日誌告警，新增診斷鏈路僅新增 `context_snapshot`/`RunDiagnosticSummary` 讀寫字段，不改寫 `litellm_model`、`agent_litellm_model`、`openai_base_url`、LLM channel 路由或配置遷移語義。
- 補充 #1391 Phase 3 兼容性說明：記錄後端診斷持久化、歷史查詢與通知回寫鏈路變更邊界與回滾策略，並補齊後端門禁級驗證要求。

### 測試

- 收斂 #1391 Phase 3 後端/API 與 Web 迴歸檢查：`./scripts/ci_gate.sh`、`test_pipeline_market_phase_context.py`、`test_analysis_api_contract.py`、`test_analysis_history.py`、`npm run lint`、`npm run build`。
- 執行 `python -c "import exchange_calendars as xcals; xcals.get_calendar('XSHG'); print('ok')"` 通過驗證，以覆蓋導入與交易日曆初始化兼容性。

## [3.18.0] - 2026-05-21

### 發佈亮點

- feat: 告警中心擴展到 P2-P6，補齊後臺評估、真實通知結果、業務冷卻、技術指標規則，以及自選股 / 持倉 / 賬戶聯動規則。
- feat: 個股分析支持策略選擇，新增熱點題材、事件驅動、成長質量和預期重估策略，併為 HK/US 報告補充基本面、財務摘要、股東回報和關聯板塊。
- feat: 新增 Finnhub / AlphaVantage 美股數據源適配器，擴展美股日線 failover 鏈，提升美股行情獲取韌性。
- fix: 修復桌面端發佈打包、分析狀態接口、AlphaVantage 漲跌幅、持倉實時估值、告警歷史去重、數據庫冷啟動和 fallback pricing 註冊等穩定性問題。

### What's Changed

- feat: Add alert-center P2-P6, Web strategy selection, HK/US fundamental context, static-report financial sections, and Finnhub / AlphaVantage US-market fallback.
- improve: Refine LiteLLM parameter recovery, yfinance currency/dividend handling, RSI calculation, market-review presentation, stock-news relevance ranking, and report table rendering.
- fix: Harden desktop packaging/update assets, completed analysis-status responses, AlphaVantage pct_chg routing, portfolio realtime snapshots, alert trigger dedupe, DatabaseManager cold start, and fallback pricing registration.
- docs/tests: Add beginner setup and settings-help docs, document compatibility/rollback boundaries, and extend regression coverage for API, alert, packaging, and release paths.

## [3.17.1] - 2026-05-16

### 發佈亮點

- fix: 桌面端 Windows / macOS 打包腳本顯式關閉 electron-builder 自動發佈，避免 tag 構建時因缺少 `GH_TOKEN` 在本地打包完成後失敗；Release workflow 繼續負責上傳和發佈產物。

### What's Changed

- fix: Add `--publish never` to the Windows and macOS Electron packaging scripts so tag builds only create local artifacts and GitHub Actions handles release upload/publish.

## [3.17.0] - 2026-05-16

### 發佈亮點

- feat: 新增 Alert API MVP，支持告警規則 CRUD、啟停、一次性測試以及觸發/通知結果查詢，首版覆蓋 `price_cross` / `price_change_percent` / `volume_spike` 並保持 legacy 配置兼容。
- feat: 通知網關新增 ntfy 與 Gotify 一等渠道，並補齊通知降噪、靜態渠道隔離、診斷、Web 測試和 GitHub Actions env 對照校驗。
- feat: Windows 桌面安裝版接入自動更新安裝鏈路，支持後臺下載、確認重啟安裝、運行時文件備份/恢復和發佈產物元數據校驗。
- improve: 大盤覆盤新增概念排行、人氣股、漲停池等底層數據源，支持指數漲跌顏色語義配置，並將覆盤結果寫入歷史記錄。
- improve: Web 設置頁支持 `.env` 配置備份導入/導出和通知/Agent 區域局部錯誤兜底；報告新增 `REPORT_SHOW_LLM_MODEL` 開關控制模型信息展示。
- improve: Docker 啟動入口自動修復掛載目錄權限並在日誌目錄不可寫時降級到控制檯，減少普通部署的手動修復步驟。
- fix: 數據源缺憑據或連接失敗時更溫和降級，Longbridge / Pytdx 加入冷卻，資金流缺失時避免輸出高置信買入結論。
- fix: 分析與報告鏈路兼容 OpenAI-compatible `content_blocks` 響應，歸一策略價格字段，並修復大盤覆盤滾動和歷史記錄丟失問題。
- docs: 補齊通知、告警中心、桌面打包、README / 指南和 PR title 治理說明，明確多處配置兼容邊界與回滾路徑。
- test: 增加 Alert API、通知降噪/路由、Docker entrypoint、數據源預取、桌面更新鏈路和分析歷史等迴歸覆蓋。

### What's Changed

- feat: Add an Alert API MVP with rule CRUD, enable/disable, one-shot testing, trigger history, notification results, and legacy config compatibility.
- feat: Promote ntfy and Gotify to first-class notification channels with Web tests, routing, Actions integration, diagnostics, and noise control.
- feat: Add the Windows desktop auto-update install flow with runtime state backup/restore and release artifact metadata verification.
- improve: Extend market review data sources, add configurable index color semantics, and persist market review results into analysis history.
- improve: Add Web `.env` backup import/export, local settings panel error boundaries, and a report model visibility toggle.
- improve: Harden Docker startup by repairing mounted directory permissions and falling back to console logging when mounted logs are not writable.
- fix: Cool down unavailable optional fetchers, reduce noisy Longbridge/Pytdx retries, and downgrade buy advice when capital flow data is missing.
- fix: Handle OpenAI-compatible `content_blocks`, normalize strategy price fields, and recover market review scrolling/history behavior.
- docs/tests: Update notification, alert, desktop packaging, README/guide, and governance docs; add focused regression coverage for the new release paths.

## [3.16.0] - 2026-05-10

### 發佈亮點

- feat: Web 首頁新增“大盤覆盤”觸發入口、任務輪詢與完成後報告直出；首次啟動配置狀態可提示缺口並引導到系統設置。
- feat: 新增通知路由策略，支持按 report、alert、system_error 將通知收窄到指定渠道；Web 設置頁支持通知渠道一鍵測試。
- feat: 系統設置頁新增配置項幫助入口與多語言幫助文案基礎設施，首批覆蓋自選股、LLM 主模型、LLM 渠道、飛書 Webhook 與 WebUI 監聽地址。
- improve: 大盤覆盤 API、CLI、Bot 共用 `build_market_review_runtime` 裝配路徑，補齊 `litellm_model` / `llm_model_list` 與 legacy key 回退說明。
- improve: 個股報告操作建議結合支撐/壓力、量能、籌碼與主力資金流校準，減少買入/賣出劇烈切換，並補強 Agent 決策兜底。
- improve: Docker 鏡像支持非 root 用戶運行，LiteLLM 依賴約束放寬到後續安全 1.x 修復版本。
- fix: 修正 LLM 渠道測試中 `Model disabled`、provider blocked 等錯誤分類，避免被誤報為網絡異常。
- fix: 港股日線跳過不支持港股的內置歷史數據源；北交所 `BJ` 前綴與 `.BJ` 後綴代碼校驗保持一致。
- fix: Web 大盤覆盤按鈕可觀測性、Windows fallback 鎖進程探測和催化線索展示更穩健。
- docs: 新增文檔中心與配置幫助維護說明，清理 README、完整指南與配置指南中的臨時 PR/文檔同步說明。

### What's Changed

- feat: Add a Web home market-review trigger with task polling and inline report display; setup status now points users to missing configuration.
- feat: Add notification routing by report, alert, and system_error; add one-click notification channel testing in Web settings.
- feat: Add settings field help infrastructure with multilingual help text for the first batch of core configuration fields.
- improve: Share `build_market_review_runtime` across API, CLI, and Bot market review paths; document `litellm_model` / `llm_model_list` and legacy key fallback behavior.
- improve: Calibrate stock advice with support/resistance, volume, chips, and main-force capital flow; strengthen Agent decision fallback behavior.
- improve: Run Docker images as a non-root user and relax LiteLLM constraints to allow safe future 1.x fixes.
- fix: Classify `Model disabled`, provider blocked, and related LLM channel test errors more accurately instead of reporting them as generic network failures.
- fix: Avoid unsupported built-in historical providers for Hong Kong daily data; align Beijing Stock Exchange `BJ` prefix and `.BJ` suffix validation.
- fix: Improve Web market-review observability, Windows fallback lock probing, and market catalyst snippet rendering.
- docs: Add the documentation index and settings-help maintenance guide; remove temporary PR/doc-sync notes from README and user-facing guides.

## [3.15.0] - 2026-05-05

### 發佈亮點

- LLM 渠道配置體驗繼續升級：新增 Anspire OpenAI-compatible 網關接入，並補齊常用服務商預設、官方來源、能力標籤、配置注意事項和 GitHub Actions 顯式映射。
- Web LLM 配置檢測更可診斷：細分錯誤 reason，並支持用戶顯式觸發 JSON、tools、vision、stream 運行時 smoke。
- LLM 運行時配置清理更穩健：只清理託管 provider 的失效運行時選擇，並保留 `cohere/*`、`google/*`、`xai/*` 等直連 provider 兼容語義。
- 通知與 Bot 狀態可觀測性增強：自定義 Webhook 支持 JSON body 模板，Bot `/status` 展示更完整的 LLM、Agent 與通知渠道狀態。
- 大盤覆盤、實時告警、Agent weak 兜底和持倉估值繼續補強，降低默認值覆蓋、缺價汙染和配置排障成本。

### 新功能

- 支持 `ANSPIRE_API_KEYS` 默認接入 Anspire OpenAI-compatible 大模型網關，並在 LLM 渠道編輯器補充 Anspire Open 預設。
- 自定義 Webhook 支持 `CUSTOM_WEBHOOK_BODY_TEMPLATE` JSON body 模板，便於適配 AstrBot、NapCat 和自建推送服務。
- 大盤覆盤結構化區塊新增大盤紅綠燈結論，基於盤面溫度輸出 green/yellow/red、核心原因和操作建議。
- EventMonitor 支持 `price_change_percent` 漲跌幅閾值規則，可按上漲或下跌方向觸發實時告警。
- Web LLM 渠道編輯器新增常用服務商配置模板與預設，覆蓋 MiniMax、火山方舟、OpenAI、Claude、Gemini、Kimi、Qwen、GLM、豆包等入口。

### 改進

- Web LLM 配置檢測補充細分錯誤分類，並新增顯式觸發的 JSON/tools/vision/stream 運行時 smoke；默認測試和保存流程不變，檢測結果僅作為當前配置的一次 best-effort 診斷。
- Bot `/status` 展示統一 LLM 主模型、Agent 模型、渠道模式、YAML 配置和更多通知渠道狀態。
- Web LLM 渠道編輯器展示 provider 能力標籤、官方來源鏈接和配置注意事項提示；這些標籤僅用於配置參考，不代表運行時能力已驗證通過。
- 抽出 Web LLM provider preset 單一模板數據源，保持現有配置保存語義不變。
- 補齊 LLM provider channel 在 GitHub Actions 中的顯式映射，並同步 `.env` 示例與配置文檔。

### 修復

- Agent weak 完整性兜底在模型缺少評分、趨勢、操作建議或 dashboard 關鍵塊時優先保留本地趨勢分析結果，並只補齊真正缺失的儀表盤字段，避免首頁評分被默認 50 覆蓋。
- 統一持倉快照輸出現價、市值、浮盈虧、收益率與價格元信息，避免缺價或 stale 價格汙染持倉估值。
- LLM 渠道測試補充結構化診斷與設置頁排障提示，便於定位 provider、模型、Base URL 和鑑權配置問題。
- 明確 runtime 清理兼容邊界：僅對託管 provider（`gemini`、`vertex_ai`、`anthropic`、`openai`、`deepseek`）觸發保存前失效值清理，`cohere/*`、`google/*`、`xai/*` 直連值按 legacy 兼容路徑保留，不做無提示遷移或覆寫。
- 將 MiniMax 預設調整為官方 OpenAI-compatible Base URL 和當前模型示例，並補充 MiniMax、火山方舟、LiteLLM 兼容來源與回退說明。
- 移除截圖識別對 Gemini 3 Vision 模型的過時降級邏輯，默認推斷改用當前 Gemini 模型配置。

### 文檔

- 完善 LLM provider 配置文檔，補充配置方式選擇、Actions 變量對照、運行時檢測邊界、錯誤 reason 排障和回滾路徑（#1180）。
- 補充 LLM 渠道編輯器的官方來源、依賴兼容窗口、保存時的運行時模型清理規則，以及舊配置回退路徑說明。
- 為 `cohere/*`、`google/*`、`xai/*` 直連語義補充官方 provider/model 說明、`litellm>=1.80.10,<1.82.7` 兼容依據引用，並明確示例模型名僅為配置保留行為說明而非可用性背書。
- 明確 `price_change_percent` 事件告警僅為配置與運行時規則擴展，未變更模型/provider/base URL/LiteLLM 兼容語義；回退路徑為關閉/移除 Event Monitor 配置。
- 同步 README、DEPLOY、full-guide、Anspire、AIHubMix 與 SerpAPI 相關說明，統一外鏈、配置口徑和評審一致性說明。

### 測試

- 補齊 AI 配置頁與 `task_queue` 的 LLM 運行時清理/同步迴歸證據：恢復渠道模型時保留 fallback、編輯模型列表期間不靜默清空運行時選擇，渠道無可用模型時清理失效 runtime 引用，並覆蓋 legacy key 與 `cohere/*`、`google/*`、`xai/*` 直連 provider 保留語義。
- 覆蓋 Web LLM 配置檢測的細分錯誤分類，以及 JSON、tools、vision、stream 運行時 smoke 的顯式觸發路徑。

## [3.14.2] - 2026-04-30

### 發佈亮點

- 大盤覆盤擴展到港股，並讓 Bot `/market` 與 CLI/調度入口使用一致的交易日過濾語義。
- 問股與 Agent 鏈路增強配置缺失、決策 fallback 和多策略選擇體驗。
- LLM 與分析報告鏈路提升穩定性：非法 JSON 響應會繼續嘗試備用模型，LiteLLM DEBUG 日誌默認降噪。
- 新增只讀首次啟動配置狀態接口，為後續配置嚮導和 smoke run 奠定基礎。

### 新功能

- 大盤覆盤支持港股市場：`MARKET_REVIEW_REGION` 新增 `hk` 選項；`both` 擴展為 A股+港股+美股，並新增港股指數（HSI/HSTECH/HSCEI）覆盤鏈路。
- 新增只讀首次啟動配置狀態接口 `GET /api/v1/system/config/setup/status`，用於識別 LLM、Agent、自選股、通知和本地存儲配置缺口；該接口不會重載運行時、寫入 `.env` 或創建數據庫文件。

### 改進

- 問股頁面支持組合選擇多個 Agent 策略。

### 修復

- Bot `/market` 命令複用 `get_open_markets_today()` / `compute_effective_region()` 做交易日過濾：結果作為 `override_region` 透傳給 `run_market_review`；若結果為空字符串則跳過覆盤並推送“今日相關市場休市”，與 CLI/調度入口行為一致。
- 問股 Agent 在未配置可用 LLM 時保留後端真實錯誤原因並維持 `done.success=false` 失敗語義，避免前端把配置缺失誤當成成功回答。
- Agent 模式未生成有效決策儀表盤時保留本地趨勢分析的評分、趨勢和操作建議，並將強買/強賣 fallback 歸一到兼容的 `buy`/`sell` 決策類型，避免首頁結果被 `50 / 觀望 / 未知` 缺省值覆蓋。
- 持倉快照現價缺失時不再靜默回退為持倉成本；當天快照優先使用歷史收盤價，僅在缺失時使用實時價 fallback，缺價持倉不再汙染市值與未實現盈虧彙總，併為持倉明細返回價格來源、日期、stale 與缺價狀態。
- 分析 Prompt 在注入 `trend_analysis` 前按最終 `trend_status` / `ma_alignment` 清洗互斥理由：空頭結構移除看多理由、多頭結構移除空頭結構風險，並在事件/技術衝突與異常放量（>10 倍）時強制提示“事件先行、技術待確認”與量能降權。
- LLM 返回非 JSON 響應時同樣觸發備用模型切換：主模型成功返回但無法解析 JSON 時，不再立即降級為純文本 fallback，而是依次嘗試 `LITELLM_FALLBACK_MODELS` 中的備用模型；所有模型均無法返回合法 JSON 時，再降級為文本 fallback。
- LiteLLM 內部 DEBUG 日誌默認壓低到 WARNING，避免流式生成時 token 級日誌汙染 `stock_analysis_debug_*.log`；如需排查 LiteLLM 內部細節，可臨時設置 `LITELLM_LOG_LEVEL=DEBUG`（Fixes #1156）。

### 文檔

- 補充 LLM 配置指南與 FAQ，明確問股 Agent 對 `LITELLM_CONFIG` / `LLM_CHANNELS` / legacy `GEMINI_*` `OPENAI_*` `ANTHROPIC_*` 的兼容優先級、回退路徑與“不靜默遷移舊配置”的結論。

### 測試

- 新增 `tests/test_bot_market_command.py`，覆蓋 `MARKET_REVIEW_REGION=both` + open markets `{"cn","us"}` / `{"cn","hk"}` 的 `override_region` 透傳斷言，並覆蓋全市場休市跳過與關閉交易日檢查路徑；新增 `tests/test_yfinance_hk_indices.py` 覆蓋港股指數符號映射與部分/全部失敗降級路徑。
- 補齊 `task_queue` 輕量導入 stub 的股票代碼規範化函數，恢復 `tests/test_task_queue_config_sync.py` 收集與運行。

## [3.14.1] - 2026-04-26
- [测试] 修正大盤覆盤 prompt 測試對“明日交易計劃”標題的斷言，並同步桌面端版本號，恢復發佈 gate。

## [3.14.0] - 2026-04-26

### 發佈亮點

- 📊 **大盤覆盤升級為盤後工作臺式結構** — A 股覆盤固定輸出盤面溫度、指數明細、板塊 Top 表、新聞催化、明日交易計劃和風險提示，減少純文字覆盤的重複與空泛。
- 🖥️ **桌面端新增 GitHub Release 更新提醒** — Windows/macOS 桌面端啟動後自動檢測新版本，也可從設置頁手動檢查並跳轉下載頁。
- 🤖 **Pipeline Agent 數據加載大幅降噪** — K 線工具改為 DB-first 並預熱 240 天曆史數據，避免同一只股票重複 HTTP 請求。
- 🐳 **Docker 發佈鏈路整理** — 發佈工作流收斂為正式發佈與手動補發兩條路徑，官方 Docker Hub 鏡像名統一為 `zhulinsen/daily_stock_analysis`。
- 🔧 **LLM 渠道與 DeepSeek V4 配置補強** — GitHub Actions 定時分析補齊多渠道變量透傳，DeepSeek 官方渠道預設與示例同步到 V4。
- 🧩 **桌面端靜態資源一致性校驗** — 打包鏈路和運行時都能更早發現靜態資源錯配，降低 Release 包白屏排查成本。

### 新功能

- 🏠 **Web 首頁歷史報告區新增重新分析入口** — 支持基於原始 prompt 重做同一只股票同日期的分析。
- 🖥️ **Windows/macOS 桌面端新增 GitHub Release 更新提醒** — 啟動後自動檢測新版本，並支持從設置頁手動檢查後跳轉下載頁。

### 改進

- 📊 **A 股大盤覆盤報告改為結構化盤後工作臺版式** — 固定輸出盤面溫度、指數明細、板塊 Top 表、新聞催化和明日交易計劃。
- 🐳 **Docker 發佈工作流收斂** — 更清晰地區分正式發佈與手動補發鏈路，並統一官方 Docker Hub 鏡像名為 `zhulinsen/daily_stock_analysis`。
- 🤖 **Agent 日線工具優先複用本地緩存** — 同時持久化新獲取的日線與新聞情報，減少重複數據源調用。

### 修復

- 🤖 **Pipeline Agent K 線工具 DB-first 加載** — `get_daily_history` / `analyze_trend` / `calculate_ma` / `get_volume_analysis` / `analyze_pattern` 改為優先讀取本地 DB，消除同一只股票 9x5=45 次重複 HTTP 請求（Fixes #1066）。
- 🤖 **Pipeline Agent 執行前按需預熱 240 天 K 線歷史到 DB** — 正常情況下 K 線工具調用無需重複網絡請求。
- 🕒 **凍結 `target_date` 並通過 ContextVar 透傳到 Pipeline Agent K 線工具線程** — 消除跨收盤邊界時間漂移。
- 🪟 **Windows 桌面端後端日誌轉抄編碼修復** — 轉抄 stdout/stderr 時優先使用 UTF-8，併兼容本地代碼頁回退，避免中文日誌亂碼。
- ⚙️ **GitHub Actions 每日分析工作流補齊 LLM 渠道變量透傳** — 支持 `LLM_CHANNELS`、多 Key 與常用 `LLM_<NAME>_*`，避免本地可用的多模型配置在雲端定時任務中失效（Fixes #1063, #872）。
- 📈 **歷史報告詳情接口修正 `change_pct` 取值** — 使用 `is None` 判斷避免把 0.0（平盤）當作缺失值丟棄，移除錯誤的 `change_60d` 兜底，並在缺失時回退到原始實時行情字段（Fixes #1084）。
- 🔧 **DeepSeek 官方渠道預設與示例配置同步到 V4** — 保留 legacy `deepseek-chat` 默認值並增加廢棄提示，同時修正模型發現後舊運行時選擇導致保存失敗的問題（Fixes #1108, #1109）。
- 🧩 **桌面端打包鏈路新增靜態資源一致性檢查** — `scripts/check_static_assets.py` 會在源 `static/` 與 PyInstaller 產物中校驗 `index.html` 引用的資源是否真實存在，運行時也會在錯配時寫入明確日誌，避免重現 Release 包打開後白屏（Refs #1064 / #1065 / #1050）。
- 🧩 **後端 `/assets/*` 改為顯式路由託管** — 資源缺失時返回與請求擴展名匹配的 `text/javascript` / `text/css` 404，減少默認 JSON 錯誤響應帶來的排查誤導（Refs #1064）。
- 🌙 **`kimi-k2.6` 自動使用固定溫度** — 主分析、大盤覆盤和 Agent 調用該模型時自動使用 `temperature=1.0`，避免模型拒絕默認溫度請求（Fixes #1102）。

### 文檔

- 🐳 **補充官方 Docker 鏡像使用說明** — 增加鏡像拉取、`docker run` 用法與 `.env` / 數據目錄映射說明，不再只覆蓋 Compose 部署路徑。
- 📨 **修正飛書自定義機器人 Webhook 示例** — `feishu_sender.py` 中的示例改為 interactive card JSON，並補充飛書自動化 Webhook 觸發器配置教程。
- 📚 **優化根 README 結構** — 保留首頁級功能特性、技術棧、快速開始、推送效果、Web、Agent、贊助商和新聞源入口，將細配置、交易紀律和基本面語義收口到完整指南，並將 Docker 徽章指向官方鏡像頁。
- 🌐 **同步英文與繁中 README 的精簡入口結構** — 同時補齊完整指南中的 LLM 用量 API 與持倉管理說明。
- 🤝 **調整 AI 協作與 PR 模板中的 README 維護規則** — 明確 README 非必要不更新，細節優先進入專題文檔。

### 測試

- 🧪 **穩定市場覆盤相關測試的 LiteLLM stub 行為** — 避免本機安裝的 LiteLLM 在測試收集順序變化時影響市場覆盤單元測試。
- 🧪 **pytest 默認跳過前端依賴目錄** — 本地存在 `apps/dsa-web/node_modules` 時不再被後端測試遞歸掃描，避免發佈前 gate 被無關目錄拖慢。

## [3.13.0] - 2026-04-21

### 發佈亮點

- 🌉 **長橋 OpenAPI 數據源接入** — 美股/港股行情優先使用 Longbridge，YFinance / AkShare 自動兜底；未配置時行為不變。
- 📈 **Tushare 港股全鏈路擴展** — 港股日線通過 `hk_daily` 獲取；籌碼分佈對港股返回 `None`；換算單位跟隨港股口徑，不再套用 A 股手/千元規則。
- 🔍 **Anspire Search 語義搜索接入** — 配置 `ANSPIRE_*` 後即可使用 Anspire Search 獲取實時行情及資訊，未配置時完全透明。
- 🚀 **普通分析鏈路支持 LLM 流式生成** — 首頁任務 SSE 新增 `task_progress` 事件，進度更細化；不支持流式的 provider 自動回退到非流式調用。
- 🤖 **Web 渠道編輯器支持按需拉取可用模型列表** — `/v1/models` 統一模型發現入口，多選寫回 `LLM_{CHANNEL}_MODELS`，拉取失敗時保留手動輸入降級。
- 🛡️ **Agent 穩定性與預算護欄全面補強** — `AGENT_MAX_STEPS` 語義統一、技能降級不中斷管線、SSE 異常透傳、技能加載 warning 日誌補齊。
- 🛠️ **SQLite 寫入鏈路原子化** — 批量原子 upsert + WAL + `busy_timeout` + 有限寫入重試，顯著降低批量分析併發鎖競爭。

### 新功能

- 🌉 **集成 Longbridge OpenAPI 作為美股/港股可選數據源**（fixes #981）— 配置 `LONGBRIDGE_*` 後優先使用長橋獲取日線與實時行情，YFinance / AkShare 兜底；未配置時行為與此前一致。聯調使用 `tests/longbridge_live_smoke.py`（手動腳本，不參與 pytest 收集）。
- 📈 **Tushare 支持港股日線查詢** — 配置 Tushare 憑證後調用 `hk_daily` 接口獲取港股數據；權限不足時拋出異常，與原流程一致。
- 🔍 **集成 Anspire Search 可選語義搜索後端** — 配置 `ANSPIRE_*` 可使用 Anspire Search 獲取實時行情及新聞資訊；未配置時行為與此前一致。聯調使用 `tests/test_anspire_search.py`（手動腳本）。
- 🚀 **普通分析鏈路支持 LiteLLM 流式生成與更細任務進度** — 股票分析在 LLM 階段優先嘗試 `stream=True` 並在服務端累積 chunk，首頁任務 SSE 新增 `task_progress` 事件與更細的 `message/progress` 更新；僅在最終 JSON 解析成功後持久化歷史報告；不支持流式的 provider 自動回退到非流式調用。
- 🤖 **Web AI 模型配置支持按渠道獲取可用模型列表** — 渠道編輯器支持調用 `/v1/models` 拉取可用模型，並以多選方式寫回 `LLM_{CHANNEL}_MODELS`；拉取失敗時保留手動輸入作為降級路徑。

### 改進

- 🔎 **SerpAPI 正文補抓範圍收斂** — 自然搜索結果不再逐條同步抓取網頁正文；僅對極少數高位且摘要不足的結果做延遲補抓，優先複用 SerpAPI 已返回的結構化摘要，降低搜索鏈路尾延遲與慢站點放大風險。
- 🤖 **LLM 接入體驗簡化** — 面向用戶的 AI 模型接入文案統一為"主模型 / Agent 主模型 / 備選模型 / 模型渠道"，不再把 LiteLLM 當作普通用戶必學概念，現有 `LITELLM_*` / `LLM_CHANNELS` 配置鍵保持兼容。
- 🧠 **IntelAgent 新增公司公告搜索與主力資金流工具** — 增加上交所/深交所/cninfo 公告搜索維度與 `get_capital_flow` 工具，修復 Agent 模式下公告和資金流數據經常缺失的問題。
- 📦 **後端股票名稱解析優先複用 `stocks.index.json`** — 懶加載緩存前端靜態索引，純後端/缺失靜態資源場景靜默降級回 `STOCK_NAME_MAP` 與原有數據源回退鏈路。
- 📊 **TushareFetcher 港股單位適配** — `get_chip_distribution` 對港股直接返回 `None`（港股暫不支持籌碼分佈）；`_normalize_data` 對港股（`hk_daily`）不再做 A 股手→股、千元→元的縮放，與 Tushare 港股字段語義一致。
- ⏱️ **Agent 超步數錯誤增加 `AGENT_MAX_STEPS` 調整提示** — 幫助用戶自助排查步數限制問題。
- ⚙️ **GitHub Actions 分析任務超時支持 `vars` 配置** — `daily_analysis.yml` 任務超時從 repository variables 讀取，無需修改代碼即可調整運行超時上限（fixes #1014）。

### 修復

- 📣 **大盤覆盤鏈路接入 `REPORT_LANGUAGE`** — `REPORT_LANGUAGE=en` 時，A 股/合併覆盤的 Prompt、章節標題、模板兜底文案與通知包裝標題統一輸出英文，避免英文正文搭配中文標題的混排問題。
- 📈 **EfinanceFetcher 指數開盤價映射兼容**（fixes #1043）— `get_main_indices()` 的開盤價映射改為兼容 `今開 → 開盤 → open`，修復部分 efinance 版本下指數開盤價被讀成缺失值的問題。
- 🤖 **AGENT_MAX_STEPS 語義統一**（fixes #1026）— 在 orchestrator 多 Agent 模式下明確為"各子 Agent 步數上限而非硬覆蓋"；TechnicalAgent 等高默認值 Agent 會被封頂，低默認值 Agent 保持原值；用戶主動調高（>10）時統一覆蓋所有子 Agent。修復了用戶設置 12 但 TechnicalAgent 仍以默認 6 步運行並報 "Agent exceeded max steps" 的問題。
- 🛡️ **Specialist（Skill）Agent 失敗改為優雅降級** — 技能 Agent 失敗不再中斷整個分析管線，與 intel/risk 保持相同的降級策略。
- 🔧 **MiniMax-M2.7 連接測試修復** — 修復 LLM 通道連接測試在 MiniMax-M2.7 下返回 "Empty response" 的問題；將 `max_tokens` 上限從 8 提升至 256 以容納思考過程，並添加 `content_blocks` 格式解析邏輯。
- 📊 **移除 `sentiment_score` 範圍約束**（fixes #942）— 移除 `HistoryItem` 與 `ReportSummary` 響應 Schema 中 `sentiment_score` 的 `ge=0/le=100` 約束，歷史庫中存儲的超範圍值不再觸發 Pydantic ValidationError。
- 🖥️ **WebUI 前端資源缺失時發出明確警告** — `webui_frontend.py` 在 `static/index.html` 存在但 `static/assets/` 缺失時發出 warning，避免 CSS/JS 資源缺失導致頁面異常變大卻無從排查（fixes #944）。
- 🔗 **分析管線可選服務降級初始化** — `StockAnalysisPipeline` 搜索服務與社交輿情服務任一初始化異常時，記錄 warning 並以禁用狀態繼續運行，避免外部依賴抖動阻塞主分析鏈路。
- 🖥️ **桌面端版本展示統一讀取 `package.json`** — 統一讀取 `apps/dsa-desktop/package.json`，移除 preload 中硬編碼的 `0.1.0`，設置頁展示真實桌面端版本；修復版本號顯示錯誤（fixes #1048）。
- 🐋 **港股名稱獲取失敗修復**（fixes #940）— 修復主數據源字段缺失時無法正確回退到備用字段獲取港股名稱的問題。
- 🔄 **SSE 任務流斷開時 `CancelledError` 正確 re-raise**（fixes #967）— 修復 SSE 流中斷時異常被靜默吞掉導致故障無日誌可查的問題。
- 🔄 **Agent SSE 清理階段後臺任務異常正確上報**（fixes #969）— 流結束時後臺執行器異常現在正確記錄並上報，避免錯誤無法感知。
- 🔇 **技能加載異常補充 `logger.warning` 日誌**（fixes #970）— 在 `ask.py`、`skills/aggregator.py`、`skills/router.py` 的靜默 except 塊補充日誌，確保技能列表為空時有日誌可查。
- 🛠️ **SQLite 寫入鏈路原子化**（fixes #878）— `stock_daily(code,date)` 使用批量原子 upsert；文件型 SQLite 連接默認啟用 WAL + `busy_timeout` + 有限寫入重試；"新增數"改按本次真正插入窗口計算。
- 💰 **多 Agent / 單 Agent 預算護欄語義統一** — 剩餘預算低於最小閾值時主動跳過並降級；已完成階段可構建降級報告時返回 `success=True` 並攜帶非空內容，否則返回 `success=False`。
- ⚙️ **GitHub Actions `daily_analysis.yml` 補齊 `REPORT_LANGUAGE` 注入**（fixes #1013）— 修復用戶在 Secrets/Variables 中配置 `REPORT_LANGUAGE` 後不生效的問題。
- 📊 **任務狀態 API 補齊實時價格字段**（fixes #983）— `GET /api/v1/analysis/status/{task_id}` 從數據庫回填已完成任務時補齊 `current_price` / `change_pct`，修復首頁報告股票名旁不顯示實時價格的問題。
- 📅 **非交易日數據返回最近交易日**（fixes #1009）— 修復非交易日（週末/節假日）籌碼分佈與板塊排行返回倒數第二個交易日數據的問題，現在正常返回最近交易日數據。
- 🔍 **A 股資訊搜索恢復中文優先** — `search_stock_news()` 在首個 provider 主要返回英文資訊時繼續嘗試後續引擎，並將同批結果中的中文資訊排到前面；非美股查詢不再默認沿用 Brave 的 `en/US` 區域語言偏好。
- 📨 **飛書群機器人通知支持簽名校驗** — 飛書通知現在支持 `FEISHU_WEBHOOK_SECRET` / `FEISHU_WEBHOOK_KEYWORD`；Web 設置與文檔明確區分 Webhook 推送模式和 `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 應用模式，降低誤配風險。
- ⚡ **LLM 適配層新增 `RateLimitError` 和 `ContextWindowExceeded` 檢測** — 識別並處理速率限制與上下文窗口超出錯誤，提升分析鏈路在高負載或長文本場景下的健壯性（fixes #1002）。

### 測試

- 🧪 **TushareFetcher 港股相關單元測試** — 新增 `get_chip_distribution` 籌碼分佈獲取與 `_normalize_data` 港股/A 股/ETF 單位處理的單元測試，覆蓋港股特殊路徑。

### 文檔

- 📘 **DEPLOY.md 補充 UI 元素異常變大排查步驟** — 新增重建 Docker 鏡像或手動執行 `npm run build` 的排查指南；`deploy-webui-cloud.md` 同步更新。
- 📨 **飛書 Webhook 配置說明補全** — 強調 `FEISHU_WEBHOOK_URL` 是群通知必填項、簽名校驗須兩端同時啟用或關閉、`FEISHU_APP_SECRET` 僅用於應用/Stream Bot 模式；`.env.example` 補充內聯註釋；同步英文指南。
- 🤝 **FAQ 補充 Ollama 連接失敗排障條目（Q12c）** — 覆蓋服務未啟動、URL 配置錯誤、模型前綴缺失、模型未下載、遠程防火牆等 5 個檢查點（fixes #854）。
- 🌉 **README 補充長橋數據源使用說明** — 中/英/繁 README 明確長橋"首選 / 兜底 / 未配置不調用"邊界；`docs/` 內相對路徑鏈接修復；`LONGBRIDGE_PRINT_QUOTE_PACKAGES` 配置與代碼及 `.env.example` 對齊。
- 🐋 **Docker 安裝場景版本說明** — 補充最小化文檔，明確 Docker 安裝場景下應以 Git tag / 鏡像 tag 判斷版本（fixes #1091）。

## [3.12.0] - 2026-04-01

### 發佈亮點

- 📊 **回測頁新增"次日驗證"視圖** — 可按股票與日期範圍查看 AI 預測 vs 次日實際漲跌，複用歷史分析與 1 日回測結果，快速驗證分析準確率。
- 🔧 **LLM 接入體驗簡化** — 用戶側文案統一收口為"主模型 / 備選模型 / 模型渠道"，不再把 LiteLLM 當作普通用戶必學概念，現有配置鍵保持兼容。
- 🐳 **Docker / WebUI 運行時穩態補強** — 修復系統設置保存後配置不生效、啟動早期日誌缺失、預構建靜態資源複用等問題，降低容器化部署的運維摩擦。
- 🔒 **安全與併發穩定性同步增強** — Discord 入站 Webhook 補齊 Ed25519 驗籤，修復併發執行時共享狀態未加鎖、單股推送模式通知併發複用等問題。
- 🖥️ **桌面端與定時任務細節打磨** — Windows 安裝器支持自選安裝目錄，內置定時調度器感知運行中 SCHEDULE_TIME 變更，斷點續傳改按市場時區判斷。

### 新功能

- 📊 **回測頁新增"次日驗證 / 1 日窗口"視圖** — 可按股票代碼與分析日期範圍查看 AI 預測、次日實際漲跌及篩選區間準確率，複用歷史分析與 1 日回測結果實現。
- 🏷️ **Web 設置頁新增版本信息卡片** — `apps/dsa-web` 現在會在構建時注入前端包版本與構建時間，系統設置頁新增只讀"版本信息"區塊，展示 `WebUI 版本 / 構建標識 / 構建時間`；當 `package.json` 仍為佔位版本 `0.0.0` 時，會自動回退為構建標識，方便 Docker 重建後快速確認當前靜態資源是否已經生效。
- 🪟 **Windows 桌面安裝器支持自選安裝目錄** — 安裝器改為支持在安裝嚮導中自定義安裝目錄，安裝到非默認盤符後仍沿用現有打包態目錄邏輯在安裝目錄旁讀寫 `.env`、`data/stock_analysis.db` 和 `logs/desktop.log`，同時保留 `win-unpacked` 免安裝分發方式。安裝器僅支持當前用戶安裝、已禁用管理員提權（`allowElevation: false`），並通過 NSIS `.onVerifyInstDir` 阻止選擇系統保護目錄。

### 改進

- 🔎 **SerpAPI 正文補抓範圍收斂** — 自然搜索結果不再逐條同步抓取網頁正文；現在僅對極少數高位且摘要明顯不足的結果，在更短超時預算內做延遲補抓，並優先複用 SerpAPI 已返回的結構化摘要，降低搜索鏈路尾延遲與慢站點放大風險。
- 🤖 **LLM 接入體驗簡化** — 面向用戶的 AI 模型接入文案已統一收口為"主模型 / Agent 主模型 / 備選模型 / 模型渠道 / 高級模型路由配置"；Web 設置頁、配置元數據、校驗提示與中英文文檔不再把 LiteLLM 當作普通用戶默認必學概念，現有 `LITELLM_*` / `LLM_CHANNELS` 配置鍵仍保持兼容。

### 修復

- 🚀 **啟動早期失敗時暴露真實根因** — `python main.py` 現在通過 stderr 暴露真實根因，bootstrap 階段不再向硬編碼 `logs/` 目錄寫入文件日誌，文件日誌推遲到 `config.log_dir` 可用後創建，避免健康啟動在非預期路徑殘留日誌文件。
- 🐳 **Docker WebUI 運行時優先複用預構建靜態資源** — `prepare_webui_frontend_assets()` 現在會先檢查鏡像內已有的 `static/index.html` 是否可直接複用；當容器運行時不包含 `apps/dsa-web` 源碼目錄且未安裝 `npm` 時，也不會誤報"未找到前端項目，無法自動構建"，從而恢復 Docker 部署後的 WebUI 打開能力。
- 🐳 **Docker WebUI 系統設置保存後配置生效** — Docker 場景下 WebUI 保存 `STOCK_LIST`、`SCHEDULE_ENABLED`、`SCHEDULE_TIME`、`SCHEDULE_RUN_IMMEDIATELY`、`RUN_IMMEDIATELY` 後，`Config` 會優先讀取持久化 `.env` 中的新值，避免被容器創建時注入的舊環境變量覆蓋。
- 📈 **市場覆盤 LLM max_tokens 提升** — 市場覆盤生成鏈路將 LLM `max_tokens` 從 `2048` 提升到 `8192`，降低長覆盤輸出因 `MAX_TOKENS` 提前截斷導致內容未完成的概率。
- ⏰ **內置定時調度器感知 SCHEDULE_TIME 運行時變更** — 調度器現在會在運行中感知 WebUI 保存後的 `SCHEDULE_TIME` 變化，並在下一輪檢查時重綁 daily job。
- 🪟 **Windows Release 渠道編輯器保留 MiniMax 模型前綴** — 渠道模式下填寫 `minimax/<模型名>` 時，後端歸一化與 Web 設置頁運行時模型列表都會保留該值原樣，不再誤改寫成 `openai/minimax/<模型名>`。
- 🤖 **Discord 入站 Webhook 補齊 Ed25519 驗籤** — `DiscordPlatform` 現在會基於 `X-Signature-Ed25519`、`X-Signature-Timestamp` 和原始請求體校驗 Discord Interaction 簽名；缺失簽名頭、公鑰格式非法或簽名不匹配時直接拒絕請求，同時對 timestamp 做 ±5 分鐘時效窗口校驗以防禦重放攻擊。
- ⚙️ **STOCK_GROUP_N / EMAIL_GROUP_N 配置關係明確化** — 明確與 `STOCK_LIST` 的關係，並在配置校驗中對超出 `STOCK_LIST` 的郵件分組給出 warning。
- 🗓️ **斷點續傳改按市場時區和交易日曆判斷**（fixes #880）— 股票數據存在性檢查不再直接使用服務器自然日，而是按 A 股 / 港股 / 美股各自市場時區解析"最新可複用交易日"。
- 📨 **單股推送模式不再併發複用共享通知實例** — `StockAnalysisPipeline.run()` 現在會保留個股分析併發，但把 `SINGLE_STOCK_NOTIFY=true` 下的即時通知挪到結果收集側串行發送。
- 🔇 **實時行情降級提示收口為單次告警** — 分析主流程獲取股票名稱時不再提前觸發一次實時行情查詢，只有在全部數據源都不可用時才提示已降級為歷史收盤價繼續分析。
- 🔍 **A 股中文資訊搜索恢復中文優先** — `search_stock_news()` 現在會在首個 provider 主要返回英文資訊時繼續嘗試後續引擎，並將同批結果中的中文資訊排到前面。
- 🔒 **併發執行時共享狀態補齊統一加鎖** — 修復併發執行時共享狀態缺少統一加鎖的問題，避免多線程場景下的數據競爭。

### 測試

- 🧪 **補充設置頁版本信息迴歸測試** — 新增 Web 設置頁版本信息渲染斷言，並覆蓋佔位版本 `0.0.0` 自動回退為構建標識的邏輯。
- 🧪 **UI 治理與關鍵路徑迴歸補強** — 補充 `SidebarNav`、`ChatPage`、`BacktestPage` 等組件測試，並新增 UI governance 守衛，持續防止交互元素重新引入原生 `title` 屬性或舊 `input-terminal` 樣式迴流。同步更新 smoke / markdown drawer 相關驗證，覆蓋主題升級後的關鍵主鏈路。

## [3.11.0] - 2026-03-27

### 發佈亮點

- 🎨 **Web 工作臺完成一輪 UI 統一與雙主題升級** — 首頁、問股、回測、持倉和設置頁進一步收口到統一設計 token、輸入表面和狀態表達；新增完整淺色主題，並支持淺色 / 深色一鍵切換與持久化保存。
- 🤖 **Bot / Agent 能力重新補回主分支** — 恢復 `/history`、`/strategies`、`/research` 等命令，`/ask` 繼續支持多股對比與組合視角；Deep Research、事件監控與 schedule 輪詢鏈路重新接回主線能力。
- 🔒 **安全性與運行穩態同步補強** — 修復 `X-Forwarded-For` 限流繞過風險，恢復 LiteLLM 官方 PyPI 安裝路徑，Tushare 初始化不再依賴本地 SDK，降低 Docker、桌面打包和環境重建時的脆弱點。
- 🖥️ **日常使用細節繼續打磨** — 修復首頁港股自動補全提交、登錄頁首屏主題閃爍、歷史長股票名重疊，以及 Telegram Markdown 解析失敗時整條通知發送中斷等問題。

### 新功能

- 🎨 **全新淺色主題與雙主題切換上線** — Web 工作臺新增完整淺色主題，並支持在側邊欄中一鍵切換淺色 / 深色模式；主題選擇會持久化保存，刷新頁面後仍保持當前偏好。此次升級不是局部配色微調，而是對卡片層級、邊界對比、輸入表面、狀態提示和頁面背景做了一整套 light theme 重繪。
- 🤖 **補回主分支缺失的 Agent / Bot 能力** — `#648` / `#649` 已重新補回 `main`：Bot 恢復 `/history`、`/strategies`、`/research`，`/ask` 保留多股對比與組合視角；Deep Research 與 Event Monitor 的配置重新在 Web 設置頁可見並可編輯，schedule 模式也重新接入事件告警輪詢。

### 改進

- 🖥️ **核心頁面統一到同一套工作臺視覺語言** — `Home / Chat / Backtest / Portfolio / Settings` 進一步收口到共享設計 token、`input-surface` 輸入體系、空態/錯誤態表達和抽屜遮罩語義，減少頁面之間的視覺割裂與局部私有樣式漂移。
- 💬 **問股交互可達性與反饋增強** — 問股頁補強了會話導出、通知發送、消息複製、歷史刪除與追問上下文提示；AI 回覆操作不再過度依賴 hover，觸屏設備和小屏場景下也能直接觸達關鍵按鈕。
- 📊 **回測與持倉頁表面和狀態表達繼續標準化** — 回測頁篩選控件、布爾狀態、結果表格與彙總卡片統一到共享輸入/狀態原語；持倉頁的導入反饋、匯率刷新提示、空態與警示信息進一步歸口到共享組件，減少頁面級重複實現。
- 🧭 **導航與頁面殼層協同優化** — 側邊欄主題切換、問股完成角標、移動端抽屜遮罩和主內容滾動契約進一步統一，首頁、問股和回測在桌面端與移動端的切頁體驗更穩定。

### 測試

- 🧪 **UI 治理與關鍵路徑迴歸補強** — 補充 `SidebarNav`、`ChatPage`、`BacktestPage` 等組件測試，並新增 UI governance 守衛，持續防止交互元素重新引入原生 `title` 屬性或舊 `input-terminal` 樣式迴流。同步更新 smoke / markdown drawer 相關驗證，覆蓋主題升級後的關鍵主鏈路。

### 修復

- 🌗 **Web 首屏默認主題預設為深色** — `apps/dsa-web/index.html` 現在會在 React 掛載前讀取本地保存的主題偏好；若沒有已保存值，則立即給 `<html>` 預設 `dark` 並同步 `color-scheme`，避免首頁和登錄頁首屏先閃出淺色主題。
- 🔐 **登錄頁獨立主題層收口** — 登錄頁輸入框、標籤、切換按鈕和按鈕文案現在使用獨立的 `--login-*` 視覺 token，不再繼承全局淺/深主題文字色；即使瀏覽器緩存了淺色主題，登錄頁仍保持穩定的深色視覺與青色密碼輸入表現，避免密碼圓點和文案落成黑色。
- 🖥️ **首頁港股代碼輸入修復** — Web 首頁分析輸入框現在可正確接受港股代碼與自動完成選中的港股項，補齊 `00700.HK` / `HK00700` 等格式識別，避免提交時誤報“請輸入有效的股票代碼或股票名稱”。

- 🔒 **認證限流 X-Forwarded-For 取值修復（CWE-345）**（#841 / #842）— `get_client_ip()` 從取 `X-Forwarded-For` 最左值改為最右值，防止攻擊者通過偽造首部旋轉限流桶繞過暴力破解保護；僅影響 `TRUST_X_FORWARDED_FOR=true` 且單層可信反向代理的部署場景，多級代理環境需按部署文檔評估配置。
- 📦 **恢復 LiteLLM 官方 PyPI 安裝並鎖定安全上限** — `requirements.txt` 重新使用 `pip install litellm` 的官方 PyPI 安裝路徑，並在保留歷史最低要求 `>=1.80.10` 的同時增加 `<1.82.7` 的安全上限，避免誤裝已被移除的 `1.82.7` / `1.82.8` 風險版本；Windows 桌面打包腳本也同步回退到標準 `pip install -r requirements.txt` 鏈路，減少特殊下載分支帶來的維護成本。
- 📨 **Telegram Markdown 解析失敗回退純文本**（fixes #850）— `src/notification_sender/telegram_sender.py` 現在會在 Telegram 返回 `HTTP 400` 且包含 `can't parse entities` / Markdown 解析錯誤時，自動去掉 `parse_mode` 後重試純文本發送，避免 `*ST` 等正文內容直接導致整條通知失敗。
- 🔢 **A 股同碼實時行情保留交易所提示**（fixes #852）— `DataFetcherManager` 與 `TushareFetcher` 現在會保留 `SZ000001` / `000001.SZ` 這類顯式滬深提示，舊版 Tushare 實時行情降級分支不再把深市 `000001` 誤判成 `sh000001` 上證指數。
- 🎯 **多 Agent 次優買點不再盲目複製理想買點**（fixes #851）— 當多智能體結果缺少獨立 `secondary_buy` 時，儀表盤現在優先展示 `N/A` 而不是把 fallback 值硬拷貝成與 `ideal_buy` 完全相同，減少誤導性的雙買點展示。
- 🧩 **Tushare 初始化不再強依賴本地 SDK 包** — `TushareFetcher` 現在直接使用內置 HTTP client 訪問 Tushare Pro，不再在啟動階段先 `import tushare` 才能初始化；修復了 Docker、桌面打包或環境重建後因缺少 `tushare` 包而提前報 `No module named 'tushare'` 的問題，並補充對應迴歸測試。
- ⚙️ **`daily_analysis` 工作流補齊 `DEEPSEEK_API_KEY` 映射** — GitHub Actions 每日分析工作流現在會正確透傳 `DEEPSEEK_API_KEY`，避免雲端任務配置了密鑰卻在運行時拿不到對應環境變量。
- 🖥️ **歷史列表過長股票名稱截斷與懸停展示**（fixes #815）— 歷史列表中過長的股票名稱, 現在會按字符類型自動截斷（英文15/中文8/混合10字符），默認顯示截斷結果，懸停時展示完整名稱；解決 1920x1080 分辨率下股票名稱與右側狀態標籤文字重疊的問題。新增 `stockName.ts` 工具函數並補充對應測試。

### 文檔

- 🧾 **README 捐贈入口更新為小紅書二維碼** — README 及中英文說明中的贊助入口更新為小紅書二維碼素材，保持展示口徑一致。

## [3.10.1] - 2026-03-24

### 新功能

- 🔔 **Web 端分析推送通知開關**（#808）— 首頁分析按鈕旁新增「推送通知」複選框，默認勾選；取消勾選時本次分析不發送 Telegram/企業微信等推送。API `POST /api/v1/analysis/analyze` 新增 `notify` 字段（`bool`，默認 `true`），不傳時行為與修改前一致，Bot 和定時任務不受影響。

### 改進

- 🖥️ **問股 / 回測頁面佈局與殼層協同優化** — 統一 Chat / Backtest 頁面容器、共享 UI 狀態和跟隨問答交互路徑，移除部分硬編碼高度限制，讓導航框架內的填充與滾動行為更連貫。
- 🎨 **全局視覺與共享組件繼續收斂** — Light theme 引入動態 HSL 陰影體系，統一側邊欄激活態、告警組件對比度和聊天氣泡樣式，並把部分零散內聯樣式收口為語義化 CSS 變量，提升一致性與可維護性。

### 修復

- 🖼️ **系統設置智能導入文件選擇恢復** — 修復了“系統設置 > 基礎設置 > 智能導入”模塊中 “選擇圖片 / 選擇文件” 兩個按鈕點擊無響應的問題。
- 🖥️ **移動端滾動與交互層級修復** — 解決主題切換菜單在移動端被主內容遮擋的 z-index 衝突，並恢復首頁長報告場景下的正常縱向滾動，不影響其他頁面現有滾動行為。
- 🧾 **Markdown 純文本複製清洗增強** — 改進純文本導出算法，複製分析報告時會更穩定地清除表格分隔符等 Markdown 痕跡，提升分享和歸檔內容的純淨度。
- 🧠 **Trading philosophy injection 覆蓋 legacy + Agent 全鏈路**（#810）— `GeminiAnalyzer`、單 Agent 模式和 skill-aware Prompt 現在共享同一套策略注入狀態；只有隱式回落到內置默認 `bull_trend` 時才保留舊的趨勢型提示，顯式策略選擇或自定義默認 skill 不再被偷偷疊加 `MA5>MA10>MA20` 多頭基線。
- 🛠️ **後端 CI 依賴安裝鏈路穩態化**（#835）— 拆分 backend gate 階段、為依賴安裝增加重試，並把 CI 用的 `litellm` 安裝來源調整為更穩定的 GitHub 源，降低依賴解析抖動導致的 backend gate 偶發失敗。
- 🪟 **Windows 桌面發版構建恢復 LiteLLM 安裝兼容性** — `scripts/build-backend.ps1` 現在會先過濾 `requirements.txt` 中的 LiteLLM GitHub 源包，再下載對應 tag 的 zipball 到本地移除上游可選 `enterprise/` 目錄後安裝，繞過 Windows runner 上 Poetry 構建 wheel 時把目錄誤當文件打包導致的失敗；同時補上 `pip install` 退出碼檢查，避免依賴安裝失敗後只在後續 `python-multipart` 校驗階段才暴露成次生報錯。

### 測試

- 🧪 **問股 / 回測 / 智能導入迴歸覆蓋補齊** — 同步更新 E2E 冒煙期望，補充 `DashboardStateBlock`、Chat 頁、智能導入文件選擇與相關交互迴歸斷言，確保近期 UI 調整後的關鍵路徑仍可穩定通過。

## [3.10.0] - 2026-03-24

### 發佈亮點

- 🔎 **自動補全與索引工具擴展到三市場** — 補全索引生成鏈路現在同時覆蓋 A 股、港股、美股，配套新增 Tushare 股票列表抓取工具與更完整的靜態索引數據，讓首頁搜索入口從“能用”走向“更全、更穩”。
- 🖥️ **Dashboard 與報告查看體驗繼續收口** — 首頁 Dashboard 面板、狀態邊界、字體層級和完整報告表格密度完成一輪統一；報告詳情也補齊了 Markdown/純文本複製與更可靠的按鈕交互，減少歷史報告查看與分享時的摩擦。
- 🤖 **Agent skill 與市場語義邊界更清晰** — skill bundle、默認策略、回測彙總語義和兼容接口進一步收斂；同時分析 Prompt 不再默認寫死 A 股上下文，美股和港股分析也能按各自市場規則生成更貼切的內容。
- ⏰ **定時與桌面配置能力更貼近真實使用場景** — 桌面端支持 `.env` 導入導出；`python main.py --schedule --stocks ...` 也不再把啟動時股票快照錯誤帶入後續計劃執行，定時任務會跟隨最新保存的 `STOCK_LIST`。
### 新功能

- 💾 **桌面端 `.env` 備份/恢復入口**（#754）— 桌面模式下的系統設置頁新增 `導出 .env` / `導入 .env` 按鈕，可直接備份當前已保存配置，或把備份文件中的鍵值合併恢復到當前桌面端 `.env`；導入沿用現有 `config_version` 衝突保護與運行時重載鏈路，不改變現有桌面端便攜模式路徑。
- 📊 **Tushare 股票列表獲取工具** — 新增 `scripts/fetch_tushare_stock_list.py`，支持從 Tushare Pro 獲取 A股、港股、美股列表信息並保存為 CSV，配有分頁讀取、智能限流、錯誤處理和進度提示；新增對應使用文檔 `docs/TUSHARE_STOCK_LIST_GUIDE.md`。
- 🔎 **索引生成腳本多市場支持** — `generate_index_from_csv.py` 重構為支持 Tushare 和 AkShare 雙數據源，同時覆蓋 A股、港股、美股三個市場；新增按市場分類的別名映射（A股、港股常見別名，美股常用股票英文縮寫）；添加 `--source` 參數切換數據源、`--test` 參數驗證模式；嚴格過濾美股 DUMMY 記錄。
- 🔎 **索引生成腳本增強** — `generate_stock_index.py` 新增 `--test`/`-t` 測試模式和 `--verbose`/`-v` 詳細輸出模式，添加市場分佈統計，優化 JSON 輸出格式。
- 📋 **首頁完整報告支持雙模式複製** — 歷史報告詳情頭部新增“複製 Markdown 源碼”和“複製純文本”工具按鈕；前者保留原始 Markdown 結構，後者去除常見 Markdown 格式符號，方便分享、歸檔和跨報告比對。複製按鈕文案會跟隨 `REPORT_LANGUAGE` 保持中英文一致，避免英文報告頁出現中文固定文案。
- 🧩 **個股分析頁補齊關聯板塊展示**（#669）— A 股分析寫路徑現在會把 `belong_boards` 一次性寫入 `fundamental_context` / `fundamental_snapshot`，結構化報告詳情同步新增 `belong_boards` 與 `sector_rankings` 字段，Web 個股分析頁首屏可直接展示所屬板塊及其是否命中當日板塊漲跌榜；無數據時保持 fail-open 隱藏，不影響現有分析主流程。

### 改進

- 🖥️ **Dashboard 面板統一化（PR7-2）** — 新增 `DashboardPanelHeader` 和 `DashboardStateBlock` 作為歷史、報告、資訊、任務和透明度等面板的通用組件；統一了各面板標題層級、加載/空態/錯誤態和 CSS 變量 token。
- 🖥️ **HomePage 狀態邊界收口（PR7-2）** — 引入 `useHomeDashboardState` hook，集中 `stockPoolStore` 狀態選取邏輯，移除 `HomePage` 中重複的本地狀態派生和回調定義。
- 🧭 **Agent skill 統一到單一配置語義** — Multi-Agent runtime、API、Web chat 和配置元數據統一圍繞 `skill` 概念收斂；`/api/v1/agent/skills` 成為主發現入口，`AGENT_SKILL_*` 成為主配置面，內置 skill 元數據也開始聲明默認啟用、排序優先級、market regime tag 等信息，減少默認策略散落在代碼裡的隱式耦合。
- 🔎 **自動補全索引數據更新** — 重新生成 `stocks.index.json`，涵蓋 A股、港股、美股三個市場，提升自動補全覆蓋率。
- 🧾 **Dashboard 字體與完整報告表格密度微調** — 收斂首頁側欄、空狀態、歷史操作區的字體層級，並將完整 Markdown 報告表格 `th/td` 的內邊距調整到更緊湊的 4-6px 區間，讓信息密度與現有 Dashboard 視覺節奏更一致。

### 修復

- ⏰ **定時模式不再鎖定啟動時 CLI 股票快照** — `python main.py --schedule --stocks ...` 現在不會讓後續計劃執行沿用啟動時的舊股票列表；定時任務每次觸發前都會重新讀取最新保存的 `STOCK_LIST`，確保 WebUI 或 `.env` 更新後的自選股配置能參與後續推送。
- 🌍 **LLM Prompt 按股票市場動態注入上下文** — 分析鏈路不再把市場規則寫死成 A 股；系統 Prompt 會根據股票代碼識別 A 股、港股或美股，並注入對應的角色描述與交易規則提示，減少跨市場分析出現口徑錯位或結論失真的問題。
- 🔎 **美股自動補全複用 ticker 去重** — `generate_index_from_csv.py` 在導入 Tushare `us_basic` CSV 時會先按 `ts_code` 摺疊複用的美股 ticker，優先保留更可能仍在使用的記錄，避免 `stocks.index.json` 出現重複 `canonicalCode` 後讓 Web 自動補全展示歷史名稱或提交歧義代碼。
- 🧾 **Web 報告詳情複製交互穩定性修復**（#749）— `ReportDetails` 中“原始分析結果 / 分析快照”的複製按鈕補齊可點擊層級，避免被下方 JSON 內容覆蓋；兩個面板的複製提示也改為各自獨立，不再出現複製一個後兩個按鈕同時顯示“已複製”的誤導反饋。
- 📊 **Agent skill 回測與兼容接口語義收斂** — `get_skill_backtest_summary` 現在要求顯式傳入 `skill_id`，缺失時返回明確校驗提示；倉庫尚未持久化真實 skill 級彙總時會返回明確的 unsupported/info 響應，並保留 `normalized` 與 `*_pct` 兼容字段，避免沿用 overall 指標誤導 Agent 或用戶。
- 🔧 **Skill 默認選擇與兼容層行為加固** — `allowed-tools` 會繼續僅作為 `SKILL.md` bundle 元數據保留，不再洩露到運行時工具選擇；`/api/v1/agent/strategies` 恢復舊 payload 形狀；顯式傳入 `skills: []` 時會清空陳舊上下文；當用戶明確選擇策略 skill 時不再偷偷疊加默認 bull-trend，而在 `AGENT_SKILLS` 為空時則統一隻回落到單一主默認 skill。

### 測試

- 🧪 **Dashboard 組件測試覆蓋率擴展（PR7-2）** — 新增 `ReportNews` 和 `TaskPanel` 測試；對 `HistoryList`、`ReportDetails`、`HomePage`、`useDashboardLifecycle` 和 `stockPoolStore` 增強了斷言覆蓋，包括刪除回退、移動端抽屜和任務生命週期等場景。
- 🧪 **多市場索引生成測試補齊** — 新增 `tests/test_generate_index_from_csv.py`，覆蓋 Tushare/AkShare 雙數據源解析、多市場判斷、美股 DUMMY 過濾與重複 ticker 去重等核心路徑。
- 🧪 **關聯板塊寫入與 API 契約迴歸** — 新增 `tests/test_pipeline_related_boards.py`，並補充分析歷史與分析接口契約測試，確保 `belong_boards` / `sector_rankings` 只做增量擴展且保持 fail-open。
- 🧪 **定時模式股票列表語義迴歸測試** — 新增 `tests/test_main_schedule_mode.py`，覆蓋定時模式忽略啟動時 `--stocks` 快照、單次運行仍保留 CLI 股票覆蓋的邊界場景。

### 文檔

- 📘 **新增 Tushare 股票列表工具文檔** — 新增 `docs/TUSHARE_STOCK_LIST_GUIDE.md`，說明股票列表抓取工具的使用方法、數據格式和常見問題。
- 🌍 **補齊定時模式與關聯板塊的雙語說明** — `docs/full-guide.md` / `docs/full-guide_EN.md` 現在明確說明 scheduled mode 會在每次執行前重新讀取 `STOCK_LIST`，並同步補充個股關聯板塊展示能力說明，減少配置預期偏差。
- 🧭 **調整 Agent 術語兼容文案** — README、雙語文檔、設置頁與問股界面繼續以“策略”作為用戶入口主稱呼，同時補充 `skill` 作為內部統一命名，降低遷移期理解成本。

## [3.9.0] - 2026-03-20

### 發佈亮點

- 🤖 **模型鏈路與報告語言更靈活** — Agent 現在可以通過 `AGENT_LITELLM_MODEL` 獨立選擇模型鏈路，普通分析與 Agent 報告也可通過 `REPORT_LANGUAGE=zh|en` 輸出統一語言，減少“英文內容 + 中文殼子”這類混排問題，並允許團隊分別權衡主分析與 Agent 的成本、速度和能力。
- 🔎 **首頁分析體驗完成一輪閉環優化** — 首頁新增 A 股自動補全，支持代碼、中文名、拼音和別名檢索；同時 Dashboard 狀態收口到統一 store，歷史、報告、新聞與 Markdown 抽屜的交互更穩定，“Ask AI” 追問也會優先攜帶當前報告上下文。
- 💬 **通知與檢索能力繼續外擴** — 新增 Slack 一等通知渠道；SearXNG 在未配置自建實例時可以自動發現公共實例並按受控輪詢降級；Tavily 時效新聞鏈路修復後，嚴格時效過濾不再錯誤丟光有效結果。
- 💼 **持倉與市場覆盤鏈路更穩** — A 股 market review 可選接入 TickFlow 強化指數與漲跌統計；持倉賬本寫入改為串行化以縮小併發超賣窗口；匯率刷新入口和禁用態提示也更加清晰，減少用戶誤判。

### 新功能

- 🔎 **Web 股票自動補全 MVP** — 首頁分析輸入框新增本地索引驅動的自動補全，支持股票代碼、中文名、拼音和別名匹配；選中候選後會提交 canonical code，並透傳 `stock_name`、`original_query`、`selection_source` 到分析請求、任務狀態和 SSE 事件；索引加載失敗時自動退回舊輸入模式，不阻斷原有提交流程。同步補充了靜態索引加載器、索引生成腳本和前後端契約測試。分階段進行開發，第一階段僅支持 A 股。
- 💬 **Slack 一等通知渠道** — 新增 Slack 原生通知支持，同時支持 Bot Token 和 Incoming Webhook 兩種接入方式；同時配置時優先使用 Bot API，確保文本與圖片發送到同一頻道；Bot Token 模式支持圖片上傳（raw body POST，不使用 multipart）；新增 `SLACK_BOT_TOKEN`、`SLACK_CHANNEL_ID`、`SLACK_WEBHOOK_URL` 配置項，GitHub Actions 工作流同步補齊對應 Secrets 傳遞。
- 🌍 **報告輸出語言可配置**（Issue #758）— 新增 `REPORT_LANGUAGE=zh|en`，默認 `zh`；語言設置會同步注入普通分析與 Agent Prompt，並覆蓋 Markdown/Jinja 模板、通知 fallback、歷史/API `report_language` 元數據及 Web 報告頁固定文案，避免“英文內容 + 中文殼子”的混合輸出。
- 🚀 **Agent 與普通分析模型解耦**（Issue #692）— 新增 `AGENT_LITELLM_MODEL`（留空繼承 `LITELLM_MODEL`，無前綴按 `openai/<model>` 歸一）；Agent 執行鏈路與 `/api/v1/agent/models` 的 `is_primary/is_fallback` 標記改為基於 Agent 實際模型鏈路；系統配置與啟動期校驗補齊 `AGENT_LITELLM_MODEL` 的 `unknown_model/missing_runtime_source` 檢查；Web 設置頁新增 Agent 主模型選擇並與渠道模式運行時配置同步。
- 🔎 **SearXNG 公共實例自動發現與受控輪詢**（#752）— 新增 `SEARXNG_PUBLIC_INSTANCES_ENABLED`，在未配置 `SEARXNG_BASE_URLS` 時默認從 `searx.space` 拉取公共實例列表，並按受控輪詢順序選擇實例；同次請求內遇到超時、連接錯誤、HTTP 非 200 或無效 JSON 會自動切換到下一個實例。已配置自建實例的用戶保持原有優先級與語義不變；`daily_analysis` GitHub Actions 工作流也已支持顯式透傳該開關並在啟動日誌中展示當前狀態。
- 📈 **TickFlow market review enhancement** (#632) — 新增可選 `TICKFLOW_API_KEY`；配置後，A 股大盤覆盤的主要指數行情優先嘗試 TickFlow；若當前 TickFlow 套餐支持標的池查詢，市場漲跌統計也會優先嘗試 TickFlow。失敗或權限不足時立即回退到現有 `AkShare / Tushare / efinance` 鏈路；板塊漲跌榜回退順序保持不變。接入層同時適配了真實 SDK 契約：主指數查詢按單次請求上限分批拉取，並將 TickFlow 返回的比例型 `change_pct` / `amplitude` 統一轉換為項目內部的百分比口徑。

### 改進

- **Dashboard state slice and workspace closure** — moved Home / Dashboard state into `stockPoolStore`, consolidated history selection, report loading, task syncing, polling refresh, and markdown drawer handling under a single state slice.
- **Dashboard panel standardization** — kept the current dashboard layout contract stable while unifying history, report, news, and markdown presentation with shared tokens, standardized states, and bounded in-panel scrolling for the history list.
- **Dashboard-to-chat follow-up bridge** — routed “Ask AI” follow-ups through report-context hydration instead of direct cross-page state coupling, while keeping chat sends usable when enriched history context is still loading.
- 💼 **持倉賬本併發寫入串行化**（#742）— 持倉源事件寫入/刪除現在會在 SQLite 下先獲取串行化寫鎖，減少併發賣出把超售流水寫入賬本的窗口；直接持倉寫接口在鎖競爭時返回 `409 portfolio_busy`，CSV 導入保持逐條提交併把 busy 計入 `failed_count`。
- 💱 **持倉頁匯率手動刷新入口補齊**（#748）— Web `/portfolio` 頁面現在會在“匯率狀態”卡片中展示“刷新匯率”按鈕，直接調用現有 `POST /api/v1/portfolio/fx/refresh` 接口；刷新後會僅重載快照與風險數據，並以內聯摘要反饋“已更新 / 仍 stale / 刷新失敗”的結果，減少用戶對 `fxStale` 長時間停留的誤解。

### 修復

- 🔎 **Web 自動補全 Enter 提交語義修正** — 股票自動補全在搜索命中候選時不再默認高亮第一項；候選列表展開但用戶尚未用方向鍵或鼠標明確選中時，按 Enter 會繼續提交原始輸入，避免手動輸入被第一條候選靜默覆蓋。
- 🌍 **補齊 `REPORT_LANGUAGE` 啟動解析與歷史展示本地化邊界** — `Config` 在啟動時繼續遵循“真實環境變量優先、`.env` 兜底”的既有語義，並在兩者衝突時輸出顯式告警，減少 `REPORT_LANGUAGE` 來源不清帶來的誤判；同時 `/api/v1/history/{id}` 英文詳情響應會同步本地化 `sentiment_label`，歷史 Markdown 也會正確識別英文 `bias_status` 的風險等級 emoji，避免出現 `乐观` 或 `🚨Safe` 這類中英混排/誤報展示。
- 📰 **Tavily 時效新聞檢索發佈時間映射修復**（#782）— Tavily 在股票新聞和嚴格時效的情報維度中現在會顯式使用 `topic="news"`，併兼容 `published_date` / `publishedDate` 兩種發佈時間字段；修復了 Tavily 明明返回結果卻在後續硬過濾階段被全部記為 `drop_unknown` 丟棄的問題，同時將機構分析、業績預期、行業分析等分析型維度恢復為寬源搜索，不再被統一壓縮成新聞模式。
- 💱 **持倉頁匯率刷新禁用語義修正**（#772）— 當 `PORTFOLIO_FX_UPDATE_ENABLED=false` 時，`POST /api/v1/portfolio/fx/refresh` 現在會返回顯式 `refresh_enabled=false` 與 `disabled_reason`，Web `/portfolio` 頁面會明確提示“匯率在線刷新已被禁用”，不再誤報“當前範圍無可刷新的匯率對”。
- 🤖 **Agent timeout and config hardening** — `AGENT_ORCHESTRATOR_TIMEOUT_S` now also protects the legacy single-agent ReAct loop, parallel tool batches stop waiting once the remaining budget is exhausted, and invalid numeric `.env` values fall back to safe defaults with warnings instead of crashing startup.
- 🌐 **CORS wildcard + credentials compatibility** — `CORS_ALLOW_ALL=true` no longer combines `allow_origins=["*"]` with credentialed requests, avoiding browser-side cross-origin failures in demo/development setups.
- 🧭 **Unavailable Agent settings hidden from Web UI** — Deep Research / Event Monitor controls are now treated as compatibility-only metadata in the current branch and are removed from the Settings page to avoid exposing non-functional toggles.

### 文檔

- 新增 Ollama 本地模型配置說明，同步更新 `README.md` 與 `docs/README_EN.md`（Fixes #690）
- 完善 Ollama 配置說明：`docs/full-guide.md` / `docs/full-guide_EN.md` 環境變量表與 Note 補充 `OLLAMA_API_BASE`，避免英文用戶誤以為 Ollama 不能作為獨立配置入口；合併重複的 `OLLAMA_API_BASE` 條目為單一條目
- 明確文檔同步治理邊界：補充 `README.md`、專題文檔、雙語文檔與交付說明之間的默認同步規則，減少後續文檔漂移

## [3.8.0] - 2026-03-17

### 發佈亮點

- 🎨 **Web 界面完成一輪骨架升級** — 新的 App Shell、側邊導航、主題能力、登錄與系統設置流程已經串成統一體驗，桌面端加載背景也完成對齊。
- 📈 **分析上下文繼續補強** — 美股新增社交輿情情報，A 股補齊財報與分紅結構化上下文，Tushare 新接入籌碼分佈和行業板塊漲跌數據。
- 🔒 **運行穩定性與配置兼容性提升** — 退出登錄會立即讓舊會話失效，定時啟動兼容舊配置，運行中的 `MAX_WORKERS` 調整和新聞時效窗口反饋更清晰。
- 💼 **持倉糾錯鏈路更完整** — 超售會被前置攔截，錯誤交易/資金流水/公司行為可以直接刪除回滾，便於修復髒數據。

### 新功能

- 📱 **美股社交輿情情報** — 新增 Reddit / X / Polymarket 社交媒體情緒數據源，為美股分析提供實時社交熱度、情緒評分和提及量等補充指標；完全可選，僅在配置 `SOCIAL_SENTIMENT_API_KEY` 後對美股生效。
- 📊 **A 股財報與分紅結構化增強**（Issue #710）— `fundamental_context.earnings.data` 新增 `financial_report` 與 `dividend` 字段；分紅統一按“僅現金分紅、稅前口徑”計算，並補充 `ttm_cash_dividend_per_share` 與 `ttm_dividend_yield_pct`；分析/歷史 API 的 `details` 追加 `financial_report`、`dividend_metrics` 可選字段，保持 fail-open 與向後兼容。
- 🔍 **接入 Tushare 籌碼與行業板塊接口** — 新增籌碼分佈、行業板塊漲跌數據獲取能力，並統一納入配置化數據源優先級；默認按上海時間區分盤中/盤後交易日取數，優先使用 Tushare 同花順接口，必要時降級到東財。
- 🧱 **Web UI 基礎骨架升級** — 重建共享設計令牌與通用組件，新增 App Shell、Theme Provider、側邊導航，並同步調整 Electron 加載背景，為 Web / Desktop 的統一體驗打底。
- 🔐 **登錄與系統設置流程重做** — 重構 Login、Settings 與 Auth 管理流程，補上顯式的認證 setup-state 處理，並讓 Web 端與運行時認證配置 API 行為對齊。
- 🧪 **前端迴歸與冒煙覆蓋補強** — 新增並擴展登錄、首頁、聊天、移動端 Shell、設置頁、回測入口等關鍵路徑的組件測試與 Playwright smoke coverage。

### 變更

- 🧭 **頁面接入新 Shell 佈局契約** — Home、Chat、Settings、Backtest 已統一接入新的頁面容器、抽屜和滾動約定，降低 UI 遷移期間的頁面行為不一致。
- 💾 **設置頁狀態同步更穩** — 優化草稿保留、直接保存同步與衝突處理，減少模塊級保存後前後端配置狀態不一致的問題。
- 🎭 **登錄頁視覺基線迴歸** — 登錄頁恢復到既有 `006` 分支的視覺基線，同時保留新的認證狀態邏輯和統一表單交互模型。
- 🏛️ **AI 協作治理資產加固** — 收斂並加強 `AGENTS.md`、`CLAUDE.md`、Copilot 指令和校驗腳本的一致性約束，降低治理資產長期漂移風險。

### Added

- **Web UI foundation refresh** — rebuilt shared design tokens and common primitives, introduced the app shell, theme provider, sidebar navigation, and Electron loading background alignment for the upgraded desktop/web experience
- **Settings and auth workflow overhaul** — rebuilt the Login, Settings, and Auth management flows, added explicit auth setup-state handling, and aligned the Web UI with the runtime auth configuration APIs
- **UI regression coverage and smoke checks** — expanded targeted frontend tests and added Playwright smoke coverage for login, home, chat, mobile shell, settings, and backtest entry flows

### Changed

- **Shell-driven page integration** — aligned Home, Chat, Settings, and Backtest with the new shell layout contract so routing, drawer behavior, and page-level scrolling are consistent during the UI migration
- **Settings state consistency** — refined draft preservation, direct-save synchronization, and conflict handling so module-level saves no longer leave the page out of sync with backend config state
- **Login visual baseline** — restored the login page visual treatment to the established `006` branch baseline while keeping the newer auth-state logic and unified form interaction model

### 修復

- ⏰ **定時啟動立即執行兼容舊配置**（Issue #726）— `SCHEDULE_RUN_IMMEDIATELY` 未設置時會回退讀取 `RUN_IMMEDIATELY`，修復升級後舊 `.env` 在定時模式下的兼容性問題；同時澄清 `.env.example` / README 中兩個配置項的適用範圍，並註明 Outlook / Exchange 強制 OAuth2 暫不支持。
- 🧵 **運行期 `MAX_WORKERS` 配置生效與可解釋性增強**（#633）— 修復異步分析隊列未按 `MAX_WORKERS` 同步的問題；新增任務隊列併發 in-place 同步機制（空閒即時生效、繁忙延後），並在設置保存反饋與運行日誌中明確輸出 `profile/max/effective`，減少“參數未生效”誤解。
- 🔐 **退出登錄立即失效現有會話** — `POST /api/v1/auth/logout` 現在會輪換 session secret，避免舊 cookie 在退出後仍可繼續訪問受保護接口；同瀏覽器標籤頁和併發頁面會被同步登出。認證開啟時，該接口也不再屬於匿名白名單，未登錄請求會返回 `401`，避免匿名請求觸發全局 session 失效。
- 🧮 **Tushare 板塊/籌碼調用限流與跨日緩存修復** — 新增的 `trade_cal`、行業板塊排行、籌碼分佈鏈路統一接入 `_check_rate_limit()`；交易日曆緩存改為按自然日刷新，避免服務跨天運行後繼續沿用舊交易日判斷取數日期。
- 💼 **持倉超售攔截與錯誤流水恢復**（#718）— `POST /api/v1/portfolio/trades` 現在會在寫入前校驗可賣數量，超售返回 `409 portfolio_oversell`；持倉頁新增交易 / 資金流水 / 公司行為刪除能力，刪除後會同步失效倉位緩存與未來快照，便於從錯誤流水中直接恢復。
- 📧 **郵件中文發件人名編碼**（#708）— 郵件通知現在會對包含中文的 `EMAIL_SENDER_NAME` 自動做 RFC 2047 編碼，並在異常路徑補充 SMTP 連接清理，修復 GitHub Actions / QQ SMTP 下 `'ascii' codec can't encode characters` 導致的發送失敗。
- 🐛 **港股 Agent 實時行情去重與快速路由** — 統一 `HK01810` / `1810.HK` / `01810` 等港股代碼歸一規則；港股實時行情改為直接走單次 `akshare_hk` 路徑，避免按 A 股 source priority 重複觸發同一失敗接口；Agent 運行期對顯式 `retriable=false` 的工具失敗增加短路緩存，減少同輪分析中的重複失敗調用。
- 📰 **新聞時效硬過濾與策略分窗**（#697）— 新增 `NEWS_STRATEGY_PROFILE`（`ultra_short/short/medium/long`）並與 `NEWS_MAX_AGE_DAYS` 統一計算有效窗口；搜索結果在返回後執行發佈時間硬過濾（時間未知剔除、超窗剔除、未來僅容忍 1 天），並在歷史 fallback 鏈路追加相同約束，避免舊聞再次進入“最新動態/風險警報”。

### 文檔

- ☁️ **新增雲服務器 Web 界面部署與訪問教程**（Fixes #686）— 補充從雲端部署到外部訪問的落地說明，降低遠程自託管門檻。
- 🌍 **補齊英文文檔索引與協作文檔** — 新增英文文檔索引、貢獻指南、Bot 命令文檔，並補充中英雙語 issue / PR 模板，方便中英文協作與外部貢獻者理解項目入口。
- 🏷️ **本地化 README 補充 Trendshift badge** — 在多語言 README 中同步補上新版能力入口標識，減少中英文說明面不一致。

## [3.7.0] - 2026-03-15

### 新功能

- 💼 **持倉管理 P0 全功能上線**（#677，對應 Issue #627）
  - **核心賬本與快照閉環**：新增賬戶、交易、現金流水、企業行為、持倉緩存、每日快照等核心數據模型與 API 端點；支持 FIFO / AVG 雙成本法回放；同日事件順序固定為 `現金 → 企業行為 → 交易`；持倉快照寫入採用原子事務。
  - **券商 CSV 導入**：支持華泰 / 中信 / 招商首批適配，含列名別名兼容；兩階段接口（解析預覽 + 確認提交）；`trade_uid` 優先、key-field hash 兜底的冪等去重；前導零股票代碼完整保留。
  - **組合風險報告**：集中度風險（Top Positions + A 股板塊口徑）、歷史回撤監控（支持回填缺失快照）、止損接近預警；多幣種統一換算 CNY 口徑；汲取失敗時回退最近成功匯率並標記 stale。
  - **Web 持倉頁**（`/portfolio`）：組合總覽、持倉明細、集中度餅圖、風險摘要、全組合 / 單賬戶切換；手工錄入交易 / 資金流水 / 企業行為；內嵌賬戶創建入口；CSV 解析 + 提交閉環與券商選擇器。
  - **Agent 持倉工具**：新增 `get_portfolio_snapshot` 數據工具，默認緊湊摘要，可選持倉明細與風險數據。
  - **事件查詢 API**：新增 `GET /portfolio/trades`、`GET /portfolio/cash-ledger`、`GET /portfolio/corporate-actions`，支持日期過濾與分頁。
  - **可擴展 Parser Registry**：應用級共享註冊，支持運行時註冊新券商；新增 `GET /portfolio/imports/csv/brokers` 發現接口。

- 🎨 **前端設計系統與原子組件庫**（#662）
  - 引入漸進式雙主題架構（HSL 變量化設計令牌），清理歷史 Legacy CSS；重構 Button / Card / Badge / Collapsible / Input / Select 等 20+ 核心組件；新增 `clsx` + `tailwind-merge` 類名合併工具；提升歷史記錄、LLM 配置等頁面可讀性。

- ⚡ **分析 API 異步契約與啟動優化**（#656）
  - 規範 `POST /api/v1/analysis/analyze` 異步請求的返回契約；優化服務啟動輔助邏輯；修復前端報告類型聯合定義與後端響應對齊問題。

### 修復

- 🔔 **Discord 環境變量向後兼容**（#659）：運行時新增 `DISCORD_CHANNEL_ID` → `DISCORD_MAIN_CHANNEL_ID` 的 fallback 讀取；歷史配置用戶無需修改即可恢復 Discord Bot 通知；全部相關文檔與 `.env.example` 對齊。
- 🔧 **GitHub Actions Node 24 升級**（#665）：將所有 GitHub 官方 actions 升級至 Node 24 兼容版本，消除 CI 日誌中的 Node.js 20 deprecation warning（影響 2026-06-02 強制升級窗口）。
- 📅 **持倉頁默認日期本地化**：手工錄入表單默認日期改用本地時間（`getFullYear/Month/Date`），修復 UTC-N 時區用戶在當天晚間出現日期偏移的問題。
- 🔁 **CSV 導入去重邏輯加固**：dedup hash 納入行序號作為區分因子，確保同字段合法分筆成交不被誤摺疊；同時在 `trade_uid` 存在時也持久化 hash，防止混合來源重複寫入。

### 變更

- `POST /api/v1/portfolio/trades` 在同賬戶內 `trade_uid` 衝突時返回 `409`。
- 持倉風險響應新增 `sector_concentration` 字段（增量擴展），原有 `concentration` 字段保持不變。
- 分析 API `analyze` 接口異步行為契約文檔化；前端報告類型聯合更新。

### 測試

- 新增持倉核心服務測試（FIFO / AVG 部分賣出、同日事件順序、重複 `trade_uid` 返回 409、快照 API 契約）。
- 新增 CSV 導入冪等性、合法分筆成交不誤去重、去重邊界、風險閾值邊界、匯率降級行為測試。
- 新增 Agent `get_portfolio_snapshot` 工具調用測試。
- 新增分析 API 異步契約迴歸測試。

## [3.6.0] - 2026-03-14

### Added
- 📊 **Web UI Design System** — implemented dual-theme architecture and terminal-inspired atomic UI components
- 📊 **UI Components Refactoring** — integrated `clsx` and `tailwind-merge` for robust class composition across Web UI

- 🗑️ **History batch deletion** — Web UI now supports multi-selection and batch deletion of analysis history; added `POST /api/v1/history/batch-delete` endpoint and `ConfirmDialog` component.
- 🔐 **Auth settings API** — new `POST /api/v1/auth/settings` endpoint to enable or disable Web authentication at runtime and set the initial admin password when needed
- openclaw Skill 集成指南 — 新增 [docs/openclaw-skill-integration.md](openclaw-skill-integration.md)，說明如何通過 openclaw Skill 調用 DSA API
- ⚙️ **LLM channel protocol/test UX** — `.env` and Web settings now share the same channel shape (`LLM_CHANNELS` + `LLM_<NAME>_PROTOCOL/BASE_URL/API_KEY/MODELS/ENABLED`); settings page adds per-channel connection testing, primary/fallback/vision model selection, and protocol-aware model prefixing
- 🤖 **Agent architecture Phase 0+1** — shared protocols (`AgentContext`, `AgentOpinion`, `StageResult`), extracted `run_agent_loop()` runner, `AGENT_ARCH` switch (`single`/`multi`), config registry entries
- 🔍 **Bot NL routing** — two-layer natural-language routing: cheap regex pre-filter (stock codes + finance keywords) → lightweight LLM intent parsing; controlled by `AGENT_NL_ROUTING=true`; supports multi-stock and strategy extraction
- 💬 **`/ask` multi-stock analysis** — comma or `vs` separated codes (max 5), parallel thread execution with 150s timeout (preserves partial results), Markdown comparison summary table at top
- 📋 **`/history` command** — per-user session isolation via `{platform}_{user_id}:{scope}` format (colon delimiter prevents prefix collision); lists both `/chat` and `/ask` sessions; view detail or clear
- 📊 **`/strategies` command** — lists available strategy YAML files grouped by category (趨勢/形態/反轉/框架) with ✅/⬜ activation status
- 🔧 **Backtest summary tools** — `get_strategy_backtest_summary` and `get_stock_backtest_summary` registered as read-only Agent tools
- ⚙️ **Agent auto-detection** — `is_agent_available()` auto-detects from `LITELLM_MODEL`; explicit `AGENT_MODE=true/false` takes full precedence
- 🏗️ **Multi-Agent orchestrator (Phase 2)** — `AgentOrchestrator` with 4 modes (`quick`/`standard`/`full`/`strategy`); drop-in replacement for `AgentExecutor` via `AGENT_ARCH=multi`; `BaseAgent` ABC with tool subset filtering, cached data injection, and structured `AgentOpinion` output
- 🧩 **Specialised agents (Phase 2-4)** — `TechnicalAgent` (8 tools, trend/MA/MACD/volume/pattern analysis), `IntelAgent` (news & sentiment, risk flag propagation), `DecisionAgent` (synthesis into Decision Dashboard JSON), `RiskAgent` (7 risk categories, two-level severity with soft/hard override)
- 📈 **Strategy system (Phase 3)** — `StrategyAgent` (per-strategy evaluation from YAML skills), `StrategyRouter` (rule-based regime detection → strategy selection), `StrategyAggregator` (weighted consensus with backtest performance factor)
- 🔬 **Deep Research agent (Phase 5)** — `ResearchAgent` with 3-phase approach (decompose → research sub-questions → synthesise report); token budget tracking; new `/research` bot command with aliases (`/深研`, `/deepsearch`)
- 🧠 **Memory & calibration (Phase 6)** — `AgentMemory` with prediction accuracy tracking, confidence calibration (activates after minimum sample threshold), strategy auto-weighting based on historical win rate
- 📊 **Portfolio Agent (Phase 7)** — `PortfolioAgent` for multi-stock portfolio analysis (position sizing, sector concentration, correlation risk, cross-market linkage, rebalance suggestions)
- 🔔 **Event-driven alerts (Phase 7)** — `EventMonitor` with `PriceAlert`, `VolumeAlert`, `SentimentAlert` rules; async checking, callback notifications, serializable persistence
- ⚙️ **New config entries** — `AGENT_ORCHESTRATOR_MODE`, `AGENT_RISK_OVERRIDE`, `AGENT_DEEP_RESEARCH_BUDGET`, `AGENT_MEMORY_ENABLED`, `AGENT_STRATEGY_AUTOWEIGHT`, `AGENT_STRATEGY_ROUTING` — all registered in `config.py` + `config_registry.py` (WebUI-configurable)

### Changed
- 🔐 **Auth password state semantics** — stored password existence is now tracked independently from auth enablement; when auth is disabled, `/api/v1/auth/status` returns `passwordSet=false` while preserving the saved password for future re-enable
- 🔐 **Auth settings re-enable hardening** — re-enabling auth with a stored password now requires `currentPassword`, and failed session creation rolls back the auth toggle to avoid lockout
- ♻️ **AgentExecutor refactored** — `_run_loop` delegates to shared `runner.run_agent_loop()`; removed duplicated serialization/parsing/thinking-label code
- ♻️ **Unified agent switch** — Bot, API, and Pipeline all use `config.is_agent_available()` instead of divergent `config.agent_mode` checks
- 📖 **README.md** — expanded Bot commands section (ask/chat/strategies/history), added NL routing note, updated agent mode description
- 📖 **.env.example** — added `AGENT_ARCH` and `AGENT_NL_ROUTING` configuration documentation
- 🔌 **Analysis API async contract** — `POST /api/v1/analysis/analyze` now documents distinct async `202` payloads for single-stock vs batch requests, and `report_type=full` is treated consistently with the existing full-report behavior

### Fixed
- 🐛 **Analysis API blank-code guardrails** — `POST /api/v1/analysis/analyze` now drops whitespace-only entries before batch enqueue and returns `400` when no valid stock code remains
- 🐛 **Bare `/api` SPA fallback** — unknown API paths now return JSON `404` consistently for both `/api/...` and the exact `/api` path
- 🎮 **Discord channel env compatibility** — runtime now accepts legacy `DISCORD_CHANNEL_ID` as a fallback for `DISCORD_MAIN_CHANNEL_ID`, and the docs/examples now use the same variable name as the actual workflow/config implementation
- 🐛 **Session secret rotation on Windows** — use atomic replace so auth toggles invalidate existing sessions even when `.session_secret` already exists
- 🐛 **Auth toggle atomicity** — persist `ADMIN_AUTH_ENABLED` before rotating session secret; on rotation failure, roll back to the previous auth state
- 🔧 **LLM runtime selection guardrails** — YAML 模式下渠道編輯器不再覆蓋 `LITELLM_MODEL` / fallback / Vision；系統配置校驗補上全部渠道禁用後的運行時來源檢查，並修復 `vertexai/...` 這類協議別名模型被重複加前綴的問題
- 🐛 **Multi-stock `/ask` follow-up regressions** — portfolio overlay now shares the same timeout budget as the per-stock phase and is skipped on timeout instead of blocking the bot reply; `/history` now stores the readable per-stock summary instead of raw dashboard JSON; condensed multi-stock output now renders numeric `sniper_points` values
- 🐛 **Decision dashboard enum compatibility** — multi-agent `DecisionAgent` now keeps `decision_type` within the legacy `buy|hold|sell` contract and normalizes stray `strong_*` outputs before risk override, pipeline conversion, and downstream統計/通知彙總
- 🛟 **Multi-Agent partial-result fallback** — `IntelAgent` now caches parsed intel for downstream reuse, shared JSON parsing tolerates lightly malformed model output, and the orchestrator preserves/synthesizes a minimal dashboard on timeout or mid-pipeline parse failure instead of always collapsing to `50/觀望/未知`
- 🐛 **Shared LiteLLM routing restored** — bot NL intent parsing and `ResearchAgent` planning/synthesis now reuse the same LiteLLM adapter / Router / fallback / `api_base` injection path as the main Agent flow, so `LLM_CHANNELS` / `LITELLM_CONFIG` / OpenAI-compatible deployments behave consistently
- 🐛 **Bot chat session backward compatibility** — `/chat` now keeps using the legacy `{platform}_{user_id}` session id when old history already exists, and `/history` can still list / view / clear those pre-migration sessions alongside the new `{platform}_{user_id}:chat` format
- 🐛 **EventMonitor unsupported rule rejection** — config validation/runtime loading now reject or skip alert types the monitor cannot actually evaluate yet, so schedule mode no longer silently accepts permanent no-op rules
- 🐛 **P0 基本面聚合穩定性修復** (#614) — 修復 `get_stock_info` 板塊語義迴歸（新增 `belong_boards` 並保留 `boards` 兼容別名）、引入基本面上下文精簡返回以控制 token、為基本面緩存增加最大條目淘汰，並補齊 ETF 總體狀態聚合與 NaN 板塊字段過濾，保證 fail-open 與最小入侵。
- 🔧 **GitHub Actions 搜索引擎環境變量補充** — 工作流新增 `MINIMAX_API_KEYS`、`BRAVE_API_KEYS`、`SEARXNG_BASE_URLS` 環境變量映射，使 GitHub Actions 用戶可配置 MiniMax、Brave、SearXNG 搜索服務（此前 v3.5.0 已添加 provider 實現但缺少工作流配置）
- 🤖 **Multi-Agent runtime consistency** — `AGENT_MAX_STEPS` now propagates to each orchestrated sub-agent; added cooperative `AGENT_ORCHESTRATOR_TIMEOUT_S` budget to stop overlong pipelines before they cascade further
- 🔌 **Multi-Agent feature wiring** — `AGENT_RISK_OVERRIDE` now actively downgrades final dashboards on hard risk findings; `AGENT_MEMORY_ENABLED` now injects recent analysis memory + confidence calibration into specialised agents; multi-stock `/ask` now runs `PortfolioAgent` to add portfolio-level allocation and concentration guidance
- 🔔 **EventMonitor runtime wiring** — schedule mode can now load alert rules from `AGENT_EVENT_ALERT_RULES_JSON`, poll them at `AGENT_EVENT_MONITOR_INTERVAL_MINUTES`, and send triggered alerts through the existing notification service
- 🛠️ **Follow-up stability fixes** — multi-stock `/ask` now falls back to usable text output when dashboard JSON parsing fails; EventMonitor skips semantically invalid rules instead of aborting schedule startup; background alert polling now runs independently of the main scheduled analysis loop
- 🧪 **Multi-Agent regression coverage** — added orchestrator execution tests for `run()`, `chat()`, critical-stage failure, graceful degradation, and timeout handling
- 🧹 **PortfolioAgent cleanup** — `post_process()` now reuses shared JSON parsing and removed stale unused imports
- 🚦 **Bot async dispatch** — `CommandDispatcher` now exposes `dispatch_async()`; NL intent parsing and default command execution are offloaded from the event loop, DingTalk stream awaits async handlers directly, and Feishu stream processing is moved off the SDK callback thread
- 🌐 **Async webhook handler** — new `handle_webhook_async()` function in `bot/handler.py` for use from async contexts (e.g. FastAPI); calls `dispatch_async()` directly without thread bridging
- 🧵 **Feishu stream ThreadPoolExecutor** — replaced unbounded per-message `Thread` spawning with a capped `ThreadPoolExecutor(max_workers=8)` to prevent thread explosion under message bursts
- 🔒 **EventMonitor safety** — `_check_volume()` now safely handles `get_daily_data` returning `None` (no tuple-unpacking crash); `on_trigger` callbacks support both sync and async callables via `asyncio.to_thread`/`await`
- 🧹 **ResearchAgent dedup** — `_filtered_registry()` now delegates to `BaseAgent._filtered_registry()` instead of duplicating the filtering logic
- 🧹 **Bot trailing whitespace cleanup** — removed W291/W293 whitespace issues across `bot/handler.py`, `bot/dispatcher.py`, `bot/commands/base.py`, `bot/platforms/feishu_stream.py`, `bot/platforms/dingtalk_stream.py`
- 🐛 **Dispatcher `_parse_intent_via_llm` safety** — replaced fragile `'raw' in dir()` with `'raw' in locals()` for undefined-variable guard in `JSONDecodeError` handler
- 🐛 **籌碼結構 LLM 未填寫時兜底補全** (#589) — DeepSeek 等模型未正確填寫 `chip_structure` 時，自動用數據源已獲取的籌碼數據補全，保證各模型展示一致；普通分析與 Agent 模式均生效
- 🐛 **歷史報告狙擊點位顯示原始文本** (#452) — 歷史詳情頁現優先展示 `raw_result.dashboard.battle_plan.sniper_points` 中的原始字符串，避免 `analysis_history` 數值列把區間、說明文字或複雜點位壓縮成單個數字；保留原有數值列作為回退
- 🐛 **Session prefix collision** — user ID `123` could see sessions of user `1234` via `startswith`; fixed with colon delimiter in session_id format
- 🐛 **NL pre-filter false positives** — `re.IGNORECASE` caused `[A-Z]{2,5}` to match common English words like "hello"; removed global flag, use inline `(?i:...)` only for English finance keywords
- 🐛 **Dotted ticker in strategy args** — `_get_strategy_args()` didn't recognize `BRK.B` as a stock code, leaving it in strategy text; now accepts `TICKER.CLASS` format
- ⏱️ **efinance 長調用掛起修復** (#660) — 為所有 efinance API 調用引入 `_ef_call_with_timeout()` 包裝（默認 30 秒，可通過 `EFINANCE_CALL_TIMEOUT` 配置）；使用 `executor.shutdown(wait=False)` 確保超時後不再阻塞主線程，徹底消除 81 分鐘掛起問題
- 🛡️ **類型安全內容完整性檢查** (#660) — `check_content_integrity()` 現在將非字符串類型的 `operation_advice` / `analysis_summary` 視為缺失字段，避免下游 `get_emoji()` 因 `dict.strip()` 崩潰
- 📄 **報告保存與通知解耦** (#660) — `_save_local_report()` 不再依賴 `send_notification` 標誌觸發，`--no-notify` 模式下本地報告照常保存
- 🔄 **operation_advice 字典歸一化** (#660) — Pipeline 和 BacktestEngine 現在將 LLM 返回的 `dict` 格式 `operation_advice` 通過 `decision_type`（不區分大小寫）映射為標準字符串，防止因模型輸出格式變化導致崩潰
- 🛡️ **runner.py usage None 防護** (#660) — `response.usage` 為 `None` 時不再拋出 `AttributeError`，回退為 0 token 計數
- 📋 **orchestrator 靜默失敗改為日誌警告** (#660) — `IntelAgent` / `RiskAgent` 階段失敗現在記錄 `WARNING` 而非靜默跳過，便於診斷

### Notes
- ⚠️ **Multi-worker auth toggles** — runtime auth updates are process-local; multi-worker deployments must restart/roll workers to keep auth state consistent

## [3.5.0] - 2026-03-12

### Added
- 📊 **Web UI full report drawer** (Fixes #214) — history page adds "Full Report" button to display the complete Markdown analysis report in a side drawer; new `GET /api/v1/history/{record_id}/markdown` endpoint
- 📊 **LLM cost tracking** — all LLM calls (analysis, agent, market review) recorded in `llm_usage` table; new `GET /api/v1/usage/summary?period=today|month|all` endpoint returns aggregated token usage by call type and model
- 🔍 **SearXNG search provider** (Fixes #550) — quota-free self-hosted search fallback; priority: Bocha > Tavily > Brave > SerpAPI > MiniMax > SearXNG
- 🔍 **MiniMax web search provider** — `MiniMaxSearchProvider` with circuit breaker (3 failures → 300s cooldown) and dual time-filtering; configured via `MINIMAX_API_KEYS`
- 🤖 **Agent models discovery API** — `GET /api/v1/agent/models` returns available model deployments (primary/fallback/source/api_base) for Web UI model selector
- 🤖 **Agent chat export & send** (#495) — export conversation to .md file; send to configured notification channels; new `POST /api/v1/agent/chat/send`
- 🤖 **Agent background execution** (#495) — analysis continues when switching pages; badge notification on completion; auto-cancel in-progress stream on session switch
- 📝 **Report Engine P0** — Pydantic schema validation for LLM JSON; Jinja2 templates (markdown/wechat/brief) with legacy fallback; content integrity checks with retry; brief mode (`REPORT_TYPE=brief`); history signal comparison
- 📦 **Smart import** — multi-source import from image/CSV/Excel/clipboard; Vision LLM extracts code+name+confidence; name→code resolver (local map + pinyin + AkShare); confidence-tiered confirmation
- ⚙️ **GitHub Actions LiteLLM config** — workflow supports `LITELLM_CONFIG`/`LITELLM_CONFIG_YAML` for flexible AI provider configuration
- ⚙️ **Config engine refactor & system API** (#602) — unified config registry, validation and API exposure
- 📖 **LLM configuration guide** — new `docs/LLM_CONFIG_GUIDE.md` covering 3-tier config, quick start, Vision/Agent/troubleshooting

### Fixed
- 🐛 **analyze_trend always reports No historical data** (#600) — now fetches from DB/DataFetcher instead of broken `get_analysis_context`
- 🐛 **Chip structure fallback when LLM omits it** (#589) — auto-fills from data source chip data for consistent display across models
- 🐛 **History sniper points show raw text** (#452) — prioritizes original strings over compressed numeric values
- 🐛 **GitHub Actions ENABLE_CHIP_DISTRIBUTION configurable** (#617) — no longer hardcoded, supports vars/secrets override
- 🐛 **`.env` save preserves comments and blank lines** — Web settings no longer destroys `.env` formatting
- 🐛 **Agent model discovery fixes** — legacy mode includes LiteLLM-native providers; source detection aligned with runtime; fallback deployments no longer expanded per-key
- 🐛 **Stooq US stock previous close semantics** — no longer misuses open price as previous close
- 🐛 **Stock name prefetch regression** — prioritizes local `STOCK_NAME_MAP` before remote queries
- 🐛 **AkShare limit-up/down calculation** (#555) — fixed market analysis statistics
- 🐛 **AkShare Tencent source field index & ETF quote mapping** (#579)
- 🐛 **Pytdx stock name cache pagination** (#573) — prevents cache overflow
- 🐛 **PushPlus oversized report chunking** (#489) — auto-segments long content
- 🐛 **Agent chat cancel & switch** (#495) — cancel no longer misreports as failure; fast switch no longer overwrites stream state
- 🐛 **MiniMax search status in `/status` command** (#587)
- 🐛 **config_registry duplicate BOCHA_API_KEYS** — removed duplicate dict entry that silently overwrote config

### Changed
- 🔎 **Fetcher failure observability** — logs record start/success/failure with elapsed time, failover transitions; Efinance/Akshare include upstream endpoint and classified failure categories
- ♻️ **Data source resilience & cleanup** (#602) — fallback chain optimization
- ♻️ **Image extract API response extension** — new `items` field (code/name/confidence); `codes` preserved for backward compatibility
- ♻️ **Import parse error messages** — specific failure reasons for Excel/CSV; improved logging with file type and size

### Docs
- 📖 LLM config guide refactored for clarity (#583)
- 📖 `image-extract-prompt.md` with full prompt documentation
- 📖 AkShare fallback cache TTL documentation
## [3.4.10] - 2026-03-07

### Fixed
- 🐛 **EfinanceFetcher ETF OHLCV data** (#541, #527) — switch `_fetch_etf_data` from `ef.fund.get_quote_history` (NAV-only, no OHLCV, no `beg`/`end` params) to `ef.stock.get_quote_history`; ETFs now return proper open/high/low/close/volume/amount instead of zeros; remove obsolete NAV column mappings from `_normalize_data`
- 🐛 **tiktoken 0.12.0 `Unknown encoding cl100k_base`** (#537) — pin `tiktoken>=0.8.0,<0.12.0` in requirements.txt to avoid plugin-registration regression introduced in 0.12.0
- 🐛 **Web UI API error classification** (#540) — frontend no longer treats every HTTP 400 as the same "server/network" failure; now distinguishes Agent disabled / missing params / model-tool incompatibility / upstream LLM errors / local connection failures
- 🐛 **北交所代碼識別失敗** (#491, #533) — 8/4/92 開頭的 6 位代碼現正確識別為北交所；Tushare/Akshare/Yfinance 等數據源支持 .BJ 或 bj 前綴；Baostock/Pytdx 對北交所代碼顯式切換數據源；避免誤判上海 B 股 900xxx
- 🐛 **狙擊點位解析錯誤** (#488, #532) — 理想買入/二次買入等字段在無「元」字時誤提取括號內技術指標數字；現先截去第一個括號後內容再提取

### Added
- **Markdown-to-image for dashboard report** (#455, #535) — 個股日報彙總支持 markdown 轉圖片推送（Telegram、WeChat、Custom、Email），與大盤覆盤行為一致
- **markdown-to-file engine** (#455) — `MD2IMG_ENGINE=markdown-to-file` 可選，對 emoji 支持更好，需 `npm i -g markdown-to-file`
- **PREFETCH_REALTIME_QUOTES** (#455) — 設為 `false` 可禁用實時行情預取，避免 efinance/akshare_em 全市場拉取
- **Stock name prefetch** (#455) — 分析前預取股票名稱，減少報告中「股票xxxxx」佔位符
- 📊 **分析報告模型標記** (#528, #534) — 在分析報告 meta、報告末尾、推送內容中展示 `model_used`（完整 LLM 模型名）；Agent 多輪調用時記錄並展示每輪實際使用的模型（支持 fallback 切換）

### Changed
- **Enhanced markdown-to-image failure warning** (#455) — 轉圖失敗時提示具體依賴（wkhtmltopdf 或 m2f）
- **WeChat-only image routing optimization** (#455) — 僅配置企業微信圖片時，不再對完整報告做冗餘轉圖，避免誤導性失敗日誌
- **Stock name prefetch lightweight mode** (#455) — 名稱預取階段跳過 realtime quote 查詢，減少額外網絡開銷

## [3.4.9] - 2026-03-06

### Added
- 🧠 **Structured config validation** — `ConfigIssue` dataclass and `validate_structured()` with severity-aware logging; `CONFIG_VALIDATE_MODE=strict` aborts startup on errors
- 🖼️ **Vision model config** — `VISION_MODEL` and `VISION_PROVIDER_PRIORITY` for image stock extraction; provider fallback (Gemini → Anthropic → OpenAI → DeepSeek) when primary fails
- 🚀 **CLI init wizard** — `python -m dsa init` 3-step interactive bootstrap (model → data source → notification), 9 provider presets, incremental merge by default
- 🔧 **Multi-channel LLM support** with visual channel editor (#494)

### Changed
- ♻️ **Vision extraction** — migrated from gemini-3 hardcode to `litellm.completion()` with configurable model and provider fallback; `OPENAI_VISION_MODEL` deprecated in favor of `VISION_MODEL`
- ♻️ **Market analyzer** — uses `Analyzer.generate_text()` for LLM calls; fixes bypass and Anthropic `AttributeError` when using non-Router path
- ♻️ **Config validation refinements** — test_env output format syncs with `validate_structured` (severity-aware ✓/✗/⚠/·); Vision key warning when `VISION_MODEL` set but no provider API key; market_analyzer test covers `generate_market_review` fallback when `generate_text` returns None
- ⚙️ **Auto-tag workflow defaults to NO tag** — only tags when commit message explicitly contains `#patch`, `#minor`, or `#major`
- ♻️ **Formatter and notification refactor** (#516)

### Fixed
- 🐛 **STOCK_LIST not refreshed on scheduled runs** — `.env` or WebUI changes to `STOCK_LIST` now hot-reload before each scheduled analysis (#529)
- 🐛 **WebUI fails to load with MIME type error** — SPA fallback route now resolves correct `Content-Type` for JS/CSS files (#520)
- 🐛 **AstrBot sender docstring misplaced** — `import time` placed before docstring in `_send_astrbot`, causing it to become dead code
- 🐛 **Telegram Markdown link escaping** — `_convert_to_telegram_markdown` escaped `[]()` characters, breaking all Markdown links in reports
- 🐛 **Duplicate `discord_bot_status` field** in Config dataclass — second declaration silently shadowed the first
- 🧹 **Unused imports** — removed `shutil`/`subprocess` from `main.py`
- 🔧 **Config validation and Vision key check** (#525)

### Docs
- 📝 Clarified GitHub Actions non-trading-day manual run controls (`TRADING_DAY_CHECK_ENABLED` + `force_run`) for Issue #461 / PR #466

## [3.4.8] - 2026-03-02

### Fixed
- 🐛 **Desktop exe crashes on startup with `FileNotFoundError`** — PyInstaller build was missing litellm's JSON data files (e.g. `model_prices_and_context_window_backup.json`). Added `--collect-data litellm` to both Windows and macOS build scripts so the files are correctly bundled in the executable.

### CI
- 🔧 Cache Electron binaries on macOS CI runners to prevent intermittent EOF download failures when fetching `electron-vX.Y.Z-darwin-*.zip` from GitHub CDN
- 🔧 Fix macOS DMG `hdiutil Resource busy` error during desktop packaging

### Docs
- 📝 Clarify non-trading-day manual run controls for GitHub Actions (`TRADING_DAY_CHECK_ENABLED` + `force_run`) (#474)

## [3.4.7] - 2026-02-28

### Added
- 🧠 **CN/US Market Strategy Blueprint System** (#395) — market review prompt injects region-specific strategy blueprints with position sizing and risk trigger recommendations

### Fixed
- 🐛 **`TRADING_DAY_CHECK_ENABLED` env var and `--force-run` for GitHub Actions** (#466)
- 🐛 **Agent pipeline preserved resolved stock names** (#464) — placeholder names no longer leak into reports
- 🐛 **Code cleanup** (#462, Fixes #422)
- 🐛 **WebUI auto-build on startup** (#460)
- 🐛 **ARCH_ARGS unbound variable** (#458)
- 🐛 **Time zone inconsistency & right panel flash** (#439)

### Docs
- 📝 Clarify potential ambiguities in code (#343)
- 📝 ENABLE_EASTMONEY_PATCH guidance for Issue #453 (#456)

## [3.4.0] - 2026-02-27

### Added
- 📡 **LiteLLM Direct Integration + Multi API Key Support** (#454, Fixes #421 #428)
  - Removed native SDKs (google-generativeai, google-genai, anthropic); unified through `litellm>=1.80.10`
  - New config: `LITELLM_MODEL`, `LITELLM_FALLBACK_MODELS`, `GEMINI_API_KEYS`, `ANTHROPIC_API_KEYS`, `OPENAI_API_KEYS`
  - Multi-key auto-builds LiteLLM Router (simple-shuffle) with 429 cooldown
  - **Breaking**: `.env` `GEMINI_MODEL` (no prefix) only for fallback; explicit config must include provider prefix

### Changed
- ♻️ **Notification Refactoring** (#435) — extracted 10 sender classes into `src/notification_sender/`

### Fixed
- 🐛 LLM NoneType crash, history API 422, sniper points extraction
- 🐛 Auto-build frontend on WebUI startup — `WEBUI_AUTO_BUILD` env var (default `true`)
- 🐛 Docker explicit project name (#448)
- 🐛 Bocha search SSL retry (#445, #446) — transient errors retry up to 3 times
- 🐛 Gemini google-genai SDK migration (Fixes #440, #444)
- 🐛 Mobile home page scrolling (Fixes #419, #433)
- 🐛 History list scroll reset (#431)
- 🐛 Settings save button false positive (fixes #417, #430)

## [3.3.22] - 2026-02-26

### Added
- 💬 **Chat History Persistence** (Fixes #400, #414) — `/chat` page survives refresh, sidebar session list
- 🎨 Project VI Assets — logo icon set, PSD, vector, banner (#425)
- 🚀 Desktop CI Auto-Release (#426) — Windows + macOS parallel builds

### Fixed
- 🐛 Agent Reasoning 400 & LiteLLM Proxy (fixes #409, #427)
- 🐛 Discord chunked sending (#413) — `DISCORD_MAX_WORDS` config
- 🐛 yfinance shared DataFrame (#412)
- 🐛 sniper_points parsing (#408)
- 🐛 Agent framework category missing (#406)
- 🐛 Date inconsistency & query id (fixes #322, #363)

## [3.3.12] - 2026-02-24

### Added
- 📈 **Intraday Realtime Technical Indicators** (Issue #234, #397) — MA calculated from realtime price, config: `ENABLE_REALTIME_TECHNICAL_INDICATORS`
- 🤖 **Agent Strategy Chat** (#367) — full ReAct pipeline, 11 YAML strategies, SSE streaming, multi-turn chat
- 📢 PushPlus Group Push — `PUSHPLUS_TOPIC` (#402)
- 📅 Trading Day Check (Issue #373, #375) — `TRADING_DAY_CHECK_ENABLED`, `--force-run`

### Fixed
- 🐛 DeepSeek reasoning mode (Issue #379, #386)
- 🐛 Agent news intel persistence (Fixes #396, #405)
- 🐛 Bare except clauses replaced with `except Exception` (#398)
- 🐛 UUID fallback for HTTP non-secure context (fixes #377, #381)
- 🐛 Docker DNS resolution (Fixes #372, #374)
- 🐛 Agent session/strategy bugs — multiple follow-up fixes for #367
- 🐛 yfinance parallel download data filtering

### Changed
- Market review strategy consistency — unified cn/us template
- Agent test assertions updated (`6 -> 11`)


## [3.2.11] - 2026-02-23

### 修復（#patch）
- 🐛 **StockTrendAnalyzer 從未執行** (Issue #357)
  - 根因：`get_analysis_context` 僅返回 2 天數據且無 `raw_data`，pipeline 中 `raw_data in context` 始終為 False
  - 修復：Step 3 直接調用 `get_data_range` 獲取 90 日曆天（約 60 交易日）歷史數據用於趨勢分析
  - 改善：趨勢分析失敗時用 `logger.warning(..., exc_info=True)` 記錄完整 traceback

## [3.2.10] - 2026-02-22

### 新增
- ⚙️ 支持 `RUN_IMMEDIATELY` 配置項，設為 `true` 時定時任務觸發後立即執行一次分析，無需等待首個定時點

### 修復
- 🐛 修復 Web UI 頁面居中問題
- 🐛 修復 Settings 返回 500 錯誤

## [3.2.9] - 2026-02-22

### 修復
- 🐛 **ETF 分析僅關注指數走勢**（Issue #274）
  - 美股/港股 ETF（如 VOO、QQQ）與 A 股 ETF 不再納入基金公司層面風險（訴訟、聲譽等）
  - 搜索維度：ETF/指數專用 risk_check、earnings、industry 查詢，避免命中基金管理人新聞
  - AI 提示：指數型標的分析約束，`risk_alerts` 不得出現基金管理人公司經營風險

## [3.2.8] - 2026-02-21

### 修復
- 🐛 **BOT 與 WEB UI 股票代碼大小寫統一**（Issue #355）
  - BOT `/analyze` 與 WEB UI 觸發分析的股票代碼統一為大寫（如 `aapl` → `AAPL`）
  - 新增 `canonical_stock_code()`，在 BOT、API、Config、CLI、task_queue 入口處規範化
  - 歷史記錄與任務去重邏輯可正確識別同一股票（大小寫不再影響）

## [3.2.7] - 2026-02-20

### 新增
- 🔐 **Web 頁面密碼驗證**（Issue #320, #349）
  - 支持 `ADMIN_AUTH_ENABLED=true` 啟用 Web 登錄保護
  - 首次訪問在網頁設置初始密碼；支持「系統設置 > 修改密碼」和 CLI `python -m src.auth reset_password` 重置

## [3.2.6] - 2026-02-20
### ⚠️ 破壞性變更（Breaking Changes）

- **歷史記錄 API 變更 (Issue #322)**
  - 路由變更：`GET /api/v1/history/{query_id}` → `GET /api/v1/history/{record_id}`
  - 參數變更：`query_id` (字符串) → `record_id` (整數)
  - 新聞接口變更：`GET /api/v1/history/{query_id}/news` → `GET /api/v1/history/{record_id}/news`
  - 原因：`query_id` 在批量分析時可能重複，無法唯一標識單條歷史記錄。改用數據庫主鍵 `id` 確保唯一性
  - 影響範圍：使用舊版歷史詳情 API 的所有客戶端需同步更新

### 修復
- 修復美股（如 ADBE）技術指標矛盾：akshare 美股復權數據異常，統一美股歷史數據源為 YFinance（Issue #311）
- 🐛 **歷史記錄查詢和顯示問題 (Issue #322)**
  - 修復歷史記錄列表查詢中日期不一致問題：使用明天作為 endDate，確保包含今天全天的數據
  - 修復服務器 UI 報告選擇問題：原因是多條記錄共享同一 `query_id`，導致總是顯示第一條。現改用 `analysis_history.id` 作為唯一標識
  - 歷史詳情、新聞接口及前端組件已全面適配 `record_id`
  - 新增後臺輪詢（每 30s）與頁面可見性變更時靜默刷新歷史列表，確保 CLI 發起的分析完成後前端能及時同步，使用 `silent` 模式避免觸發 loading 狀態
- 🐛 **美股指數實時行情與日線數據** (Issue #273)
  - 修復 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指數無法獲取實時行情的問題
  - 新增 `us_index_mapping` 模塊，將用戶輸入（如 SPX）映射為 Yahoo Finance 符號（如 ^GSPC）
  - 美股指數與美股股票日線數據直接路由至 YfinanceFetcher，避免遍歷不支持的數據源
  - 消除重複的美股識別邏輯，統一使用 `is_us_stock_code()` 函數

### 優化
- 🎨 **首頁輸入欄與 Market Sentiment 佈局對齊優化**
  - 股票代碼輸入框左緣與歷史記錄 glass-card 框左對齊
  - 分析按鈕右緣與 Market Sentiment 外框右對齊
  - Market Sentiment 卡片向下拉伸填滿格子，消除與 STRATEGY POINTS 之間的空隙
  - 窄屏時輸入欄填滿寬度，響應式對齊保持一致

## [3.2.5] - 2026-02-19

### 新增
- 🌍 **大盤覆盤可選區域**（Issue #299）
  - 支持 `MARKET_REVIEW_REGION` 環境變量：`cn`（A股）、`us`（美股）、`both`（兩者）
  - us 模式使用 SPX/納斯達克/道指/VIX 等指數；both 模式可同時覆盤 A 股與美股
  - 默認 `cn`，保持向後兼容

## [3.2.4] - 2026-02-18

### 修復
- 🐛 **統一美股數據源為 YFinance**（Issue #311）
  - akshare 美股復權數據異常，統一美股歷史數據源為 YFinance
  - 修復 ADBE 等美股股票技術指標矛盾問題

## [3.2.3] - 2026-02-18

### 修復
- 🐛 **標普500實時數據缺失**（Issue #273）
  - 修復 SPX、DJI、IXIC、NDX、VIX、RUT 等美股指數無法獲取實時行情的問題
  - 新增 `us_index_mapping` 模塊，將用戶輸入（如 SPX）映射為 Yahoo Finance 符號（如 `^GSPC`）
  - 美股指數與美股股票日線數據直接路由至 YfinanceFetcher，避免遍歷不支持的數據源

## [3.2.2] - 2026-02-16

### 新增
- 📊 **PE 指標支持**（Issue #296）
  - AI System Prompt 增加 PE 估值關注
- 📰 **新聞時效性篩查**（Issue #296）
  - `NEWS_MAX_AGE_DAYS`：新聞最大時效（天），默認 3，避免使用過時信息
- 📈 **強勢趨勢股乖離率放寬**（Issue #296）
  - `BIAS_THRESHOLD`：乖離率閾值（%），默認 5.0，可配置
  - 強勢趨勢股（多頭排列且趨勢強度 ≥70）自動放寬乖離率到 1.5 倍

## [3.2.1] - 2026-02-16

### 新增
- 🔧 **東財接口補丁可配置開關**
  - 支持 `EFINANCE_PATCH_ENABLED` 環境變量開關東財接口補丁（默認 `true`）
  - 補丁不可用時可降級關閉，避免影響主流程

## [3.2.0] - 2026-02-15

### 新增
- 🔒 **CI 門禁統一（P0）**
  - 新增 `scripts/ci_gate.sh` 作為後端門禁單一入口
  - 主 CI 改為 `backend-gate`、`docker-build`、`web-gate` 三段式
  - CI 觸發改為所有 PR，避免 Required Checks 因路徑過濾缺失而卡住合併
  - `web-gate` 支持前端路徑變更按需觸發
  - 新增 `network-smoke` 工作流承載非阻斷網絡場景迴歸
- 📦 **發佈鏈路收斂（P0）**
  - `docker-publish` 調整為 tag 主觸發，並增加發布前門禁校驗
  - 手動發佈增加 `release_tag` 輸入與 semver/changelog 強校驗
  - 發佈前新增 Docker smoke（關鍵模塊導入）
- 📝 **PR 模板升級（P0）**
  - 增加背景、範圍、驗證命令與結果、回滾方案、Issue 關聯等必填項
- 🤖 **AI 審查覆蓋增強（P0）**
  - `pr-review` 納入 `.github/workflows/**` 範圍
  - 新增 `AI_REVIEW_STRICT` 開關，可選將 AI 審查失敗升級為阻斷

## [3.1.13] - 2026-02-15

### 新增
- 📊 **僅分析結果摘要**（Issue #262）
  - 支持 `REPORT_SUMMARY_ONLY` 環境變量，設為 `true` 時只推送彙總，不含個股詳情
  - 默認 `false`，多股時適合快速瀏覽

## [3.1.12] - 2026-02-15

### 新增
- 📧 **個股與大盤覆盤合併推送**（Issue #190）
  - 支持 `MERGE_EMAIL_NOTIFICATION` 環境變量，設為 `true` 時將個股分析與大盤覆盤合併為一次推送
  - 默認 `false`，減少郵件數量、降低被識別為垃圾郵件的風險

## [3.1.11] - 2026-02-15

### 新增
- 🤖 **Anthropic Claude API 支持**（Issue #257）
  - 支持 `ANTHROPIC_API_KEY`、`ANTHROPIC_MODEL`、`ANTHROPIC_TEMPERATURE`、`ANTHROPIC_MAX_TOKENS`
  - AI 分析優先級：Gemini > Anthropic > OpenAI
- 📷 **從圖片識別股票代碼**（Issue #257）
  - 上傳自選股截圖，通過 Vision LLM 自動提取股票代碼
  - API: `POST /api/v1/stocks/extract-from-image`；支持 JPEG/PNG/WebP/GIF，最大 5MB
  - 支持 `OPENAI_VISION_MODEL` 單獨配置圖片識別模型
- ⚙️ **通達信數據源手動配置**（Issue #257）
  - 支持 `PYTDX_HOST`、`PYTDX_PORT` 或 `PYTDX_SERVERS` 配置自建通達信服務器

## [3.1.10] - 2026-02-15

### 新增
- ⚙️ **立即運行配置**（Issue #332）
  - 支持 `RUN_IMMEDIATELY` 環境變量，`true` 時定時任務啟動後立即執行一次
- 🐛 修復 Docker 構建問題

## [3.1.9] - 2026-02-14

### 新增
- 🔌 **東財接口補丁機制**
  - 新增 `patch/eastmoney_patch.py` 修復 efinance 上游接口變更
  - 不影響其他數據源的正常運行

## [3.1.8] - 2026-02-14

### 新增
- 🔐 **Webhook 證書校驗開關**（Issue #265）
  - 支持 `WEBHOOK_VERIFY_SSL` 環境變量，可關閉 HTTPS 證書校驗以支持自簽名證書
  - 默認保持校驗，關閉存在 MITM 風險，僅建議在可信內網使用

## [3.1.7] - 2026-02-14

### 修復
- 🐛 修復包導入錯誤（package import error）

## [3.1.6] - 2026-02-13

### 修復
- 🐛 修復 `news_intel` 中 `query_id` 不一致問題

## [3.1.5] - 2026-02-13

### 新增
- 📷 **Markdown 轉圖片通知**（Issue #289）
  - 支持 `MARKDOWN_TO_IMAGE_CHANNELS` 配置，對 Telegram、企業微信、自定義 Webhook（Discord）、郵件發送圖片格式報告
  - 郵件為內聯附件，增強對不支持 HTML 客戶端的兼容性
  - 需安裝 `wkhtmltopdf` 和 `imgkit`

## [3.1.4] - 2026-02-12

### 新增
- 📧 **股票分組發往不同郵箱**（Issue #268）
  - 支持 `STOCK_GROUP_N` + `EMAIL_GROUP_N` 配置，不同股票組報告發送到對應郵箱
  - 大盤覆盤發往所有配置的郵箱

## [3.1.3] - 2026-02-12

### 修復
- 🐛 修復 Docker 內運行時通過頁面修改配置報錯 `[Errno 16] Device or resource busy` 的問題

## [3.1.2] - 2026-02-11

### 修復
- 🐛 修復 Docker 一致性問題，解決關鍵批次處理與通知 Bug

## [3.1.1] - 2026-02-11

### 變更
- ♻️ `API_HOST` → `WEBUI_HOST`：Docker Compose 配置項統一

## [3.1.0] - 2026-02-11

### 新增
- 📊 **ETF 支持增強與代碼規範化**
  - 統一各數據源 ETF 代碼處理邏輯
  - 新增 `canonical_stock_code()` 統一代碼格式，確保數據源路由正確

## [3.0.5] - 2026-02-08

### 修復
- 🐛 修復信號 emoji 與建議不一致的問題（複合建議如"賣出/觀望"未正確映射）
- 🐛 修復 `*ST` 股票名在微信/Dashboard 中 markdown 轉義問題
- 🐛 修復 `idx.amount` 為 None 時大盤覆盤 TypeError
- 🐛 修複分析 API 返回 `report=None` 及 ReportStrategy 類型不一致問題
- 🐛 修復 Tushare 返回類型錯誤（dict → UnifiedRealtimeQuote）及 API 端點指向

### 新增
- 📊 大盤覆盤報告注入結構化數據（漲跌統計、指數表格、板塊排名）
- 🔍 搜索結果 TTL 緩存（500 條上限，FIFO 淘汰）
- 🔧 Tushare Token 存在時自動注入實時行情優先級
- 📰 新聞摘要截斷長度 50→200 字

### 優化
- ⚡ 補充行情字段請求限制為最多 1 次，減少無效請求

## [3.0.4] - 2026-02-07

### 新增
- 📈 **回測引擎** (PR #269)
  - 新增基於歷史分析記錄的回測系統，支持收益率、勝率、最大回撤等指標評估
  - WebUI 集成回測結果展示

## [3.0.3] - 2026-02-07

### 修復
- 🐛 修復狙擊點位數據解析錯誤問題 (PR #271)

## [3.0.2] - 2026-02-06

### 新增
- ✉️ 可配置郵件發送者名稱 (PR #272)
- 🌐 外國股票支持英文關鍵詞搜索

## [3.0.1] - 2026-02-06

### 修復
- 🐛 修復 ETF 實時行情獲取、市場數據回退、企業微信消息分塊問題
- 🔧 CI 流程簡化

## [3.0.0] - 2026-02-06

### 移除
- 🗑️ **移除舊版 WebUI**
  - 刪除基於 `http.server.ThreadingHTTPServer` 的舊版 WebUI（`web/` 包）
  - 舊版 WebUI 的功能已完全被 FastAPI（`api/`）+ React 前端替代
  - `--webui` / `--webui-only` 命令行參數標記為棄用，自動重定向到 `--serve` / `--serve-only`
  - `WEBUI_ENABLED` / `WEBUI_HOST` / `WEBUI_PORT` 環境變量保持兼容，自動轉發到 FastAPI 服務
  - `webui.py` 保留為兼容入口，啟動時直接調用 FastAPI 後端
  - Docker Compose 中移除 `webui` 服務定義，統一使用 `server` 服務

### 變更
- ♻️ **服務層重構**
  - 將 `web/services.py` 中的異步任務服務遷移至 `src/services/task_service.py`
  - Bot 分析命令（`bot/commands/analyze.py`）改為使用 `src.services.task_service`
  - Docker 環境變量 `WEBUI_HOST`/`WEBUI_PORT` 更名為 `API_HOST`/`API_PORT`（舊名仍兼容）

## [2.3.0] - 2026-02-01

### 新增
- 🇺🇸 **增強美股支持** (Issue #153)
  - 實現基於 Akshare 的美股歷史數據獲取 (`ak.stock_us_daily()`)
  - 實現基於 Yfinance 的美股實時行情獲取（優先策略）
  - 增加對不支持數據源（Tushare/Baostock/Pytdx/Efinance）的美股代碼過濾和快速降級

### 修復
- 🐛 修復 AMD 等美股代碼被誤識別為 A 股的問題 (Issue #153)

## [2.2.5] - 2026-02-01

### 新增
- 🤖 **AstrBot 消息推送** (PR #217)
  - 新增 AstrBot 通知渠道，支持推送到 QQ 和微信
  - 支持 HMAC SHA256 簽名驗證，確保通信安全
  - 通過 `ASTRBOT_URL` 和 `ASTRBOT_TOKEN` 配置

## [2.2.4] - 2026-02-01

### 新增
- ⚙️ **可配置數據源優先級** (PR #215)
  - 支持通過環境變量（如 `YFINANCE_PRIORITY=0`）動態調整數據源優先級
  - 無需修改代碼即可優先使用特定數據源（如 Yahoo Finance）

## [2.2.3] - 2026-01-31

### 修復
- 📦 更新 requirements.txt，增加 `lxml_html_clean` 依賴以解決兼容性問題

## [2.2.2] - 2026-01-31

### 修復
- 🐛 修復代理配置區分大小寫問題 (fixes #211)

## [2.2.1] - 2026-01-31

### 修復
- 🐛 **YFinance 兼容性修復** (PR #210, fixes #209)
  - 修復新版 yfinance 返回 MultiIndex 列名導致的數據解析錯誤

## [2.2.0] - 2026-01-31

### 新增
- 🔄 **多源回退策略增強**
  - 實現了更健壯的數據獲取回退機制 (feat: multi-source fallback strategy)
  - 優化了數據源故障時的自動切換邏輯

### 修復
- 🐛 修復 analyzer 運行後無法通過改 .env 文件的 stock_list 內容調整跟蹤的股票

## [2.1.14] - 2026-01-31

### 文檔
- 📝 更新 README 和優化 auto-tag 規則

## [2.1.13] - 2026-01-31

### 修復
- 🐛 **Tushare 優先級與實時行情** (Fixed #185)
  - 修復 Tushare 數據源優先級設置問題
  - 修復 Tushare 實時行情獲取功能

## [2.1.12] - 2026-01-30

### 修復
- 🌐 修復代理配置在某些情況下的區分大小寫問題
- 🌐 修復本地環境禁用代理的邏輯

## [2.1.11] - 2026-01-30

### 優化
- 🚀 **飛書消息流優化** (PR #192)
  - 優化飛書 Stream 模式的消息類型處理
  - 修改 Stream 消息模式默認為關閉，防止配置錯誤運行時報錯

## [2.1.10] - 2026-01-30

### 合併
- 📦 合併 PR #154 貢獻

## [2.1.9] - 2026-01-30

### 新增
- 💬 **微信文本消息支持** (PR #137)
  - 新增微信推送的純文本消息類型支持
  - 添加 `WECHAT_MSG_TYPE` 配置項

## [2.1.8] - 2026-01-30

### 修復
- 🐛 修正日誌中 API 提供商顯示錯誤 (PR #197)

## [2.1.7] - 2026-01-30

### 修復
- 🌐 禁用本地環境的代理設置，避免網絡連接問題

## [2.1.6] - 2026-01-29

### 新增
- 📡 **Pytdx 數據源 (Priority 2)**
  - 新增通達信數據源，免費無需註冊
  - 多服務器自動切換
  - 支持實時行情和歷史數據
- 🏷️ **多源股票名稱解析**
  - DataFetcherManager 新增 `get_stock_name()` 方法
  - 新增 `batch_get_stock_names()` 批量查詢
  - 自動在多數據源間回退
  - Tushare 和 Baostock 新增股票名稱/列表方法
- 🔍 **增強搜索回退**
  - 新增 `search_stock_price_fallback()` 用於數據源全部失敗時
  - 新增搜索維度：市場分析、行業分析
  - 最大搜索次數從 3 增加到 5
  - 改進搜索結果格式（每維度 4 條結果）

### 改進
- 更新搜索查詢模板以提高相關性
- 增強 `format_intel_report()` 輸出結構

## [2.1.5] - 2026-01-29

### 新增
- 📡 新增 Pytdx 數據源和多源股票名稱解析功能

## [2.1.4] - 2026-01-29

### 文檔
- 📝 更新贊助商信息

## [2.1.3] - 2026-01-28

### 文檔
- 📝 重構 README 佈局
- 🌐 新增繁體中文翻譯 (README_CHT.md)

### 修復
- 🐛 修復 WebUI 無法輸入美股代碼問題
  - 輸入框邏輯改成所有字母都轉換成大寫
  - 支持 `.` 的輸入（如 `BRK.B`）

## [2.1.2] - 2026-01-27

### 修復
- 🐛 修復個股分析推送失敗和報告路徑問題 (fixes #166)
- 🐛 修改 CR 錯誤，確保微信消息最大字節配置生效

## [2.1.1] - 2026-01-26

### 新增
- 🔧 添加 GitHub Actions auto-tag 工作流
- 📡 添加 yfinance 兜底數據源及數據缺失警告

### 修復
- 🐳 修復 docker-compose 路徑和文檔命令
- 🐳 Dockerfile 補充 copy src 文件夾 (fixes #145)

## [2.1.0] - 2026-01-25

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代碼直接輸入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作為美股數據源
- 📈 **MACD 和 RSI 技術指標**
  - MACD：趨勢確認、金叉死叉信號（零軸上金叉⭐、金叉✅、死叉❌）
  - RSI：超買超賣判斷（超賣⭐、強勢✅、超買⚠️）
  - 指標信號納入綜合評分系統
- 🎮 **Discord 推送支持** (PR #124, #125, #144)
  - 支持 Discord Webhook 和 Bot API 兩種方式
  - 通過 `DISCORD_WEBHOOK_URL` 或 `DISCORD_BOT_TOKEN` + `DISCORD_MAIN_CHANNEL_ID` 配置
- 🤖 **機器人命令交互**
  - 釘釘機器人支持 `/分析 股票代碼` 命令觸發分析
  - 支持 Stream 長連接模式
- 🌡️ **AI 溫度參數可配置** (PR #142)
  - 支持自定義 AI 模型溫度參數
- 🐳 **Zeabur 部署支持**
  - 添加 Zeabur 鏡像部署工作流
  - 支持 commit hash 和 latest 雙標籤

### 重構
- 🏗️ **項目結構優化**
  - 核心代碼移至 `src/` 目錄，根目錄更清爽
  - 文檔移至 `docs/` 目錄
  - Docker 配置移至 `docker/` 目錄
  - 修復所有 import 路徑，保持向後兼容
- 🔄 **數據源架構升級**
  - 新增數據源熔斷機制，單數據源連續失敗自動切換
  - 實時行情緩存優化，批量預取減少 API 調用
  - 網絡代理智能分流，國內接口自動直連
- 🤖 Discord 機器人重構為平臺適配器架構

### 修復
- 🌐 **網絡穩定性增強**
  - 自動檢測代理配置，對國內行情接口強制直連
  - 修復 EfinanceFetcher 偶發的 `ProtocolError`
  - 增加對底層網絡錯誤的捕獲和重試機制
- 📧 **郵件渲染優化**
  - 修復郵件中表格不渲染問題 (#134)
  - 優化郵件排版，更緊湊美觀
- 📢 **企業微信推送修復**
  - 修復大盤覆盤推送不完整問題
  - 增強消息分割邏輯，支持更多標題格式
  - 增加分批發送間隔，避免限流丟失
- 👷 **CI/CD 修復**
  - 修復 GitHub Actions 中路徑引用的錯誤

## [2.0.0] - 2026-01-24

### 新增
- 🇺🇸 **美股分析支持**
  - 支持美股代碼直接輸入（如 `AAPL`, `TSLA`）
  - 使用 YFinance 作為美股數據源
- 🤖 **機器人命令交互** (PR #113)
  - 釘釘機器人支持 `/分析 股票代碼` 命令觸發分析
  - 支持 Stream 長連接模式
  - 支持選擇精簡報告或完整報告
- 🎮 **Discord 推送支持** (PR #124)
  - 支持 Discord Webhook 推送
  - 添加 Discord 環境變量到工作流

### 修復
- 🐳 修復 WebUI 在 Docker 中綁定 0.0.0.0 (fixed #118)
- 🔔 修復飛書長連接通知問題
- 🐛 修復 `analysis_delay` 未定義錯誤
- 🔧 啟動時 config.py 檢測通知渠道，修復已配置自定義渠道情況下仍然提示未配置問題

### 改進
- 🔧 優化 Tushare 優先級判斷邏輯，提升封裝性
- 🔧 修復 Tushare 優先級提升後仍排在 Efinance 之後的問題
- ⚙️ 配置 TUSHARE_TOKEN 時自動提升 Tushare 數據源優先級
- ⚙️ 實現 4 個用戶反饋 issue (#112, #128, #38, #119)

## [1.6.0] - 2026-01-19

### 新增
- 🖥️ WebUI 管理界面及 API 支持（PR #72）
  - 全新 Web 架構：分層設計（Server/Router/Handler/Service）
  - 核心 API：支持 `/analysis` (觸發分析), `/tasks` (查詢進度), `/health` (健康檢查)
  - 交互界面：支持頁面直接輸入代碼並觸發分析，實時展示進度
  - 運行模式：新增 `--webui-only` 模式，僅啟動 Web 服務
  - 解決了 [#70](https://github.com/ZhuLinsen/daily_stock_analysis/issues/70) 的核心需求（提供觸發分析的接口）
- ⚙️ GitHub Actions 配置靈活性增強（[#79](https://github.com/ZhuLinsen/daily_stock_analysis/issues/79)）
  - 支持從 Repository Variables 讀取非敏感配置（如 STOCK_LIST, GEMINI_MODEL）
  - 保持對 Secrets 的向下兼容

### 修復
- 🐛 修復企業微信/飛書報告截斷問題（[#73](https://github.com/ZhuLinsen/daily_stock_analysis/issues/73)）
  - 移除 notification.py 中不必要的長度硬截斷邏輯
  - 依賴底層自動分片機制處理長消息
- 🐛 修復 GitHub Workflow 環境變量缺失（[#80](https://github.com/ZhuLinsen/daily_stock_analysis/issues/80)）
  - 修復 `CUSTOM_WEBHOOK_BEARER_TOKEN` 未正確傳遞到 Runner 的問題

## [1.5.0] - 2026-01-17

### 新增
- 📲 單股推送模式（[#55](https://github.com/ZhuLinsen/daily_stock_analysis/issues/55)）
  - 每分析完一隻股票立即推送，不用等全部分析完
  - 命令行參數：`--single-notify`
  - 環境變量：`SINGLE_STOCK_NOTIFY=true`
- 🔐 自定義 Webhook Bearer Token 認證（[#51](https://github.com/ZhuLinsen/daily_stock_analysis/issues/51)）
  - 支持需要 Token 認證的 Webhook 端點
  - 環境變量：`CUSTOM_WEBHOOK_BEARER_TOKEN`

## [1.4.0] - 2026-01-17

### 新增
- 📱 Pushover 推送支持（PR #26）
  - 支持 iOS/Android 跨平臺推送
  - 通過 `PUSHOVER_USER_KEY` 和 `PUSHOVER_API_TOKEN` 配置
- 🔍 博查搜索 API 集成（PR #27）
  - 中文搜索優化，支持 AI 摘要
  - 通過 `BOCHA_API_KEYS` 配置
- 📊 Efinance 數據源支持（PR #59）
  - 新增 efinance 作為數據源選項
- 🇭🇰 港股支持（PR #17）
  - 支持 5 位代碼或 HK 前綴（如 `hk00700`、`hk1810`）

### 修復
- 🔧 飛書 Markdown 渲染優化（PR #34）
  - 使用交互卡片和格式化器修復渲染問題
- ♻️ 股票列表熱重載（PR #42 修復）
  - 分析前自動重載 `STOCK_LIST` 配置
- 🐛 釘釘 Webhook 20KB 限制處理
  - 長消息自動分塊發送，避免被截斷
- 🔄 AkShare API 重試機制增強
  - 添加失敗緩存，避免重複請求失敗接口

### 改進
- 📝 README 精簡優化
  - 高級配置移至 `docs/full-guide.md`


## [1.3.0] - 2026-01-12

### 新增
- 🔗 自定義 Webhook 支持
  - 支持任意 POST JSON 的 Webhook 端點
  - 自動識別釘釘、Discord、Slack、Bark 等常見服務格式
  - 支持配置多個 Webhook（逗號分隔）
  - 通過 `CUSTOM_WEBHOOK_URLS` 環境變量配置

### 修復
- 📝 企業微信長消息分批發送
  - 解決自選股過多時內容超過 4096 字符限制導致推送失敗的問題
  - 智能按股票分析塊分割，每批添加分頁標記（如 1/3, 2/3）
  - 批次間隔 1 秒，避免觸發頻率限制

## [1.2.0] - 2026-01-11

### 新增
- 📢 多渠道推送支持
  - 企業微信 Webhook
  - 飛書 Webhook（新增）
  - 郵件 SMTP（新增）
  - 自動識別渠道類型，配置更簡單

### 改進
- 統一使用 `NOTIFICATION_URL` 配置，兼容舊的 `WECHAT_WEBHOOK_URL`
- 郵件支持 Markdown 轉 HTML 渲染

## [1.1.0] - 2026-01-11

### 新增
- 🤖 OpenAI 兼容 API 支持
  - 支持 DeepSeek、通義千問、Moonshot、智譜 GLM 等
  - Gemini 和 OpenAI 格式二選一
  - 自動降級重試機制

## [1.0.0] - 2026-01-10

### 新增
- 🎯 AI 決策儀表盤分析
  - 一句話核心結論
  - 精確買入/止損/目標點位
  - 檢查清單（✅⚠️❌）
  - 分持倉建議（空倉者 vs 持倉者）
- 📊 大盤覆盤功能
  - 主要指數行情
  - 漲跌統計
  - 板塊漲跌榜
  - AI 生成覆盤報告
- 🔍 多數據源支持
  - AkShare（主數據源，免費）
  - Tushare Pro
  - Baostock
  - YFinance
- 📰 新聞搜索服務
  - Tavily API
  - SerpAPI
- 💬 企業微信機器人推送
- ⏰ 定時任務調度
- 🐳 Docker 部署支持
- 🚀 GitHub Actions 零成本部署

### 技術特性
- Gemini AI 模型（gemini-3-flash-preview）
- 429 限流自動重試 + 模型切換
- 請求間延時防封禁
- 多 API Key 負載均衡
- SQLite 本地數據存儲

---

[Unreleased]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.32.0...HEAD
[3.32.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.31.0...v3.32.0
[3.31.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.30.0...v3.31.0
[3.30.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.29.0...v3.30.0
[3.29.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.28.0...v3.29.0
[3.28.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.27.0...v3.28.0
[3.27.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.26.1...v3.27.0
[3.26.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.25.0...v3.26.1
[3.25.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.24.1...v3.25.0
[3.24.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.24.0...v3.24.1
[3.24.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.23.0...v3.24.0
[3.23.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.22.0...v3.23.0
[3.22.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.21.1...v3.22.0
[3.21.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.21.0...v3.21.1
[3.21.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.20.0...v3.21.0
[3.20.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.19.0...v3.20.0
[3.19.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.18.0...v3.19.0
[3.18.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.17.1...v3.18.0
[3.17.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.17.0...v3.17.1
[3.17.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.16.0...v3.17.0
[3.16.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.15.0...v3.16.0
[3.15.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.14.2...v3.15.0
[3.14.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.14.1...v3.14.2
[3.14.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.14.0...v3.14.1
[3.14.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.13.0...v3.14.0
[3.13.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.12.0...v3.13.0
[3.12.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.11.0...v3.12.0
[3.11.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.10.1...v3.11.0
[3.10.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.10.0...v3.10.1
[3.10.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.9.0...v3.10.0
[3.9.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.8.0...v3.9.0
[3.8.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.7.0...v3.8.0
[3.7.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.6.0...v3.7.0
[3.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.5.0...v3.6.0
[3.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.10...v3.5.0
[3.4.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.9...v3.4.10
[3.4.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.8...v3.4.9
[3.4.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.7...v3.4.8
[3.4.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.4.0...v3.4.7
[3.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.3.22...v3.4.0
[3.3.22]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.3.12...v3.3.22
[3.3.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.2.11...v3.3.12
[3.2.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v3.2.10...v3.2.11
[2.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.5...v2.3.0
[2.2.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.4...v2.2.5
[2.2.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.3...v2.2.4
[2.2.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.2...v2.2.3
[2.2.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.1...v2.2.2
[2.2.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.2.0...v2.2.1
[2.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.14...v2.2.0
[2.1.14]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.13...v2.1.14
[2.1.13]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.12...v2.1.13
[2.1.12]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.11...v2.1.12
[2.1.11]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.10...v2.1.11
[2.1.10]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.9...v2.1.10
[2.1.9]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.8...v2.1.9
[2.1.8]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.7...v2.1.8
[2.1.7]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.6...v2.1.7
[2.1.6]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.5...v2.1.6
[2.1.5]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.4...v2.1.5
[2.1.4]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.3...v2.1.4
[2.1.3]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.2...v2.1.3
[2.1.2]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.1...v2.1.2
[2.1.1]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.1.0...v2.1.1
[2.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.6.0...v2.0.0
[1.6.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/ZhuLinsen/daily_stock_analysis/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/ZhuLinsen/daily_stock_analysis/releases/tag/v1.0.0
