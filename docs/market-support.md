# 市場支持與邊界

## 日本/韓國個股 suffix-only MVP（Issue #1718，Refs #1718）

當前階段支持手動輸入日本、韓國股票的 Yahoo Finance 後綴代碼，進入既有個股分析、歷史保存和基礎報告展示鏈路。Web 自動補全內置一批常用日股/韓股種子索引，支持按 suffix 代碼、中英文名稱或常用別名搜索。

支持格式：

- 日本：`7203.T`、`6758.T`
- 韓國 KOSPI：`005930.KS`
- 韓國 KOSDAQ：`035720.KQ`

約束與邊界：

- 手動輸入裸代碼時會先檢索本地/遠程股票池；若 `005930`、`000660` 等裸碼命中 `005930.KS`、`000660.KS` 等日韓條目，則按命中的市場提交分析；若股票池未命中，仍按既有 6 位數字代碼規則默認落到 A 股語義，並保留為可追蹤的跨市場歧義邊界。
- 日股/韓股 suffix 識別已集中到共享市場代碼工具，數據源路由、Prompt 市場識別、交易日曆和股票索引裸碼解析複用同一組規則，減少後續市場擴展時的規則漂移。
- 日股/韓股日線和基礎實時/近實時行情只走 `YfinanceFetcher`，不嘗試 AkShare、Tushare、Efinance、Pytdx、Baostock 等 A 股專屬數據源；yfinance 報價會盡量帶上 `market`、`currency`、`data_quality`、`missing_fields` 等質量元數據。
- 基本面複用既有 offshore yfinance 輕量路徑；A 股專屬資金流、龍虎榜、板塊等能力按 `not_supported` 降級，offshore 基本面上下文也會標記 provider、as_of、data_quality 和缺失塊。
- 報告 Prompt 已增加日股/韓股市場語義，避免套用 A 股漲跌停、北向資金、龍虎榜、融資融券等概念。
- 交易日曆註冊 `jp: XTKS / Asia/Tokyo` 與 `kr: XKRX / Asia/Seoul`。日股常規階段可識別盤前、盤中、午休、15:25-15:30 收盤集合競價、盤後與非交易日；韓股常規階段可識別盤前、盤中、15:20-15:30 收盤集合競價、盤後與非交易日。若本地 `exchange-calendars` 版本缺少對應日曆，既有 fail-open/fail-closed 語義保持不變。

兼容性與回退說明（針對結構化檢測命中項）：

- `#1815` 本次僅新增 `yfinance` 報價/基本面上下文中的可選字段元數據（如 `market`、`currency`、`data_quality`、`missing_fields`、`provider`），未改動 LLM provider/model/base URL、配置 Schema、運行時環境變量、數據庫字段、存量緩存序列化或消息協議版本。
- 與本條 PR 相關的配置語義上，未新增或替換 provider、model、base URL，未新增配置清理/遷移分支；已保存配置仍保持原樣，回退方式為回退該提交。
- 外部 API 邊界仍僅限既有 `yfinance` fetch 路徑（含 `Ticker`/`history`/`fast_info`）與既有兜底邏輯；沒有新增或遷移 API 網關/host，`YFINANCE_PRIORITY` 是唯一受影響的可見參數。JP/KR 主指數與 Yahoo symbol 對應如下（可核驗）：
  - 日經225：`^N225`（<https://finance.yahoo.com/quote/%5EN225/>）
  - 東證指數：`^TOPX`（<https://finance.yahoo.com/quote/%5ETOPX/>）
  - KOSPI：`^KS11`（<https://finance.yahoo.com/quote/%5EKS11/>）
  - KOSDAQ：`^KQ11`（<https://finance.yahoo.com/quote/%5EKQ11/>）
  - 依賴版本：`requirements.txt` 中 `yfinance>=0.2.0`，迴歸覆蓋路徑見 `tests/test_yfinance_jp_kr_indices.py` 與 `tests/test_yfinance_hk_indices.py`。
