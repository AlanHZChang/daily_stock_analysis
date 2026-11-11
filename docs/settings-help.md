# 設置頁配置幫助維護說明

設置頁配置幫助用於把配置項的關鍵說明放到 WebUI 內部，減少用戶在設置頁和文檔之間反覆切換。頁面上仍保留短描述，詳細說明通過配置項標題旁的 help icon 打開。

本文只說明幫助系統的維護規則，不替代完整配置文檔。配置語義、默認值、運行時優先級和排障細節仍以 `.env.example`、`docs/full-guide.md` 及對應專題文檔為事實源。

## 數據結構

後端配置註冊表在 `src/core/config_registry.py` 中為字段追加幫助元數據：

- `help_key`：前端多語言幫助文案的穩定 key。
- `examples`：可直接展示的配置樣例。敏感字段只能使用佔位符，例如 `sk-xxxx`、`your_token`。
- `docs`：相關文檔鏈接，優先指向倉庫內已有專題文檔或完整指南。
- `warning_codes`：面向前端或後續校驗擴展的穩定提示 code。

前端長文案維護在 `apps/dsa-web/src/locales/settingsHelp.ts`：

- 默認展示中文文案。
- 英文文案保留同樣結構，便於後續擴展語言切換。
- 文案應解釋用途、取值說明、影響範圍、注意事項和相關文檔，不應複製完整專題文檔。

## WebUI 語言說明（非配置項）

本項目新增獨立的 WebUI 界面語言能力（`zh` / `en`），用於靜態頁面文案、導航與通用控件文案。該狀態與 `REPORT_LANGUAGE` 解耦，不改寫報告語言語義。

- 狀態鍵：`dsa.uiLanguage`（`localStorage`，瀏覽器端持久化）。
- 初始化優先級：`localStorage` 有效值優先，其次識別瀏覽器語言（`zh-*` / `en-*`），最後回退 `zh`。
- 該語言開關不屬於 `.env` 配置字段，不在 `system/config` 的可配置字段清單中體現。
- 界面切換會同步 `document.documentElement.lang`（`zh-CN` 或 `en`）以利於可訪問性與無障礙語義。

## 覆蓋範圍

PR1 覆蓋基礎設施與首批代表性配置項：

- `STOCK_LIST`
- `LITELLM_MODEL`
- `LLM_CHANNELS`
- `FEISHU_WEBHOOK_URL`
- `WEBUI_HOST`

PR2 繼續覆蓋高頻、易填錯配置項：

- AI 模型運行時：Agent 主模型、fallback 模型、高級 YAML 路由、temperature、provider API Key、OpenAI-compatible Base URL。
- LLM Channels 編輯器內部字段：渠道名、協議、Base URL、API Key、模型列表、運行時能力檢測、主模型、Agent 主模型、fallback、Vision 和 temperature。
- 數據源與搜索：Tushare、股票索引遠程更新開關、實時行情優先級、實時技術指標、搜索 API Key、SearXNG、籌碼分佈、新聞窗口。
- 通知：Webhook、Telegram、郵件、Discord/Slack 等聊天平臺、報告輸出、Webhook SSL 校驗。
- WebUI / auth / schedule / proxy：Host、Port、登錄保護、可信反向代理、定時任務、交易日檢查、網絡代理。

PR3 registered-field slice / 階段性補齊：聚焦 Web 設置頁中實際展示/可配置字段的 Help 補齊，包括通用配置卡片當前可見字段和 AI legacy 條件可見字段：

- Agent 配置（22 字段）：問股生成方式、Agent 模式、最大推理步數、策略列表、策略目錄、自然語言路由、架構、編排器模式、超時、風險否決、Deep Research 預算/超時、記憶、策略自動權重、策略路由、問股可見對話上下文壓縮、事件監控開關/間隔、告警規則 JSON。普通用戶只看到新的 `AGENT_BACKEND` 選擇器；舊 `AGENT_GENERATION_BACKEND` 僅保留配置兼容。
- 回測配置（5 字段）：回測開關、評估窗口、最小記錄年齡、引擎版本、中性回報帶。
- 報告配置（9 字段）：僅推送摘要、顯示模型名、模板目錄、渲染引擎、完整性校驗/重試、歷史信號對比、逐股推送、合併郵件。
- 通知路由配置（9 字段）：報告/告警/系統錯誤渠道路由、去重/冷卻、靜默時段/時區、最低等級、每日摘要（預留）。
- 系統運行時（7 字段）：日誌級別、調試模式、最大併發、分析間隔、大盤分析開關/市場/配色。
- AI legacy 與 Anspire 配置：provider 專用多 Key、模型名、溫度、Vision 模型、max tokens 與 Anspire LLM 網關字段。
- 數據源與搜索：TickFlow、SerpAPI、Brave、Bocha、MiniMax、SearXNG 公共實例、BIAS 閾值和 Pytdx 服務器字段。
- 通知高級字段：飛書高級安全/應用字段、Telegram topic、Discord/Slack 高級字段、Pushover、ntfy、Gotify、PushPlus、ServerChan3、AstrBot 和自定義 Webhook 高級模板/鑑權字段。

