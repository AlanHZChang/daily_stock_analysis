# 資訊 / 情報源 MVP

Issue #1707 的首版能力聚焦“合規資訊源採集、本地沉澱、可查詢證據”，不把 RSS/Atom 混入按需搜索語義，也不默認新增獨立輿情頁。

## 能力範圍

- 支持配置 RSS / Atom HTTP(S) 資訊源。
- 支持 NewsNow HTTP JSON 源，默認內置財聯社熱門、雪球熱門股票、華爾街見聞快訊、金十數據和格隆匯事件等主流財經源。
- 支持查詢內置 RSS/Atom/NewsNow 模板，並可從模板創建可測試、可啟停的資訊源；也可以一鍵創建全部內置默認源。
- 保存資訊源配置、啟用狀態、作用域和最近一次拉取狀態。
- 拉取條目落庫到 `intelligence_items`，保存標題、摘要、URL、來源、發佈時間、拉取時間、市場與作用域。
- 按 URL 去重；無 URL 條目使用 `no-url:intel:<hash>` 兜底鍵。
- 支持 `symbol` / `market` / `sector` 作用域，以及 `cn` / `hk` / `us` / `jp` / `kr` / `tw` / `global` 市場標記。
- 拉取批處理採用 fail-open：單個源失敗不會阻塞其他源或主分析鏈路。
- 支持 retention 清理，避免資訊池無限增長。

## 安全邊界

自定義 URL 會做基礎校驗：

- 只允許絕對 `http` / `https` URL；
- 禁止 URL 中攜帶 username/password；
- 禁止 `localhost`、`.local`、迴環地址、內網地址、鏈路本地地址、保留地址、共享地址段和組播地址；
- 解析與拉取階段顯式禁用環境代理（如 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`），避免通過環境代理繞過校驗邊界；
- 實際連接階段會再次校驗目標主機 DNS 解析結果，避免校驗後解析漂移到受限地址；
- 重定向後的最終 URL 也會再次校驗；
- 錯誤消息會脫敏常見 `token` / `key` / `secret` 查詢參數。

明確非目標：不做反爬、模擬登錄、Cookie 抓取或非授權門戶直抓。

## 配置項

```env
NEWS_INTEL_RETENTION_DAYS=30
NEWS_INTEL_FETCH_TIMEOUT_SEC=8
NEWS_INTEL_MAX_ITEMS_PER_SOURCE=50
NEWS_INTEL_AUTO_FETCH_ENABLED=false
NEWSNOW_BASE_URL=https://newsnow.busiyi.world
```

`NEWSNOW_BASE_URL` 用於拼出 `GET {NEWSNOW_BASE_URL}/api/s?id=<source_id>`。

`NEWS_INTEL_AUTO_FETCH_ENABLED` 默認關閉。設為 `true` 後，個股分析、Agent 分析和大盤覆盤在讀取本地資訊池前會先執行一次 fail-open 自動刷新：缺少內置資訊源時自動創建並啟用默認源，已有但禁用的內置默認源會重新啟用，然後拉取全部啟用源並寫入 `intelligence_items`。為避免每隻股票重複請求外部站點，運行進程內有 60 分鐘冷卻；冷卻內複用本地庫數據。

**外部依賴兼容性說明：**

- **官方項目與部署指南**：https://github.com/qqhann/newsnow
- **當前默認值** `https://newsnow.busiyi.world` 是公開示例實例，**非官方部署**，存在以下風險：
  - 可能因官方維護、限流或停止服務而不可用
  - 不保證穩定性、可靠性或數據準確性，僅用於演示和測試
  - 每個用戶都指向同一公開實例，可能遭遇限流
- **生產環境強烈建議**：自建 NewsNow 實例或接入已確認可控的私有/企業部署，以確保穩定性和數據可靠性

**API 契約兼容性核驗（部署前必做）：**

- 驗證基礎可達性和返回格式：
  ```bash
  curl -sS "${NEWSNOW_BASE_URL}/api/s?id=cls-hot" | python -c "import sys, json; data=json.load(sys.stdin); assert isinstance(data, dict) and isinstance(data.get('items'), list); print('OK')"
  ```
- 詳細字段兼容性可參考自動化測試：`test_newsnow_source_fetches_json_items`，涵蓋 `status`、`id`、`items[].title`、`items[].url`/`mobileUrl`、`items[].pubDate`/`items[].extra.date` 等字段
- **部署實例不在自動化上線保障範圍內**；如果依賴公開示例實例，部署前務必在實際生產環境執行上述驗證

## API

所有接口位於 `/api/v1/intelligence`。

- `POST /sources`：創建資訊源。
- `GET /sources`：查詢資訊源。
- `GET /sources/templates?market=hk`：查詢內置資訊源模板。
- `POST /sources/templates/{template_id}`：從內置模板創建資訊源，可覆蓋名稱、啟用狀態、作用域和說明。
- `POST /sources/defaults`：一鍵創建全部內置默認源；接口冪等，已存在的同名源會返回 `created=false`，不會重複插入。默認不傳 `enabled` 時以 `false` 創建；如需默認啟用可傳 `{ "enabled": true }`。
- `POST /sources/test`：測試 payload，不落庫。
- `POST /sources/{source_id}/fetch?dry_run=false`：拉取單個源。
- `POST /sources/fetch-enabled`：fail-open 拉取全部啟用源。
- `GET /items?scope_type=market&market=cn&days=7`：查詢資訊條目。