- 兼容性與回退：`MARKET_REVIEW_REGION` 會保留合法逗號子集（如 `cn,us`）並保持 `both` 全量行為，非法值或空值回退到 `cn`，不會清空或遷移已保存配置。
- 運行時邊界：JP/KR 指數按 market_review 的 fail-open 約定逐項抓取；單項失敗不會阻斷其餘指數與其他市場；當兩個市場均無可用主指數行情時返回本地可見 `None/空`，主流程繼續可按其餘市場輸出或直接降級。
- 兼容性驗證依據：行情/基本面上下文在 `data_provider/base.py` 與 `realtime_types.py` 中按現有 `getattr`/可選字段約定向下游透傳，不強制讀寫新增字段；無配置遷移腳本，未觀察到 provider/model/base URL fallback 路徑變更。
- 回退方式：若新增元數據字段在某端產生兼容問題，可先忽略這些字段並按既有市場判定+行情展示鏈路運行；必要時回滾本次提交或通過移除 `jp/kr` `MarketSymbol` 及路由擴展恢復舊行為。

不承諾項：

- 不承諾實時行情；Yahoo Finance 數據可能延遲或字段缺失。
- 不承諾完整基本面、行業/板塊、市場寬度或漲跌家數。JP/KR 大盤覆盤 v1 僅提供主要指數、新聞線索與模板/LLM 覆盤，不提供日韓市場寬度或板塊排行。
- 不承諾完整日韓全市場股票列表；Web 自動補全當前僅覆蓋倉內種子索引中的常用標的（已擴充至各 30 只左右的頭部標的），未命中時仍可手動輸入 suffix 代碼。
- 不補齊 Portfolio 的 JPY/KRW 匯率、成本、市值完整口徑；相關字段僅放開市場類型以避免前後端校驗拒絕。

回滾方式：移除 `jp/kr` 市場識別、交易日曆註冊、YFinance 路由擴展、Web/API 類型放行、`scripts/stock_index_seeds/` 日韓種子索引，並刪除本文檔中的能力聲明。

## 日本/韓國大盤覆盤 v1（Issue #1815 Phase 2）

大盤覆盤 `MARKET_REVIEW_REGION` 新增 `jp` 與 `kr`，並納入 `both` 的多市場順序：`cn,hk,us,jp,kr`。

支持範圍：

- `jp`：通過 Yahoo Finance 獲取日經225 `^N225` 與東證指數 `^TOPX`，輸出日股大盤覆盤。可複核頁面：
  - `^N225`：<https://finance.yahoo.com/quote/%5EN225/>
  - `^TOPX`：<https://finance.yahoo.com/quote/%5ETOPX/>
- `kr`：通過 Yahoo Finance 獲取 KOSPI `^KS11` 與 KOSDAQ `^KQ11`，輸出韓股大盤覆盤。可複核頁面：
  - `^KS11`：<https://finance.yahoo.com/quote/%5EKS11/>
  - `^KQ11`：<https://finance.yahoo.com/quote/%5EKQ11/>
- Web 設置頁通過 `MARKET_REVIEW_REGION` 文本框輸入逗號分隔子集（如 `cn,jp`、`cn,us,jp,kr`）；交易日檢查會按 `XTKS / Asia/Tokyo` 與 `XKRX / Asia/Seoul` 過濾 `both` 中當日開市市場。
- 覆盤策略、新聞搜索詞、Prompt 市場語義和中英文通知標題均按 JP/KR 獨立 profile 處理。

說明（兼容性與驗收口徑）：

- 線上數據可用性來自 Yahoo Finance 指數頁面與接口契約，當前實現僅覆蓋 `data_provider/yfinance_fetcher.py` 的指數路由與降級行為；不對實時行情連通性作穩定性承諾。
- 與該條目標相關的本地自動化驗證默認使用離線迴歸：`tests/test_yfinance_jp_kr_indices.py`、`tests/test_yfinance_hk_indices.py`（共性映射/回退）與 `tests/test_trading_calendar.py`（交易日過濾）。如果要補充實時可用性複核，可在聯網環境直接訪問上述 Yahoo Finance 頁面進行一次性抽檢。

