# 選股引擎

DSA 將選股能力作為主項目的一部分維護。實現參考 [AlphaSift](https://github.com/ZhuLinsen/alphasift) 提交 [`9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf`](https://github.com/ZhuLinsen/alphasift/commit/9f522747caafd3c0b1ddb7e14d5cf44c8580b6cf)，並按 Apache License 2.0 修改和分發。衍生文件保留來源頭，許可證位於 `src/services/screening/LICENSE`，第三方聲明見根目錄 `THIRD_PARTY_NOTICES.md`。

## 代碼邊界

- `src/services/screening/`：快照、日 K、策略加載、過濾、評分、風險、LLM 重排與熱點實現。
- `src/services/screening/strategies/`：隨 DSA 版本發佈的策略 YAML。
- `src/services/screening/pipeline.py`：篩選流程的直接入口。
- `src/services/screening_service.py`：DSA 業務編排，直接調用 pipeline，負責配置、數據源上下文、響應歸一化、緩存與錯誤映射。
- `src/storage.py`：使用 DSA 現有 SQLAlchemy/SQLite 基礎設施持久化已完成的選股運行，不另建文件數據庫。
- `api/v1/endpoints/screening.py`：`/api/v1/screening` API。
- `apps/dsa-web/src/api/screening.ts` 與 `StockScreeningPage.tsx`：Web 調用與展示。

服務層靜態調用 `screening.pipeline`、`screening.strategy` 和 `screening.hotspot`。核心邏輯不通過模塊名探測、動態適配器或多套路由分發，因此代碼結構、錯誤邊界和打包收集目標均由主項目直接定義。

## 配置

默認關閉：

```dotenv
SCREENING_ENABLED=false
```

Web“基礎設置”頁展示“選股”開關。導航始終保留“選股”入口；關閉時頁面展示開啟提示，選股 API 繼續拒絕業務請求。頁面加載狀態時不會顯示“未開啟”或允許開啟操作；狀態請求失敗時顯示“狀態未知”和重試入口，不把網絡失敗當作配置關閉。只有確認已開啟且引擎可用後，才允許運行策略和熱點任務。打開入口或重試狀態不會自動修改配置或提交選股任務。

常用可選項：

```dotenv
SCREENING_DATA_DIR=data/screening
SCREENING_SNAPSHOT_CACHE_TTL_SEC=300
SCREENING_SOURCE_CALL_TIMEOUT_SEC=
SCREENING_HOTSPOT_CALL_TIMEOUT_SEC=8
SCREENING_HOTSPOT_SEARCH_TIMEOUT_SEC=12
SCREENING_SNAPSHOT_CALL_TIMEOUT_SEC=60
SCREENING_DAILY_CALL_TIMEOUT_SEC=20
SCREENING_EASTMONEY_MIN_INTERVAL_SEC=1.0
SCREENING_EASTMONEY_JITTER_SEC=0.3
```

路徑、緩存、超時和限流項隻影響選股鏈路。`SCREENING_SNAPSHOT_CACHE_TTL_SEC` 默認 300 秒，設為 `0` 可關閉新鮮快照複用。`SCREENING_HOTSPOT_CALL_TIMEOUT_SEC` 的正數值是默認熱點 provider 單次板塊、成分股或直接詳情 fallback 調用的總預算，後續 fallback 和並行成分股源共用同一截止時間，並把剩餘時間傳入可終止的 AkShare 子進程與 HTTP socket；設為 `0/off/disabled` 只關閉這層總預算，各真實數據源仍保留自身硬超時。`SCREENING_HOTSPOT_SEARCH_TIMEOUT_SEC` 是用戶主動新聞搜索的端到端截止時間，緩存 owner 等待、重新競爭和 provider 子進程共享同一個絕對 deadline；`0/off/disabled` 會回退到安全默認值 12 秒，而不是無限等待。完整示例以 `.env.example` 為準。

## API 契約

| 路徑 | 方法 | 行為 |
| --- | --- | --- |
| `/api/v1/screening/status` | GET | 返回開關、引擎狀態、契約版本、參考項目和數據源健康信息 |
| `/api/v1/screening/strategies` | GET | 返回選股策略 |
| `/api/v1/screening/hotspots` | GET | 讀取緩存或顯式刷新熱點題材 |
| `/api/v1/screening/hotspots/{topic}` | GET | 返回題材路線、成分股與核心股；`include_search=true` 時按需搜索近期消息 |
| `/api/v1/screening/screen/check` | POST | 用調用方提供的單條快照，逐項檢查策略硬過濾條件；不抓取行情 |
| `/api/v1/screening/screen` | POST | 同步執行選股；可傳匿名 `variant_seed` 在每次運行中生成有界的近分候選組合 |
| `/api/v1/screening/screen/tasks` | POST | 提交後臺選股任務；請求字段與同步接口一致 |
| `/api/v1/screening/screen/tasks/{task_id}` | GET | 查詢任務進度、錯誤或最終結果 |
| `/api/v1/screening/history` | GET | 按策略、市場查詢最近完成的選股運行摘要 |
| `/api/v1/screening/history/{run_id}` | GET | 讀取一條持久化的完整選股結果 |
| `/api/v1/screening/source-history` | GET | 彙總歷史運行中的快照源命中、錯誤和降級次數 |

後臺任務使用 `report_type=screening_screen`，Web 會保存活動任務 ID，並在頁面恢復時繼續輪詢。任務狀態會分別提示全市場快照、候選上下文、LLM 重排、最終評分和新聞事件增強等階段；完成後的結果同時寫入 DSA 數據庫，因此服務重啟後仍可按 `run_id` 查詢。新運行的同步/後臺響應及歷史詳情保留 `strategy_version`、`strategy_category` 和 `effective_factor_weights`，記錄執行時的策略版本、類別和實際歸一化因子權重；舊記錄不回填，也不依據升級後的策略文件改寫歷史。

## 單股條件檢查（提供快照）

快照或日線硬過濾後沒有候選的運行也保留當次策略的歸一化因子權重，與非空結果一致；權重由實際執行策略在管線出口生成，服務響應和歷史記錄不重新讀取策略目錄補填缺失權重。這些元數據記錄選股配置，不表示被淘汰的候選已經完成評分。

`POST /api/v1/screening/screen/check` 供腳本/API 客戶端解釋任意一條快照為什麼通過或未通過策略硬過濾。需要開啟 `SCREENING_ENABLED`；與已有選股接口共用管理員認證中間件，啟用認證時無有效會話返回 `401`。策略 ID 從當前啟用的策略目錄查找，並校驗 `market`（`cn`/`us`）是否在該策略的 `market_scope` 內。

```json
{
  "strategy": "dual_low",
  "market": "cn",
  "snapshot": {
    "code": "600000", "name": "Example", "price": 10,
    "amount": 100000000, "total_mv": 10000000000,
    "pe_ratio": 8, "pb_ratio": 1, "change_pct": 0
  }
}
```

- 返回 `strategy`、`strategy_version`、`market`、`provenance: "supplied_snapshot"`、整體 `passed` 和 `checks`。每項包含 `filter`、標準 `field`、實際命中的 `source_field`、`threshold`、`current_value`、`status`（`pass`/`fail`/`missing`）與 `passed`（布爾值或 `null`）；`missing_reason` 區分缺列、空值、非法數值/文本和非有限值
- 所有啟用的硬過濾條件按配置模型字段順序獨立執行，即使第一項失敗也繼續檢查後續項。複用現有過濾謂詞；數值上下界含邊界，`0` 閾值仍生效，空白名單和關閉的布爾條件不返回
- 缺列、`null`、空文本、不可解析數字和非有限數字輸出 `missing`，`current_value`/`passed` 為 `null`。缺失不是通過；整體 `passed` 僅在所有條件通過時為 `true`（無啟用條件時為 `true`）。這是診斷接口對不可用數據的保守未知標記：舊管線可能允許空名稱通過 ST 檢查或允許正無窮通過數值下界，本接口仍返回 `missing`；不改寫舊管線行為
- 輸入須為 1–64 個字段的扁平 JSON 對象；鍵長 1–64 字符，文本值最多 256 字符；嵌套值和超出有限浮點範圍的整數返回有界 `422`。使用現有標準字段/中文別名、已歸一化單位，不做幣種或百分比換算；同時提供標準名和別名時，標準名優先
- 日 K 條件直接使用提供的特徵，未提供則為 `missing`，不會補算或補抓。響應沒有實時、時間戳或數據源可信度聲明；股票代碼和市場歸屬由調用方負責，不能把該結果當成已驗證的證券身份或實時選股結果
- 不評分、不排名、不調用 LLM、不寫運行歷史、不交易。已有同步/後臺選股、水瀑統計和 Web 頁面保持原行為；此小接口尚未添加 Web UI

該交互參考 [Koyfin Check Ticker](https://www.koyfin.com/help/release-notes/check-ticker/) 的逐條件值與通過/失敗展示，僅借鑑解釋方式；不接入其數據或服務。

## 核心流程

```text
策略加載
  -> 全市場快照與字段標準化
  -> 硬過濾
  -> 因子評分與風險調整
  -> 有界候選行情/基本面/新聞與事件上下文補充
  -> LLM 重排（可降級）
  -> 風險/組合約束與近分候選輪換
  -> Top 候選 DSA 行情/基本面/新聞增強
  -> API 歸一化響應與 DSA 數據庫持久化
  -> 用戶按需進入 DSA 單股深度分析
```

- 全市場快照在短 TTL 內優先複用最近成功結果；新緩存會記錄完整且有序的數據源優先級，只在當前優先級與寫入時一致時複用，因此同一來源鏈中的後備源結果可以加速後續請求，修改來源配置後則會重新讀取實時數據。緩存過期後按配置優先級逐源嘗試，單一數據源失敗後繼續降級，並記錄 source health 與 last-good 緩存。當前 Sina、Efinance、AkShare/東財和 Tushare 快照接口均不提供增量遊標或變更序列，因此 TTL 內可以零請求複用，TTL 到期後仍需重新讀取全表；本地比較前後差異不能減少上游傳輸量，不作為“增量拉取”宣傳。
- 有 `TUSHARE_TOKEN` 時默認優先 Tushare，否則默認從 Sina 開始；顯式 `SNAPSHOT_SOURCE_PRIORITY` 始終優先。
- 日 K 優先通過請求級 fetcher 複用 DSA 歷史行情鏈路，無結果時再走篩選引擎的數據源降級；該橋接不會替換進程級函數，因此重疊選股請求之間不會共享 wrapper 或阻塞彼此。
- 存在可用的 LLM 配置時，重排前對快照評分前 3 個候選補充 DSA 行情、基本面、新聞與事件（每類搜索最多 3 條），讓事件風險可以進入既有 LLM `risk/risk_flags` 與後續風險評分。僅因子排序時繼續使用 `pre_rank_light`，新聞和事件仍在名單確定後獲取；不新增關鍵詞否決或風險閾值。
- 提示詞中的新聞/事件證據包含有界標題、摘要、來源、鏈接，並保留已有的原始發佈時間與檢索時間；搜索適配器將上游結果的 `retrieved_at` 原樣傳遞至排序、最終響應與運行歷史，缺少時間字段時保持未知，不使用適配或緩存讀取時刻補造檢索時間。真實搜索結果模型包含可空 `retrieved_at`：供應商實際查詢成功時記錄 UTC 檢索完成時間，後續日期歸一化、過濾、相關性排序及緩存複用均保留原值；已有時間不會覆蓋，舊結果缺少時間仍為未知。檢索時間不代表事件發生或發佈的時間。未採集、無結果、查詢失敗都不代表已排除風險，模型應區分證據覆蓋差異與真實風險。已有提示詞長度預算仍可能壓縮證據，並記錄裁剪說明。
- 市場上下文及候選資料（包括名稱、摘要、新聞、事件和鏈接）作為不可信 JSON 數據傳遞，獨立 system 消息要求模型不執行其中的排序命令或偽造指令。直接調用、渠道、Router、備用模型和參數恢復使用相同邊界；長度預算包含 system 消息及覆蓋率重試提示，裁剪不會截斷外部數據的 JSON 邊界，預算不足時交由既有覆蓋率保護降級。此措施降低提示詞注入風險，不保證模型一定忽略所有惡意內容；候選代碼白名單與結構化輸出校驗繼續生效。
- `pre_rank_research` 的完整結果在單次選股調用內複用，入選候選不重複查詢已嘗試的新聞/事件，包括空結果、未知發佈時間和失敗結果；下一次運行重新走搜索服務的既有緩存與降級鏈路。重排後新入選且未提前查詢的候選仍按原有入選增強上限（前 3 個入選候選）補充；一次運行最多覆蓋重排前 3 個加入選後 3 個不同候選。搜索延遲可能前移，單個來源失敗不會中斷選股。
- 該改進讓有限候選的事件證據參與 LLM 排序，不等於全市場事件硬過濾或已確認的自動事件風控；LLM 不可用時保留原有因子排序和降級提示，因子模式不依據事後搜索結果改寫名單。
- 默認本地 `scorecard` 會覆蓋完整短名單，保證所有可能進入近分輪換的候選使用同一最終評分口徑；多個後置分析器串聯時，每一步完成後都會按最新分數重排，因此後續 `dsa` 與 `external_http` 的 `POST_ANALYSIS_MAX_PICKS` 上限作用於當前真實前列。遠程狀態按實際提交候選記錄，外部響應中的超限代碼不會改寫未提交候選；啟用遠程分析時輪換只會在已完成相同分析的候選之間發生。
- 模型、渠道、base URL、額外 headers、fallback、timeout 和 token 上限在單次調用範圍內注入，不改寫用戶配置；主模型即使 HTTP 調用成功，但返回空內容、非 JSON 或覆蓋率不足，也會繼續嘗試已配置的備用模型。最終 JSON 必須在 `content` 塊或 `output` 塊中；`reasoning_content`（鏈式思考）被視為內部輔助，不作為最終結果。
- 熱點榜單刷新與選股長流程可並行執行；列表默認不批量預取詳情，用戶選中具體題材時才加載該題材詳情；顯式刷新後若繼續保留當前題材，Web 會同步繞過詳情緩存重拉該題材，保證榜單與詳情來自同次刷新。
- 熱點成分股並行獲取東方財富與同花順數據，並按固定數據源優先級合併，避免響應先後改變重複股票的字段：正數 `SCREENING_HOTSPOT_CALL_TIMEOUT_SEC` 作為默認 provider 整次調用的共享預算，板塊列表、成分股以及引擎失敗後的直接詳情 fallback 都進入該預算；AkShare/東方財富的可終止子進程與同花順 HTTP connect/read timeout 每一步只使用剩餘時間，fallback 不會重新獲得完整預算。直接詳情 fallback 不再額外啟動無法由該預算強制回收的實時行情預取，行情字段以已受控的成分股源結果為準。超時子進程會 terminate/kill 並回收；進程級併發槽限制活躍任務數量，方法返回前會等待已接納的 worker 結束，不遺留後臺線程。關閉整次調用預算時，各單源仍保留默認硬超時；單源失敗不會阻止另一源和本地核心股回退。
- “搜索最新消息”複用 DSA 原生搜索服務的 provider 優先級、SearXNG 公共實例能力、結果緩存與請求合併，同一緩存鍵只有 owner 可以啟動供應商鏈；owner 未產出可緩存結果時，等待者重新競爭且未獲得所有權的請求繼續等待，但緩存等待、搶佔和 provider 執行共用請求的絕對 deadline，不會在排隊後重新獲得完整超時。搜索只補充有鏈接的事件/催化，不從網頁內容推斷板塊成分股；增強記錄分別追加到展示路線和原始時間線，不覆蓋已有 `timeline`。搜索由用戶主動觸發，摘要在本地確定性壓縮，不調用 LLM；響應以 `available`、`no_results`、`unavailable` 區分有結果、有效空結果和超時/容量/供應商失敗，Web 不會再把運行失敗提示成“沒有近期消息”。搜索增強僅存在於本次響應，不寫入或續期共享熱點詳情緩存，默認詳情請求不會看到搜索狀態或增加搜索等待。供應商子進程在啟動、執行或清理任一階段失敗時都會釋放進程級容量。
- 熱點實時請求失敗時優先使用 last-good cache；無緩存時返回穩定空態與明確錯誤。

## 結果輪換

Web 會在瀏覽器本地生成一個不含用戶信息的匿名種子，並隨同步或後臺選股請求傳入 `variant_seed`。如果 Web Storage 不可讀寫，則在當前頁面會話的模塊內存中複用同一個臨時種子，保證同步和後臺任務入口一致。服務端將匿名種子與本次運行 ID、市場和策略共同作為擾動輸入：不同瀏覽器以及同一瀏覽器的不同運行，都可能在質量接近的候選中看到不同股票。

擾動不是隨機改分，也不會繞過策略：硬過濾、風險否決、因子/LLM 得分、最終評分和組合集中度懲罰全部先執行。默認本地評分覆蓋完整短名單；啟用有數量上限的遠程後置分析時，只有完成相同分析的候選才可參與輪換。分析器產出的候選順序是輪換輸入的權威順序，並列分不會再按股票代碼重新排序；原 Top-N 的前半部分和明顯高於截止分的候選始終受保護，只有後半部分名額可從不低於原截止分 1.5 分的近分池中抽取，入選候選繼續保持該輸入相對順序。種子不寫入選股結果或運行歷史。未傳 `variant_seed` 或將輪換比例設為 0 時返回嚴格輸入 Top-N，保持腳本與舊客戶端兼容。

## 緩存與持久化

| 數據 | 位置 | 有效期/行為 |
| --- | --- | --- |
| 全市場快照 | `data/screening/snapshot.last_good.json` | 默認 5 分鐘內直接複用且不標記 fallback；過期後請求實時源，實時源全部失敗時仍可按最大陳舊時間約束回退並標記 stale/fallback |
| 個股日 K | `data/screening/daily_history/` | 按代碼、來源和回看窗口分鍵，默認 TTL 24 小時，並核驗最新已收盤交易日及緩存獲取時段；刷新失敗時可使用舊數據並標記 stale |
| 行業/概念映射 | `data/screening/industry_provider_cache/` | 默認 TTL 24 小時，並保存板塊熱度歷史用於趨勢計算 |
| 熱點列表與歷史 | `data/screening/hotspots.json`、`hotspot.history.jsonl` | 顯式刷新寫入；實時失敗時回退最近可用快照 |
| 熱點詳情 | `data/screening/hotspot_details/` | 默認 TTL 30 分鐘；只緩存結構化基礎詳情，顯式消息搜索不寫入或續期該緩存；實時失敗時可回退過期詳情並返回陳舊時長 |
| DSA 實時行情 | `DataFetcherManager` 的行情緩存 | 默認 TTL 10 分鐘，沿用 `REALTIME_CACHE_TTL` |
| DSA 基本面/資金流 | `DataFetcherManager` 的基本面緩存 | 默認 TTL 120 秒，沿用 `FUNDAMENTAL_CACHE_TTL_SECONDS` |
| DSA 新聞/公告事件 | `SearchService` 內存緩存 | 成功結果默認 TTL 10 分鐘；同題材併發請求在父進程合併，實際供應商鏈在限流、可終止的子進程中執行；服務重啟後重新查詢 |
| 完整選股結果 | DSA 數據庫 `screening_runs` 表 | 完成後按 `run_id` 冪等寫入；數據庫寫入失敗不阻斷選股主流程 |

候選上下文模塊也支持 24 小時文件緩存，但 DSA 集成默認關閉其獨立新聞/公告抓取，改用 DSA 自己的資訊、基本面和實時行情鏈路，避免同一候選重複請求兩套數據源。

### 日線新鮮度

- 複用現有交易日曆與市場時區：盤前只接受上一已收盤交易日，盤中要求至少覆蓋上一已收盤交易日且最新日期為實際交易日，收盤後要求覆蓋當日；週末與節假日要求覆蓋最近已收盤交易日。重新開盤後的盤中階段也拒絕日期區間內的休市日偽日線。TTL 仍是獨立上限，休市不會自動延長 TTL。
- 緩存文件在收盤前生成，即使包含當日的部分 K 線，也不能在收盤後直接視為完整日線。緩存覆蓋日期不足、日期缺失/無效、日期超出當前市場日期或最新日期沒有有效收盤價時，TTL 內也會嘗試刷新。
- DSA 日線同樣核驗覆蓋日期並保留已有陳舊標記。舊 DSA 數據先嘗試選股原生數據源；原生來源取得新鮮日線時替換，全源陳舊時選擇最新有效日期，同日保留 DSA 優先級，並記錄備用來源的失敗和降級信息。DSA 與原生來源的陳舊日線均不會覆蓋 last-good 文件緩存；調用方注入舊日線時也會標記陳舊。
- `DAILY_SOURCE=auto` 的非空陳舊結果不會終止來源鏈路，仍按既有來源順序嘗試後續來源。取得新鮮結果才更新緩存；所有來源都無法提供新鮮日線時，比較所有實時陳舊結果和文件緩存的最新有效日線日期，優先使用日期較近的數據，同日仍保留原來源優先級。緩存中的盤中數據繼續標為陳舊，不能冒充完整收盤數據。陳舊來源記入來源順序說明，真實請求失敗仍記錄在 `source_errors`；新鮮備用結果不會繼承陳舊標記。
- 文件緩存優先使用載荷內帶時區的獲取時間檢查 TTL 與收盤切換，桌面備份恢復改寫 mtime 不會刷新這類緩存的獲取時間；舊版無時區的 `created_at` 無法確定原寫入機器時區，與時間缺失或非法的緩存一樣回退 mtime，跨主機遷移時應保留文件 mtime。所有帶有效收盤價的日期行均核驗實際交易日，原生來源、DSA 與緩存中夾雜的週末、節假日或缺失/無法解析日期的 bar 也會被拒絕，即使最新一行是合法交易日；沒有有效收盤價的行不參與該核驗。
- 顯式 `DAILY_SOURCE=yfinance` 按美東市場日期確定日線下載範圍，排他的 `end` 設為下一自然日，使 UTC、美東等部署時區在收盤後都能取得供應商已提供的當日 K 線。
- 陳舊數據沿用 `daily_stale` / `daily_quality_flags=stale_cache` 的降級契約，進入既有日線質量評分與風險懲罰，不將數據源故障變成整個選股任務失敗。新鮮度檢查不改變策略硬過濾、風險否決開關或因子權重。
- 日曆不可用、市場無法識別或日曆範圍不足時，保留 TTL 判斷；顯式陳舊標記仍有效。日期覆蓋只能檢查歷史是否滯後，無法證明供應商同日 K 線已完成結算；無供應商獲取時間的同日數據保留這一邊界。

選股運行歷史目前用於復現名單與診斷；已有 `BacktestService` 的候選來自單股分析歷史，並未直接評估 `screening_runs`。直接按選股運行進行 T+N 評估仍需接入現有回測鏈路，保存策略元數據本身不代表已完成收益驗證。

## 兩類策略的邊界

DSA 中存在兩類用途不同的策略文件：

| 位置 | 解決的問題 | 加載方 | 執行階段 |
| --- | --- | --- | --- |
| `src/services/screening/strategies/*.yaml` | 從全市場篩出哪些候選 | `src/services/screening/strategy.py` | 快照過濾、因子評分、風險和排序 |
| `strategies/*.yaml` | 對單隻股票如何分析和形成結論 | `src/agent/skills/base.py` | DSA Agent/報告分析 |

即使 `shrink_pullback`、`volume_breakout` 同名，兩者也使用不同目錄、Schema 和 loader，不會相互覆蓋。篩選策略可通過 `analysis_skills` 聲明下一階段建議使用的分析 skill；Web 的“進一步深度分析”會顯式攜帶這些 skill。未聲明映射的篩選策略繼續使用用戶當前選擇或默認分析策略，不做含義不可靠的強行映射。

## DSA 原生能力複用

- 行情：日 K 優先調用 DSA `DataFetcherManager`，無結果才進入篩選模塊自己的多源 fallback；最終候選繼續補 DSA 實時行情。
- 基本面與資訊：最終候選複用 DSA 基本面上下文和 `SearchService`；資本流向來自 DSA 基本面上下文，重要公告/業績/減持事件調用 DSA `search_stock_events`，熱點消息搜索沿用其數據源優先級、時效過濾、緩存和同請求合併，僅將真實供應商調用隔離到可終止子進程，不重複維護獨立資訊入口。
- 模型：沿用 DSA LiteLLM 模型、渠道、fallback、base URL、額外 headers、超時和 token 配置。
- 任務與頁面：複用 DSA 後臺任務隊列、Web 輪詢和桌面端同源 Web 資源。
- 存儲與後續分析：運行結果寫入 DSA 數據庫；候選可進入 DSA 原生單股分析並攜帶策略 skill。

對照固定參考提交，快照、日 K、美股、行業/概念、熱點、候選新聞/公告/資金流、字段標準化、過濾、評分、風險、排序和數據源熔斷等原始數據與選股能力均已納入；其中公告/事件和資金流在 DSA 編排層分別接入原生事件搜索與基本面上下文。參考項目另外提供獨立 CLI/server、JSON 文件 store、報告渲染、doctor、運行/數據源歷史和 T+N 評估：本實現只吸收 DSA 確實缺少的運行歷史與數據源歷史，並接到 DSA 數據庫；CLI/server 不重複建設。後續選股 T+N 評估應接入 DSA 已有 BacktestService，避免形成第二套回測真源；當前服務評估單股分析記錄。實時 source health 已在 `/status` 返回，歷史穩定性由 `/source-history` 補齊。

## 收益

1. 選股服務、策略、API、Web 和打包腳本在同一版本中演進，避免契約漂移。
2. 服務層只有一套原生調用路徑，狀態探針和業務請求反映相同實現。
3. Docker 與桌面產物直接收集同一份模塊和策略資源，部署結果更一致。
4. 數據源降級、評分和策略變化可以在主倉庫完成端到端審查與迴歸。
5. 來源 commit、許可證和逐文件歸因明確，便於後續選擇性同步上游修復。

## 風險與控制

| 風險 | 影響 | 控制措施 |
| --- | --- | --- |
| 主倉庫維護面擴大 | 數據源或策略問題由 DSA 直接承擔 | 模塊邊界、契約測試和 CI 打包探針共同約束 |
| 與參考項目逐漸分叉 | 上游修復不能直接覆蓋 | 固定參考 revision，逐模塊比較並選擇性移植 |
| 數據源限流或字段變化 | 快照、熱點或日 K 降級 | timeout、retry、source health 與 last-good cache |
| LLM 超時或格式異常 | 重排不可用或解釋字段缺失 | 非結構化響應繼續嘗試備用模型；全部失敗時保留因子排序，並返回嘗試模型與失敗原因 |
| 結果輪換擴大候選差異 | 臨界候選可能因瀏覽器不同而變化 | 僅輪換近分尾部位，保持硬過濾、風險否決、分值和頭部候選不變；無種子時關閉 |
| 緩存目錄變化 | 升級後舊緩存不會自動複用 | 新目錄獨立為 `data/screening`；升級前按需備份 |
| 運行歷史增長 | 完整候選結果會增加數據庫體積 | 歷史接口默認只讀摘要，運維可按現有數據庫備份/保留策略管理 |
| 配置與 API 更名 | 舊自動化需同步調整 | 在發佈說明明確 `SCREENING_ENABLED` 與 `/api/v1/screening` |
| 許可證歸因遺漏 | 發佈合規風險 | 保留 LICENSE、THIRD_PARTY_NOTICES 和衍生文件頭 |

選股結果僅用於研究和輔助判斷，不構成投資建議，也不保證收益或數據完整性。

## 更新參考實現

AlphaSift 是參考來源，不是自動同步源。更新時應：

1. 記錄目標 commit 和許可證變化；
2. 比較 `src/services/screening/` 的 DSA 特有修改，按模塊選擇性移植；
3. 更新衍生文件頭、`REFERENCE_REVISION` 和 `THIRD_PARTY_NOTICES.md`；
4. 檢查 pipeline、API/Web 字段、數據源降級、策略資源與凍結打包；
5. 更新本文檔和 `docs/CHANGELOG.md`，完成後端、Web、Docker/桌面驗證。

## 回滾

- 業務回滾：設置 `SCREENING_ENABLED=false` 並重啟；普通個股分析、報告、通知和問股不受影響。
- 代碼回滾：revert 引入選股引擎的提交併重建後端、Docker 與桌面產物。
- 數據回滾：如需保留選股緩存和運行歷史，先備份 `data/screening/` 與 DSA 數據庫；代碼回滾不會主動刪除 `screening_runs` 用戶數據。

實際運行元數據 `effective_factor_weights` 保留有限、非負權重，包括明確為 0 的禁用因子；候選解釋只消費正權重，避免將禁用因子作為入選理由。

盤前只接受上一已完成交易日，盤前獲取的當天佔位 K 線在盤中仍需刷新。DSA 和備用來源都陳舊時同樣優先較新有效日期，同日保留 DSA 優先級。

全源降級比較只認可非未來、實際交易日的最新日線；非法日期優先級低於有效陳舊日線。日曆不可用時保持原有降級語義。

僅有非法日期或盤前佔位數據且無合法備用行情時，走已有聚合取數失敗路徑，不生成虛假交易日的技術因子；DSA 與文件緩存同樣驗證。

日線通過交易日期驗證後才計來源成功；非法日期響應累計現有失敗計數與熔斷，冷卻後合法響應恢復，合法陳舊行情仍按成功取數及陳舊質量處理。