如果希望在本地 `.env`、Docker 或其他已顯式透傳環境變量的運行環境中自動完成“建源 -> 拉取 -> 入庫 -> 分析消費”，設置：

```env
NEWS_INTEL_AUTO_FETCH_ENABLED=true
```

該開關代表用戶明確同意運行時訪問已配置的外部 RSS/Atom/NewsNow HTTP 源；默認關閉是為了避免未確認的外部請求、公開 NewsNow 示例實例壓力和分析 prompt 輸入變化。

> 說明：該開關只有在實際執行進程環境變量中可見時才會生效。倉庫默認隨帶的 `00-daily-analysis.yml` 為 `env` 採用 allowlist 映射策略，未顯式列入映射時，即便在倉庫 Variables/Secrets 中設置同名變量也不會注入運行環境，因此默認 workflow 中不會自動接收該開關。若要在倉庫自帶每日分析任務裡開啟該能力，請在 workflow 中顯式添加該變量透傳，或改為本地/Docker 直接配置環境變量運行。

## NewsNow 默認源

NewsNow 不是 RSS，而是一個聚合熱點平臺。DSA 直接按 HTTP API 讀取它的 JSON 返回，不需要 MCP：

```text
GET {NEWSNOW_BASE_URL}/api/s?id=cls-hot
```

本 PR 先接入以下財經相關默認源，保證流程能從“源配置 -> 拉取 -> 落庫 -> 分析讀取”跑通：

- `cls-hot`：財聯社熱門，偏 A 股和題材熱點。
- `xueqiu-hotstock`：雪球熱門股票，偏個股關注度。
- `wallstreetcn-quick`：華爾街見聞快訊，偏宏觀、商品和市場事件。
- `jin10`：金十數據，偏全球宏觀和外盤事件。
- `gelonghui`：格隆匯事件，偏港股和中概股上下文。

如果需要更多國內平臺，可以繼續通過 `POST /sources` 手動添加 NewsNow 源，`source_type=newsnow`，`url` 填 `https://<your-newsnow>/api/s?id=<source_id>`。如果更偏好 RSS，也可以用 RSSHub 等合規 RSS 源繼續按 `source_type=rss` 接入。

## 後續接入建議

首版基線之上，分析鏈路會 best-effort 讀取本地資訊池：

- 個股傳統分析會優先讀取 `symbol=<股票代碼>` 的資訊，並補充同市場 `market` 級資訊；內容追加到既有 `news_context`，隨 AnalysisContextPack 摘要和歷史 `news_content` 保存。
- Agent 分析同樣通過 `news_context` 注入本地資訊證據，避免 Agent 必須重新搜索才能看到已沉澱新聞。
- 大盤覆盤會把同市場 `market` 級資訊合併到市場新聞列表，Prompt、結構化 payload 和報告 news 字段都能看到來源鏈接。
- 如果 `NEWS_INTEL_AUTO_FETCH_ENABLED=true`，上述入口會先 fail-open 自動刷新本地資訊池；刷新失敗不會阻塞分析。
- 本次能力僅新增本地資訊消費路徑，不改模型名、provider/base URL、默認模型策略、回退策略、`save_context_snapshot` 前清理邏輯或運行時配置語義；兼容現有部署配置，回滾方式為清退本地資訊接入入口或移除本地資訊源配置/數據。

後續 PR 可以繼續完善 NewsNow HTTP provider、報告 evidence 展示和 Web 設置/報告查看入口。

## 兼容性與回滾說明（Issue #1707）

- 本功能不改動第三方 LLM provider 語義，不新增 provider/model/base URL/默認模型策略/運行時路由或配置遷移分支。
- 結構化檢測提示中的模型/API 兼容風險在本次改動中不成立：`news_context` 注入鏈路僅複用現有 LLM 分析輸入構造流程（`src/core/pipeline.py`、`src/market_analyzer.py`、`src/analyzer.py`），且不新增 `.env` 寫入、保存前清理、清空/回填邏輯。
- 回滾方式：`revert` 本 PR；如需降級配置，僅需停用並移除本地資訊源配置（含 `sources` 表與 `intelligence_items` 存量）即可，不影響原有模型、provider 或其它歷史分析鏈路。

## PR 描述可複用內容（Issue #1707）

- Refs: `#1707`
- 兼容性結論：本次僅新增本地資訊消費鏈路，不改模型名/provider/base URL/默認模型策略/回退策略/保存前清理邏輯/運行時配置遷移。`news_context` 與 `market_review_payload` 的擴展為 best-effort 追加，不影響既有契約與兼容性邊界。
- 回滾方案：最小回滾路徑為 `revert this PR`；如僅需降級接入，可在運行時停用並清理本地資訊源（`sources` 與 `intelligence_items`）。