- 外部兼容性邊界（當前實現默認假設）：
  - 數據源：`yfinance`（版本下限 `requirements.txt` 中的 `yfinance>=0.2.0`）
  - 長期約束：`^N225`、`^TOPX`、`^KS11`、`^KQ11` 必須在 Yahoo Finance 端有可檢索 quote 頁面；無法檢索視為索引級不可用，由 `market_review` fail-open 機制退化到已有市場輸出，不中斷主流程。
- 兼容驗證（可複核）：
  - <https://finance.yahoo.com/quote/%5EN225/>
  - <https://finance.yahoo.com/quote/%5ETOPX/>
  - <https://finance.yahoo.com/quote/%5EKS11/>
  - <https://finance.yahoo.com/quote/%5EKQ11/>
  - 可復現聯機複核命令（選做）：
```bash
python - <<'PY'
from yfinance import Ticker
for symbol in ("^N225", "^TOPX", "^KS11", "^KQ11"):
    data = Ticker(symbol).history(period="5d")
    print(symbol, "rows", len(data))
PY
```

邊界：

- JP/KR 大盤覆盤 v1 不提供漲跌家數、漲跌停、行業/板塊排行或資金流統計；結構化 payload 中 `breadth` 仍只在有市場寬度數據時出現。
- 單一 JP/KR 指數拉取失敗按既有 yfinance fail-open 邏輯跳過，不拖垮其它指數或其它市場。
- 如果 `exchange-calendars` 缺少對應交易所日曆，繼續沿用既有交易日 fail-open/fail-closed 語義。

回滾方式：從 `MARKET_REVIEW_REGION` 合法值、Web 設置枚舉、MarketProfile/MarketStrategy、`_MARKET_REVIEW_MARKETS` 和本文檔中移除 `jp` / `kr`。

## 臺灣個股支持（suffix-only，Issue #1772 / #1777）

當前階段支持手動輸入臺灣股票的 Yahoo Finance 後綴代碼，進入既有個股分析、歷史保存、報告渲染、DecisionSignal、Portfolio 和 Intelligence 鏈路。TWSE 上市股票使用 `.TW` 後綴，TPEx 上櫃（櫃買）股票使用 `.TWO` 後綴，二者摺疊為同一 `tw` 市場標籤。

近期臺股鏈路已從早期 MVP 收斂為一等個股分析市場：市場識別、數據路由、交易日曆/市場階段、YFinance 日線與基礎行情、主要指數、服務層/API/Web 市場枚舉、TWD 幣種標註、三大法人報告區塊與 LLM prompt 消費均已接入。仍需保留的邊界是：臺股股票池種子/自動補全、大盤覆盤 `MARKET_REVIEW_REGION=tw`、Market Light 大盤紅綠燈告警和完整臺股市場寬度/板塊排行尚未納入。

支持格式：

- 上市（TWSE）：`2330.TW`、`0050.TW`
- 上櫃（TPEx / 櫃買）：`6488.TWO`、`5483.TWO`
- 代碼 base 為 4-6 位數字（普通股 4 位，ETF/其他至 6 位，如 `00878.TW`、`006208.TW`），較日股 `.T` 的 4-5 位更寬。

約束與邊界：