Issue #1512 收口後，Web 設置頁只展示後端配置註冊表中的正式字段。未註冊的 `.env` key 不再作為普通可編輯設置項展示，避免 raw key、`Auto-inferred field metadata.` 和無 help 按鈕的配置項進入中文界面；這些 key 仍可通過 `.env` 文件或導入/導出能力保留和維護。

例外：`LLM_CHANNELS` 聲明的動態渠道詳情鍵（如 `LLM_DEEPSEEK_API_KEY`、`LLM_MY_PROXY_MODELS`）會保留在配置接口返回中，供“AI 模型接入”編輯器讀取和保存；它們不作為普通配置卡片展示，也不復用 `WEB_SETTINGS_HIDDEN_FROM_UI` 的運維隱藏語義。

暫不納入 Web 設置頁展示的低頻/運維類 `.env` 變量包括 `DATABASE_PATH`、`SQLITE_*`、`USE_PROXY`、`PROXY_HOST`、`PROXY_PORT` 等。若後續需要在 Web 中編輯這些字段，應先在 `src/core/config_registry.py` 中正式註冊並補齊 help 元數據，而不是依賴自動推斷。

### 覆蓋邊界

- `settingsHelp.ts` 中的 `settings.llm_channel.*` 系列為 LLM 渠道編輯器內部字段說明，僅用於前端渲染，不對應 `.env` 的單獨配置項；這是 PR2 中刻意的“內置擴展”設計，用於提升編輯器可用性。
- 其餘 help 文案均應能從 `src/core/config_registry.py` 中某個字段的 `help_key` 映射到後端註冊元數據，便於與文檔源、`warning_codes` 一起統一維護。

## 事實源優先級

新增或修改幫助文案時，優先從以下位置核對：

1. `.env.example`：配置鍵名、默認值、樣例格式和敏感佔位符。
2. `docs/full-guide.md`：主要配置說明、運行入口和部署上下文。
3. `docs/LLM_CONFIG_GUIDE.md`、`docs/llm-providers.md`：LLM 優先級、Channels、provider/model、兼容邊界和排障說明。
4. 專題文檔：例如 `docs/bot/feishu-bot-config.md`、`docs/deploy-webui-cloud.md`、`docs/desktop-package.md`。
5. 代碼實現和測試：當文檔與代碼不一致時，先以可執行實現為準，並同步修正文檔。

## 維護邊界

- 幫助文案不能改變配置保存、校驗、運行時優先級、`.env` 寫回或環境變量覆蓋語義。
- 不展示真實密鑰、賬號、token、Webhook 完整值或本機絕對路徑。
- LLM 相關示例如果寫入具體 provider 前綴、模型名或 Base URL，必須能追溯到當前倉庫文檔或官方來源；否則應使用佔位符或鏈接到事實源。
- 對第三方模型/API 的可用性、LiteLLM 兼容窗口或 provider fallback 規則，不在設置幫助中單獨承諾；需要變更時必須同步更新專題文檔和 PR 兼容性說明。
- 中英雙語文案應保持同一語義範圍。若只更新一種語言，需要在交付說明中寫明原因。
- 首屏短描述保持簡潔，詳細說明放在 help dialog 中，避免 hover tooltip 與常駐短描述重複。

## 重啟語義

設置頁保存通常只寫入 `.env` 並觸發可運行時重載的配置刷新。幫助文案和 `warning_codes` 必須顯式區分以下情況：

- `WEBUI_HOST`、`WEBUI_PORT`：監聽地址和端口只在進程啟動時綁定，保存後必須重啟當前進程、Docker 容器或服務管理器才會生效。
- `RUN_IMMEDIATELY`：非 schedule 模式啟動期單次運行配置，保存後不會讓已運行的 WebUI/API 進程立即觸發分析。
- Web 設置頁不直接暴露 `SCHEDULE_TIME` / `SCHEDULE_TIMES` / `SCHEDULE_RUN_IMMEDIATELY` 等內部鍵；用戶通過“定時任務”卡片維護啟用狀態、多個執行時間和立即執行一次。
- `SCHEDULE_ENABLED`：WebUI/API/Desktop 長運行進程（包括 `python main.py --serve --schedule`）會在保存後按新值啟動或停止 runtime scheduler；重啟 `--serve-only` 或 Desktop 進程時也會恢復已啟用的 daily jobs，但不會因此立即執行分析。純 CLI schedule 模式（`python main.py --schedule`）仍按啟動時參數和配置運行。
- `SCHEDULE_TIME`、`SCHEDULE_TIMES`：不是重啟必需項。`SCHEDULE_TIMES` 為空時使用 `SCHEDULE_TIME`；已運行的 scheduler 會按新時間重建 daily jobs。
- `SCHEDULE_RUN_IMMEDIATELY`：schedule 模式啟動行為，保存後不會讓當前進程立即執行一次分析；手動執行請使用 runtime scheduler 的 run-now API。
- `SCHEDULE_STARTUP_DEDUP`：純 CLI schedule 模式（`python main.py --schedule`）啟動立即執行的當日去重開關，Web 設置頁不直接暴露該鍵；詳見 `docs/full-guide.md` 配置表。
- runtime scheduler 的 run-now API 只會在沒有分析任務運行時接受請求；如果已有分析在執行，會返回忙碌狀態，Web 設置頁會提示稍後重試。