- **嚴格 suffix-only**：裸 `2330`、`00878` 等不帶後綴的代碼不會進入臺股語義（`detect_market` / `get_market_for_stock` 僅在顯式 `.TW`/`.TWO` 後綴時返回 `tw`）。當前未內置臺股股票索引/種子解析，Web 自動補全不承諾完整臺股股票池；未命中時請手動輸入完整 suffix 代碼。
- 臺股日線和基礎實時/近實時行情只走 `YfinanceFetcher`，不嘗試 AkShare、Tushare、Efinance、Pytdx、Baostock 等 A 股專屬數據源。
- 基本面複用既有 offshore yfinance 輕量路徑；`institution` 區塊額外消費臺股三大法人資料並渲染到報告，A 股專屬資金流、龍虎榜、板塊等能力按 `not_supported` 降級。
- 報告 Prompt 已增加臺股市場語義（新臺幣、三大法人、TWSE/TPEx ±10% 漲跌停），並將三大法人淨買賣超注入 LLM 分析上下文，避免套用 A 股北向資金、龍虎榜等概念。
- 交易日曆註冊 `tw: XTAI / Asia/Taipei`。TWSE 為 09:00–13:30 連續交易、無午休；收盤集合競價 13:25–13:30 已按 5 分鐘啟發式窗口建模（`_CLOSING_AUCTION_WINDOW_MINUTES["tw"]=5`，`market_phase` 可返回 `closing_auction`）。JP/KR 也已按常規交易時段補齊收盤集合競價窗口（JP 15:25-15:30、KR 15:20-15:30）。若本地 `exchange-calendars` 版本缺少對應日曆，既有 fail-open/fail-closed 語義保持不變。
- 主要指數提供加權指數 `^TWII` 與櫃買指數 `^TWOII`。
- 三大法人買賣超（institutional flows）資料層：`TwInstitutionalFetcher`（`data_provider/tw_institutional_fetcher.py`）提供上市（TWSE T86，legacy `rwd` 端點）/ 上櫃（TPEx OpenAPI）每日外資·投信·自營商·三大法人買賣超（單位：**股數**；按日期+市場做單日全市場緩存再過濾個股，TPEx 民國年轉西元有單測覆蓋）。接口失敗/限流/空響應/字段缺失一律 **fail-open** 返回無數據，不中斷分析；僅對 `.TW`/`.TWO` 生效，不改動現有市場流程。資料來源為政府開放資料，採「政府資料開放授權條款第 1 版」(OGDL v1，允許商用與再散佈，需標示來源)。
- 三大法人 fetcher 已具備併發緩存防擊穿和按 TWSE/TPEx 分流的熔斷保護；TPEx OpenAPI 僅服務最新交易日，傳入與服務日期不符的明確日期會 fail-open 返回無數據，避免錯日資料靜默進入報告。
- 臺股財務金額會使用 TWD -> 「新臺幣」標註，避免落入 A 股語境下的默認「元」。

不承諾項：

- 不承諾實時行情；Yahoo Finance 數據可能延遲或字段缺失。
- 不承諾完整基本面、行業/板塊、市場寬度、漲跌家數或臺股大盤覆盤；`MARKET_REVIEW_REGION` 仍只接受 `cn/hk/us/jp/kr/both` 或這些市場的逗號子集。
- 臺股股票索引/種子和 Web 自動補全仍未完整接入；告警 MarketRegion 與後端 Market Light 告警仍為 `cn/hk/us`，未含 `tw`。
- 不補齊 Portfolio 的 TWD 匯率、成本、市值完整口徑；臺股 Portfolio 當前屬於 partial valuation 市場。

回滾方式：移除 `tw` 市場識別、交易日曆註冊、YFinance 路由擴展、三大法人資料層/報告消費、TWD 標註、服務層/API 市場枚舉及前端市場類型放行，並刪除本文檔中的能力聲明。

## 日本/韓國 Portfolio 與 Market Light 邊界（Issue #1815 Phase 3）

Portfolio 允許 JP/KR 賬戶、交易和持倉快照進入現有鏈路，但會將賬戶/持倉快照標記為 `data_quality=partial`，並通過 `limitations` 明確 `realtime_quote_best_effort`、`fx_and_cost_basis_partial`、`sector_and_risk_metrics_limited`；不承諾 JPY/KRW 匯率、成本、市值、行業集中度或組合風險指標完整口徑。

- JP/KR 賬戶、交易、現金流水和公司行動 API 保持可創建/查詢；當前不新增 JPY/KRW 匯率源、稅費模型、交易單位/最小變動價位校驗或行業映射。
- Market Light 快照和 Market Light 告警仍只支持 `cn` / `hk` / `us`。
- Web 告警市場下拉不展示 `jp` / `kr`；後端 `normalize_market_region()` 對 `jp` / `kr` 返回顯式 unsupported 錯誤。
- Web 設置頁中 `MARKET_REVIEW_REGION` 從固定枚舉下拉收斂為自由文本輸入，用於保存 `cn,us,jp`、`cn,hk,us` 等逗號分隔子集；該 UI 變化隻影響大盤覆盤配置，不影響 Market Light 告警市場枚舉。
- `MARKET_REVIEW_REGION` 既有 `cn`、`hk`、`us` 可原樣保留；若用戶希望維持 JP/KR 擴展前 `both` 對應的三市場覆盤邊界，應改為 `cn,hk,us`；只有希望納入五市場覆盤時才繼續使用 `both` 或顯式配置 `cn,hk,us,jp,kr`。
- 該輪邊界收斂不改動 LLM Provider / Model / Base URL 的持久化語義，也不執行默認模型、運行時配置清理或回寫；配置更新仍是**原子 upsert**（`ConfigManager.apply_updates`），保存/導入只寫入提交的鍵，未提交的 `LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`OPENAI_BASE_URL` 等舊值保留不清空。
- 可直接核驗的配置兼容證據：本輪未新增或替換外部 provider/model/Base URL，仍沿用 LiteLLM OpenAI-compatible 路由（<https://docs.litellm.ai/docs/providers/openai_compatible>）、OpenAI Chat Completions 請求形狀（<https://platform.openai.com/docs/api-reference/chat/create>），以及 [LLM 服務商配置指南](llm-providers.md#官方來源與兼容性) 中集中維護的各 provider 官方來源鏈接。當前運行時依賴窗口以 `requirements.txt` 的 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 為準；舊配置沒有遷移腳本或清理分支，保存/導入仍只通過 `ConfigManager.apply_updates` 寫入本次提交鍵。回退路徑是恢復變更前 `.env`/配置備份中的 `MARKET_REVIEW_REGION`，或直接 revert 本 PR；未提交的 `LITELLM_CONFIG`、`LLM_CHANNELS`、`LLM_OPENAI_*`、`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`VISION_MODEL`、`OPENAI_*` 等既有運行時配置不需要遷移。迴歸證據為 `tests/test_system_config_service.py::SystemConfigServiceTestCase::test_update_market_review_region_does_not_trigger_runtime_model_cleanup` 與 `tests/test_config_env_compat.py::test_market_review_region_updates_do_not_change_llm_provider_model_contract`。
- Web UI 可視證據口徑：Market Light 告警目標範圍切到“大盤市場”時，市場區域下拉只顯示 A 股、港股、美股，不顯示日股/韓股；設置頁 `MARKET_REVIEW_REGION` 渲染為可輸入逗號分隔值的文本框。當前倉庫不保存一次性截圖證據，可替代證據為 `apps/dsa-web/src/components/alerts/__tests__/AlertRuleForm.test.tsx`、`apps/dsa-web/src/components/settings/__tests__/SettingsField.test.tsx` 和 `apps/dsa-web/tests/system_config_i18n.test.ts` 的斷言。

回滾方式：移除 Portfolio snapshot 的 `data_quality` / `limitations` 擴展，恢復告警前端/後端對市場枚舉的舊邊界說明；如需整體回滾，移除 `jp/kr` 市場識別、交易日曆註冊、YFinance 路由擴展、Web/API 類型放行、`scripts/stock_index_seeds/` 日韓種子索引，並刪除本文檔中的能力聲明。
