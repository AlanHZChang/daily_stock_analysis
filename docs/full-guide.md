# 📖 完整配置與部署指南

本文檔包含 A股智能分析系統的完整配置說明，適合需要高級功能或特殊部署方式的用戶。

> 💡 快速上手請參考 [README.md](../README.md)，本文檔為進階配置。

## 📁 項目結構

```
daily_stock_analysis/
├── main.py              # 主程序入口
├── src/                 # 核心業務邏輯
│   ├── analyzer.py      # AI 分析器
│   ├── config.py        # 配置管理
│   ├── notification.py  # 消息推送
│   └── ...
├── data_provider/       # 多數據源適配器
├── bot/                 # 機器人交互模塊
├── api/                 # FastAPI 後端服務
├── apps/dsa-web/        # React 前端
├── docker/              # Docker 配置
├── docs/                # 項目文檔
└── .github/workflows/   # GitHub Actions
```

## 📑 目錄

- [項目結構](#-項目結構)
- [GitHub Actions 詳細配置](#github-actions-詳細配置)
- [環境變量完整列表](#環境變量完整列表)
- [Docker 部署](#docker-部署)
- [本地運行詳細配置](#本地運行詳細配置)
- [定時任務配置](#定時任務配置)
- [通知渠道詳細配置](#通知渠道詳細配置)
- [數據源配置](#數據源配置)
- [高級功能](#高級功能)
- [回測功能](#回測功能)
- [本地 WebUI 管理界面](#本地-webui-管理界面)

---

## GitHub Actions 詳細配置

### 1. Fork 本倉庫

點擊右上角 `Fork` 按鈕

### 2. 配置 Secrets

進入你 Fork 的倉庫 → `Settings` → `Secrets and variables` → `Actions` → `New repository secret`

<div align="center">
  <img src="assets/secret_config.png" alt="GitHub Secrets 配置示意圖" width="600">
</div>

#### AI 模型配置（至少配置一個）

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `MODELFLARE_KEY` | [Modelflare](https://modelflare.dev/sign-up?utm_source=github&utm_campaign=daily_stock_analysis) API Key，自動補齊默認地址和模型 | 推薦 |
| `AIHUBMIX_KEY` | [AIHubMix](https://inferera.com/?aff=CfMq) API Key，一 Key 切換使用全系模型，本項目可享 10% 優惠 | 推薦 |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) 獲取免費 Key | 可選 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | 可選 |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（支持 DeepSeek、通義千問等） | 可選 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址（如 `https://api.deepseek.com`） | 可選 |
| `OPENAI_MODEL` | 模型名稱（如 `gemini-3.6-flash`、`deepseek-v4-flash`、`gpt-6.1-sol`） | 可選 |
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC) API Key（可選，模型與搜索共用；可用性以賬號權限為準） | 可選 |

> *注：以上模型 Key / 渠道至少配置一個。Modelflare 只需填寫 `MODELFLARE_KEY`，單渠道默認模型為 `openai/gpt-6.1-sol`（可通過 `LITELLM_MODEL` 覆蓋），接入地址默認使用 `https://modelflare.dev/v1`，完整示例見 [LLM 配置指南](LLM_CONFIG_GUIDE.md#示例modelflare)。實際模型以賬號權限為準。啟動時配置校驗會在缺少可用 AI 模型 Key 或模型渠道時給出明確錯誤提示。

#### 通知渠道配置（可同時配置多個，全部推送）

> 通知渠道、minimal/advanced key 分層、Actions 映射、`--check-notify` 診斷、Web 一鍵測試和本地 / Docker / GitHub Actions / Desktop 場景說明詳見 [通知專題文檔](notifications.md)。

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `WECHAT_WEBHOOK_URL` | 企業微信 Webhook URL | 可選 |
| `FEISHU_WEBHOOK_URL` | 飛書 Webhook URL | 可選 |
| `FEISHU_WEBHOOK_SECRET` | 飛書 Webhook 簽名密鑰（開啟“簽名校驗”時必填） | 可選 |
| `FEISHU_WEBHOOK_KEYWORD` | 飛書 Webhook 關鍵詞（開啟“關鍵詞”時必填） | 可選 |
| `DINGTALK_WEBHOOK_URL` | 釘釘群機器人 Webhook URL | 可選 |
| `DINGTALK_SECRET` | 釘釘群機器人加簽密鑰 (SEC開頭) | 可選 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token（@BotFather 獲取） | 可選 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可選 |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID (用於發送到子話題) | 可選 |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL（[創建方法](https://support.discord.com/hc/en-us/articles/228383668)） | 可選 |
| `DISCORD_BOT_TOKEN` | Discord Bot Token（與 Webhook 二選一） | 可選 |
| `DISCORD_MAIN_CHANNEL_ID` | Discord Channel ID（使用 Bot 時需要） | 可選 |
| `DISCORD_INTERACTIONS_PUBLIC_KEY` | Discord Public Key（僅入站 Interaction/Webhook 回調驗籤時需要） | 可選 |
| `SLACK_BOT_TOKEN` | Slack Bot Token（推薦，支持圖片上傳；同時配置時優先於 Webhook） | 可選 |
| `SLACK_CHANNEL_ID` | Slack Channel ID（使用 Bot 時需要） | 可選 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL（僅文本，不支持圖片） | 可選 |
| `EMAIL_SENDER` | 發件人郵箱（如 `xxx@qq.com`） | 可選 |
| `EMAIL_PASSWORD` | 郵箱授權碼（非登錄密碼） | 可選 |
| `EMAIL_RECEIVERS` | 收件人郵箱（多個用逗號分隔，留空則發給自己） | 可選 |
| `EMAIL_SENDER_NAME` | 發件人顯示名稱（默認：daily_stock_analysis股票分析助手） | 可選 |
| `PUSHPLUS_TOKEN` | PushPlus Token（[獲取地址](https://www.pushplus.plus)，國內推送服務） | 可選 |
| `SERVERCHAN3_SENDKEY` | Server醬³ Sendkey（[獲取地址](https://sc3.ft07.com/)，手機APP推送服務） | 可選 |
| `ASTRBOT_URL` | AstrBot Webhook URL | 可選 |
| `ASTRBOT_TOKEN` | AstrBot Bearer Token（可選） | 可選 |
| `NTFY_URL` | ntfy 完整 topic endpoint，必須包含 topic path，例如 `https://ntfy.sh/my-topic` | 可選 |
| `NTFY_TOKEN` | ntfy Bearer Token（可選） | 可選 |
| `GOTIFY_URL` | Gotify server base URL，不包含 `/message`；系統會自動拼接 `/message` | 可選 |
| `GOTIFY_TOKEN` | Gotify application token，通過 `X-Gotify-Key` Header 發送 | 可選 |
| `CUSTOM_WEBHOOK_URLS` | 自定義 Webhook（支持釘釘等，多個用逗號分隔） | 可選 |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | 自定義 Webhook 的 Bearer Token（用於需要認證的 Webhook） | 可選 |
| `CUSTOM_WEBHOOK_BODY_TEMPLATE` | 自定義 Webhook JSON body 模板，適配 AstrBot、NapCat、自建服務等特殊 payload | 可選 |
| `WEBHOOK_VERIFY_SSL` | 讀取該配置的 webhook-style HTTPS 通知請求證書校驗（默認 true）。設為 false 可支持自簽名證書。警告：關閉有嚴重安全風險（MITM），僅限可信內網 | 可選 |

> *注：至少配置一個渠道，配置多個則同時推送。啟動時配置校驗會提示 Telegram / 郵件成對字段缺失，以及常見 Webhook URL 未以 `http://` 或 `https://` 開頭的問題。
>
> 當前默認 `00-daily-analysis.yml` 只顯式映射固定 Secret / Variable 名稱，不會自動把 `STOCK_GROUP_1`、`EMAIL_GROUP_1` 這類任意編號變量導入運行環境，也不會自動導入 `NEWS_INTEL_AUTO_FETCH_ENABLED` 這類新增可選開關。所以分組郵箱功能和本地資訊自動刷新能力目前不適用於倉庫自帶默認 GitHub Actions workflow；它們適用於本地 `.env`、Docker，或你自行顯式擴展過 `env:` 映射的運行環境。Actions 已顯式映射 `CUSTOM_WEBHOOK_BODY_TEMPLATE`、`WEBHOOK_VERIFY_SSL`、`FEISHU_WEBHOOK_SECRET`、`FEISHU_WEBHOOK_KEYWORD`、`PUSHPLUS_TOPIC`、`NTFY_URL`、`NTFY_TOKEN`、`GOTIFY_URL`、`GOTIFY_TOKEN`、P3 通知路由鍵以及 P4 通知降噪鍵；`MARKDOWN_TO_IMAGE_CHANNELS` 和 `MERGE_EMAIL_NOTIFICATION` 仍作為行為開關不在默認 workflow 中自動映射。

#### 推送行為配置

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `SINGLE_STOCK_NOTIFY` | 單股推送模式：設為 `true` 則每分析完一隻股票立即推送 | 可選 |
| `REPORT_TYPE` | 報告類型：`simple`(精簡)、`full`(完整)、`brief`(3-5句概括)，Docker環境推薦設為 `full` | 可選 |
| `REPORT_LANGUAGE` | 報告與 Agent Chat 的默認輸出語言：`zh`(默認中文) / `en`(英文) / `ko`(韓文)；會同步影響 Prompt、模板、通知 fallback、Web 報告頁固定文案，以及未顯式傳入 `context.report_language` 的問股回覆。`ko` 複用英文結構骨架並通過輸出語言指令約束模型用韓文輸出，通知按報告語言渲染本地化標籤。倉庫自帶 `00-daily-analysis.yml` 已顯式映射該變量，直接在 Actions Secrets/Variables 中配置即可生效 | 可選 |
| `REPORT_SUMMARY_ONLY` | 僅分析結果摘要：設為 `true` 時只推送彙總，不含個股詳情；多股時適合快速瀏覽（默認 false，Issue #262） | 可選 |
| `REPORT_SHOW_LLM_MODEL` | 通知報告底部是否顯示本次分析使用的 LLM 模型名稱，默認 `true`；設為 `false` 可隱藏運行時模型信息。該變量僅調整展示，不影響 provider/model/Base URL、LiteLLM 路由或運行時模型保存/遷移/清理語義。 | 可選 |
| `REPORT_TEMPLATES_DIR` | Jinja2 模板目錄（相對項目根，默認 `templates`） | 可選 |
| `REPORT_RENDERER_ENABLED` | 啟用 Jinja2 模板渲染（默認 `false`，保證零迴歸） | 可選 |
| `REPORT_INTEGRITY_ENABLED` | 啟用報告完整性校驗，缺失必填字段時重試或佔位補全（默認 `true`） | 可選 |
| `REPORT_INTEGRITY_RETRY` | 完整性校驗重試次數（默認 `1`，`0` 表示僅佔位不重試） | 可選 |
| `REPORT_HISTORY_COMPARE_N` | 歷史信號對比條數，`0` 關閉（默認），`>0` 啟用 | 可選 |
| `ANALYSIS_DELAY` | 個股分析和大盤分析之間的延遲（秒），避免API限流，如 `10` | 可選 |
| `SAVE_CONTEXT_SNAPSHOT` | 是否保存分析歷史 `context_snapshot`，默認 `true`；設為 `false` 或使用 `--no-context-snapshot` 時不持久化整份上下文快照 | 可選 |
| `MERGE_EMAIL_NOTIFICATION` | 個股與大盤覆盤合併推送（默認 false），減少郵件數量、降低垃圾郵件風險；與 `SINGLE_STOCK_NOTIFY` 互斥（單股模式下合併不生效） | 可選 |
| `MARKDOWN_TO_IMAGE_CHANNELS` | 將 Markdown 轉為圖片發送的渠道（用逗號分隔）：telegram,wechat,custom,email,slack；單股推送需同時配置且安裝轉圖工具 | 可選 |
| `NOTIFICATION_REPORT_CHANNELS` | report 路由渠道（單股推送、聚合日報、大盤覆盤、合併推送等）；留空表示所有已配置渠道 | 可選 |
| `NOTIFICATION_ALERT_CHANNELS` | alert 路由渠道（EventMonitor 告警）；留空表示所有已配置渠道 | 可選 |
| `NOTIFICATION_SYSTEM_ERROR_CHANNELS` | system_error 預留路由渠道；當前不新增自動系統錯誤生產者，留空表示所有已配置渠道 | 可選 |
| `NOTIFICATION_DEDUP_TTL_SECONDS` | 通知去重 TTL 秒數，`0` 關閉；同一穩定去重 key 在 TTL 內只發送一次 | 可選 |
| `NOTIFICATION_COOLDOWN_SECONDS` | 通知冷卻秒數，`0` 關閉；同一冷卻 key 在窗口內限頻 | 可選 |
| `NOTIFICATION_QUIET_HOURS` | 通知靜默時段，格式 `HH:MM-HH:MM`，支持跨午夜；留空關閉 | 可選 |
| `NOTIFICATION_TIMEZONE` | 靜默時段使用的 IANA 時區，如 `Asia/Shanghai`；留空跟隨 `TZ` 或系統本地時區 | 可選 |
| `NOTIFICATION_MIN_SEVERITY` | 最低通知級別：`info`、`warning`、`error`、`critical`；留空保持現狀 | 可選 |
| `NOTIFICATION_DAILY_DIGEST_ENABLED` | 每日摘要預留開關；當前不會發送摘要或持久化摘要內容 | 可選 |
| `MARKDOWN_TO_IMAGE_MAX_CHARS` | 超過此長度不轉圖片，避免超大圖片（默認 15000） | 可選 |
| `MD2IMG_ENGINE` | 轉圖引擎：`wkhtmltoimage`（默認）、`markdown-to-file` 或 `playwright`（需安裝 Web 依賴與 Chromium） | 可選 |
| `SHARE_IMAGE_XIAOHONGSHU_URL` | 分享圖小紅書主頁 URL；留空可不顯示鏈接 | 可選 |
| `SHARE_IMAGE_XIAOHONGSHU_HANDLE` | 分享圖小紅書暱稱；全部小紅書配置留空時顯示內置暱稱 `@霸天土小豆` | 可選 |
| `SHARE_IMAGE_XIAOHONGSHU_QR_PATH` | 分享圖小紅書二維碼文件路徑；支持絕對路徑或相對項目根目錄，全部小紅書配置留空時使用倉庫內置二維碼 | 可選 |
| `PREFETCH_REALTIME_QUOTES` | 設為 `false` 可禁用實時行情預取，避免 efinance/akshare_em 全市場拉取（默認 true） | 可選 |

> 兼容性說明：`REPORT_SHOW_LLM_MODEL` 維持默認 `true` 的原始展示語義，關閉時隻影響底部模型文案輸出。該配置不會變更 provider/model/Base URL、LiteLLM 路由、模型保存、遷移或清理語義；回退方式為恢復或刪除該變量，並設為 `true`。

> 說明：`REPORT_LANGUAGE` 影響報告文本、Web 報告頁固定文案與未顯式指定語言的 Agent Chat 回覆；WebUI 頁面語言（導航、登錄頁、側邊欄、設置頁、通用控件）使用獨立狀態，不與其聯動。
> WebUI 語言狀態保存在瀏覽器 `localStorage` 的 `dsa.uiLanguage`，啟動順序為：
> 1) 明確選擇（`localStorage.dsa.uiLanguage`，僅支持 `zh`/`en`）
> 2) 瀏覽器語言檢測（`navigator.languages` / `navigator.language`，`zh-*` 或 `en-*`）
> 3) 默認回退 `zh`。

#### 其他配置

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `STOCK_LIST` | 自選股代碼，如 `600519,300750,002594,7203.T,005930.KS`；推薦使用英文逗號，中文逗號、頓號、分號、空格和換行會被識別並規範為英文逗號 | ✅ |
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/github-daily-stock-analysis) 搜索引擎結果補強，適合實時金融新聞 | 推薦 |
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC) API Key（可選，模型與搜索共用；可用性以賬號權限為準） | 可選 |
| `TAVILY_API_KEYS` | [Tavily](https://tavily.com/) 搜索 API（新聞搜索） | 可選 |
| `BOCHA_API_KEYS` | [博查搜索](https://open.bocha.cn/) Web Search API（中文搜索優化，支持AI摘要，多個key用逗號分隔） | 可選 |
| `BRAVE_API_KEYS` | [Brave Search](https://brave.com/search/api/) API（隱私優先，美股優化，多個key用逗號分隔） | 可選 |
| `MINIMAX_API_KEYS` | [MiniMax](https://platform.minimax.io/) Coding Plan Web Search（結構化搜索結果） | 可選 |
| `SEARXNG_BASE_URLS` | SearXNG 自建實例（無配額兜底，需在 settings.yml 啟用 format: json）；留空時僅在顯式啟用公共實例發現後使用 `searx.space` | 可選 |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | 是否在 `SEARXNG_BASE_URLS` 為空時自動從 `searx.space` 獲取公共實例（默認 `false`）。公共實例普遍限流或未開啟 JSON 輸出，開啟後每次分析可能多耗 30~60 秒且新聞面為空 | 可選 |
| `SEARXNG_TIMEOUT_SECONDS` | 自建 SearXNG 單次搜索超時（秒，默認 `10`，最小 `1`）；實例較慢（如聚合引擎較多的 NAS 部署）時可調大，公共實例超時不受影響。GitHub Actions 需顯式映射該變量 | 可選 |
| `TUSHARE_TOKEN` | [Tushare Pro](https://tushare.pro/weborder/#/login?reg=834638 ) Token | 可選 |
| `TUSHARE_HTTP_URL` | Tushare Pro HTTP 接入地址；留空（或未設置/空白）時使用官方端點 `http://api.tushare.pro`，僅在需通過公司內網代理、跨境網絡或自建鏡像時填寫 `http://` 或 `https://` 開頭的完整地址 | 可選 |
| `TICKFLOW_API_KEY` | [TickFlow](https://tickflow.org) API Key；可選，用於 A 股日 K、實時行情、股票列表/名稱與大盤覆盤增強；失敗或權限不足時自動回退。 | 可選 |
| `MX_APIKEY` / `MX_PRIORITY` | 妙想（東方財富 MX_API）補充數據源：在東財公開接口失敗/限流時兜底獲取籌碼分佈與個股資金流。**嚴格 opt-in 的第三方能力**：需用戶自備 Key（妙想 Skills 頁面），限時免費/會員配額策略可能調整、不承諾長期免費；未配置則不啟用、行為不變。`MX_PRIORITY` 默認 `6`。GitHub Actions 需在 Secrets 配置 `MX_APIKEY` | 可選 |
| `LONGBRIDGE_OAUTH_CLIENT_ID` | [Longbridge OpenAPI](https://open.longbridge.com/) OAuth client_id；留空且無 Legacy Access Token 時會兼容使用 `LONGBRIDGE_APP_KEY` | 可選 |
| `LONGBRIDGE_OAUTH_TOKEN_CACHE_B64` | OAuth token 緩存文件的 base64 內容，供 GitHub Actions / Docker 等 headless 環境恢復 SDK token 緩存 | 可選 |
| `LONGBRIDGE_APP_KEY` | Longbridge Legacy App Key；無 `LONGBRIDGE_ACCESS_TOKEN` 時也可作為 OAuth client_id 兼容別名 | 可選 |
| `LONGBRIDGE_APP_SECRET` | Longbridge App Secret | 可選 |
| `LONGBRIDGE_ACCESS_TOKEN` | Longbridge Legacy Access Token（不是 OAuth access token） | 可選 |
| `LONGBRIDGE_STATIC_INFO_TTL_SECONDS` | 長橋 `static_info` 進程內緩存秒數（默認 86400，0=不緩存） | 可選 |
| `LONGBRIDGE_CONNECTION_COOLDOWN_SECONDS` | 長橋連接關閉類異常後的冷卻秒數（默認 15；冷卻期內臨時跳過 Longbridge，避免頻繁重連） | 可選 |
| `LONGBRIDGE_HTTP_URL` | HTTP 接口地址（默認 `https://openapi.longbridge.com`） | 可選 |
| `LONGBRIDGE_QUOTE_WS_URL` | 行情 WebSocket 地址（默認 `wss://openapi-quote.longbridge.com/v2`） | 可選 |
| `LONGBRIDGE_TRADE_WS_URL` | 交易 WebSocket 地址（默認 `wss://openapi-trade.longbridge.com/v2`） | 可選 |
| `LONGBRIDGE_REGION` | 覆蓋接入點；SDK 會按網絡自動選擇，默認 `hk`，若判斷不正確可設置（如 `cn`、`hk`） | 可選 |
| `LONGBRIDGE_ENABLE_OVERNIGHT` | 是否開啟夜盤行情 `true` / `false`，默認 `false` | 可選 |
| `LONGBRIDGE_PUSH_CANDLESTICK_MODE` | K 線推送模式：`realtime` 或 `confirmed`（默認 `realtime`） | 可選 |
| `LONGBRIDGE_PRINT_QUOTE_PACKAGES` | 連接時是否打印行情包（未設置時默認 `false`；設為 `1`/`true`/`yes` 開啟） | 可選 |
| `ENABLE_CHIP_DISTRIBUTION` | 啟用籌碼分佈（Actions 默認 false；需籌碼數據時在 Variables 中設為 true，接口可能不穩定） | 可選 |

妙想籌碼/資金流在同一進程內共享網絡請求准入鎖：進入查詢方法時若已有請求未結束，新查詢直接跳過，不在此鎖上排隊。資金流補充的超時隔離保持到實際後臺請求退出，其他數據源仍可回退；不取消已經發出的請求，也不改變管理器原有的籌碼調用串行化。該補充源通過能力檢查排除所有日線請求，並在選表和解析時統一支持字典/列表形式的 `nameMap`。

妙想資金流僅使用明確的主力淨流入金額指標；收盤價、佔比及缺失金額不會作為資金流回退值。最新交易日金額缺失時保持未知，5/10 日窗口包含缺失金額時不輸出合計，不使用更早日期補位。

> **GitHub Actions：** 倉庫自帶 `00-daily-analysis.yml` 已把 `TUSHARE_TOKEN`、`TICKFLOW_API_KEY` / `TICKFLOW_*` 和上表中的 `LONGBRIDGE_*` 映射到任務環境。TickFlow 的 API Key 建議放在 **Secrets**，優先級、復權和批量開關可放在 **Variables** 或 **Secrets**。Longbridge OAuth 方式需要一個 client_id（優先 `LONGBRIDGE_OAUTH_CLIENT_ID`；留空且無 Legacy Access Token 時使用 `LONGBRIDGE_APP_KEY` 兼容），並把本機 `~/.longbridge/openapi/tokens/<client_id>` 文件 base64 後保存為 Secret `LONGBRIDGE_OAUTH_TOKEN_CACHE_B64`；Legacy 方式仍可配置 `LONGBRIDGE_APP_KEY`、`LONGBRIDGE_APP_SECRET`、`LONGBRIDGE_ACCESS_TOKEN`。可選接入點變量（如 `LONGBRIDGE_REGION`）可放在 **Variables** 或 **Secrets**。

> **TUSHARE_HTTP_URL 在每日 workflow 中的映射：** `00-daily-analysis.yml` 已顯式映射 `TUSHARE_HTTP_URL`（採用 `vars.TUSHARE_HTTP_URL || secrets.TUSHARE_HTTP_URL` 優先級，與倉庫現有 `TICKFLOW_PRIORITY` 等非敏感配置取值策略一致）。該地址屬"接入地址"配置而非憑據，建議放 **Variables** 便於團隊 review 與版本可審計。注意：真實的優先級是 `vars` 非空即勝出，**Secrets 中的同名變量無法覆蓋非空 Variables**，兩者中只有 vars 為空時 secrets 才被採用，請按這個真實語義做安全建模。GitHub 把 Variables 與 Secrets 設計為兩套獨立的寫權限模型：任何對 repository Variables 有寫權限的人或自動化，都可以在不讀取、不修改 Secrets 的情況下，通過設置一個非空 Variable 來改寫運行時端點（包括將 `TUSHARE_TOKEN` 和完整請求體指向攻擊者控制的地址）；Secrets 僅保護值的機密性，並不自動提供"端點完整性"或"優先級覆蓋"保障。如確需對端點施加更強的訪問控制，請使用 GitHub Environment protection rules、CODEOWNERS、branch protection 或獨立的部署審批流程，**不要把"只放 Secrets 而 Variables 留空"當作防改護欄**。未設置或留空時 fetcher 仍走官方 `http://api.tushare.pro` 端點，不會因為本變量缺失而報錯。

> **Longbridge 運行時行為：** 未配置憑據時不會實例化 Longbridge 這個可選 fetcher；若運行時遇到 `client is closed`、`context closed`、`connection closed` 等連接關閉類異常，會進入冷卻期（默認 15 秒，可用 `LONGBRIDGE_CONNECTION_COOLDOWN_SECONDS` 調整），冷卻期內美股/港股的實時與日線請求會自動跳過 Longbridge，退回 YFinance / AkShare 等兜底鏈路。

> 補充說明
- TUSHARE_TOKEN，當此參數配置後，但不具備港股日線接口權限時，也會出現港股數據查詢不出來或者錯誤的情況，和老版本提示不支持港股效果相同

#### ✅ 最小配置示例

如果你想快速開始，最少需要配置以下項：

1. **AI 模型**：按 [Modelflare Channels 示例](LLM_CONFIG_GUIDE.md#示例modelflare) 配置，或使用 `AIHUBMIX_KEY`（[AIHubmix](https://inferera.com/?aff=CfMq)，一 Key 多模型）、`GEMINI_API_KEY` 或 `OPENAI_API_KEY`
2. **通知渠道**：至少配置一個，如 `WECHAT_WEBHOOK_URL` 或 `EMAIL_SENDER` + `EMAIL_PASSWORD`
3. **股票列表**：`STOCK_LIST`（必填）
4. **搜索 API**：`SERPAPI_API_KEYS` 或 `TAVILY_API_KEYS`；`ANSPIRE_API_KEYS` 仍可選用

> 💡 配置完以上 4 項即可開始使用！

### 3. 啟用 Actions

1. 進入你 Fork 的倉庫
2. 點擊頂部的 `Actions` 標籤
3. 如果看到提示，點擊 `I understand my workflows, go ahead and enable them`

### 4. 手動測試

1. 進入 `Actions` 標籤
2. 左側選擇 `每日股票分析` workflow
3. 點擊右側的 `Run workflow` 按鈕
4. 選擇運行模式
5. 點擊綠色的 `Run workflow` 確認

### 5. 完成！

默認每個工作日 **18:00（北京時間）** 自動執行。

---

## 環境變量完整列表

### AI 模型配置

> 完整說明見 [LLM 配置指南](LLM_CONFIG_GUIDE.md)（三層配置、渠道模式、Vision、Agent、排錯）；常用服務商預設、Actions 變量對照和錯誤排障見 [LLM 服務商配置指南](llm-providers.md)。
> 兼容性說明（Issue #1306/#1391，順帶確認 #1381）：本節相關改動只複用已有歷史寫入鏈路展示大盤覆盤結果，不新增 API/API 參數、Web 階段結果獨立展示、日報四階段結構化持久化或日報狀態表，不修改 `provider` / `model` / `base_url` 運行時路由與默認模型行為；#1381 同樣僅為後端 runtime 複用，不新增配置遷移/清理/回寫分支。若 Issue #1381 的 API/Web/日報結構化驗收未同步落地，本 PR 不應作為完整交付收口，需留待後續 PR 繼續交付。回退路徑為發佈回滾（可直接 revert 當前提交，或按現有配置回退鏈路）。兼容驗證主要沿用既有約束檢查（`requirements.txt`：`litellm` 版本約束）與既有配置迴歸測試：`tests/test_system_config_service.py`、`tests/test_system_config_api.py`、`tests/test_llm_channel_config.py`、`tests/test_market_review_runtime.py`；官方源參考：[LiteLLM OpenAI-compatible](https://docs.litellm.ai/docs/providers/openai_compatible)、[OpenAI Chat Completion API](https://platform.openai.com/docs/api-reference/chat)。
> #1391 Phase 2 的結構化檢測風險來自 `src/agent/factory.py` 的 `agent_max_steps` / `agent_orchestrator_timeout_s` int 安全兜底，屬於配置讀取側的類型兼容增強，不會改寫 `litellm_model`、`agent_litellm_model`、`openai_base_url` 或 `LLM_*` 路由狀態；迴歸可複核 `tests/test_agent_pipeline.py::TestAgentConfig::test_build_agent_executor_does_not_mutate_llm_route_config` 與 `tests/test_agent_pipeline.py::TestAgentConfig::test_build_agent_executor_multi_arch_does_not_mutate_llm_route_config`。當配置值非法（如非數字）時，`src.agent.factory` 會記錄 warning 並回退到默認值，便於排障與避免誤判配置已生效。
> #1815 Phase 3 的兼容邊界說明：本輪僅收斂 JP/KR 與 Market Light 的服務邊界，不新增 LLM provider/model/base_url 遷移邏輯，不改寫 `.env` 主路由模型持久化語義。`MarketSymbol`、告警枚舉與快照 `data_quality/limitations` 調整按已有 `.env` 原子 upsert 語義寫入保存配置；未顯示提交的鍵不會被清空。
> 本節僅同步模型/渠道配置清單，不額外引入新的外部 provider / Base URL 兼容約定；兼容語義以當前倉庫 `requirements.txt` 依賴約束和相關測試為準，歷史回退路徑見上述兩份文檔中“回退/恢復”說明。

| 變量名 | 說明 | 默認值 | 必填 |
|--------|------|--------|:----:|
| `GENERATION_BACKEND` | 普通分析生成後端；支持 `litellm` 或顯式 opt-in 的 `codex_cli` / `claude_code_cli` / `opencode_cli`（experimental/limited） | `litellm` | 否 |
| `OPENCODE_CLI_MODEL` | `GENERATION_BACKEND=opencode_cli` 時可選傳給 OpenCode `--model` 的模型覆蓋；留空則使用本機 OpenCode 默認模型，認證和模型可用性由本機 OpenCode 配置負責 | 空 | 否 |
| `GENERATION_FALLBACK_BACKEND` | backend 級 fallback；未配置默認 `litellm`，空值禁用，self fallback 解析為 no-op | `litellm` | 否 |
| `GENERATION_BACKEND_TIMEOUT_SECONDS` | 單次 generation backend 調用超時秒數，主要用於本地 CLI backend；範圍 `1-3600` | `300` | 否 |
| `GENERATION_BACKEND_MAX_OUTPUT_BYTES` | 單次本地 CLI backend 診斷 stdout/stderr 與最終響應捕獲總上限；`--output-last-message` 重複打印到 stdout 的最終響應不重複計入；範圍 `1-33554432` | `1048576` | 否 |
| `GENERATION_BACKEND_MAX_CONCURRENCY` | generation backend 全局併發上限；範圍 `1-16`，不改變 LiteLLM Router / `MAX_WORKERS` 行為 | `1` | 否 |
| `LOCAL_CLI_BACKEND_MAX_CONCURRENCY` | 本地 CLI backend 併發上限；範圍 `1-4`，有效併發取它與 `GENERATION_BACKEND_MAX_CONCURRENCY` 的較小值 | `1` | 否 |
| `AGENT_BACKEND` | 問股 Chat 執行方式：`auto`（推薦，保持默認 LiteLLM）或 `litellm` | `auto` | 否 |
| `AGENT_GENERATION_BACKEND` | Agent Chat 生成後端；Web 設置頁僅暴露 `auto|litellm`，手寫 local CLI backend 會返回 unsupported tool-calling 診斷 | `auto` | 否 |
| `AGENT_SKILL_CONCURRENCY` | `specialist` 模式策略專家 worker 併發上限，範圍 `1-4`；最多選擇 4 個策略，默認 3 個併發，第 4 個進入下一批次並共享整體超時預算 | `3` | 否 |
| `AGENT_DATA_TOOL_TIMEOUT_S` | Agent `data` 類工具默認超時秒數；同時作為 `market` 類工具（`get_market_indices` / `get_sector_rankings` 等網絡數據調用）的類別默認；`0` 表示關閉，回退到全局預算；有效超時按 first-wins 解析：顯式 per-run `tool_call_timeout_seconds` > 單工具顯式 `timeout_seconds` > 類別默認 > 無限制，剩餘 wall-clock 預算僅作不可突破的外層 cap，`inf`/`nan`/負數降級為「無限制」；超時為 best-effort 軟中斷：Python 線程無法被強制停止，handler 可能在超時後繼續運行，超時結果標記 `retriable: false` 並寫入 `non_retriable_tool_results` 阻斷重試，且為仍在後臺的 handler 武裝協作取消信號（`is_tool_cancellation_requested()` 與既有 `check_tool_execution()` 檢查點均響應，handler 從不輪詢則行為不變）以儘量減小副作用 | `0` | 否 |
| `AGENT_SEARCH_TOOL_TIMEOUT_S` | Agent `search` 類工具默認超時秒數；`0` 表示關閉，回退到全局預算 | `0` | 否 |
| `AGENT_ANALYSIS_TOOL_TIMEOUT_S` | Agent `analysis` 類工具默認超時秒數；`0` 表示關閉，回退到全局預算 | `0` | 否 |
| `AGENT_ACTION_TOOL_TIMEOUT_S` | Agent `action` 類工具默認超時秒數；`0` 表示關閉，回退到全局預算 | `0` | 否 |
| `LITELLM_MODEL` | 主模型，格式 `provider/model`（如 `gemini/gemini-3.6-flash`），推薦優先使用 | - | 否 |
| `AGENT_LITELLM_MODEL` | 「默認模型」問股的主模型（可選）；留空繼承主模型，無 provider 前綴按 `openai/<model>` 解析；Codex 不使用此項 | - | 否 |
| `AGENT_CONTEXT_COMPRESSION_ENABLED` | 「默認模型」問股可見歷史的 LLM 壓縮開關；Codex 使用最近 20 條可見對話且保留該配置 | `false` | 否 |
| `AGENT_CONTEXT_COMPRESSION_PROFILE` | 問股上下文壓縮策略：`cost` / `balanced` / `long_context_raw_first` | `balanced` | 否 |
| `AGENT_CONTEXT_COMPRESSION_TRIGGER_TOKENS` | 歷史 token 估算超過該值時觸發壓縮；留空則跟隨 profile preset | - | 否 |
| `AGENT_CONTEXT_PROTECTED_TURNS` | 壓縮時最近 N 個用戶輪次及其後的回覆保留原文；留空則跟隨 profile preset | - | 否 |
| `LITELLM_FALLBACK_MODELS` | 備選模型，逗號分隔 | - | 否 |
| `LLM_CHANNELS` | 渠道名稱列表（逗號分隔），配合 `LLM_{NAME}_*` 使用，詳見 [LLM 配置指南](LLM_CONFIG_GUIDE.md) | - | 否 |
| `MODELFLARE_KEY` | Modelflare 單 Key 接入，自動啟用默認渠道；Actions 僅從 Secrets 讀取 | - | 選用時 |
| `LLM_MODELFLARE_API_KEY` | 高級渠道 Key，優先於 MODELFLARE_KEY；多 Key 可用 `LLM_MODELFLARE_API_KEYS` | - | 否 |
| `LLM_MODELFLARE_PROTOCOL` | Modelflare 渠道協議，默認地址自動識別為 `openai` | `openai` | 否 |
| `LLM_MODELFLARE_API_SURFACE` | Modelflare 渠道 API Surface，快速開始示例使用 `chat_completions` | `chat_completions` | 否 |
| `LLM_MODELFLARE_BASE_URL` | Modelflare 接入地址，顯式配置優先於默認值 | `https://modelflare.dev/v1` | 否 |
| `LLM_MODELFLARE_MODELS` | 高級顯式渠道模型列表；單 Modelflare 渠道可複用 LITELLM_MODEL | 單渠道自動推導 | 否 |
| `LLM_HERMES_API_KEY` | Hermes reserved 本地 HTTP generation 的單一 API Key；只應來自 `.env`、運行時配置或 Secrets | - | Hermes 使用時必填 |
| `LLM_HERMES_BASE_URL` | Hermes 本地 loopback `/v1` 地址；默認 `http://127.0.0.1:8642/v1`，不支持遠程地址 | `http://127.0.0.1:8642/v1` | 否 |
| `LLM_HERMES_MODELS` | Hermes 原始模型列表；Phase 3 默認 `hermes-agent`，運行時 route 為 `openai/hermes-agent`，不支持 Vision / stream / tools / Agent tools | `hermes-agent` | 否 |
| `LITELLM_CONFIG` | 高級模型路由 YAML 配置文件路徑（高級） | - | 否 |
| `LLM_PROMPT_CACHE_TELEMETRY_ENABLED` | Provider prompt cache usage / diagnostics 遙測；不控制 provider implicit cache | `true` | 否 |
| `LLM_PROMPT_CACHE_HINTS_ENABLED` | 主分析路徑是否主動發送已驗證的 provider-specific prompt cache hints；Agent 路徑當前僅記錄 diagnostics，不主動發 hints；默認關閉 | `false` | 否 |
| `LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL` | Prompt cache 診斷級別：`off` / `basic` / `debug`；basic/debug 僅在 debug 日誌和測試可觀察對象中提供脫敏診斷，不作為公開 Usage API 或普通設置頁輸出 | `off` | 否 |
| `LLM_USAGE_HMAC_SECRET` | LLM 用量遙測 message HMAC 密鑰；留空時自動使用數據目錄中的本地密鑰文件 | - | 否 |
| `LLM_USAGE_HMAC_KEY_VERSION` | LLM 用量遙測 HMAC 密鑰版本標籤，輪換密鑰時同步更新 | `local-v1` | 否 |
| `AIHUBMIX_KEY` | [AIHubmix](https://inferera.com/?aff=CfMq) API Key，一 Key 切換使用全系模型，無需額外配置 Base URL | - | 可選 |
| `GEMINI_API_KEY` | Google Gemini API Key | - | 可選 |
| `GEMINI_MODEL` | 主模型名稱（legacy，`LITELLM_MODEL` 優先） | `gemini-3.6-flash` | 否 |
| `GEMINI_MODEL_FALLBACK` | 備選模型（legacy） | `gemini-3.5-flash-lite` | 否 |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key | - | 可選 |
| `OPENAI_BASE_URL` | OpenAI 兼容 API 地址 | - | 可選 |
| `OLLAMA_API_BASE` | Ollama 本地服務地址（如 `http://localhost:11434`），詳見 [LLM 配置指南](LLM_CONFIG_GUIDE.md) | - | 可選 |
| `OPENAI_MODEL` | OpenAI 模型名稱（legacy，AIHubmix 用戶可填如 `gemini-3.6-flash`、`gpt-6.1-sol`） | `gpt-6.1-sol` | 可選 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | - | 可選 |
| `ANTHROPIC_MODEL` | Claude 模型名稱 | `claude-sonnet-4-6` | 可選 |
| `ANTHROPIC_TEMPERATURE` | Claude 溫度參數（0.0-1.0） | `0.7` | 可選 |
| `ANTHROPIC_MAX_TOKENS` | Claude 響應最大 token 數 | `8192` | 可選 |
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC) API Key（可選，模型與搜索共用；可用性以賬號權限為準） | - | 可選 |

> GitHub Actions 說明：倉庫自帶 `00-daily-analysis.yml` 在 `GENERATION_FALLBACK_BACKEND` 未配置時顯式使用 `litellm`，避免未設置的 Secret/Variable 被導出為空值並意外禁用 backend fallback。若要在 Actions 中禁用 backend fallback，請將 fallback 設為 primary backend，讓 resolver 走 self no-op。

> 生成後端狀態說明：Web 設置頁的快速檢查只讀取已保存配置、未保存草稿，並檢查本地 CLI 可執行文件是否可見，不發起真實模型請求；JSON 冒煙測試是單獨的顯式操作，會使用服務端固定的 JSON 提示詞和 schema 發起一次真實請求。`health_status` 與 `last_error_code/message` 只表示本次狀態計算或冒煙測試結果，不是歷史持久健康狀態。

> *注：至少配置一個可用的 `LLM_CHANNELS` / `LITELLM_CONFIG`，或 legacy provider Key / `OLLAMA_API_BASE`。Modelflare 通過 Channels 接入；已有 `ANSPIRE_API_KEYS` 與 `AIHUBMIX_KEY` 的 legacy 兼容入口仍無需配置 `OPENAI_BASE_URL`，系統自動適配。

> 問股 single-agent 路徑會在後臺為 DeepSeek V4 thinking + tool-call 保存最近 3 條 provider trace，並按原時序回放 `reasoning_content` / tool 結果；該能力不新增配置項，不進入 Web 歷史 API，Claude extended thinking 僅覆蓋離線 plumbing，multi-agent trace 注入留作後續增強。

> Codex App Server 問股後端已移除。`AGENT_BACKEND` 僅支持 `auto`（推薦，保持默認 LiteLLM）或 `litellm`。舊 `codex_app_server` 可加載、顯示和導出，但執行請求在準備與接受提交前返回 `backend_removed`，不會自動切換模型、賬號或 provider。請在「設置 → Agent 設置 → 問股生成方式」主動選擇合法值並保存；已有舊值不阻止無關設置保存，顯式保存或導入舊值則拒絕且不部分寫入。狀態與草稿預覽只檢查配置，不啟動 Codex 命令或 schema/version 探針，也不調用模型。歷史會話、股票身份、Skill、單/多 Agent 與 provider trace 保持原契約。獨立 `GENERATION_BACKEND=codex_cli` 普通報告及其他 generation-only 不受此移除影響，仍需各自 CLI 及其原有依賴。

### 通知渠道配置

更多通知配置基線、診斷和部署場景說明見 [通知專題文檔](notifications.md)。

| 變量名 | 說明 | 必填 |
|--------|------|:----:|
| `WECHAT_WEBHOOK_URL` | 企業微信機器人 Webhook URL | 可選 |
| `FEISHU_WEBHOOK_URL` | 飛書機器人 Webhook URL | 可選 |
| `FEISHU_WEBHOOK_SECRET` | 飛書機器人簽名密鑰（僅在機器人安全設置啟用“簽名校驗”時填寫） | 可選 |
| `FEISHU_WEBHOOK_KEYWORD` | 飛書機器人關鍵詞（僅在機器人安全設置啟用“關鍵詞”時填寫） | 可選 |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | 可選 |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID | 可選 |
| `TELEGRAM_MESSAGE_THREAD_ID` | Telegram Topic ID | 可選 |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL | 可選 |
| `DISCORD_BOT_TOKEN` | Discord Bot Token（與 Webhook 二選一） | 可選 |
| `DISCORD_MAIN_CHANNEL_ID` | Discord Channel ID（使用 Bot 時需要） | 可選 |
| `DISCORD_INTERACTIONS_PUBLIC_KEY` | Discord Public Key（僅入站 Interaction/Webhook 回調驗籤時需要） | 可選 |
| `DISCORD_MAX_WORDS` | Discord 單條消息 content 上限（默認 2000；運行時不會超過 Discord 2000 字符限制，長報告會自動分片並對 429 限流做有限重試） | 可選 |
| `SLACK_BOT_TOKEN` | Slack Bot Token（推薦，支持圖片上傳；同時配置時優先於 Webhook） | 可選 |
| `SLACK_CHANNEL_ID` | Slack Channel ID（使用 Bot 時需要） | 可選 |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL（僅文本，不支持圖片） | 可選 |
| `EMAIL_SENDER` | 發件人郵箱 | 可選 |
| `EMAIL_PASSWORD` | 郵箱授權碼（非登錄密碼） | 可選 |
| `EMAIL_RECEIVERS` | 收件人郵箱（逗號分隔，留空發給自己） | 可選 |
| `EMAIL_SENDER_NAME` | 發件人顯示名稱 | 可選 |
| `STOCK_GROUP_N` / `EMAIL_GROUP_N` | 郵件分組路由（Issue #268）：`STOCK_GROUP_N` 應為 `STOCK_LIST` 子集，僅影響郵件收件人，不改變分析範圍或其他通知渠道 | 可選 |
| `CUSTOM_WEBHOOK_URLS` | 自定義 Webhook（逗號分隔） | 可選 |
| `CUSTOM_WEBHOOK_BEARER_TOKEN` | 自定義 Webhook Bearer Token | 可選 |
| `WEBHOOK_VERIFY_SSL` | 讀取該配置的 webhook-style HTTPS 通知請求證書校驗（默認 true）。設為 false 可支持自簽名。警告：關閉有嚴重安全風險 | 可選 |
| `PUSHOVER_USER_KEY` | Pushover 用戶 Key | 可選 |
| `PUSHOVER_API_TOKEN` | Pushover API Token | 可選 |
| `NTFY_URL` | ntfy 完整 topic endpoint，必須包含 topic path，例如 `https://ntfy.sh/my-topic` | 可選 |
| `NTFY_TOKEN` | ntfy Bearer Token（可選） | 可選 |
| `GOTIFY_URL` | Gotify server base URL，不包含 `/message` | 可選 |
| `GOTIFY_TOKEN` | Gotify application token，通過 `X-Gotify-Key` Header 發送 | 可選 |
| `PUSHPLUS_TOKEN` | PushPlus Token（國內推送服務） | 可選 |
| `SERVERCHAN3_SENDKEY` | Server醬³ Sendkey | 可選 |
| `ASTRBOT_URL` | AstrBot Webhook URL | 可選 |
| `ASTRBOT_TOKEN` | AstrBot Bearer Token（可選） | 可選 |
| `NOTIFICATION_REPORT_CHANNELS` | report 路由渠道，逗號分隔；允許值：wechat,feishu,telegram,email,pushover,ntfy,gotify,pushplus,serverchan3,custom,discord,slack,astrbot | 可選 |
| `NOTIFICATION_ALERT_CHANNELS` | alert 路由渠道，逗號分隔；留空保持全渠道 | 可選 |
| `NOTIFICATION_SYSTEM_ERROR_CHANNELS` | system_error 預留路由渠道，逗號分隔；留空保持全渠道 | 可選 |
| `NOTIFICATION_DEDUP_TTL_SECONDS` | 通知去重 TTL 秒數，`0` 關閉 | 可選 |
| `NOTIFICATION_COOLDOWN_SECONDS` | 通知冷卻秒數，`0` 關閉 | 可選 |
| `NOTIFICATION_QUIET_HOURS` | 靜默時段，格式 `HH:MM-HH:MM`，支持跨午夜 | 可選 |
| `NOTIFICATION_TIMEZONE` | 靜默時段時區，如 `Asia/Shanghai`；留空跟隨 `TZ` 或系統本地時區 | 可選 |
| `NOTIFICATION_MIN_SEVERITY` | 最低通知級別：info, warning, error, critical；留空保持現狀 | 可選 |
| `NOTIFICATION_DAILY_DIGEST_ENABLED` | 每日摘要預留開關；當前不會發送摘要 | 可選 |

> 說明：默認 `00-daily-analysis.yml` GitHub Actions workflow 只映射固定變量名，不會自動導入任意編號的 `STOCK_GROUP_N` / `EMAIL_GROUP_N`。因此分組郵箱目前僅在本地 `.env`、Docker 或其他已顯式注入這些環境變量的運行環境中生效；若你要在自己的 GitHub Actions 中使用，需在 workflow 的 job `env:` 中逐組顯式映射。

#### 飛書雲文檔配置（可選，解決消息截斷問題）

| 變量名 | 說明 | 必填 |
|--------|------|:----:|
| `FEISHU_APP_ID` | 飛書應用 ID | 可選 |
| `FEISHU_APP_SECRET` | 飛書應用 Secret | 可選 |
| `FEISHU_FOLDER_TOKEN` | 飛書雲盤文件夾 Token | 可選 |
| `FEISHU_SEND_AS_FILE` | 飛書 App Bot 以文件形式發送報告（默認 `false`） | 可選 |

> 飛書雲文檔配置步驟：
> 1. 在 [飛書開發者後臺](https://open.feishu.cn/app) 創建應用
> 2. 配置 GitHub Secrets
> 3. 創建群組並添加應用機器人
> 4. 在雲盤文件夾中添加群組為協作者（可管理權限）
>
> 說明：`FEISHU_APP_ID` / `FEISHU_APP_SECRET` 用於飛書應用、雲文檔或 Stream Bot 模式，不會直接啟用群 Webhook 推送。只想簡單收群通知時，請優先配置 `FEISHU_WEBHOOK_URL`。
>
> 補充：若同時配置 `FEISHU_APP_ID`、`FEISHU_APP_SECRET` 和 `FEISHU_CHAT_ID`，則可啟用飛書 App Bot 主動通知渠道，無需 Webhook 即可主動向指定 chat 或用戶推送；`FEISHU_RECEIVE_ID_TYPE` 默認 `chat_id`，私聊時改為 `open_id`。該方式走飛書 OpenAPI Bot 會話，與群 Webhook 是兩條獨立鏈路。

### 搜索服務配置

| 變量名 | 說明 | 必填 |
|--------|------|:----:|
| `SERPAPI_API_KEYS` | SerpAPI 搜索引擎結果補強，適合實時金融新聞 | 推薦 |
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC) API Key（可選，模型與搜索共用；可用性以賬號權限為準） | 可選 |
| `TAVILY_API_KEYS` | Tavily 搜索 API Key | 可選 |
| `BOCHA_API_KEYS` | 博查搜索 API Key（中文優化） | 可選 |
| `BRAVE_API_KEYS` | Brave Search API Key（美股優化） | 可選 |
| `MINIMAX_API_KEYS` | MiniMax Coding Plan Web Search（結構化搜索結果） | 可選 |
| `SOCIAL_SENTIMENT_API_KEY` | Stock Sentiment API Key（Reddit / X / Polymarket，可選） | 可選 |
| `SOCIAL_SENTIMENT_API_URL` | Stock Sentiment API 地址（默認 `https://api.adanos.org`） | 可選 |
| `SEARXNG_BASE_URLS` | SearXNG 自建實例（無配額兜底，需在 settings.yml 啟用 format: json）；留空時僅在顯式啟用公共實例發現後使用 `searx.space` | 可選 |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | 是否在 `SEARXNG_BASE_URLS` 為空時自動從 `searx.space` 獲取公共實例（默認 `false`）。公共實例普遍限流或未開啟 JSON 輸出，開啟後每次分析可能多耗 30~60 秒且新聞面為空 | 可選 |
| `SEARXNG_TIMEOUT_SECONDS` | 自建 SearXNG 單次搜索超時（秒，默認 `10`，最小 `1`）；實例較慢（如聚合引擎較多的 NAS 部署）時可調大，公共實例超時不受影響。GitHub Actions 需顯式映射該變量 | 可選 |
| `NEWS_STRATEGY_PROFILE` | 新聞策略窗口檔位：`ultra_short`(1天)/`short`(3天)/`medium`(7天)/`long`(30天)；實際窗口取與 `NEWS_MAX_AGE_DAYS` 的最小值 | 默認 `short` |
| `NEWS_MAX_AGE_DAYS` | 新聞最大時效（天），搜索時限制結果在近期內 | 默認 `3` |
| `BIAS_THRESHOLD` | 乖離率閾值（%），超過提示不追高；強勢趨勢股自動放寬到 1.5 倍 | 默認 `5.0` |

> Anspire 保留為可選服務。搜索順序為 Bocha → Tavily → Brave → SerpAPI → Anspire → MiniMax → SearXNG，按已配置且可用的渠道依次嘗試；僅配置 Anspire 時仍可直接使用。

> 行為說明：搜索服務與社交輿情服務為可選增強鏈路。任一服務初始化失敗時，系統會記錄 warning 並降級為跳過該服務，僅影響對應環節，不會阻塞技術面主鏈路和主任務流。

### 新聞檢索可解釋排序（Issue #1356）

`search_stock_news` 對每條候選新聞會計算「可解釋相關度」並落地為 3 類標籤：

- `direct_company_news`：命中目標代碼、公司名（含官方/交易所來源加權）；
- `sector_related_news`：命中行業板塊語義；
- `macro_market_news`：未命中目標主體時的宏觀/市場語境新聞。

排序策略為：先按類別優先級（direct > sector > macro）排序，再按語言偏好（中文優先）再按分數排序，因此當同一時窗內存在明確標的命中的新聞時會優先展示。

排序後還會執行一層域名無關的准入過濾：明顯的下載/安裝包/應用評分頁、成人/招嫖服務垃圾頁會被剔除；當同一批次已經存在直接標的或有分數的行業/市場候選時，`score=0` 的背景填充項不會進入 `news_context`、Agent 工具輸出或歷史情報緩存。該規則不內置具體網站黑名單，避免靠窮舉域名維護。

調試入口：

- 每條返回會保留 `relevance_score` / `relevance_category` / `relevance_reasons` 元數據，最終 `to_text()` 與情報上下文會附帶對應「關聯度」說明；
- 搜索鏈路日誌會輸出 `[新聞相關度]` 統計，便於覆盤為何該批次觸發了 direct/sector/macro 分層。

兼容與回退說明：該改動不新增/修改模型、provider、Base URL、LiteLLM route、配置清理或回寫邏輯；若出現異常，只能通過回滾本次提交恢復舊排序行為，不涉及歷史配置遷移。

### Futu 持倉導入配置

| 變量名 | 說明 | 默認值 | 必填 |
|--------|------|--------|:----:|
| `FUTU_OPEND_HOST` | OpenD 地址；鎖定的 `futu-api==10.8.6808` 僅支持 IPv4 地址或可解析到 IPv4 的主機名。跨主機連接只應使用受信網絡或本機端口轉發。 | `127.0.0.1` | 可選 |
| `FUTU_OPEND_PORT` | OpenD 端口，合法範圍 `1-65535`。 | `11111` | 可選 |
| `FUTU_SECURITY_FIRM` | Futu `SecurityFirm` 枚舉名；`NONE` 表示使用 SDK 官方自動識別一次，也可顯式指定券商。 | `NONE` | 可選 |
| `FUTU_ACC_ID` | 指定一個符合條件的 REAL 賬戶 ID；留空時合併所有狀態為 `ACTIVE` 的 `NORMAL`（普通）和 `MASTER`（主）證券賬戶。賬戶 ID 應按敏感配置處理，不要提交到倉庫。 | 空 | 可選 |

`MASTER` 僅表示 Futu 的主賬戶角色，不表示賬戶具有隻讀屬性。本集成的只讀邊界來自它只調用賬戶、持倉和證券信息查詢接口，不調用交易解鎖、下單、改單或撤單接口。

### 數據源配置

| 變量名 | 說明 | 默認值 | 必填 |
|--------|------|--------|:----:|
| `TUSHARE_TOKEN` | Tushare Pro Token | - | 可選 |
| `TUSHARE_HTTP_URL` | Tushare Pro HTTP 接入地址；留空時使用官方端點 `http://api.tushare.pro`，僅在需通過公司內網代理、跨境網絡或自建鏡像時填 `http://` 或 `https://` 開頭的完整地址 | `http://api.tushare.pro` | 可選 |
| `TICKFLOW_API_KEY` | TickFlow API Key；可選，用於 A 股日 K、實時行情、股票列表/名稱與大盤覆盤增強；失敗或權限不足時自動回退。 | - | 可選 |
| `TICKFLOW_PRIORITY` | TickFlow 普通 A 股日 K 數據源優先級；數字越小越早嘗試，默認 `2`；未配置 API Key 時不啟用；已登記指數使用獨立固定鏈，不讀取本變量；不影響實時行情。 | `2` | 可選 |
| `TENCENT_PRIORITY` | 騰訊直連普通 A 股日 K 數據源優先級；數字越小越早嘗試，默認 `5`，作為通用鏈路最終兜底；已登記指數使用獨立固定鏈，不讀取本變量；不影響實時行情。 | `5` | 可選 |
| `TICKFLOW_KLINE_ADJUST` | TickFlow 日 K 復權模式：`none`、`forward`、`backward`、`forward_additive`、`backward_additive`。 | `none` | 可選 |
| `TICKFLOW_BATCH_DAILY_ENABLED` | 是否啟用 TickFlow 批量日 K 預取；權限不足會短期緩存失敗狀態，並繼續走常規回退。 | `true` | 可選 |
| `TICKFLOW_BATCH_SIZE` | TickFlow 日 K 與實時行情批量請求的單批最大標的數。 | `100` | 可選 |
| `FUTU_HK_REALTIME_SOURCE_PRIORITY` | 港股實時行情獨立優先級，可選 `futu`、`longbridge`、`akshare`、`yfinance`，按逗號分隔；失敗自動回退。 | `futu,longbridge,akshare,yfinance` | 可選 |
| `LONGBRIDGE_OAUTH_CLIENT_ID` | Longbridge OAuth client_id；留空且無 Legacy Access Token 時會兼容使用 `LONGBRIDGE_APP_KEY` | - | 可選 |
| `LONGBRIDGE_OAUTH_TOKEN_CACHE_B64` | OAuth token 緩存文件的 base64 內容，供 GitHub Actions / Docker 等 headless 環境使用 | - | 可選 |
| `LONGBRIDGE_APP_KEY` | Longbridge Legacy App Key；無 `LONGBRIDGE_ACCESS_TOKEN` 時也可作為 OAuth client_id 兼容別名 | - | 可選 |
| `LONGBRIDGE_APP_SECRET` | Longbridge App Secret | - | 可選 |
| `LONGBRIDGE_ACCESS_TOKEN` | Longbridge Legacy Access Token（不是 OAuth access token） | - | 可選 |
| `LONGBRIDGE_*`（可選） | 見官方 [環境變量](https://open.longbridge.com/zh-CN/docs/getting-started#環境變量)；另有 `LONGBRIDGE_STATIC_INFO_TTL_SECONDS` 與 `LONGBRIDGE_CONNECTION_COOLDOWN_SECONDS` | - | 可選 |
| `ENABLE_REALTIME_QUOTE` | 啟用實時行情（關閉後使用歷史收盤價分析） | `true` | 可選 |
| `ENABLE_REALTIME_TECHNICAL_INDICATORS` | 盤中實時技術面：啟用時用實時價計算 MA5/MA10/MA20 與多頭排列（Issue #234）；關閉則用昨日收盤 | `true` | 可選 |
| `ENABLE_CHIP_DISTRIBUTION` | 啟用籌碼分佈分析（該接口不穩定，雲端部署建議關閉）。GitHub Actions 用戶需在 Repository Variables 中設置 `ENABLE_CHIP_DISTRIBUTION=true` 方可啟用；workflow 默認關閉。 | `true` | 可選 |
| `ENABLE_EASTMONEY_PATCH` | 東財接口補丁：東財接口頻繁失敗（如 RemoteDisconnected、連接被關閉）時建議設為 `true`，注入 NID 令牌與隨機 User-Agent 以降低被限流概率 | `false` | 可選 |
| `REALTIME_SOURCE_PRIORITY` | 實時行情源優先級，逗號分隔，例如 `tencent,akshare_sina,efinance,akshare_em`；需要顯式加入 `tickflow` 才會使用 TickFlow 實時行情。 | 見 `.env.example` | 可選 |
| `ENABLE_FUNDAMENTAL_PIPELINE` | 基本面聚合總開關；關閉時僅返回 `not_supported` 塊，不改變原分析鏈路 | `true` | 可選 |
| `FUNDAMENTAL_STAGE_TIMEOUT_SECONDS` | 基本面階段總時延預算（秒） | `8.0` | 可選 |
| `FUNDAMENTAL_FETCH_TIMEOUT_SECONDS` | 單能力源調用超時（秒）；市場結構行業/概念排行也複用該預算 | `8.0` | 可選 |
| `FUNDAMENTAL_RETRY_MAX` | 基本面能力重試次數（含首次） | `1` | 可選 |
| `FUNDAMENTAL_CACHE_TTL_SECONDS` | 基本面聚合緩存 TTL（秒），短緩存減輕重複拉取 | `120` | 可選 |
| `FUNDAMENTAL_CACHE_MAX_ENTRIES` | 基本面緩存最大條目數（TTL 內按時間淘汰） | `256` | 可選 |

> 行為說明：
> - A 股：按 `valuation/growth/earnings/institution/capital_flow/dragon_tiger/boards` 聚合能力返回；
> - ETF：返回可得項，缺失能力標記為 `not_supported`，整體不影響原流程；
> - 美股/港股：通過 yfinance 適配器返回 `valuation/growth/earnings/belong_boards`（來源 `info.sector`/`industry`），`institution/capital_flow/dragon_tiger/boards` 暫無對應數據源仍標記 `not_supported`；yfinance 不可用或字段缺失時整體降級回 `not_supported`，仍走 fail-open；
> - 日股/韓股：當前僅走 Yfinance 基礎路徑獲取日線與實時行情；`institution`、`capital_flow`、`dragon_tiger`、`boards` 等依賴 A 股專屬源/離岸完整版的能力會降級為 `not_supported`（詳見 [市場支持與邊界](market-support.md)）；
> - 臺股：在美股/港股 offshore 基礎路徑之外，`institution` 區塊額外展示三大法人原始買賣超淨額（TWSE T86 / TPEx，默認開啟、fail-open，取不到數據時維持 `not_supported`）；`capital_flow`、`dragon_tiger`、`boards` 仍為 `not_supported`；
> - 任何異常走 fail-open，僅記錄錯誤，不影響技術面/新聞/籌碼主鏈路。
> - 配置 `TICKFLOW_API_KEY` 後，TickFlow 會作為可選 A 股日 K 數據源和大盤覆盤增強源實例化；`TICKFLOW_PRIORITY` 隻影響普通 A 股日 K/通用數據源回退鏈。實時行情優先級由 `REALTIME_SOURCE_PRIORITY` 單獨控制，只有顯式包含 `tickflow` 時才會使用 TickFlow 實時行情。`REALTIME_SOURCE_PRIORITY` 中排在 `tickflow` 前面的數據源會先被嘗試。
> - 當前 `IndexRegistry` 已登記的全部滬深指數（`sh`/`sz`/`csi` 前綴，具體清單以 [指數自選股配置](#指數自選股配置) 的註冊表說明與 `scripts/stock_index_seeds/index_registry.csv` 為準）在使用顯式市場輸入（也接受 `000016.SH` 等交易所後綴形式）時，不參與通用 priority 排序，固定按 Tencent → AkShare → TickFlow → YFinance 降級；未配置或不可用的來源會跳過。裸 `000016` 等代碼仍按股票處理，不觸發指數鏈。該固定鏈不讀取 `EFINANCE_PRIORITY`、`AKSHARE_PRIORITY`、`TUSHARE_PRIORITY`、`TICKFLOW_PRIORITY`、`PYTDX_PRIORITY`、`BAOSTOCK_PRIORITY`、`YFINANCE_PRIORITY` 或 `TENCENT_PRIORITY`，不影響普通股票和實時行情的既有順序。
> - 已登記指數名稱優先來自本地註冊表；只有註冊名稱無效時才按 Tencent → AkShare → TickFlow 查詢，名稱鏈不使用 YFinance。指數日線四源全部失敗時返回空結果並記錄彙總告警；普通股票仍保持既有的 `DataFetchError` 最終失敗契約。
> - TickFlow 日 K 默認 `TICKFLOW_KLINE_ADJUST=none`；日線 `volume` 從手統一轉為股，`amount` 保持元口徑。
> - TickFlow 日 K 區間請求會顯式傳入 `start_time` / `end_time` / `count`；官方 quickstart 明確說明時間範圍查詢仍受 `count` 限制。若返回非空但行數打滿 `count` 且首個返回交易日晚於請求起始交易日，系統會判定為疑似截斷，不寫入緩存並讓 manager 繼續回退。
> - 批量分析時，`prefetch_daily_klines()` 會在逐股 `get_daily_data()` 之前預熱進程內緩存，不改變對外調用路徑。
> - TickFlow 能力按套餐權限分層：有限權限套餐仍可使用主指數查詢；支持 `CN_Equity_A` 標的池查詢的套餐才會啟用 TickFlow 市場統計。
> - TickFlow 可通過申萬一級行業標的池與全 A 股行情生成行業漲跌排行，並優先參與市場結構行業主線 fallback；概念題材排行仍由現有 AkShare / Tushare / Efinance 鏈路提供。
> - TickFlow 官方 quickstart 提供了 `quotes.get(universes=["CN_Equity_A"])` 用法，但不同 API Key 不一定擁有對應權限；批量日 K、深度和財務等能力也按權限 fail-open。
> - TickFlow 實際返回的 `change_pct` / `amplitude` 為比例值；系統已在接入層統一轉換為百分比值，確保與現有數據源字段語義一致。
> - A 股大盤覆盤報告採用盤後工作臺式結構：固定包含盤面信號、指數明細、板塊 Top 表、近三日市場線索、明日交易計劃和風險提示；盤面信號以 `66/100（偏暖，可進攻）` 這類純文本分數表達，避免色塊進度條在不同終端顯示不一致；近三日市場線索只列標題、來源和鏈接，不再展示搜索摘要片段；若部分數據源缺失，則保留可用區塊並在對應位置降級展示。
> - 字段契約：
>   - `fundamental_context.belong_boards` = 個股關聯板塊列表；A 股從 AkShare 板塊名單寫入，美股/港股從 yfinance `info.sector` / `info.industry` 寫入，無數據時為 `[]`；
>   - `fundamental_context.boards.data` = `sector_rankings`（板塊漲跌榜，結構 `{top, bottom}`，HK/US 當前不提供）；
>   - `fundamental_context.concept_boards.data` = `concept_rankings`（概念/題材漲跌榜，結構 `{top, bottom}`，當前僅 A 股提供；不可用時 fail-open 為空或缺失）；
>   - `fundamental_context.earnings.data.financial_report` = 財報摘要（報告期、營收、歸母淨利潤、經營現金流、ROE，及 `currency` 來源 `info.financialCurrency`，HK ADR 常見為 CNY）；
>   - `fundamental_context.earnings.data.dividend` = 分紅指標（僅現金分紅稅前口徑，含 `events`、`ttm_cash_dividend_per_share`、`ttm_dividend_yield_pct`、`currency`）。`currency` 獨立讀取自 `info.currency`，與 `financial_report.currency` 可能不同（HK ADR 財報 CNY、分紅 HKD）；TTM yield 默認按 `ttm_cash / latest_price * 100`（同幣種）即時重算，僅在 TTM cash 或 latest price 缺失時回退到 yfinance `trailingAnnualDividendYield` 或 `dividendYield`；
>   - `get_stock_info.belong_boards` = 個股所屬板塊列表；
>   - `get_stock_info.boards` 為兼容別名，值與 `belong_boards` 相同（未來僅在大版本考慮移除）；
>   - `get_stock_info.sector_rankings` 與 `fundamental_context.boards.data` 保持一致。
>   - `AnalysisReport.details.belong_boards` = 結構化報告詳情中的關聯板塊列表；
>   - `AnalysisReport.details.sector_rankings` = 結構化報告詳情中的板塊漲跌榜（用於前端板塊聯動展示）。
>   - `AnalysisReport.details.concept_rankings` = 結構化報告詳情中的概念/題材漲跌榜（用於前端關聯板塊信號匹配，以及通知表格按類型區分行業/概念）。
> - 板塊漲跌榜使用數據源順序：與全局 priority 一致。
> - 超時控制為 `best-effort` 軟超時：階段會按預算快速降級繼續執行，但不保證硬中斷底層三方調用。
> - `FUNDAMENTAL_STAGE_TIMEOUT_SECONDS=8.0` 表示新增基本面階段的目標預算，不是嚴格硬 SLA；Windows、Docker 或免費數據源被限流時可繼續調高到 `12-15s`。
> - 若要硬 SLA，請在後續版本升級為子進程隔離執行並在超時後強制終止。

### 其他配置

| 變量名 | 說明 | 默認值 |
|--------|------|--------|
| `STOCK_LIST` | 自選股代碼（逗號分隔） | - |
| `ADMIN_AUTH_ENABLED` | Web 登錄：設為 `true` 啟用密碼保護；首次訪問在網頁設置初始密碼，可在「系統設置 > 修改密碼」修改；忘記密碼執行 `python -m src.auth reset_password`。Web 的 `.env` 備份導入導出僅在開啟該開關後可用（桌面端不受此限制）。 | `false` |
| `TRUST_X_FORWARDED_FOR` | 單層可信反向代理部署時設為 `true`，取 `X-Forwarded-For` 最右值作為真實客戶端 IP（用於登錄限流等）；直連公網時保持 `false` 防偽造。多級代理/CDN 場景下限流 key 可能退化為邊緣代理 IP，需額外評估 | `false` |
| `MAX_WORKERS` | 併發線程數 | `3` |
| `GUARD_ENABLED` | 啟用可選的 [fastapi-guard](https://github.com/Guard-Core/fastapi-guard) 安全中間件：按 IP 限流、IP 白/黑名單、路徑/查詢參數/請求頭特徵攔截（除 `ssrf` 外的全部檢測類別：瀏覽器會把頁面地址作為 `Referer` 發送，而 guard-core 4.4.0 會把其中的 localhost 和局域網地址判為 ssrf）、掃描器自動封禁。與登錄失敗限流疊加而非替代；狀態在進程內存中，無需 Redis；修改後需重啟。CORS 仍由原 CORS 中間件處理（位於 guard 外層，429/403 也帶 CORS 頭）。需要依賴 `fastapi-guard`（已在 `requirements.txt`，未安裝時啟用會報錯） | `false` |
| `GUARD_RATE_LIMIT` / `GUARD_RATE_LIMIT_WINDOW` | 每個 IP 在窗口（秒）內的最大請求數，靜態資源與健康檢查同樣計數，冷緩存加載一個 WebUI 頁面約 14 至 34 個請求 | `300` / `60` |
| `GUARD_WHITELIST` / `GUARD_BLACKLIST` | IP 白/黑名單（逗號分隔，支持 CIDR）。白名單非空時，名單外 IP 一律 403；名單內 IP 不受限流約束 | 空 |
| `GUARD_TRUSTED_PROXIES` | 僅在 `TRUST_X_FORWARDED_FOR=true` 時生效：可信反向代理地址，默認僅本機迴環。只有來自這些地址的連接才採信 `X-Forwarded-For` 最右值，其它來源偽造的該首部被忽略（登錄限流的 `get_client_ip()` 同樣取最右值，但不校驗代理來源）；`TRUST_X_FORWARDED_FOR` 為 `false` 時一律使用 TCP 對端地址。啟用 guard 後，內置啟動入口（`main.py`、`server.py`、`webui.py`）讓 Uvicorn 只信任同一組代理，`TRUST_X_FORWARDED_FOR=false` 時關閉 Uvicorn 的代理頭處理，因此反向代理後部署請設 `TRUST_X_FORWARDED_FOR=true`；啟用 guard 且 `TRUST_X_FORWARDED_FOR=false` 時 Uvicorn 的代理頭處理被關閉，HTTPS 反向代理後登錄 cookie 會不帶 `Secure` 標誌（`_cookie_params()` 讀取的是 `request.url.scheme`），因此 HTTPS 代理後請設 `TRUST_X_FORWARDED_FOR=true`；自行用 `uvicorn` 命令啟動時，請讓 `FORWARDED_ALLOW_IPS` 與本項一致或加 `--no-proxy-headers`。Docker 中代理不在迴環時請填代理地址，否則所有用戶會共用同一個限流 key | `127.0.0.1,::1` |
| `GUARD_SCAN_BODY` | 是否同時掃描請求體（默認只檢查路徑、查詢參數和請求頭） | `false` |
| `GUARD_PASSIVE_MODE` | 僅記錄日誌不攔截，便於先觀察 | `false` |
| `MARKET_REVIEW_ENABLED` | 啟用大盤覆盤 | `true` |
| `DAILY_MARKET_CONTEXT_ENABLED` | 將當日大盤環境摘要注入個股分析 Prompt，並在高風險/退潮環境下軟化激進買入建議；默認開啟，設為 `false` 後仍可運行大盤覆盤 | `true` |
| `MARKET_REVIEW_REGION` | 大盤覆盤市場區域：cn(A股)、hk(港股)、us(美股)、jp(日股)、kr(韓股)、both(五市場)，us/jp/kr 適合僅關注單區域用戶 | `cn` |
| `MARKET_REVIEW_COLOR_SCHEME` | 大盤覆盤指數漲跌顏色：`green_up`=綠漲紅跌（默認），`red_up`=紅漲綠跌 | `green_up` |
| `TRADING_DAY_CHECK_ENABLED` | 交易日檢查：默認 `true`，非交易日跳過執行；設為 `false` 或使用 `--force-run` 可強制執行（Issue #373） | `true` |
| `SCHEDULE_ENABLED` | 啟用定時任務 | `false` |
| `SCHEDULE_TIME` | 定時執行時間 | `18:00` |
| `SCHEDULE_TIMES` | 多個定時執行時間，逗號分隔；為空時使用 `SCHEDULE_TIME` | 空 |
| `DSA_RUNTIME_SCHEDULER_TIMEOUT_SECONDS` | Web/API runtime scheduler 單次分析硬超時（秒，最小 60 秒）；超時後終止獨立分析進程，不阻塞後續任務 | `2700` |
| `DSA_TIMEOUT_PARTIAL_NOTIFY` | **默認開啟（行為變化）**：硬超時後對已落庫個股發送「部分完成」通知；此前超時不推送。`false` 時仍寫入結構化 `last_error`，但不推送 | `true` |
| `LOG_DIR` | 日誌目錄 | `./logs` |
| `SAVE_CONTEXT_SNAPSHOT` | 保存分析歷史 `context_snapshot`；設為 `false` 時新歷史不保存 enhanced_context、market_phase_summary、AnalysisContextPack overview 或診斷快照，但不關閉當次 Prompt 低敏摘要 | `true` |

---

## Docker 部署

Dockerfile 使用多階段構建，前端會在構建鏡像時自動打包並內置到 `static/`。
如需覆蓋靜態資源，可掛載本地 `static/` 到容器內 `/app/static`。
運行中的 `server` 容器默認直接複用 `/app/static` 裡的預構建產物，不要求容器內保留 `apps/dsa-web` 源碼目錄或運行時安裝 `npm`；若 WebUI 無法打開，請優先確認 `/app/static/index.html` 是否存在。

當前官方鏡像發佈地址：

- GHCR：`ghcr.io/zhulinsen/daily_stock_analysis:<tag>`
- Docker Hub：`<DOCKERHUB_USERNAME>/daily_stock_analysis:<tag>`（由發佈者的 `DOCKERHUB_USERNAME` secret 決定，官方發佈為 `zhulinsen/daily_stock_analysis`）

### 快速啟動

```bash
# 1. 克隆倉庫
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 2. 配置環境變量
cp .env.example .env
vim .env  # 填入 API Key 和配置

# 3. 啟動容器
docker-compose -f ./docker/docker-compose.yml up -d server     # Web 服務模式（推薦，提供 API 與 WebUI）
docker-compose -f ./docker/docker-compose.yml up -d analyzer   # 定時任務模式
docker-compose -f ./docker/docker-compose.yml up -d            # 同時啟動兩種模式

# 4. 訪問 WebUI
# http://localhost:8000

# 5. 查看日誌
docker-compose -f ./docker/docker-compose.yml logs -f server
```

默認 Compose 為每個服務設置 `limits.memory: 1G`、`reservations.memory: 512M`。`512M` 僅建議用於輕量 Web/API、單股、低併發場景，並將 `MAX_WORKERS=1`；常規完整分析建議 `1G`，同時啟動 `server + analyzer`、多股票、大盤覆盤、新聞擴展、圖片報告或選股建議 `2G+`。如果只能使用 `512M`，請避免同時啟動兩個服務並減少重型功能。

### 直接拉官方鏡像運行

如果你不打算在目標機器上保留源碼，可以直接拉取官方鏡像：

```bash
# Web/API 模式
docker pull zhulinsen/daily_stock_analysis:latest
docker run -d \
  --name dsa-server \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/reports:/app/reports" \
  zhulinsen/daily_stock_analysis:latest \
  python main.py --serve-only --host 0.0.0.0 --port 8000

# 定時任務模式
docker run -d \
  --name dsa-analyzer \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/reports:/app/reports" \
  zhulinsen/daily_stock_analysis:latest
```

如需固定版本或便於回滾，請將 `latest` 替換為具體版本 tag，例如 `v3.13.0`。

### 運行模式說明

| 命令 | 說明 | 端口 |
|------|------|------|
| `docker-compose -f ./docker/docker-compose.yml up -d server` | Web 服務模式，提供 API 與 WebUI | 8000 |
| `docker-compose -f ./docker/docker-compose.yml up -d analyzer` | 定時任務模式，每日自動執行 | - |
| `docker-compose -f ./docker/docker-compose.yml up -d` | 同時啟動兩種模式 | 8000 |

### Docker Compose 配置

`docker-compose.yml` 使用 YAML 錨點複用配置：

```yaml
version: '3.8'

x-common: &common
  build:
    context: ..
    dockerfile: docker/Dockerfile
  restart: unless-stopped
  env_file:
    - ../.env
  environment:
    - TZ=Asia/Shanghai
  volumes:
    - ../data:/app/data
    - ../logs:/app/logs
    - ../reports:/app/reports
    - ../strategies:/app/strategies:ro
  deploy:
    resources:
      limits:
        memory: 1G
      reservations:
        memory: 512M

services:
  # 定時任務模式
  analyzer:
    <<: *common
    container_name: stock-analyzer

  # FastAPI 模式
  server:
    <<: *common
    container_name: stock-server
    command: ["python", "main.py", "--serve-only", "--host", "0.0.0.0", "--port", "${API_PORT:-8000}"]
    ports:
      - "${API_PORT:-8000}:${API_PORT:-8000}"
```

### `.env` 與數據目錄映射說明

無論你使用 `docker run` 還是 Compose，都需要區分啟動環境變量注入和運行時文件寫入：

- 環境變量注入：`--env-file .env` 或 Compose 的 `env_file`
  作用：把 `.env` 中的鍵值作為容器啟動時的環境變量傳入 Python 進程。
- 運行時配置寫入：不要把宿主機 `.env` 作為單文件 bind mount 覆蓋容器內 `.env` 路徑。Docker 會把單文件掛載目標作為 mount point，配置保存時的 `os.replace()` 原子更新可能失敗並報 `Device or resource busy`，回退寫入也可能受權限限制。

默認 Compose 和 `docker run` 示例僅使用 `env_file` / `--env-file` 注入啟動配置，不再把宿主機 `.env` 單文件掛載進容器。WebUI 設置頁會在當前活躍 `.env` 文件缺少某些鍵時展示啟動注入的同名環境變量作為兜底，避免 Docker 用戶誤以為配置完全未讀取；但“導出 `.env`”仍只導出當前活躍配置文件內容。

WebUI 中保存的運行時配置默認寫入容器內部配置文件，不等同於回寫宿主機 `.env`；刪除或重建容器後仍以啟動時注入的 `.env` 為準。若需要持久化運行時配置，請將寫入目標放到可寫數據卷中（例如通過 `ENV_FILE=/app/data/runtime.env` 指向 `data` volume 中的文件），不要使用 `.env` 單文件 bind mount。注意：如果啟動時的 `env_file`、`--env-file`、`docker run -e` 或 Compose `environment:` 中仍保留同名舊值，容器重啟時這些進程環境變量仍可能覆蓋運行時文件中的保存值；要讓 WebUI 保存值接管，請同步更新或移除啟動環境中的同名覆蓋。

推薦同時映射這幾個目錄：

- `./data:/app/data`：數據庫、緩存和運行時數據
- `./logs:/app/logs`：日誌輸出
- `./reports:/app/reports`：生成的分析報告
- `./strategies:/app/strategies:ro`：自定義策略 YAML（只讀掛載）

官方 Docker 鏡像啟動時會自動創建並修復 `/app/data`、`/app/logs`、`/app/reports` 的掛載目錄權限，然後降權為容器內非 root 用戶 `dsa`（UID/GID `1000:1000`）運行應用。普通 Docker / Compose 部署不需要手動 `chown` 或 `chmod` 宿主機目錄。

如果你通過 `--user` 或 Compose `user:` 指定了其他運行用戶，或使用只讀掛載、rootless Docker、NFS 等限制 `chown` 的存儲環境，自動修復可能無法生效。此時請確保實際運行用戶對 `data`、`logs`、`reports` 具備寫入權限，或改用可寫卷。

如果你需要覆蓋內置靜態資源，還可以額外掛載：

- `./static:/app/static:ro`

### 常用命令

```bash
# 查看運行狀態
docker-compose -f ./docker/docker-compose.yml ps

# 查看日誌
docker-compose -f ./docker/docker-compose.yml logs -f server

# 停止服務
docker-compose -f ./docker/docker-compose.yml down

# 重建鏡像（代碼更新後）
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d server
```

### 手動構建鏡像

```bash
docker build -f docker/Dockerfile -t stock-analysis .
docker run -d \
  --name dsa-server-local \
  --env-file .env \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  -v "$(pwd)/reports:/app/reports" \
  stock-analysis \
  python main.py --serve-only --host 0.0.0.0 --port 8000
```

---

## 本地運行詳細配置

### 安裝依賴

```bash
# Python 3.10+ 推薦
pip install -r requirements.txt

# 或使用 conda
conda create -n stock python=3.10
conda activate stock
pip install -r requirements.txt
```

Windows PowerShell 若仍使用系統默認代碼頁，首次安裝依賴或運行環境檢查前建議先啟用 UTF-8，避免第三方工具或終端輸出在中文字符上失敗：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
python -m pip install -r requirements.txt
python scripts/check_env.py --config
```

**智能導入依賴**：`pypinyin`（名稱→代碼拼音匹配）和 `openpyxl`（Excel .xlsx 解析）已包含在 `requirements.txt` 中，執行上述 `pip install -r requirements.txt` 時會自動安裝。若使用智能導入（圖片/CSV/Excel/剪貼板）功能，請確保依賴已正確安裝；缺失時可能報 `ModuleNotFoundError`。

### 命令行參數

```bash
python main.py                        # 完整分析（個股 + 大盤覆盤）
python main.py --market-review        # 僅大盤覆盤
python main.py --no-market-review     # 僅個股分析
python main.py --etf-rotation         # ETF 輪動信號 + 規則回測（不調用 LLM，見 docs/etf-rotation.md）
python main.py --stocks 600519,300750 # 指定股票
python main.py --portfolio futu       # 使用 Futu 真實 LONG 正股持倉（覆蓋 --stocks/STOCK_LIST）
python main.py --dry-run              # 僅獲取數據，不 AI 分析
python main.py --no-notify            # 不發送推送
python main.py --schedule             # 定時任務模式
python main.py --force-run            # 非交易日也強制執行（Issue #373）
python main.py --debug                # 調試模式（詳細日誌）
python main.py --workers 5            # 指定併發數
```

### 指數一次性分析（Phase 1）

`--stocks` 一次性入口支持對已登記的 SH、SZ 與 CSI 指數執行完整分析。指數目標使用 `sh`/`sz` 前綴（如 `sh000016`）或 `.CSI` alias（如 `000300.CSI`、`930955.CSI`）顯式指定；裸六碼（如 `000016`）始終按股票處理。

```bash
# 同批分析上證50、滬深300、紅利低波100 三個指數
python main.py --stocks sh000016,000300.CSI,930955.CSI
# 指數與普通股票同批分析（000016 按股票身份執行）
python main.py --stocks sh000016,000016
# 僅獲取指數數據，不執行 AI 分析
python main.py --stocks sh000016 --dry-run
```

指數目標在 Pipeline 內以 `market=cn` 統一處理市場階段、日線目標日期、斷點續傳日期、歷史窗口與 `DecisionSignal`；籌碼分佈、基本面、板塊歸屬、資金流、龍虎榜與公司事件等個股專屬模塊會被集中跳過。未登記的 `.CSI` 輸入（如 `930956.CSI`）會在任何行情數據 provider 請求前明確拒絕：CLI `--stocks` 與 Actions 每日工作流對含未登記目標的整批拒絕本輪運行（不執行同批任何目標），Web/API 則為異步批量中僅該目標進入 `rejected`、同步/單股返回 4xx。搜索與報告使用註冊表中文指數名稱，不攜帶機器碼。

指數與 A 股共享交易日語義：啟用交易日檢查時，已登記指數（`sh`/`sz` 前綴或 `.CSI` alias）按 `market=cn` 參與 A 股休市過濾，A 股休市日指數會被跳過；市場仍無法識別的非指數 code 保持既有 fail-open 行為。`--force-run` 可強制在非交易日執行。

指數實時行情使用獨立固定鏈：騰訊 → 新浪 → 東財單股接口 → TickFlow；SH/SZ 指數按 `sh000016`/`sz399001` 顯式符號請求，CSI 指數僅由東財單股接口提供（`2.{code}` secid）。顯式指數身份全程保留，不會退化為同碼股票行情。

### 指數 Web/API 入口（Phase 2 PR1）

Web 自動補全與搜索已放行已登記指數：搜索註冊中文名（如 `上证50`）或顯式代碼（`sh000016`、`930955.CSI`）會返回對應指數條目並可提交分析；熱門候選仍僅展示股票（`assetType=stock`），不包含指數。

API `/analyze` 對顯式指數輸入構造結構化 `AnalysisTarget`：`sh000016` 以 `asset_type=INDEX` 且 `canonical_id=sh000016` 入隊，`930955.CSI`/`csi930955` 收斂為 `csi930955`。指數與同碼個股（如 `sh000016` 與 `000016`）獨立去重調度、互不折疊；未登記的 CSI 輸入（如 `930956.CSI`）在異步單股或同步模式返回明確的 4xx，在異步批量中僅該目標進入響應 `rejected` 列表、同批其他目標正常入隊。中文名稱輸入（如 `贵州茅台`）仍走既有股票名解析，不進入指數判型。

Bot `/analyze` 已支持已登記指數的顯式代碼（`sh000016`）、CSI alias（`930955.CSI`）和註冊中文名（`上证50`）。指數以 registry canonical 和結構化 `AnalysisTarget` 進入與 CLI/API 相同的 Pipeline；未登記 CSI、未知名稱或歧義註冊名稱會明確報錯且不提交任務。普通 A/HK/US 代碼與股票名稱繼續沿用 legacy code 路徑。

### 指數 GitHub Actions 入口（Phase 2 PR3）

GitHub Actions 每日工作流（`.github/workflows/00-daily-analysis.yml`）把 `STOCK_LIST` 配置中的顯式指數 token 與個股同批分析：`GITHUB_ACTIONS=true` 環境下 `python main.py` 無參數運行時（`full` 與 `stocks-only` 模式；`market-only` 不經個股列表，不參與此分類），`STOCK_LIST` 會按與 `--stocks` 相同的判型規則分類為結構化 target，顯式指數 token（如 `sh000016`、`930955.CSI`）進入指數路徑、個股 token 保持既有路徑，不新增第二條 Pipeline 或能力矩陣；含未登記 `.CSI` 目標時整批拒絕本輪運行。本地無參數默認路徑（`.env`/Docker 的 `STOCK_LIST`）與 `--schedule`/`config.schedule_enabled` 定時模式不參與此分類：本地 `--stocks` 參與分類，但本地無參默認路徑與定時模式不經 `--stocks` 構造 targets，`STOCK_LIST` 的其它運行環境語義不變。

> **Phase 2 邊界**：`--schedule`、Bot `/ask`、Bot `/batch` 仍未開放指數入口；Web/API、Bot `/analyze`、一次性 `--stocks` 與 GitHub Actions 每日工作流已支持指數。

### 指數自選股配置

`STOCK_LIST` 支持在兩類入口按下列規則混入指數目標：一次性 `--stocks` 與 GitHub Actions 每日工作流（`GITHUB_ACTIONS=true` 無參數運行的 full/stocks-only 模式）。本地 `.env` 或 Docker 無參數默認運行不參與指數分類，`STOCK_LIST` 保持既有股票語義；本地 `.env`/Docker 若想分析指數，請顯式加 `--stocks`（一次性運行）或改用 GitHub Actions 入口。分類判斷先於股票解析：命中已登記指數的顯式形態時按 `market=cn` 的指數 Pipeline 執行；未命中則繼續走股票路徑（`.CSI` 前綴除外，見下文拒絕規則）。判斷髮生在**歸一化之前**，因此必須寫顯式代碼形態，不要依賴裸碼“自動識別”。

**可用的已登記指數代碼形態：**

| 指數家族 | canonical（註冊身份） | display / 等價顯式寫法 | 示例 |
|----------|----------------------|------------------------|------|
| 上海（上證/中證系列 SH 掛牌） | `sh` + 6 位 | `{code}.SH`（另有跨家族 alias 如 `sz399300` → `sh000300`） | `sh000016`、`000016.SH`（上證50） |
| 深圳（深證/國證系列） | `sz` + 6 位 | `{code}.SZ` | `sz399006`、`399006.SZ`（創業板指）；`sz399365`、`399365.SZ`（國證糧食） |
| 中證（CSI 代碼段） | `csi` + 6 位 | `{code}.CSI` | `csi930606`、`930606.CSI`（中證鋼鐵）；`csi930955`、`930955.CSI`（紅利低波100） |
| 美股指數 | 不進 CN 註冊表 | 直接裸碼 | `NDX`（納斯達克100）、`SPX`、`DJI` |

> 完整清單以 `scripts/stock_index_seeds/index_registry.csv` 為準，構建產物 `apps/dsa-web/public/stocks.index.json` 由它生成（`python scripts/generate_index_from_csv.py --index-only`）。SH/SZ 家族的等價後綴與 canonical 等價；`csi` 家族的 canonical 是 `csi930606`，等價顯式寫法是 `930606.CSI`（兩者都收斂到同一指數）。

**規則與正誤示例：**

- **必須寫已登記代碼的顯式形態**（前綴或交易所後綴），不能寫未登記代碼段（會整批拒絕或按股票處理）。大小寫不敏感：`930955.csi`、`CSI930955` 與 `930955.CSI` 等價；同一指數的 canonical 與顯式 alias/display 等價（`csi930606` 與 `930606.CSI`、`sz399365` 與 `399365.SZ` 等價）。寫錯交易所後綴（如 `399365.SH`）會直接報 unsupported（該後綴不接受該代碼基碼），而裸 6 位碼才落回股票路徑。
- **未登記 `.CSI` 目標整批拒絕（僅限 `--stocks` 與 GitHub Actions 入口）**：含未登記 `.CSI`（如 `930956.CSI`、`930606.CSI` 以外的 CSI 段）的 `--stocks` 或 GitHub Actions 每日工作流的 `STOCK_LIST` 會整批拒絕本輪運行，任何一個目標都不執行；本地 `.env`/Docker 無參數默認路徑不參與指數分類，不存在此整批拒絕。Web/API 異步批量只拒絕該目標、同步/單股返回 4xx（見下方 Web/API 指數入口小節的 rejected 列表語義）。寫錯交易所後綴（如 `399365.SH`）同樣直接報 unsupported。
- **裸碼不自動提升為指數**：裸 `399365` / `930606` / `000016` 等 6 位代碼一律按股票路徑處理（契約保持“裸碼默認股票”），只記錄歧義提示。注意：SZ 家族指數（如 `sz399365`）的股票 canonical 與指數 canonical 同為 `sz{code}` 前綴形態，同碼裸股與指數共用同一落庫鍵域，混合自選時請留意下方 canonical 隔離小節的摺疊語義。
- **NDX 等美股指數直接寫裸碼就是正確寫法**：它們走 `us_index_mapping` 的專用美股指數路由，**不要**套用 CN 前綴/後綴（如 `NDX.US`、`usNDX`），加了反而可能落入股票路徑。
- **ETF（如 159934 黃金 ETF、XOP）不進指數註冊表**：ETF 語義走股票路徑，與同數字開頭的指數無關；直接寫裸碼即可，不需要也不支持指數前綴。

**配置示例（`STOCK_LIST`，逗號分隔）：**

```text
600519,sh000016,930606.CSI,sz399365,159934,NDX
```

上面混排了個股（600519 貴州茅臺）、上證指數（sh000016）、CSI 指數（930606.CSI）、SZ 指數（sz399365）、A 股 ETF（159934，走股票路徑）與美股指數（NDX，走美股指數路由）。批量含未登記 `.CSI` 時整批不運行，因此**推薦對每個指數先核對註冊表再配置**。

### 指數與個股 Dashboard canonical 隔離（PR #2312）

已登記指數以 lowercase canonical（`sh000016`/`sz399001`/`csi930955`）寫入歷史存儲；歷史篩選、按代碼刪除、計數與個股欄（stock-bar）聚合統一使用 parser 判型，指數記錄與同碼裸股票（如 `000016`）嚴格隔離，互不折疊。例外：SZ 家族指數（如 `sz399365`）的裸股票 canonical 與指數 canonical 同為 `sz{code}` 前綴形態（裸 `399365` 按股票解析時 canonical 即 `sz399365`），二者天然共鍵；該家族的同碼裸股與指數記錄不在上述隔離範圍，混合自選時按同一鍵摺疊。

- **歷史候選**：指數查詢（`sh000016`、`SH000016`、`000016.SH`、`sz399001`、`csi930955`、`930955.CSI` 等顯式形式）會命中 lowercase canonical、uppercase legacy canonical 與顯式 alias 的既有記錄，但**不會**命中裸同碼股票記錄；裸碼查詢（`000016`/`930955`）也不會命中指數記錄。股票 alias、港股與海外市場的既有等價匹配保持不變。
- **刪除與計數**：`DELETE /api/v1/history/by-code/{code}` 與歷史總數對指數 canonical 收斂全部顯式形態；無記錄時仍返回 `deleted=0`，不引入破壞性 404。
- **個股欄**：同一指數的 `sh000016`/`SH000016`/`000016.SH` 舊記錄在 `/history/stocks` 合併為一行並計數全部顯式形態，且與裸 `000016` 股票行並列存在、互不合並。stock-bar 判型來自持久化 `record.code`，不從 display code 反推。
- **API `stock_code` 輸出 canonical**：歷史列表、歷史詳情與 stock-bar 對已登記指數（含舊 uppercase/顯式 alias 持久化記錄，例如 `SZ399300`、`000300.CSI`）一律輸出 parser canonical（`sh000300`/`csi930955`），前端不再需要從別名猜 canonical。
- **任務 / SSE / API 元數據**：任務列表與 SSE 事件對已提交的 `analysis_target` 暴露可選 `asset_type`（`stock`/`index`），不重新猜測；歷史列表項與 stock-bar 項也追加可選 `asset_type`。不認識該字段的舊客戶端直接忽略，字段可選追加不破壞既有契約。
- **Web Dashboard 身份鍵**：任務/報告/歷史的 `assetType` 優先，且被後端保證為 parser canonical 的代碼只做**大小寫摺疊**（`SH000016`→`sh000016`），**禁止**再用前綴/後綴正則猜 canonical（否則 `000300.CSI` 會被誤猜成 `csi000300`、`sz399300` 被誤當成獨立 canonical，違反註冊表唯一判型真源）；僅 watchlist 原始字符串缺少類型時，才使用已加載 `stocks.index.json` 中 `assetType=index` 行的 canonical/display/顯式 alias **精確命中**（不做先 normalize 再匹配、不用前綴正則猜測；加載期間禁用批量分析，加載失敗或請求超過 10 秒時按既有股票語義 fail-open）。行選中、active task 與完成自動選中均按資產類型分桶，指數行與同碼股票行狀態獨立，完成後自動選中正確的 canonical 指數報告。

### Futu 真實持倉作為分析列表

標準源碼安裝（`pip install -r requirements.txt`）、官方 Docker 鏡像和 Windows/macOS Desktop backend 已默認包含鎖定的 `futu-api==10.8.6808`。僅在使用裁剪過的自定義 Python 環境時，才需要按 [Futu OpenAPI SDK 安裝說明](https://openapi.futunn.com/futu-api-doc/en/intro/intro.html) 手動補裝。啟動並登錄 Futu OpenD 後運行：

```bash
# 僅裁剪過的自定義環境需要執行下一行
pip install "futu-api==10.8.6808"
# 所有標準安裝均可直接運行
python main.py --portfolio futu
```

`--portfolio futu` 固定讀取狀態明確為 `ACTIVE` 的 `REAL` 真實證券賬戶，並在每次分析開始前用 `refresh_cache=True` 刷新持倉；狀態缺失、`N/A`、未知或 `DISABLED` 的賬戶一律拒絕。未設置 `FUTU_ACC_ID` 時會合並所有可用的 `NORMAL`（普通）及 `MASTER`（主）證券賬戶並按代碼去重；設置後只讀取指定的正整數賬戶 ID。根據 [Futu `get_acc_list` 賬戶角色定義](https://openapi.futunn.com/futu-api-doc/trade/get-acc-list.html)，`MASTER` 表示主賬戶而非只讀屬性，馬來西亞 `IPO` 賬戶不屬於本功能的持倉來源並會被跳過。本集成的只讀邊界來自它只調用查詢接口。

只有持倉方向明確為 `LONG`、Futu 靜態類型為 `STOCK` 且數量非零的正股持倉會進入分析；`SHORT`、方向未知、期權、ETF、窩輪、期貨等持倉會被排除。Futu 持倉代碼轉換僅支持滬深 A 股、港股和美股；滬深 B 股、日股及其他 Futu 市場持倉會在日誌中列出代碼並跳過，這不改變手工股票列表的既有市場支持邊界。如果可用賬戶 ID 無效，或 `LONG` 持倉數量無效、非零 `LONG` 持倉代碼無效、靜態類型缺失 / 未知，或已確認的正股代碼無法轉換為當前分析格式，整次持倉導入會明確失敗，不會返回靜默截斷的部分結果。

OpenD 默認地址為 `127.0.0.1:11111`，可用 `FUTU_OPEND_HOST` / `FUTU_OPEND_PORT` 覆蓋。鎖定的 `futu-api==10.8.6808` 網絡層使用 IPv4 socket，因此 `FUTU_OPEND_HOST` 應填寫 IPv4 地址或可解析到 IPv4 的主機名，不支持 `::1` 等 IPv6 地址。在 Docker 容器中，`127.0.0.1` 指向容器自身；OpenD 運行在宿主機時，macOS / Windows 可設置 `FUTU_OPEND_HOST=host.docker.internal`，Linux 需要先為容器增加 `host.docker.internal:host-gateway` 映射後再使用該主機名。跨主機連接會傳輸真實賬戶與持倉信息；[Futu 官方建議實盤連接配置協議加密](https://openapi.futunn.com/futu-api-doc/en/ftapi/protocol.html)。本功能不修改進程級 SDK 加密配置，建議優先讓 OpenD 與本程序同機，或使用受信網絡 / 本機端口轉發。未設置 `FUTU_SECURITY_FIRM` 時只使用 Futu SDK 官方的 `SecurityFirm.NONE` 自動識別一次，不會枚舉多個券商或在部分探測失敗後靜默拼接結果；需要固定券商時可顯式配置該變量。

若同時傳入 `--stocks`，Futu 持倉優先；定時模式會在每輪執行前重新讀取真實持倉，而不是複用啟動時快照。若沒有符合條件的 Futu 持倉，本輪會跳過個股分析且不會回退到 `STOCK_LIST`；已啟用的大盤覆盤仍按原配置執行，大盤覆盤也未請求時不會刷新股票索引或構造分析管線，已啟用的自動回測仍作為獨立步驟執行。單次 CLI 僅在 SDK、OpenD、賬戶發現、持倉讀取或證券分類等持倉解析邊界失敗時返回非零退出碼；持倉解析成功後的交易日曆、分析管線和報告異常仍沿用原分析流程的記錄與容錯語義。已啟動服務與定時調度會記錄持倉導入錯誤並繼續運行。該能力只讀取賬戶和持倉，不執行下單、改單、撤單或交易解鎖。現有分析日誌會記錄本輪股票代碼，但不會記錄賬戶 ID、持倉數量、成本或資金；分享運行日誌前請按需脫敏。

---

## 定時任務配置

### GitHub Actions 定時

編輯 `.github/workflows/00-daily-analysis.yml`:

```yaml
schedule:
  # UTC 時間，北京時間 = UTC + 8
  - cron: '0 10 * * 1-5'   # 週一到週五 18:00（北京時間）
```

常用時間對照：

| 北京時間 | UTC cron 表達式 |
|---------|----------------|
| 09:30 | `'30 1 * * 1-5'` |
| 12:00 | `'0 4 * * 1-5'` |
| 15:00 | `'0 7 * * 1-5'` |
| 18:00 | `'0 10 * * 1-5'` |
| 21:00 | `'0 13 * * 1-5'` |

#### GitHub Actions 非交易日手動運行（Issue #461 / #466）

`00-daily-analysis.yml` 支持兩種控制方式：

- `TRADING_DAY_CHECK_ENABLED`：倉庫級配置（`Settings → Secrets and variables → Actions`），默認 `true`
- `workflow_dispatch.force_run`：手動觸發時的單次開關，默認 `false`

推薦優先級理解：

| 配置組合 | 非交易日行為 |
|---------|-------------|
| `TRADING_DAY_CHECK_ENABLED=true` + `force_run=false` | 跳過執行（默認行為） |
| `TRADING_DAY_CHECK_ENABLED=true` + `force_run=true` | 本次強制執行 |
| `TRADING_DAY_CHECK_ENABLED=false` + `force_run=false` | 始終執行（定時和手動都不檢查交易日） |
| `TRADING_DAY_CHECK_ENABLED=false` + `force_run=true` | 始終執行 |

手動觸發步驟：

1. 打開 `Actions → 每日股票分析 → Run workflow`
2. 選擇 `mode`（`full` / `market-only` / `stocks-only`）
3. 若當天是非交易日且希望仍執行，將 `force_run` 設為 `true`
4. 點擊 `Run workflow`

### 本地定時任務

內建的定時任務調度器支持每天在指定時間（默認 18:00）運行分析。

#### 命令行方式

```bash
# 啟動定時模式（啟動時立即執行一次，隨後每天 18:00 執行）
python main.py --schedule

# 啟動定時模式（啟動時不執行，僅等待下次定時觸發）
python main.py --schedule --no-run-immediately
```

> 說明：定時模式每次觸發前都會重新讀取當前保存的 `STOCK_LIST`。如果同時傳入 `--stocks`，該參數不會鎖定後續計劃執行的股票列表；需要臨時只跑指定股票時，請使用非定時的單次運行命令。
>
> 從 `python main.py --schedule` 或等價純 CLI 調度模式啟動後，WebUI 保存新的 `SCHEDULE_TIME` / `SCHEDULE_TIMES` 會在下一輪調度檢查內自動重綁 daily jobs，無需重啟進程；舊的執行時間不會繼續保留。`python main.py --serve --schedule` 會由 Web/API runtime scheduler 接管定時任務，WebUI/API/Desktop 長運行進程保存 `SCHEDULE_ENABLED`、`SCHEDULE_TIME` 或 `SCHEDULE_TIMES` 後會按當前配置啟停或重建 runtime scheduler。重啟 `python main.py --serve-only` 或 Desktop 時，已啟用的 daily jobs 會自動恢復，但服務啟動本身不會立即執行分析。
>
> Web/API runtime scheduler 的立即執行入口只會在沒有分析任務運行時接受請求；如果已有分析在執行，會返回忙碌狀態而不是假裝排隊成功。

#### 環境變量方式

你也可以通過環境變量配置定時行為（適用於 Docker 或 .env）：

| 變量名 | 說明 | 默認值 | 示例 |
|--------|------|:-------:|:-----:|
| `SCHEDULE_ENABLED` | 是否啟用定時任務 | `false` | `true` |
| `SCHEDULE_TIME` | 每日執行時間 (HH:MM) | `18:00` | `09:30` |
| `SCHEDULE_TIMES` | 多個每日執行時間，逗號分隔；為空時使用 `SCHEDULE_TIME` | 空 | `09:20,12:30,15:10,18:00` |
| `DSA_RUNTIME_SCHEDULER_TIMEOUT_SECONDS` | Web/API runtime scheduler 單次分析硬超時（秒，最小 60 秒） | `2700` | `3600` |
| `DSA_TIMEOUT_PARTIAL_NOTIFY` | **默認開啟（行為變化）**：硬超時後是否推送已落庫個股的部分完成通知；此前超時不推送 | `true` | `false` |
| `SCHEDULE_RUN_IMMEDIATELY` | 定時模式啟動時是否立即運行一次；未顯式設置時沿用 `RUN_IMMEDIATELY` 的運行時覆蓋語義 | `true` | `false` |
| `SCHEDULE_STARTUP_DEDUP` | 定時模式啟動立即執行的當日去重：當天已有成功且覆蓋當前應分析清單的全量分析記錄（日期 + scope=full + 覆蓋面子集判定；標記位於 `DATABASE_PATH` 所在目錄，默認 `data/analysis_run_state.json`）時跳過本次啟動補跑；每日定時任務與手動/API/GitHub Actions 觸發永不去重；標記缺失、損壞、schema 未知或覆蓋不全一律放行執行（fail-open），v1 舊標記同樣放行一次以完成升級；股票清單指紋僅作觀測、不參與判定；大盤覆盤完成度僅記錄、不參與判定 | `true` | `false` |
| `RUN_IMMEDIATELY` | 非定時模式啟動時是否立即運行一次；同時作為未顯式設置 `SCHEDULE_RUN_IMMEDIATELY` 時的 legacy 回退 | `true` | `false` |
| `TRADING_DAY_CHECK_ENABLED` | 交易日檢查：非交易日跳過執行；設為 `false` 可強制執行 | `true` | `false` |

> 超時部分完成排障：通知渠道異常只記 warning（`Partial timeout notification failed`）並跳過推送，**不拋出、不佔用** `status().running`（notify 在分析鎖釋放後的後臺線程）。掃庫 / `src.storage` 導入失敗同樣 fail-open：API 上可能仍是 baseline `timed out after Ns`，或被 enrich 成 `completed=0`（與「確實沒有落庫」無法區分）。運維請搜 `Failed to collect completed analyses after timeout`、`Timeout partial delivery failed open`、`Partial timeout notification failed`。合入後首次發佈請關注通知量，避免默認開啟造成騷擾；可設 `DSA_TIMEOUT_PARTIAL_NOTIFY=false` 關閉推送。

例如在 Docker 中配置：

```bash
# 設置啟動時不立即分析
docker run -e SCHEDULE_ENABLED=true -e SCHEDULE_RUN_IMMEDIATELY=false ...
```

> 兼容說明：如果運行時顯式傳入 `RUN_IMMEDIATELY`，但沒有單獨傳 `SCHEDULE_RUN_IMMEDIATELY`，內置調度模式會繼續繼承前者，避免被 `.env` 中持久化的 `SCHEDULE_RUN_IMMEDIATELY` 舊值反向覆蓋。

> 兼容說明（Issue #1815）：`MARKET_REVIEW_REGION=cn|hk|us|jp|kr|both` 僅擴展大盤覆盤輸入集合；JP/KR 僅供覆盤上下文消費，不會放開 Market Light 告警。
> - `src/config.py`、`src/core/config_registry.py`、`src/services/system_config_service.py` 的改動僅是配置語義擴展，不改 `provider`/`model`/`base_url` 的運行時路由，也不觸發 provider/model/base URL 遷移或清理邏輯。
> - 本輪實際受控配置項：`MARKET_REVIEW_REGION`、`MARKET_REVIEW_COLOR_SCHEME`；`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`VISION_MODEL`、`OPENAI_BASE_URL` 等舊值保持原子 upsert 語義，不會在更新其他字段時被靜默清空或覆蓋。
> - 可核驗證據摘要：官方 provider / Base URL / 模型命名來源沿用 [LLM 配置指南](LLM_CONFIG_GUIDE.md#常用官方文檔來源用於核對預設-provider--base-url--模型命名)，當前運行時依賴窗口沿用 `requirements.txt` 中的 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`；本輪不新增配置遷移腳本或清理分支，保存/導入仍只寫本次提交鍵。`tests/test_system_config_service.py::SystemConfigServiceTestCase::test_update_market_review_region_does_not_trigger_runtime_model_cleanup` 覆蓋只保存 `MARKET_REVIEW_REGION` 時不清空或改寫 `LITELLM_CONFIG`、`LLM_CHANNELS`、`LLM_OPENAI_*`、`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`VISION_MODEL`、`OPENAI_*` 等舊配置。
> - 舊值回退策略：先恢復備份 `MARKET_REVIEW_REGION` 與配置文件即可回到舊邊界，未提交的模型/路由鍵保留原值；必要時 `revert` PR 並按 `.env` 備份完成回退。
> - 可回滾路徑：恢復提交前 `.env` / 配置備份中的 `MARKET_REVIEW_REGION` 與相關運行時變量，或直接 revert 本 PR。

#### 交易日判斷（Issue #373）

默認根據自選股市場（A 股 / 港股 / 美股 / 日股 / 韓股）和 `MARKET_REVIEW_REGION` 判斷是否為交易日：
- 使用 `exchange-calendars` 區分 A 股 / 港股 / 美股 / 日股 / 韓股各自的交易日曆（含節假日）
- 混合持倉時，每隻股票只在其市場開市日分析，休市股票當日跳過
- 全部相關市場均為非交易日時，整體跳過執行（不啟動 pipeline、不發推送）
- 斷點續傳和 `--dry-run` 的“數據已存在”判斷共用同一套“最新可複用交易日”解析邏輯，不再直接使用服務器自然日
- `最新可複用交易日` 會按股票所屬市場的本地時區解析：A 股使用 `Asia/Shanghai`，港股使用 `Asia/Hong_Kong`，美股使用 `America/New_York`，日股使用 `Asia/Tokyo`，韓股使用 `Asia/Seoul`
- 非交易日（週末 / 節假日）運行時，會回退到最近一個交易日檢查本地數據；若該交易日數據已存在，則跳過重複抓取，否則繼續補數
- 交易日盤中或收盤前運行時，會以上一個已完成交易日作為複用目標；交易日收盤後運行時，當日數據已存在則可直接跳過，不存在則繼續抓取
- 覆蓋方式：`TRADING_DAY_CHECK_ENABLED=false` 或 命令行 `--force-run`

#### 市場階段基線（Issue #1386 P0）

P0 只新增內部市場階段推斷基線，不改變現有每日收盤報告、交易日跳過、斷點續傳、API、Web、Bot、Agent 或 GitHub Actions 默認行為。階段推斷用於後續 P1+ 的上下文契約準備；未安裝 `exchange-calendars` 或日曆異常時，階段返回 `unknown`，但現有交易日判斷和最新可複用交易日邏輯仍保持原來的 fail-open 行為。

階段枚舉基於 regular session 語義：

| 階段 | 含義 |
| --- | --- |
| `premarket` | 常規交易時段開盤前；不代表已經獲取盤前擴展時段行情 |
| `intraday` | 常規交易時段內，且不處於午休或臨近收盤窗口 |
| `lunch_break` | 市場日曆提供的午間休市窗口；無午休市場不會進入此階段 |
| `closing_auction` | 臨近收盤啟發式窗口：A 股 3 分鐘、港股 10 分鐘、美股 5 分鐘、臺股 5 分鐘（13:25–13:30）；不代表完整交易所競價制度 |
| `postmarket` | 常規交易時段收盤後；不代表已經獲取盤後擴展時段行情 |
| `non_trading` | 當前市場本地日期不是交易日 |
| `unknown` | 未知市場、日曆不可用或日曆異常，無法可靠推斷階段 |

當前入口現狀：

- 普通個股分析、Agent 分析、Web 手動分析、Bot `/analyze` / `/ask`、schedule、GitHub Actions 仍沿用既有分析路徑和盤後覆盤口徑，不會因為 P0 階段基線自動切換 Prompt 或輸出結構。
- 大盤覆盤仍按 `MARKET_REVIEW_REGION` 與交易日過濾運行，不消費市場階段標籤。
- 跨市場混合自選股應按每個 symbol 自身市場分別推斷階段；聚合報告展示“多市場階段不一致”留給 P1+。

已知問題基線：

- 盤中觸發時，報告仍可能把尚未收盤的日內行情寫成完整交易日覆盤。
- 輸出仍可能偏向“今日走勢覆盤 / 明日關注”，而不是“當前盤中下一步觀察”。
- 實時行情時間戳、數據源、緩存和 stale 狀態還沒有統一進入階段上下文。
- 午間休市、臨近收盤、非交易日強制運行等場景還沒有被 Prompt 和報告結構顯式表達。

P0 不做：不接入 pipeline / Agent / API / Web / Bot，不修改報告 schema，不改告警 technical indicator 的 partial bar 判斷，也不新增配置項。

#### 運行態市場階段上下文（Issue #1386 P1a）

P1a 在普通個股分析 pipeline、legacy Agent context 和 multi-agent `ctx.meta` 中構造並傳遞內部 `market_phase_context`。該上下文包含市場、階段、市場本地日期、最新可複用日線日期、交易日/開市/partial bar 三態標記、開收盤分鐘數 best-effort 估算，以及 `unknown_market`、`calendar_unavailable`、`calendar_error` 等降級 warning code。

P1a 本身不改變 Prompt 文案、API/Web/Bot 參數、報告結構、history/task status 穩定 metadata 或 quote freshness/data quality 語義；普通分析 history snapshot 和 Agent history snapshot 會剝離該運行態字段。後續 P1b 再定義可持久化 metadata 與任務狀態展示契約。

#### 市場階段低敏 Metadata（Issue #1386 P1b）

P1b 將 P1a 的 runtime `market_phase_context` 投影為穩定、低敏、可公開的 `market_phase_summary`，並寫入 `analysis_history.context_snapshot` 頂層。歷史詳情、同步分析響應和 completed `/api/v1/analysis/status/{task_id}` 都通過 `report.meta.market_phase_summary` 返回同一份市場階段元信息；completed 任務狀態不新增 `TaskStatus` 頂層字段，只通過 `status.result.report.meta.market_phase_summary` 間接暴露。

`market_phase_summary` 只包含市場、階段、市場本地時間、session date、effective daily-bar date、交易日/開市/partial-bar 標記、開收盤分鐘數、觸發來源、分析意圖和 warning code。它不暴露完整 `market_phase_context`，也不加入 quote freshness、fallback、stale 或 data_quality scoring 字段。`report.details.analysis_context_pack_overview` 仍表示 #1389 輸入數據塊質量摘要；API 返回的 `details.context_snapshot` 會剝離頂層 `market_phase_summary` 和 `analysis_context_pack_overview`，避免 raw snapshot 重複展示這些穩定公開字段。`SAVE_CONTEXT_SNAPSHOT=false` 時不持久化整份 `analysis_history.context_snapshot`，舊歷史記錄缺少 summary 時字段為空，報告仍正常返回。

P1b 不改 Prompt、不新增 `analysis_phase` 請求參數、不做 Web 階段標籤或頁面展示，也不覆蓋 pending/processing TaskPanel、SSE 進行中事件、Bot、通知、`market_review` 或 P3 盤中數據質量字段。

#### 市場階段 Prompt 注入（Issue #1386 P2-min）

P2-min 開始在已獲得 `market_phase_context` 的分析路徑中，把運行態市場階段渲染為 LLM 可讀的 Prompt 區塊。普通分析、single Agent 和 multi-agent 會在 Prompt 中看到當前階段、市場本地時間、最新可複用完整日線日期以及最小階段約束：盤前不得描述“今日走勢已經發生”，盤中 / 午間 / 臨近收盤需說明最後一根日線可能未完成，盤後保留完整交易日覆盤語義，非交易日或未知階段保持保守表述。

P2-min 仍不新增 API/Web/Bot 參數，不寫入 history/task status/report metadata，不改變報告 JSON schema，也不引入完整 quote freshness、fallback、stale 或 data_quality 契約。Bot/API 直連 Agent 若未經過 P1a pipeline 構建 `market_phase_context`，仍保持舊行為；入口透傳和可見展示留給後續 P4+。

#### 盤中數據包與實時質量控制（Issue #1386 P3）

P3 補齊普通分析主路徑使用的實時行情質量元數據，但仍不新增 `analysis_phase` 參數，不改 API/Web/Bot 階段入口，不改變報告 JSON schema，也不做 #1389 P5 數據質量評分或模型置信度限制。實時 quote 會帶上 `fetched_at`、`provider_timestamp`、`is_stale`、`stale_seconds`、`fallback_from`；其中 `fetched_at` 是系統獲取時間，`provider_timestamp` 只在 provider 真實提供行情時間時填寫。缺少 provider 時間時不會偽造 fresh，`stale_seconds` 和 `is_stale` 保持空值。

整源 fallback 的語義固定為：`source` 保留實際成功的數據源 token，`fallback_from` 記錄本輪失敗的最高優先級整源 token；首選源成功後只從後續源補字段時不寫 `fallback_from`。`AnalysisContextBuilder` 只映射這些上游 artifact，不重新取數、不做質量評分；quote block 狀態按 `STALE > FALLBACK > AVAILABLE` 歸併。盤中實時價覆蓋 `today` 時會標記 `is_partial_bar`、`is_estimated`、`estimated_fields`、`realtime_source` 和 quote 元數據；`daily_bars` block 仍表示 storage 中完整日線窗口，partial/estimated 只進入 technical block。freshness scoring、盤中 cache TTL 分級、Agent 工具級複用和 API/Web 展示留給後續階段。

#### 分析階段入口與任務隊列透傳（Issue #1386 P4a）

P4a 新增 `analysis_phase=auto|premarket|intraday|postmarket` 請求參數，默認 `auto`，用於讓 API 調用方顯式覆蓋本次分析階段。該參數目前接入 `POST /api/v1/analysis/analyze`、異步任務隊列、`AnalysisService`、普通分析 pipeline 和市場階段上下文；Web 前端類型和 API mapper 已承接該字段，但不新增頁面 selector，Bot、schedule、GitHub Actions 和 DB migration 也不在本階段範圍內。

`analysis_phase` 是請求覆蓋值；最終報告階段仍以 `report.meta.market_phase_summary.phase` 為準。異步 accepted response、內存任務 status、任務列表和 SSE payload 會回顯請求階段；歷史 DB fallback 不新增持久化字段，舊記錄仍可能為空。同股不同 phase 仍按同一個股票任務去重，避免併發重複分析。

內部階段上下文構造仍兼容舊參數 `analysis_intent`：僅當 `analysis_phase` 保持 `auto` 時，非 `auto` 的 `analysis_intent` 會被歸一為本次請求階段；外部調用方應優先使用 `analysis_phase`。

`auto` 保持既有交易日曆推斷；非 `auto` 只覆蓋 phase 並重算 `is_trading_day`、`is_market_open_now`、`is_partial_bar`、`minutes_to_open` 和 `minutes_to_close`。覆蓋不會改寫真實 `market_local_time` 或 `effective_daily_bar_date`；如果當前日期不是交易日或日曆不支持對應 session，分鐘字段可以為空。

#### Web 階段標籤展示（Issue #1386 P4b）

P4b 在 Web 端補齊階段可見性，但不新增階段覆蓋 selector。進行中的任務面板只展示 P4a 回顯的請求階段 `analysis_phase`，其中 `auto` 明確顯示為“自動階段”，不偽裝成最終推斷階段。最終報告頁以 `report.meta.market_phase_summary.phase` 展示實際市場階段標籤，並在 `is_partial_bar=true` 時提示“日線未完成”。

數據質量摘要繼續複用 `report.details.analysis_context_pack_overview.data_quality` 和現有 `AnalysisContextSummary`；Web 會在同一報告詳情頁展示階段標籤，並繼續複用低敏數據質量摘要，不暴露完整 `AnalysisContextPack`、Prompt summary、raw payload 或已剝離的 snapshot 內部字段。歷史列表、Bot、schedule、GitHub Actions、Desktop、通知摘要和高級階段覆蓋入口仍為後續工作。

#### AnalysisContextPack Prompt 摘要（Issue #1389 P3）

P3 在普通分析和 Agent 初始上下文中接入 `AnalysisContextPack` 低敏摘要。Pipeline 會用已獲取的行情、日線、趨勢、籌碼、基本面、新聞和市場階段 artifacts 組裝 pack，再把 `analysis_context_pack_summary` 插入 Prompt；在這個新增的 pack 摘要區塊中，LLM 只看到 subject、版本、各數據塊的狀態/來源/warning/missing reason 和新聞結果數，不會通過該區塊看到完整 `news.content`、`trend_result`、籌碼或基本面原始 payload。既有 `news_context`、Agent pre-fetched JSON 和 `enhanced_context` 原始數據通道保持 P3 前行為，不由本摘要替代或脫敏。

P3 當時不新增 API/Web/Bot 參數，不寫入 history/task status/report metadata，不改變報告 JSON schema，也不把完整 pack 暴露到歷史、通知或 Web。Agent 工具級複用 pack 數據和 P5 數據質量評分留給後續階段。

#### Multi-Agent 決策分歧摘要輸入（Issue #1904 P1 plumbing）

Multi-agent 在進入 `DecisionAgent` 前會構造內部低敏 `agent_disagreement_summary`，用於提示前序 Agent opinion 的方向分歧、風險 override 證據、風險 override 是否受當前 `AGENT_RISK_OVERRIDE` 配置啟用，以及非關鍵階段降級信息。該摘要只包含 agent name、signal、confidence、conflict type、decision path hint、低敏 risk control 狀態和 degraded stage marker，不包含 reasoning、raw_data、原始錯誤文本、token 或私密 payload。

該能力當前只是 `DecisionAgent` 的內部 Prompt 輸入管線：摘要寫入運行態 `ctx.meta`，不進入 Agent pre-fetched data，不新增 public API、Web/Desktop 展示、history/task status/report metadata、dashboard schema 或最終解釋字段。`risk_level=high` 只作為風險證據，不會單獨觸發 override；summary 與最終 `_apply_risk_override()` 複用同一套 override 判斷，並尊重 `AGENT_RISK_OVERRIDE=false`。非關鍵降級階段沿用 orchestrator 的 `intel`、`risk` 和 specialist/skill agent 降級契約，避免把單一方向意見誤描述成 multi-agent 共識。#1904 的用戶可見最終解釋輸出仍屬於後續階段。

`AgentResult.runtime_facts` 是內部可選字段，用於保存本次 Orchestrator 運行中已收集的基礎 Agent 意見、degradation event、Pipeline termination 和實際 risk application。degradation event 使用 `DURING_STAGE` 區分 stage 自身失敗，使用 `BEFORE_STAGE` 表示該 stage 因 Pipeline deadline 或 budget guard 未啟動。stage 已完成後觸發 deadline check 時不把該 stage 記錄為 timeout degradation；`pipeline_termination.last_completed_stage` 從 `AgentRunStats.stage_results` 中最後一個真實 `COMPLETED` 結果取得，也可能為空。

結構化 Orchestrator dashboard 按 input preparation、單次 risk application 和 post-risk finalization 的順序處理。post-risk finalization 更新 top-level decision/operation advice、core signal/position advice、battle-plan position strategy，以及 DecisionAgent signal/canonical payload。本階段不處理 dashboard 其他自由文本中的方向性措辭；runtime facts 和 post-risk Agent dashboard 也不表示 Pipeline-final decision，不生成公開 explanation 字段。

Multi-Agent 結果進入 `StockAnalysisPipeline` 後，會繼續完成結構與資金流、市場階段和 daily-market context。系統在每個可能改變公開動作的步驟後使用與 DecisionSignal builder 相同的解析入口刷新八態 action，並按執行順序記錄真實的 `from_action` / `to_action` 轉換。只有調整鏈起點、每個中間動作和最終動作都能由共享規則唯一解析時，系統才基於 `AgentResult.runtime_facts` 確定性生成可選的 `dashboard.agent_disagreement_explanation`。該字段以 `pipeline_start_action` 為調整鏈起點，以 `final_action` 作為唯一權威最終結論；`final_action` 與報告 `action`、歷史記錄 action 和 `DecisionSignal.action` 一致。三態 `decision_type` 不再作為 explanation 的最終結論；`risk_control.post_risk_signal` 僅保留為 Agent 風控階段的統計背景事實。

模型返回的頂層或嵌套同名 explanation 會在共享 Agent dashboard 解析邊界被刪除，最終字段只由 Pipeline 構造。非法 Agent signal 沿用既有策略意見有效性規則從 runtime facts 和公開分歧統計中排除，不會靜默轉換成 `hold`。若自由文本無法唯一解析成八態 action，共享 resolver 保持 fail-closed：報告與歷史記錄保留 `action=None`，不生成 explanation，也不創建 DecisionSignal；Pipeline 不使用 `decision_type` 私自補值。字段在存在 canonical action 時隨 dashboard 一起持久化，並在 DecisionSignal 提取前完成。舊報告、single Agent/非 Agent 路徑和沒有 `runtime_facts` 的兼容調用不要求包含該字段；本階段不增加 Web/Desktop 專屬展示、完整 trace 或 P2-P4 的權重與審計能力。

#### AnalysisContextPack 低敏可見性（Issue #1389 P4）

P4 新增 `report.details.analysis_context_pack_overview`，歷史詳情和 completed `/api/v1/analysis/status/{task_id}` 會從已持久化的 `context_snapshot` 返回同一份低敏 overview；同步分析響應也會讀取本次已落庫的 `analysis_history.context_snapshot` 提取 overview，因此 `SAVE_CONTEXT_SNAPSHOT=false` 時新記錄不保證返回該字段。Web 端報告頁在“策略點位”和“資訊”之後展示默認摺疊的數據塊摘要，摺疊頭部展示可用數、缺失數、非零的其他狀態計數和觸發來源，展開後展示數據塊狀態、來源、warning、missing reason、狀態計數和新聞結果數。API 返回的 `details.context_snapshot` 會剝離頂層 `analysis_context_pack_overview`，避免透明度面板重複展示 raw snapshot。

該 overview 不包含完整 pack、`analysis_context_pack_summary` Prompt 字符串、`items.value`、新聞正文、`trend_result`、籌碼或基本面原始 payload。`SAVE_CONTEXT_SNAPSHOT=false` 時不持久化整份 `analysis_history.context_snapshot`，因此不會從新歷史記錄讀取 overview；舊歷史記錄缺少 overview 時字段為空，報告仍正常返回。本階段不覆蓋 pending/processing TaskPanel、SSE 進行中事件、通知摘要、Bot/Desktop 專屬展示、`market_review` overview 或數據質量評分。

#### AnalysisContextPack 數據質量評分與 Prompt 數據限制（Issue #1389 P5）

P5 在不修改 `PACK_VERSION = "1.0"`、不新增數據源和不改變報告 JSON schema 的前提下，給 `AnalysisContextPack` 增加輕量數據質量評分與模型可讀的數據限制區塊。`ContextFieldStatus` 新增 `fetch_failed`，只表示字段或數據塊本次抓取明確失敗；首版僅把 `fundamental_context.status == "failed"` 映射為 `fetch_failed`，空新聞、未配置搜索、無實時 quote 或 chip 缺失仍按既有 `missing` / `not_supported` 處理。

`DataQuality` 現在包含 `overall_score`、`level`、`block_scores`、`limitations`，並保留舊 `warnings` / `metadata`。評分固定覆蓋 `quote`、`daily_bars`、`technical`、`news`、`fundamentals`、`chip` 六塊，不因輔助塊缺失重歸一化；核心塊降級會在 Prompt 的“數據限制”區塊中要求模型不要輸出高置信度，輔助塊缺失只限制對應分析段落，不應被解釋為利好或利空。該 Prompt 區塊由 `format_analysis_context_pack_prompt_section()` 統一生成，普通分析、single Agent 和 multi-agent 沿用同一低敏 summary，不暴露 raw payload、新聞正文、趨勢原始值、secret、token 或 webhook。

歷史詳情、同步分析響應和 completed 任務狀態繼續只通過 `report.details.analysis_context_pack_overview` 暴露低敏字段；P5 只在該 overview 下新增 `data_quality`，包含 score、level、block_scores 和 limitations，不重複公開 `warnings`。Web 報告頁仍默認摺疊展示數據塊摘要，摺疊頭部新增質量分/等級，展開後展示限制說明和 `fetch_failed` 狀態；`details.context_snapshot` 繼續剝離頂層 `analysis_context_pack_overview`。

#### AnalysisContextPack 文檔、遷移與回滾（Issue #1389 P6）

P6 只做文檔與配置可見性收口，不新增 pack runtime、不新增 pack enable/disable feature flag、不修改 `PACK_VERSION = "1.0"`、不新增 API 參數、不改變報告 JSON schema，也不做數據庫遷移。完整契約、字段狀態、低敏摘要可見性、脫敏邊界、遷移和回滾說明見 [AnalysisContextPack 專題文檔](analysis-context-pack.md)。

`SAVE_CONTEXT_SNAPSHOT` 是既有環境變量，P6 只是把它同步到 `.env.example`、配置註冊表和 Web 設置幫助。默認 `true`；設為 `false` 或 CLI 使用 `--no-context-snapshot` 時，新歷史記錄不再持久化整份 `analysis_history.context_snapshot`，包括 `enhanced_context`、`market_phase_summary`、`analysis_context_pack_overview`、診斷快照和 raw snapshot 字段。該設置不關閉當次 `AnalysisContextPack` 構建，不移除 Prompt 中的低敏 `analysis_context_pack_summary`，也不改變分析結果 JSON schema 或 API 請求參數。

當前沒有運行時 pack 總開關；如果需要關閉 P3-P5 的 pack Prompt 摘要、overview 或數據質量接入，只能通過發佈回滾或代碼回滾完成。舊歷史記錄沒有 `analysis_context_pack_overview` / `data_quality` 時繼續返回空字段，報告讀取保持兼容。

#### 市場結構上下文（Issue #1909）

個股分析現在新增低敏 `market_structure_context`，並通過 `AnalysisReport.details.market_structure` 對歷史詳情、同步分析響應和 completed 任務狀態暴露。該字段採用兩層結構：`market_theme_context` 表示大盤/題材層，包含 A 股行業/概念榜單、活躍題材、領漲行業/概念、題材寬度和數據質量；`stock_market_position` 表示個股位置層，包含個股所屬板塊、主關聯題材、題材階段、個股位置、風險標籤和缺失證據。

首版市場結構由原生服務基於 `DataFetcherManager.get_sector_rankings()`、`get_concept_rankings()` 和 `fundamental_context.belong_boards` 生成，不調用選股引擎。選股中參考 AlphaSift 實現的熱點詳情、發酵路線、成分股和 leader stocks 可作為後續可選數據源，但當前不會被普通個股分析隱式調用。缺少成分股或 leader 證據時，`stock_role` 默認保持 `follower/edge/unknown`，並在 `missing_fields` 中標記 `hotspot_constituents`、`leader_stocks`，避免把普通關聯股誤寫成題材龍頭。

兼容性邊界：`market_structure_context` 中的 provider / model 快照字段（含 `model_used`、`market_structure_context.*.source.provider` 等）僅用於歷史回溯和頁面展示，不構成 LLM provider 路由、`base URL`、`provider/model` 運行時配置輸入；不會觸發 `.env` 配置清理、回寫、遷移或靜默變更。

普通 LLM、single Agent 和 multi-agent prompt 會注入市場結構低敏摘要；DecisionSignal 自動提取會把 `primary_theme`、`theme_phase`、`stock_role`、版本號和風險標籤寫入 metadata，不改變主字段、去重鍵或生命週期規則。Web 報告頁在概覽後展示“市場位置”卡片，分別呈現大盤題材層和個股位置層；舊歷史記錄缺少該字段時不展示。非 A 股市場首版返回 `not_supported`，不影響原有報告。

#### 盤中決策護欄與質量校驗（Issue #1386 P5）

P5 在個股分析報告的 `dashboard.phase_decision` 中追加階段化決策字段：`phase_context`、`action_window`、`immediate_action`、`watch_conditions`、`next_check_time`、`confidence_reason` 和 `data_limitations`。該字段只作為報告 JSON 的向後兼容擴展進入歷史 `raw_result`；不新增 `analysis_phase` API 參數、不改變 Web 階段入口、不新增配置項，也不影響每日收盤覆盤默認行為。

普通分析與 Agent 分析會在保存歷史前複用當次 `market_phase_summary` 和 `analysis_context_pack_overview.data_quality` 執行輕量護欄：核心 quote / daily_bars / technical 數據 stale、fallback、missing、fetch_failed、partial 或 estimated 時，不允許高置信結論；盤前、非交易日或未知階段不得輸出高置信盤中買賣；盤中、午間和臨近收盤會檢查主結論裡的盤後覆盤口吻，並把明顯的"今日收盤後覆盤顯示""明日重点关注"類措辭改為階段安全的觀察/等待表述。護欄只補低敏 `phase_context` 和數據限制，不編造觀察條件或下一次檢查時間；通知摘要、告警、持倉和回測聯動留給後續 P6。

#### 信號歸因分析（Issue #1742）

Issue #1742 在個股分析報告的 `dashboard.signal_attribution` 中新增信號歸因分析字段：`technical_indicators`、`news_sentiment`、`fundamentals`、`market_conditions`（四個貢獻度；有效非零貢獻度歸一化到 100；全零表示無有效信號）、`strongest_bullish_signal` 和 `strongest_bearish_signal`。該字段解釋推薦理由的構成，幫助用戶理解 AI 決策的歸因權重。

信號歸因分析在所有報告渲染路徑中同步展示：
- `generate_dashboard_report()`（默認通知報告）
- `generate_single_stock_report()`（單股推送報告）
- `templates/report_markdown.j2`（Jinja2 模板）
- `HistoryService._generate_single_stock_markdown()`（Web 歷史抽屜）

歸一化函數在 `_parse_response()` 和 `parse_dashboard_json()` 中顯式調用，確保：
- 字符串百分比轉為 int（如 `"35%"` → `35`）
- 負數轉為 0
- 總和≠100 時歸一化為總和=100
- 值裁剪到 [0, 100] 範圍

`signal_attribution` 是可選展示字段（非必填）。缺失不會失敗完整性檢查，也不會寫入 `missing` 列表或觸發補全 prompt；存在時會被歸一化並在支持的報告路徑展示。

#### 告警、持倉和歷史聯動（Issue #1386 P6）

P6 將既有 `market_phase_summary` 與 `analysis_context_pack_overview` 複用到告警、持倉、歷史、回測和通知鏈路，不新增 phase/pack 協議，也不做數據庫遷移。告警觸發記錄仍使用現有 `diagnostics` 文本字段；當 diagnostics 可 JSON 化時，worker 會在 `status=triggered` 記錄中合併寫入 `analysis_visibility.market_phase_summary`、`analysis_visibility.analysis_context_pack_overview` 和 `analysis_visibility.source`。舊純文本 diagnostics 繼續保留原文，Alert API 派生字段為空且 `analysis_visibility_source=legacy_text`。

告警 phase 摘要來自觸發時上下文：symbol 目標按股票市場推斷，`target_scope=market` 直接使用 `cn|hk|us|jp|kr` 市場區域，賬戶級無法唯一定位時允許落為 `unknown`。pack overview 只來自評估器已帶 overview 或最近 30 天曆史 snapshot 的低敏 overview，缺失時返回 `null`，不偽造 pack，不自動觸發輕量 LLM 分析。公開 source 取值為 `alert_trigger_market_context`、`analysis_history_snapshot`、`evaluator_snapshot`、`legacy_text` 或 `null`。

持倉頁新增手動單股分析入口，對應 `POST /api/v1/portfolio/positions/{symbol}/analysis`。請求字段為 `account_id`、`analysis_phase=auto|premarket|intraday|postmarket` 和 `force`；只有當前持倉快照中非零持倉可提交，無持倉返回 404，多賬戶同持一隻股票但未傳 `account_id` 返回 `400 ambiguous_position_account`。該入口沿用異步任務 accepted / duplicate 語義，`force` 隻影響分析刷新，不繞過 in-flight duplicate。後端只把低敏 `portfolio_context` 傳入內部 pipeline 和 context pack 的可選 `portfolio` block；該 block 不參與既有六塊數據質量總分，也不會出現在任務列表或 SSE payload 中。

歷史列表、單股歷史、StockBar 和詳情會從 `context_snapshot` 提取 `market_phase_summary`；舊記錄、缺失 snapshot 或解析失敗返回 `null`。回測結果項增加 `market_phase` 與 `market_phase_summary`，結果列表和 performance/summary 查詢支持 `analysis_phase=premarket|intraday|postmarket|unknown`；統計統一把 `intraday`、`lunch_break`、`closing_auction` 歸入 intraday，把 `non_trading`、缺失和非法值歸入 unknown。帶 phase 過濾的回測查詢會在 repository 層按 SQL 條件批量讀取結果和 snapshot，先 bucket 再分頁，並在 summary diagnostics 中返回 `phase_breakdown` 與 `raw_phase_counts`。

通知摘要複用統一公開格式化 helper，只輸出階段標籤、trigger source、partial-bar warning、數據質量等級和前兩條 limitations；不會輸出 raw context pack、Prompt、新聞正文或持倉敏感明細。Web 告警歷史、持倉、歷史列表、StockBar 和回測頁同步展示階段 badge、質量摘要、phase filter 與 breakdown。

#### 文檔、配置與遷移說明（Issue #1386 P7）

P7 只做盤前 / 盤中 / 盤後分析的用戶可見說明收口，不新增運行時能力、配置項、API 參數、數據庫遷移、Web 階段覆蓋 selector、Bot phase 參數或 GitHub Actions 盤中 workflow。默認每日收盤分析、默認 GitHub Actions 和現有 schedule 行為保持不變。

推薦使用方式：

| 場景 | 推薦用途 | 說明 |
| --- | --- | --- |
| 盤前 | 生成開盤計劃和觀察條件 | 不能把尚未發生的今日走勢寫成事實；重點看上一完整交易日、隔夜信息和開盤觸發條件。 |
| 盤中 / 午間 / 臨近收盤 | 做實時狀態判斷、風險和機會提醒 | 關注當前價、實時行情新鮮度、partial bar、數據限制和下一步觀察條件，不替代盤後完整覆盤。 |
| 盤後 | 保留完整覆盤和次日計劃 | 使用完整交易日語義，是默認每日分析最接近的場景。 |

入口與可見性：

| 入口 | 階段行為 |
| --- | --- |
| `POST /api/v1/analysis/analyze` | 支持 `analysis_phase=auto|premarket|intraday|postmarket`；不傳時默認 `auto`。 |
| Web 主分析 / 重新分析 / 持倉手動分析 | 當前沒有階段覆蓋 selector；前端調用默認傳 `auto`。進行中任務面板展示請求階段，最終報告頁展示最終階段標籤。 |
| Bot / CLI / schedule / 默認 GitHub Actions | 不傳 `analysis_phase`，繼續走 `auto` 推斷；默認收盤分析行為不變。 |
| 歷史 / 回測 / 通知 / 告警 | 只消費公開 `market_phase_summary` 和低敏 `analysis_context_pack_overview`；不公開完整 pack、Prompt summary、新聞正文或持倉敏感明細。 |

`analysis_phase` 是請求覆蓋值，最終報告階段仍以 `report.meta.market_phase_summary.phase` 為準。舊調用不傳 `analysis_phase` 時保持兼容；舊歷史缺少 `market_phase_summary` 或 `analysis_context_pack_overview` 時返回空字段，不影響報告讀取。回測查詢支持 `analysis_phase=premarket|intraday|postmarket|unknown` 過濾，並按 P6 規則把午間和臨近收盤歸入 intraday。

`SAVE_CONTEXT_SNAPSHOT=false` 或 CLI `--no-context-snapshot` 只停止新歷史持久化整份 `context_snapshot`，因此新歷史不再公開 phase summary / pack overview / diagnostics snapshot 等持久化摘要；它不關閉當次 `AnalysisContextPack` 構建，不移除 Prompt 中的低敏 `analysis_context_pack_summary`，也不改變報告 JSON schema。調用方若要臨時回到更接近舊盤後口徑的輸出，可固定傳 `analysis_phase=postmarket`；若要徹底移除 P0-P6 階段/pack runtime 接入，需要發佈回滾或代碼回滾。

#### 使用 Crontab

如果不想使用常駐進程，也可以使用系統的 Cron：

```bash
crontab -e
# 添加：0 18 * * 1-5 cd /path/to/project && python main.py
```

---

## 通知渠道詳細配置

通知渠道矩陣、minimal/advanced key 分層、`--check-notify` 診斷口徑和場景化配置說明見 [通知專題文檔](notifications.md)。

### 企業微信

1. 在企業微信群聊中添加"群機器人"
2. 複製 Webhook URL
3. 設置 `WECHAT_WEBHOOK_URL`

### 飛書

> ⚠️ **關鍵區分**：`FEISHU_WEBHOOK_SECRET`（Webhook 簽名密鑰）和 `FEISHU_APP_SECRET`（飛書應用 Secret）是兩個完全不同的配置，不能互換。

**最小可用配置（無安全限制）：**

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_token
```

**完整步驟：**

1. **在飛書群聊中創建自定義機器人**：
   - 打開目標群聊 → 右上角「群設置」→「群機器人」→「添加機器人」→「自定義機器人」
   - 填寫機器人名稱，複製生成的 **Webhook URL**（格式：`https://open.feishu.cn/open-apis/bot/v2/hook/...`）
2. 設置 `FEISHU_WEBHOOK_URL`（即上一步複製的 URL）。
3. 查看機器人**安全設置**，根據啟用的安全項決定是否需要補充配置：
   - **無額外安全設置**：僅填 `FEISHU_WEBHOOK_URL` 即可。
   - **開啟了「簽名校驗」**：把飛書顯示的 secret 填到 `FEISHU_WEBHOOK_SECRET`。兩端必須同時啟用或同時不填，否則飛書返回簽名校驗失敗。
   - **開啟了「關鍵詞」**：把同一個關鍵詞填到 `FEISHU_WEBHOOK_KEYWORD`；系統會自動在每條消息前補上，無需手動修改報告模板。
   - **開啟了 IP 白名單**：確保當前運行環境的出口 IP 在白名單中（本地/Docker/GitHub Actions 出口 IP 各不相同）。
4. `FEISHU_APP_ID` / `FEISHU_APP_SECRET` 是飛書應用 / Stream Bot / 雲文檔模式專用，不會觸發群 Webhook 推送，不要只用它們替代 `FEISHU_WEBHOOK_URL`。
5. 若已配置 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，再配置 `FEISHU_CHAT_ID`，則可通過飛書 App Bot 直接向指定群聊或用戶推送通知，無需依賴群 Webhook；`FEISHU_RECEIVE_ID_TYPE` 默認 `chat_id`，私聊時改為 `open_id`。該方式走飛書 OpenAPI Bot 會話，與群 Webhook 是兩條獨立鏈路。
6. App Bot 發送路徑複用 `requirements.txt` 中已有的 `lark-oapi>=1.0.0`，標準源碼安裝、Docker、GitHub Actions daily workflow 和桌面構建鏈路都會通過 `pip install -r requirements.txt` 安裝，不需要單獨安裝新庫。參考：[Feishu message create OpenAPI](https://open.feishu.cn/document/server-docs/im-v1/message/create)、[lark-oapi PyPI](https://pypi.org/project/lark-oapi/)、[SDK repo](https://github.com/larksuite/oapi-sdk-python)。

**常見失敗原因：**
- 只填了 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`，既沒有配置 `FEISHU_WEBHOOK_URL`，也沒有配置 App Bot 主動推送所需的 `FEISHU_CHAT_ID`
- 飛書機器人開啟了「簽名校驗」，但 `FEISHU_WEBHOOK_SECRET` 未配置（或誤填為 `FEISHU_APP_SECRET`）
- 飛書機器人開啟了「關鍵詞」，但本地沒有同步配置 `FEISHU_WEBHOOK_KEYWORD`
- 機器人沒有被加入目標群，或群管理員限制了機器人發言
- 飛書側額外配置了 IP 白名單，但當前運行環境 IP 不在白名單中
- 消息內容超長：飛書單條消息有長度限制，系統會自動分段發送；如需在一個文檔內查看完整內容，可配置飛書雲文檔功能（`FEISHU_APP_ID` / `FEISHU_APP_SECRET` / `FEISHU_FOLDER_TOKEN`）

更完整的圖文排查請看 [docs/bot/feishu-bot-config.md](bot/feishu-bot-config.md)。
### Telegram

1. 與 @BotFather 對話創建 Bot
2. 獲取 Bot Token
3. 獲取 Chat ID（可通過 @userinfobot）
4. 設置 `TELEGRAM_BOT_TOKEN` 和 `TELEGRAM_CHAT_ID`
5. (可選) 如需發送到 Topic，設置 `TELEGRAM_MESSAGE_THREAD_ID` (從 Topic 鏈接末尾獲取)

### 郵件

1. 開啟郵箱的 SMTP 服務
2. 獲取授權碼（非登錄密碼）
3. 設置 `EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS`

支持的郵箱：
- QQ 郵箱：smtp.qq.com:465
- 163 郵箱：smtp.163.com:465
- Gmail：smtp.gmail.com:587

**股票分組發往不同郵箱**（Issue #268，可選）：
配置 `STOCK_GROUP_N` 與 `EMAIL_GROUP_N` 可實現不同股票組的報告發送到不同郵箱，例如多人共享分析時互不干擾。`STOCK_LIST` 仍決定本次實際分析的股票集合，`STOCK_GROUP_N` 應寫成 `STOCK_LIST` 的子集；它隻影響郵件收件人，不會改變 Telegram、企業微信、Webhook 等其他渠道收到的完整報告。大盤覆盤會發往所有配置的郵箱。

> GitHub Actions 限制：截至 2026-03-29，倉庫自帶 `00-daily-analysis.yml` 不會自動導入任意編號的 `STOCK_GROUP_N` / `EMAIL_GROUP_N`。因此如果你只在倉庫 Secrets / Variables 中新增這些變量，而沒有修改 workflow 顯式映射，它們不會進入運行進程，看起來就像“分組配置不生效”。

```bash
STOCK_LIST=600519,300750,002594,AAPL
STOCK_GROUP_1=600519,300750
EMAIL_GROUP_1=user1@example.com
STOCK_GROUP_2=002594,AAPL
EMAIL_GROUP_2=user2@example.com
```

### 自定義 Webhook

支持任意 POST JSON 的 Webhook，包括：
- 釘釘機器人
- Discord Webhook
- Slack Webhook
- Bark（iOS 推送）
- 自建服務

設置 `CUSTOM_WEBHOOK_URLS`，多個用逗號分隔。

如需適配 AstrBot、NapCat 或自建服務的特殊 body，可設置 `CUSTOM_WEBHOOK_BODY_TEMPLATE`。這是全局模板，會先於 Bark、Slack、Discord 等 URL 自動識別 payload 生效；如果渲染後不是 JSON object，系統會回退默認 payload。推薦使用 `$content_json` / `$title_json` 避免換行和引號破壞 JSON：

```env
CUSTOM_WEBHOOK_BODY_TEMPLATE={"msg_type":"text","content":$content_json}
```

可用佔位符：`$content_json`、`$content`、`$title_json`、`$title`。其中 `$content` / `$title` 是裸字符串，不做 JSON 轉義；正文含雙引號或換行時可能觸發 fallback。

Docker Compose 部署中，通過 Web 設置頁保存時會把這些應用佔位符寫成 `$$content_json` / `$$title_json` 等形式，避免 Compose 重新部署時將其展開為空；應用運行時會還原為單個 `$`。如果手動編輯 Docker 使用的 `.env`，請同樣使用 `$$content_json` 這類寫法。

Bark 使用全局模板時需顯式寫出 Bark body：

```env
CUSTOM_WEBHOOK_BODY_TEMPLATE={"title":$title_json,"body":$content_json,"group":"stock"}
```

NapCat / OneBot 示例需按實際 endpoint、`user_id` 或 `group_id` 調整：

```env
CUSTOM_WEBHOOK_BODY_TEMPLATE={"user_id":123456,"message":$content_json}
```

### ntfy / Gotify

ntfy 和 Gotify 都是一等通知渠道，只發送文本 / JSON，不參與 Markdown 轉圖片。

ntfy 使用完整 topic endpoint，最後一個 path segment 會作為 topic：

```env
NTFY_URL=https://ntfy.sh/my-topic
NTFY_TOKEN=
```

Gotify 使用 server base URL，系統會自動拼接固定 `/message` API，並通過 `X-Gotify-Key` Header 發送 application token。`GOTIFY_URL` 可包含反向代理 path prefix，但不要包含 `/message`：

```env
GOTIFY_URL=https://gotify.example
GOTIFY_TOKEN=app-token
```

```env
# 實際請求會發送到 https://example.com/gotify/message
GOTIFY_URL=https://example.com/gotify
GOTIFY_TOKEN=app-token
```

`NTFY_URL` 與 `GOTIFY_URL` 的語義不同是兩個服務 API 設計不同導致的刻意選擇：ntfy 由用戶 topic 構成 endpoint，Gotify 的 `/message` 是固定服務 API。

### Discord

Discord 支持兩種方式推送：

長報告會按 Discord 單條 content 2000 字符上限自動分片發送；如果某一片遇到 429 限流，發送器會按 Discord 返回的 `retry_after` 或 `Retry-After` 做有限重試，並繼續嘗試後續分片。`DISCORD_MAX_WORDS` 可調低單片長度，但運行時不會允許超過 2000。

**方式一：Webhook（推薦，簡單）**

1. 在 Discord 頻道設置中創建 Webhook
2. 複製 Webhook URL
3. 配置環境變量：

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
```

**方式二：Bot API（需要更多權限）**

1. 在 [Discord Developer Portal](https://discord.com/developers/applications) 創建應用
2. 創建 Bot 並獲取 Token
3. 邀請 Bot 到服務器
4. 獲取頻道 ID（開發者模式下右鍵頻道複製）
5. 配置環境變量：

```bash
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_MAIN_CHANNEL_ID=your_channel_id
```

如果你要接收 Discord Slash Command / Interaction 回調，而不僅是向 Discord 推送消息，還需要在 Discord Developer Portal 的 `General Information -> Public Key` 複製公鑰並配置：

```bash
DISCORD_INTERACTIONS_PUBLIC_KEY=your_public_key
```

未配置該公鑰時，系統會拒絕所有 Discord 入站 webhook 請求。

### Slack

Slack 支持兩種方式推送，同時配置時優先使用 Bot API，確保文本與圖片發送到同一頻道：

**方式一：Bot API（推薦，支持圖片上傳）**

1. 創建 Slack App：https://api.slack.com/apps → Create New App
2. 添加 Bot Token Scopes：`chat:write`、`files:write`
3. 安裝到工作區並獲取 Bot Token (xoxb-...)
4. 獲取頻道 ID：頻道詳情 → 底部複製頻道 ID
5. 配置環境變量：

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C01234567
```

**方式二：Incoming Webhook（配置簡單，僅文本）**

1. 在 Slack App 管理頁面創建 Incoming Webhook
2. 複製 Webhook URL
3. 配置環境變量：

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx
```

### Pushover（iOS/Android 推送）

[Pushover](https://pushover.net/) 是一個跨平臺的推送服務，支持 iOS 和 Android。

1. 註冊 Pushover 賬號並下載 App
2. 在 [Pushover Dashboard](https://pushover.net/) 獲取 User Key
3. 創建 Application 獲取 API Token
4. 配置環境變量：

```bash
PUSHOVER_USER_KEY=your_user_key
PUSHOVER_API_TOKEN=your_api_token
```

特點：
- 支持 iOS/Android 雙平臺
- 支持通知優先級和聲音設置
- 免費額度足夠個人使用（每月 10,000 條）
- 消息可保留 7 天

### Markdown 轉圖片（可選）

配置 `MARKDOWN_TO_IMAGE_CHANNELS` 可將報告以圖片形式發送至不支持 Markdown 的渠道（telegram, wechat, custom, email, slack）。

**依賴安裝**：

1. **imgkit**：已包含在 `requirements.txt`，執行 `pip install -r requirements.txt` 時會自動安裝
2. **wkhtmltopdf**（默認引擎）：系統級依賴，需手動安裝：
   - **macOS**：`brew install wkhtmltopdf`
   - **Debian/Ubuntu**：`apt install wkhtmltopdf fonts-noto-cjk`（用於正確渲染項目支持的中文和韓文報告）
3. **markdown-to-file**（可選，emoji 支持更好）：`npm i -g markdown-to-file`，並設置 `MD2IMG_ENGINE=markdown-to-file`
4. **Playwright**（可選，適合 Web 服務）：在 `apps/dsa-web` 執行 `npm ci` 和 `npx playwright install chromium`，並設置 `MD2IMG_ENGINE=playwright`

未安裝或安裝失敗時，將自動回退為 Markdown 文本發送。

**單股推送 + 圖片發送**（Issue #455）：

單股推送模式（`SINGLE_STOCK_NOTIFY=true`）下，若希望 Telegram 等渠道以圖片形式推送，需同時配置 `MARKDOWN_TO_IMAGE_CHANNELS=telegram` 並安裝轉圖工具（wkhtmltopdf 或 markdown-to-file）。個股日報彙總同樣支持轉圖，無需額外配置。

**故障排查**：若日誌出現「Markdown 轉圖片失敗，將回退為文本發送」，請檢查 `MARKDOWN_TO_IMAGE_CHANNELS` 配置及轉圖工具是否已正確安裝（`which wkhtmltoimage` 或 `which m2f`）。

---

## 數據源配置

系統默認使用 AkShare（免費），也支持其他數據源：

### AkShare（默認）
- 免費，無需配置
- 數據來源：東方財富爬蟲

### Tushare Pro
- 需要註冊獲取 Token
- 更穩定，數據更全
- 設置 `TUSHARE_TOKEN`

### Baostock
- 免費，無需配置
- 作為備用數據源

### YFinance
- 免費，無需配置
- 支持美股/港股數據
- 美股歷史數據與實時行情均統一使用 YFinance，以避免 akshare 美股復權異常導致的技術指標錯誤

### Longbridge（長橋）
- 美股/港股數據兜底，補充 YFinance 缺失的量比、換手率、PE 等字段
- 新接入推薦使用 Longbridge 官方 OAuth 2.0：client_id 優先使用 `LONGBRIDGE_OAUTH_CLIENT_ID`，留空且沒有 Legacy Access Token 時兼容使用 `LONGBRIDGE_APP_KEY`；先在可交互環境執行 `python scripts/generate_longbridge_oauth_token.py --client-id <client_id>` 生成 SDK token 緩存
- GitHub Actions / Docker 等 headless 環境不能在分析任務裡等待瀏覽器授權；可將本機 `~/.longbridge/openapi/tokens/<client_id>` 文件 base64 後配置為 `LONGBRIDGE_OAUTH_TOKEN_CACHE_B64`
- OAuth 運行時依賴 SDK 提供 `OAuthBuilder` / `Config.from_oauth`；若當前 Linux/Docker 環境只能安裝舊版 SDK，日誌會明確提示並自動跳過 Longbridge，不影響 YFinance / AkShare 兜底
- Legacy API Key 仍兼容：設置 `LONGBRIDGE_APP_KEY`、`LONGBRIDGE_APP_SECRET`、`LONGBRIDGE_ACCESS_TOKEN`；其中 Access Token 是舊版 API Key 憑證，不是 OAuth access token
- 可選設置 `LONGBRIDGE_CONNECTION_COOLDOWN_SECONDS` 控制連接關閉類異常後的冷卻秒數（默認 15）
- 接入點可配 `LONGBRIDGE_HTTP_URL`、`LONGBRIDGE_QUOTE_WS_URL`、`LONGBRIDGE_TRADE_WS_URL`、`LONGBRIDGE_REGION`
- 其餘可選參數見官方 [環境變量說明](https://open.longbridge.com/zh-CN/docs/getting-started#環境變量)
- 僅在 YFinance（美股）或 AkShare（港股）返回數據不完整時自動觸發，不影響 A 股鏈路
- 未配置憑據時不會實例化該可選數據源；若運行時出現連接關閉類異常，會在冷卻期內臨時跳過 Longbridge，避免請求級頻繁重連

### 東財接口頻繁失敗時的處理

若日誌出現 `RemoteDisconnected`、`push2his.eastmoney.com` 連接被關閉等，多為東財限流。建議：

1. 在 `.env` 中設置 `ENABLE_EASTMONEY_PATCH=true`
2. 將 `MAX_WORKERS=1` 降低併發
3. 若已配置 Tushare，可優先使用 Tushare 數據源

---

## 高級功能

### 深度研究的階段預算與超時診斷

`/research` 和 `/api/v1/agent/research` 使用 `AGENT_DEEP_RESEARCH_TIMEOUT` 作為整體研究預算。規劃階段的單次模型調用上限仍為 15 秒，報告合成上限為 120 秒；兩者都會被剩餘整體預算進一步限制。提高整體預算不等於每個階段都能使用全部剩餘時間，SDK 的網絡重試也不代表嚴格的牆鍾終止保證。

階段或 provider 超時會保留階段、實際累計耗時、整體預算和原始原因，不再將階段失敗誤報為整體預算已耗盡。`ResearchResult.timed_out` 繼續表示階段/provider 或整體 deadline 超時，調用方應結合 `error` 判斷；HTTP 研究響應結構不變，失敗時保留已知的 `token_usage`，該值不包含失敗調用未返回的用量。超時仍返回 `success=false`，不會將失敗材料冒充完整報告。

### 港股支持

使用 `hk` 前綴指定港股代碼：

```bash
STOCK_LIST=600519,hk00700,hk01810
```

港股日線會跳過 efinance、pytdx、baostock 等不支持港股日線的數據源，避免把港股代碼錯配到非港股市場；默認改由 AkShare/Tushare/YFinance/Longbridge 等港股路徑繼續兜底。

### ETF 與指數分析

針對指數跟蹤型 ETF 和美股指數（如 VOO、QQQ、SPY、510050、SPX、DJI、IXIC），分析僅關注**指數走勢、跟蹤誤差、市場流動性**，不納入基金管理人/發行方的公司層面風險（訴訟、聲譽、高管變動等）。風險警報與業績預期均基於指數成分股整體表現，避免將基金公司新聞誤判為標的本身利空。詳見 Issue #274。

### 多模型切換

配置多個模型，系統自動切換：

```bash
# Gemini（主力）
GEMINI_API_KEY=xxx
GEMINI_MODEL=gemini-3.6-flash

# OpenAI 兼容（備選）
OPENAI_API_KEY=xxx
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash
# deepseek-chat / deepseek-reasoner 已被官方公告於 2026/07/24 停用，請遷移
```

### 高級模型路由（底層由 LiteLLM 驅動）

詳見 [LLM 配置指南](LLM_CONFIG_GUIDE.md)。默認使用時你只需要理解主模型、備選模型和模型渠道；如果進入這一節，說明你要直接使用底層 [LiteLLM](https://github.com/BerriAI/litellm) 路由能力，無需單獨啟動 Proxy 服務。

**兩層機制**：同一模型多 Key 輪換（Router）與跨模型降級（Fallback）分層獨立，互不干擾。

**多 Key + 跨模型降級配置示例**：

```env
# 主模型：3 個 Gemini Key 輪換，任一 429 時 Router 自動切換下一個 Key
GEMINI_API_KEYS=key1,key2,key3
LITELLM_MODEL=gemini/gemini-3.6-flash

# 跨模型降級：主模型全部 Key 均失敗時，按序嘗試 Claude → GPT
# 需配置對應 API Key：ANTHROPIC_API_KEY、OPENAI_API_KEY
LITELLM_FALLBACK_MODELS=anthropic/claude-sonnet-4-6,openai/gpt-6.1-terra
```

**預期行為**：首次請求用 `key1`；若 429，Router 下次用 `key2`；若 3 個 Key 均不可用，則切換到 Claude，再失敗則切換到 GPT。

> ⚠️ `LITELLM_MODEL` 必須包含 provider 前綴（如 `gemini/`、`anthropic/`、`openai/`），
> 否則系統無法識別應使用哪組 API Key。舊格式的 `GEMINI_MODEL`（無前綴）僅用於未配置 `LITELLM_MODEL` 時的自動推斷。

**依賴說明**：`requirements.txt` 中保留 `openai>=1.0.0`，因 LiteLLM 內部依賴 OpenAI SDK 作為統一接口；顯式保留可確保版本兼容性，用戶無需單獨配置。

**視覺模型（圖片提取股票代碼）**：詳見 [LLM 配置指南 - Vision](LLM_CONFIG_GUIDE.md#擴展功能看圖模型-vision-配置)。

從圖片提取股票代碼（如 `/api/v1/stocks/extract-from-image`）使用統一視覺模型接入，底層採用 LiteLLM Vision 與 OpenAI `image_url` 格式，支持 Gemini、Claude、OpenAI、DeepSeek 等 Vision-capable 模型。返回 `items`（code、name、confidence）及兼容的 `codes` 數組。

> 兼容性說明：`/api/v1/stocks/extract-from-image` 響應在原 `codes` 基礎上新增 `items` 字段。若下游客戶端使用嚴格 JSON Schema 且不接受未知字段，請同步更新 schema。

**智能導入**：除圖片外，還支持 CSV/Excel 文件及剪貼板粘貼（`/api/v1/stocks/parse-import`），自動解析代碼/名稱列，名稱→代碼解析支持本地映射、拼音匹配及 AkShare 在線 fallback。依賴 `pypinyin`（拼音匹配）和 `openpyxl`（Excel 解析），已包含在 `requirements.txt` 中。

- **AkShare 名稱解析緩存**：名稱→代碼解析使用 AkShare 在線 fallback 時，結果緩存 1 小時（TTL），避免頻繁請求；首次調用或緩存過期後會自動刷新。
- **CSV/Excel 列名**：支持 `code`、`股票代码`、`代码`、`name`、`股票名称`、`名称` 等（不區分大小寫）；無表頭時默認第 1 列為代碼、第 2 列為名稱。
- **文本編碼**：CSV 與剪貼板文本支持 UTF-8（含 BOM）和 GBK。
- **常見解析失敗**：文件過大（>2MB）、編碼非 UTF-8/GBK、Excel 工作表為空或損壞、CSV 分隔符/列數不一致時，API 會返回具體錯誤提示。

- **模型優先級**：`VISION_MODEL` > `LITELLM_MODEL` > 根據已有 API Key 推斷（`OPENAI_VISION_MODEL` 已廢棄，請改用 `VISION_MODEL`）
- **Provider 回退**：主模型失敗時，按 `VISION_PROVIDER_PRIORITY`（默認 `gemini,anthropic,openai`）自動切換到下一個可用 provider
- **主模型不支持 Vision 時**：若主模型為 DeepSeek 等非 Vision 模型，可顯式配置 `VISION_MODEL=openai/gpt-6.1-sol` 或 `gemini/gemini-3.6-flash` 供圖片提取使用
- **配置校驗**：若配置了 `VISION_MODEL` 但未配置對應 provider 的 API Key，啟動時會輸出 warning，圖片提取功能將不可用

### 調試模式

```bash
python main.py --debug
```

日誌文件位置：
- 常規日誌：`logs/stock_analysis_YYYYMMDD.log`
- 調試日誌：`logs/stock_analysis_debug_YYYYMMDD.log`

調試日誌默認保留項目自身 DEBUG 信息，但會將 LiteLLM 內部日誌壓低到 `WARNING`，避免流式生成時按 token 寫入大量第三方調試日誌；如需排查 LiteLLM 內部細節，可在 `.env` 中臨時設置 `LITELLM_LOG_LEVEL=DEBUG`。

### SQLite 寫入穩態配置

默認文件型 SQLite 會在連接建立時啟用 `WAL` 並設置 `busy_timeout`，`save_daily_data()` 也已改為按 `(code, date)` 批量原子 upsert，以降低批量更新和併發回寫時的鎖競爭。

如需調整，可在 `.env` 中設置：

| 變量 | 默認值 | 說明 |
|------|-------|------|
| `SQLITE_WAL_ENABLED` | `true` | 文件型 SQLite 是否啟用 `journal_mode=WAL` |
| `SQLITE_BUSY_TIMEOUT_MS` | `5000` | SQLite 等鎖超時（毫秒） |
| `SQLITE_WRITE_RETRY_MAX` | `3` | 遇到 `database is locked` / `database table is locked` 時的最大重試次數 |
| `SQLITE_WRITE_RETRY_BASE_DELAY` | `0.1` | 寫入重試基礎退避時間（秒，按指數退避遞增） |

---

## 分析決策可操作性

個股報告的操作建議會結合支撐位、壓力位、量能/籌碼、主力資金流向和風險事件進行校準，避免僅因單日漲跌或評分跨線在“買入/賣出”之間劇烈切換。若價格處在支撐與壓力之間且資金流不明確，報告會優先給出“持有、震盪觀望、洗盤觀察”等中性可執行建議；只有接近支撐確認、有效突破壓力且量價/資金配合時才給出買入，跌破關鍵支撐或主力資金持續流出時才給出賣出/減倉。
該項調整會影響可操作決策的運行時落盤與提示詞約束鏈路，但不變更 LLM 模型、LiteLLM 路由、Provider/Key 及其兼容邊界，不影響配置保存/清理語義。
兼容性核驗結論：除配置和模型側語義外，該決策穩定性鏈路覆蓋 `src/analyzer.py`、`src/core/pipeline.py`、`src/core/backtest_engine.py`、`src/report_language.py` 及 `src/agent` 決策路徑的運行時行為，建議複核報告決策類型映射與回測入口聯動。
核驗路徑：相關邏輯在上述運行時路徑與對應測試（`tests/test_backtest_engine.py`、`tests/test_analyzer_news_prompt.py`、`tests/test_decision_stability.py`、`tests/test_agent_pipeline.py` 等）中生效；未在 `src/config.py`、`src/report.py`、存儲/持久化鏈路新增配置字段或清理邏輯。

### 建議動作 Taxonomy（#1390 P0）

個股報告在保留 `operation_advice` 自由文本的同時，新增可選 `action` / `action_label` 字段，作為 Web 歷史列表、同股歷史、StockBar 和回測結果行的結構化展示輔助。`decision_type` 仍保持舊的 `buy|hold|sell` 三態統計口徑；`action` 為空時不會改寫既有 `decision_type` 推斷鏈。

| `action` | 常見來源文本 | `decision_type` 橋接 |
| --- | --- | --- |
| `buy` | `strong_buy`、`强烈买入`、`买入`、`布局`、`建仓` | `buy` |
| `add` | `add`、`加仓`、`增持`、`accumulate` | `buy` |
| `hold` | `hold`、`持有`、`持有观察`、`洗盘观察` | `hold` |
| `watch` | `watch`、`观望`、`等待`、`wait` | `hold` |
| `reduce` | `reduce`、`减仓`、`trim` | `sell` |
| `sell` | `sell`、`卖出`、`清仓`、`strong_sell`、`强烈卖出` | `sell` |
| `avoid` | `avoid`、`回避`、`规避`、`不建议买入`、`避免买入`、`do not buy` | `hold` |
| `alert` | `alert`、`风险预警`、`警惕`、`触发告警`、`risk alert` | `hold` |

上表的 `decision_type` 橋接只說明八態 action 與舊三態統計口徑的兼容關係；#1390 P0 不會把 `action` 自動反寫到既有 `decision_type`。若上游顯式 `action` 與 `decision_type` 同時存在但語義不一致，三態統計、回測和舊報表口徑仍以 `decision_type` / 原有推斷鏈為準，`action/action_label` 只承擔結構化展示輔助。

未知或歧義建議不會兜底成 `watch` 或 `hold`，而是返回空 `action/action_label`。Web 歷史卡片、StockBar、同股歷史抽屜和回測結果行會在舊記錄缺少 `action/action_label` 時從 `operation_advice` 做展示級 fallback；該 fallback 隻影響前端標籤，不等價於穩定 API action 或後續信號資產。Web 展示層在同時收到 `action` 與 `action_label` 時，會優先按當前界面語言從 `action` 生成標籤；API 中的 `action_label` 仍按報告語言生成，供非 Web 客戶端或無 `action` 的兼容展示使用。大盤覆盤和其他非個股報告不會產生交易 `action`，只保留 `operation_advice` 文本。`dashboard.phase_decision.immediate_action` 屬於市場階段護欄報告字段，不參與 #1390 P0 的八態 action 派生；最終市場階段仍來自 `report.meta.market_phase_summary.phase`。

#1390 P0 不會把後續信號資產字段平鋪到現有 summary、歷史列表、StockBar 或回測響應。#1390 P1 開始通過獨立 `DecisionSignal` 資源承接 `horizon`、`plan_quality`、`status` 等更細粒度計劃字段，仍不改變既有報告主契約、不回填歷史、不新增配置項。

### 決策信號資產（#1390 P1/P2/P3/P4/P5）

`DecisionSignal` 是獨立後端資源，用於把 AI 建議沉澱為可查詢、可去重、可更新狀態的信號資產。它不替換 `operation_advice`、不擴展 `decision_type=buy|hold|sell`。#1390 P2 開始，普通個股分析和 Agent 個股分析在分析歷史保存成功後，會從最終 `AnalysisResult` best-effort 提取一條 `source_type=analysis` 的信號；顯式 API 或 service 調用仍然保留。

自動提取只消費已生成報告中的結構化字段，不重新解析 Markdown，也不回填舊歷史、不新增配置項、不改變報告主契約。提取失敗、建議動作未知或歧義、非個股報告、無法識別市場時會跳過寫入，不影響分析報告保存。`source_report_id` 使用剛保存的 `AnalysisHistory.id`；`trace_id` 優先使用運行診斷 trace，缺失時降級到 pipeline trace 或 `query_id`；`stock_name` 來自 `AnalysisResult.name`；`trigger_source` 來自運行入口，缺失時為 `system`。

P2 自動提取的市場階段優先讀取保存快照中的 `market_phase_summary.phase`，其次讀取 `AnalysisResult.market_phase_summary.phase`；數據質量優先讀取保存快照中的 `analysis_context_pack_overview.data_quality`，其次讀取 `AnalysisResult.analysis_context_pack_overview.data_quality`。價格計劃複用歷史保存的狙擊點解析規則，從 `dashboard.battle_plan.sniper_points.ideal_buy/secondary_buy/stop_loss/take_profit` 映射到 `entry_low/entry_high/stop_loss/target_price`；只有 `ideal_buy` 時寫入 `entry_low`，只有 `secondary_buy` 時寫入 `entry_high`，兩者同時存在時按有效價格排序為 `entry_low <= entry_high`。缺失止損或目標價只會降低 service 自動計算的 `plan_quality`，不會編造字段。`watch_conditions` 優先讀取 `dashboard.phase_decision.watch_conditions`，沒有時才讀取 `dashboard.battle_plan.action_checklist`；`catalyst_summary` 僅在 `dashboard.intelligence.positive_catalysts` 存在且為列表時寫入。`confidence` 由報告置信等級做保守映射：`高/high=0.8`、`中/medium/mid=0.6`、`低/low=0.4`，原始置信等級保留在 `metadata`。

P3 開始，生命週期由 `DecisionSignalService` 統一補齊：顯式傳入的 `horizon` / `expires_at` 永遠優先；未傳 `horizon` 時，`alert` 或 `premarket/intraday/lunch_break/closing_auction` 默認 `intraday`，`postmarket/non_trading/unknown` 或無階段上下文時默認 `3d`；未傳 `expires_at` 時，`intraday` 優先讀取 `metadata.market_phase_summary.minutes_to_close/minutes_to_open`，無上下文時使用確定性 TTL fallback（A 股 4h、港股 5.5h、美股 6.5h、未知 4h），`1d/3d/5d/10d` 按自然日，`swing/long` 不自動過期。fallback TTL 只是缺少交易日曆上下文時的降級策略，不等價於真實交易所收盤時間。自動提取只把 `market_phase_summary.phase/session_date/minutes_to_open/minutes_to_close` 作為低敏 hint 寫入 `metadata.market_phase_summary`，最終 `horizon/expires_at` 仍由 service 計算。

核心字段包括 `stock_code`、`stock_name`、`market`、`source_type`、`source_agent`、`source_report_id`、`trace_id`、`decision_profile`、`market_phase`、`trigger_source`、`action`、`action_label`、`confidence`、`score`、`horizon`、`entry_low`、`entry_high`、`stop_loss`、`target_price`、`invalidation`、`watch_conditions`、`reason`、`risk_summary`、`catalyst_summary`、`evidence`、`data_quality_summary`、`plan_quality`、`status`、`expires_at`、`created_at`、`updated_at` 和 `metadata`。`action` 複用八態建議動作；`decision_profile` 支持 `conservative|balanced|aggressive`，數據庫 `NULL` 僅表示 legacy/unknown；`market_phase` 複用市場階段枚舉；`source_type` 支持 `analysis|agent|alert|market_review|manual`；`status` 支持 `active|expired|invalidated|closed|archived`；`horizon` 支持 `intraday|1d|3d|5d|10d|swing|long`。

`confidence` 為 `0.0-1.0`，`score` 為 `0-100`，與歷史報告的 `sentiment_score` 解耦。價格計劃字段 `entry_low`、`entry_high`、`stop_loss`、`target_price` 必須是有限正數，且同時傳入 `entry_low` 和 `entry_high` 時要求 `entry_low <= entry_high`。`plan_quality` 支持 `complete|partial|minimal|unknown`：調用方顯式傳入合法值時直接保存；未傳時由 service 計算，入場區間（`entry_low` 或 `entry_high` 任一有值）算 1 項，`stop_loss`、`target_price`、`invalidation`、`watch_conditions` 各算 1 項，滿足 2 項為 `partial`，滿足 4 項及以上為 `complete`，僅有 action/reason 為 `minimal`。

新增 API：

- `POST /api/v1/decision-signals`：創建或按同源鍵去重，返回 `{ item, created }`，HTTP 200。新寫入可省略 `decision_profile` 並默認 `balanced`，也可傳合法 `conservative|balanced|aggressive`；頂層顯式 `null`、空值或非法值會被拒絕。頂層缺失時才 fallback 合法 `metadata.decision_profile`，寫入前會同步 `metadata.decision_profile` 為正式字段值；metadata 省略或顯式 `null` 均按無 metadata 處理，object 會淺複製，非 object 會被拒絕。精確去重鍵為 `(source_report_id, source_type, market, stock_code, decision_profile, action, horizon, market_phase)`；沒有 report 但有 `trace_id` 時使用 `(trace_id, source_type, market, stock_code, decision_profile, action, horizon, market_phase)`；兩者皆無則不去重。精確匹配、relaxed fallback、horizon/phase fill、expired refresh、active invalidation 和 stale backfill invalidation 都遵循 same-profile 語義：`NULL` 只匹配 `NULL`，非空 profile 只匹配相同 profile；expired duplicate refresh 不會改寫 `decision_profile`。精確匹配失敗後，會按同源 + `source_type/market/stock_code/decision_profile/action` 做窄 relaxed fallback，只填補舊記錄為空的 `horizon/market_phase`，且 `horizon` 只有在新值由 service 默認生成時才可填補；顯式不同期限、已有不同階段或不同 profile 仍保留多條。若命中同源 expired 同 profile 記錄，且新請求為 active 並攜帶未來 `expires_at`，會原地刷新該記錄並返回 `created=false`，這次續期按新的 active 激活事件處理。active 新建或 expired 續期後的 bullish 信號（`buy/add`）會把更早同 profile 的 active defensive 信號（`reduce/sell/avoid`）標記為 `invalidated`，反向同理；不同非空 profile 可並存，即使動作相反。active duplicate retry 也會重跑同 profile 失效修復，以恢復上次創建成功但失效寫入失敗的 partial create；普通舊 duplicate/replay 不作為新的激活事件。`hold/watch/alert` 不觸發自動失效。刷新或重複命中都對外返回 `created=false`；本功能不提供併發唯一性保證。
- `GET /api/v1/decision-signals`：分頁查詢，支持 `market`、`stock_code`、`action`、`market_phase`、`decision_profile`、`source_type`、`source_report_id`、`trace_id`、`trigger_source`、`status`、時間範圍、`holding_only`、`account_id`。省略或傳空 `decision_profile` 不加 profile 條件，返回所有 profile；`decision_profile=unknown` 查詢 legacy `NULL` 行；合法 profile 精確匹配。
- `GET /api/v1/decision-signals/{signal_id}`：查詢單條，不存在返回 404。
- `PATCH /api/v1/decision-signals/{signal_id}/status`：更新合法狀態和可選 `metadata`；省略 metadata 時保留原值，顯式 `null` 時清空為 SQL `NULL`，object 時整包替換。正式 `decision_profile` 非 `NULL` 時會覆蓋 metadata 中的衝突 profile；正式字段為 legacy `NULL` 時會移除請求 object 中的 profile key，且不會提升正式字段。`expired/invalidated/closed/archived` 等 terminal 狀態不能直接 PATCH 回 `active`，expired 續期仍只能重新 `POST` active + 未來 `expires_at`。
- `GET /api/v1/decision-signals/latest/{stock_code}`：按股票查詢最新 active 信號，默認 `limit=1`。

讀取入口會懶過期：列表、詳情和 latest 查詢前會把已到 `expires_at` 的 active 信號標為 expired；創建時已過期的 active 信號會直接保存為 expired；同源 expired 信號只能通過重新 `POST` active + 未來 `expires_at` 的方式延展，`PATCH /status` 不接受 `expires_at`。`expired|invalidated|closed|archived` 不會被 PATCH 直接復活，`closed|invalidated|archived` 也不會被 create 路徑復活。相反信號自動失效會合並寫入舊信號 `metadata`：`invalidated_by_signal_id`、`invalidated_reason`、`invalidated_at`、`previous_status`；正式 profile 非 `NULL` 時同步 metadata profile，正式 profile 為 legacy `NULL` 時保留原 metadata profile 且不提升正式字段。舊 metadata JSON 損壞或不是 object 時會替換為失效 metadata 並寫入對應 replacement marker，不阻斷新信號創建。時間字段按 UTC 歸一化為無時區 `datetime` 保存和比較；帶時區輸入會先轉為 UTC 後去掉 `tzinfo`，無時區輸入按 UTC 處理，API 響應繼續返回不帶時區後綴的 ISO 字符串。股票代碼入庫與查詢按 `market` 確定性歸一化：A 股 `600519`、`SH600519`、`600519.SH` 等常見變體按同一代碼匹配；港股 `00700`、`HK00700`、`00700.HK` 按 `HK00700` 匹配；美股 ticker 統一大寫。`holding_only=true` 只讀取 active 賬戶下 `portfolio_positions` 中 `quantity > 0` 的緩存持倉，並按持倉 `(market, stock_code)` 匹配信號，可選 active `account_id`；該查詢不會調用組合 snapshot replay，無緩存時返回空結果，需先通過 portfolio snapshot API 刷新緩存。

`source_report_id` 可為空且不強制校驗歷史記錄存在；刪除歷史記錄時只顯式清理 `source_type=analysis` 且 `source_report_id` 命中實際刪除 ID 的歷史綁定信號，`manual/agent/alert/market_review` 等弱引用信號不會僅因 ID 碰撞被刪除；列表接口支持按 `source_report_id` 和 `trace_id` 做 typed filter。`task_id`、`alert_trigger_id` 等後續關聯字段先放入 `metadata`，P1 不新增獨立列，也不提供 typed filter，後續聯動階段再提升為獨立契約。JSON 字段、長文本字段和展示型短文本字段（`stock_name/source_agent/trigger_source/action_label`）會在寫入前執行信號專用脫敏，覆蓋敏感 key、Bearer、Authorization/Cookie header 或賦值、token-like 字符串、其他敏感賦值、webhook URL、URL userinfo 以及帶敏感 query/fragment 參數的 URL；普通證據 URL 會保留以保證來源可追溯，且長文本不會套用診斷文本的 300 字符截斷。`trace_id` 是同源去重身份字段，若包含會被脫敏的敏感 credential，API 會拒絕請求而不是保存有損 redaction 後的值。

這些接口繼承現有 `/api/v1/*` 管理員鑑權：`ADMIN_AUTH_ENABLED=true` 時必須攜帶有效管理員會話 Cookie；本功能不新增獨立認證方式。

#1390 P4 在 Web 端接入已有 `DecisionSignal` API。#1756 後側邊欄“AI 建議”入口 `/decision-signals` 仍是結構化決策信號的集中查詢入口，默認展示 `status=active` 的信號，並支持按市場、股票代碼、動作、市場階段、來源、來源報告 ID 和狀態篩選；時間線區域新增 profile filter，複用 list API 的 server-side `decision_profile` 查詢，`unknown` 僅用於篩選和展示 legacy `NULL` 行，普通高級列表不新增 profile filter。頁面還提供按股票代碼查詢最新 active 信號的入口。卡片、詳情和時間線展示優先讀取正式 `decision_profile` 字段，只有字段缺失時才 fallback legacy metadata；顯式 `null`、歷史缺失或非法 profile 顯示為 unknown。信號詳情展示動作、風格、置信度/評分、horizon、plan_quality、market_phase、價格計劃、風險、觀察條件、來源報告和數據質量；Web 只允許把信號標記為 `closed`、`invalidated` 或 `archived`，不提供 terminal 狀態恢復為 active。

#1390 P5 新增信號級反饋、後驗評估和統計 sidecar，不擴展 `decision_signals` 主表，也不復用綁定 `analysis_history_id` 的 `BacktestResult`。`decision_signal_feedback` 按 `signal_id` 保存最新 `useful|not_useful` 反饋、可選原因/備註和來源；`decision_signal_outcomes` 按 `(signal_id, horizon, engine_version)` 冪等保存後驗結果，當前 `engine_version=decision-signal-v1`。Outcome 在評估時凍結 `action/market/market_phase/source_type/source_agent/plan_quality/data_quality_level/holding_state` 等統計維度，歷史統計不依賴後續 live join 改寫。刪除歷史報告時，會先找出 `source_type=analysis` 且綁定被刪歷史 ID 的信號，再清理對應 feedback/outcome 子表。

P5 後驗評估只支持日線可驗證的 `1d/3d/5d/10d`，窗口語義是 anchor 後 1/3/5/10 根 `StockDaily` 交易 bar，不復用 `DecisionSignalService._horizon_days()` 的自然日過期語義。`anchor_date` 優先讀取 `metadata.market_phase_summary.session_date`，否則使用 `created_at.date()`；anchor 當日必須存在 `StockDaily.close`，不會回退到前一交易日。動作映射為 `buy/add -> up`、`hold -> not_down`、`reduce/sell/avoid -> not_up`；`watch/alert`、`intraday/swing/long`、缺 anchor 價、forward bars 不足等會寫入 `eval_status=unable` 和明確 `unable_reason`。缺 anchor 價、非法 anchor 價、forward bars 不足、缺/非法窗口收盤價屬於可恢復 unable，後續默認重跑會在數據補齊後重新評估；非方向動作、不支持 horizon 和缺 anchor date 屬於終態 unable，默認保持冪等跳過。自動提取運行時可額外接收 `portfolio_context.quantity`，只把低敏 `holding_state=holding|empty|unknown` 寫入 metadata 供後驗快照使用，不保存數量、賬戶或成本。

P5 在 Web `/decision-signals` 頁面篩選區下方展示當前 outcome engine 的整體統計卡片；詳情抽屜按需讀取該信號 outcomes，並可提交 useful/not useful 反饋。該頁面不新增導航頁，不進入 BacktestPage，也不新增後臺定時任務；後驗計算由 `POST /api/v1/decision-signals/outcomes/run` 顯式觸發。批量運行默認優先推進缺失 outcome 的信號，再重試可恢復 unable，不會讓已完成或終態 unable 的最新信號長期佔滿 `limit`。

#1758 在同一個 `GET /api/v1/decision-signals/outcomes/stats` 響應中追加 `profile_calibration`，按 decision profile、profile + action、profile + horizon、profile + market phase、profile + frozen data quality 和 profile source 返回結構化分組。每個分組獨立要求 `completed >= 30`，不足時只保留 counts，五項描述性指標統一返回 `null`；Web 只展示樣本量和“樣本不足，僅供觀察。”，不排名或推薦風格。命中/未命中率的分母是 `hit + miss`，無法評估率的分母是 total；最大不利波動只從 outcome 已保存的 `start_price/min_low/max_high` 計算，不觸發行情讀取。`decision_profile` 和 metadata-backed `profile_source` 是查詢時關聯信號的當前歸因；action、horizon、market phase、data quality 繼續使用 outcome 凍結值。新 outcome 的 data quality 在 summary 沒有顯式 level 時才 fallback 到規範化的 metadata level，既有 outcome 不會靜默重寫。Web 複用原統計請求和 Card，只提供保守/均衡/進取及按動作/按週期兩個用戶視圖；舊後端缺少新字段時原統計仍可用。完整口徑見 [DecisionSignal 決策信號專題](decision-signals.md)。

持倉頁會把 AI 建議作為非阻斷增強異步加載：組合快照和風險模塊先按原邏輯渲染，隨後按當前快照中的唯一持倉調用 `GET /api/v1/decision-signals/latest/{stock_code}?market=<market>&limit=1` 查詢 latest active 信號；不再通過 `holding_only=true` 通用列表分頁掃描，也不存在固定頁數截斷。單個持倉 latest 查詢失敗時，頁面保留其他已加載信號並顯示可見降級提示；無匹配信號時持倉行顯示空佔位。匹配邏輯複用 Web 端股票代碼等價規則，覆蓋 A 股 `600519/SH600519/600519.SH`、港股 `00700/HK00700/00700.HK` 和美股大小寫 ticker。

#1390 P6 將 `DecisionSignal` 複用到告警、通知和組合風險，不新增表、遷移或配置。真實股票級告警觸發會優先關聯同標的 latest active 信號，並把低敏 `decision_signal_summary` 寫入 `alert_triggers.diagnostics`；沒有 active 信號時，worker 只創建最小 `source_type=alert`、`action=alert` 信號，`trace_id=alert-rule-<hash>` 僅用於同源重試的 best-effort 冪等去重，不覆蓋 active 信號本體，且不寫 `market_phase` 避免跨階段重複。告警通知和分析通知只引用摘要中的 `action/horizon/reason/watch_conditions/risk_summary/source_report_id` 等公開字段，通知失敗不影響 trigger 或信號寫入。`GET /api/v1/portfolio/risk` 追加 `decision_signal_risk` 聚合塊，只統計當前持倉中的 active `sell/reduce/alert` 信號，明確排除 `avoid/buy/add/hold/watch`；信號查詢失敗時風險接口 fail-open，Web 風險區顯示降級狀態。

#1390 P7 的收口文檔見 [DecisionSignal 決策信號專題](decision-signals.md)。#1756 不新增 `DECISION_SIGNAL_*` 配置或運行時開關，但會為 `decision_signals` 增加 nullable `decision_profile` 字段、API 請求/響應字段和 profile-aware index；existing SQLite 只在缺列時 `ALTER TABLE ADD COLUMN`，不會 drop/rebuild 表，也不會刪除舊 index。遷移會冪等創建 profile-aware index，並 row-by-row 防禦解析 `metadata_json`，僅合法 `metadata.decision_profile` 回填，invalid JSON、非 object 或非法 profile 保持 `NULL`。當前回滾方式為 revert 對應代碼。回滾後信號提取和寫入停止，既有報告保存、告警觸發、通知發送和組合風險主流程不依賴信號池繼續運行；歷史 signal、feedback 和 outcome 數據不會自動清理。

普通個股歷史報告詳情不再內嵌展示該報告提取出的 `source_type=analysis` 信號，也不會因打開報告詳情而發起 `source_report_id=<recordId>` 的信號查詢；需要查看結構化 AI 建議時統一進入 `/decision-signals` 頁面篩選來源報告 ID、打開 `/decision-signals?sourceReportId=<recordId>` deep link，或按股票查詢。填寫來源報告 ID 或使用該 URL 參數時，Web 會發起 `source_type=analysis + source_report_id=<recordId>` 的精確查詢，不疊加默認 `status=active` 等其他列表篩選，以保留舊報告 best-effort 懶回填語義。

## 回測功能

回測模塊自動對歷史 AI 分析記錄進行事後驗證，評估分析建議的準確性。

### 工作原理

1. 選取已過冷卻期（默認 14 天）的 `AnalysisHistory` 記錄
2. 獲取分析日之後的日線數據（前向 K 線）
3. 根據操作建議推斷預期方向，與實際走勢對比
4. 評估止盈/止損命中情況，模擬執行收益
5. 彙總為整體和單股兩個維度的表現指標

### 操作建議映射

| 操作建議 | 倉位推斷 | 預期方向 | 勝利條件 |
|---------|---------|---------|---------|
| 買入/加倉/strong buy | long | up | 漲幅 ≥ 中性帶 |
| 賣出/減倉/strong sell | cash | down | 跌幅 ≥ 中性帶 |
| 持有/持有觀察/震盪觀望/洗盤觀察/hold/hold and watch/range-bound watch/shakeout watch | long | not_down | 未顯著下跌 |
| 觀望/等待/wait | cash | flat | 價格在中性帶內 |

### 配置

在 `.env` 中設置以下變量（均有默認值，可選）：

| 變量 | 默認值 | 說明 |
|------|-------|------|
| `BACKTEST_ENABLED` | `true` | 是否在每日分析後自動運行回測 |
| `BACKTEST_EVAL_WINDOW_DAYS` | `10` | 評估窗口（交易日數） |
| `BACKTEST_MIN_AGE_DAYS` | `14` | 僅回測 N 天前的記錄，避免數據不完整 |
| `BACKTEST_ENGINE_VERSION` | `v1` | 引擎版本號，升級邏輯時用於區分結果 |
| `BACKTEST_NEUTRAL_BAND_PCT` | `2.0` | 中性區間閾值（%），±2% 內視為震盪 |

### 自動運行

回測在每日分析流程完成後自動觸發（非阻塞，失敗不影響通知推送）。也可通過 API 手動觸發。

### 評估指標

| 指標 | 說明 |
|------|------|
| `direction_accuracy_pct` | 方向預測準確率（預期方向與實際一致） |
| `win_rate_pct` | 勝率（勝 / (勝+負)，不含中性） |
| `avg_stock_return_pct` | 平均股票收益率 |
| `avg_simulated_return_pct` | 平均模擬執行收益率（含止盈止損退出） |
| `stop_loss_trigger_rate` | 止損觸發率（僅統計配置了止損的記錄） |
| `take_profit_trigger_rate` | 止盈觸發率（僅統計配置了止盈的記錄） |

---

## 本地 WebUI 管理界面

WebUI 與 FastAPI API 服務共用同一服務進程，啟動後可在瀏覽器中完成配置管理、手動分析、任務進度查看、歷史報告、回測、持倉管理和智能導入等操作。認證、雲服務器訪問和 API 調用細節見下方說明。

### FastAPI API 服務

FastAPI 提供 RESTful API 服務，支持配置管理和觸發分析。

### 啟動方式

| 命令 | 說明 |
|------|------|
| `python main.py --serve` | 啟動 API 服務 + 執行一次完整分析 |
| `python main.py --serve-only` | 僅啟動 API 服務；可手動觸發分析，並恢復配置中已啟用的定時任務，但啟動時不立即分析 |

### 功能特性

- 📝 **配置管理** - 查看/修改自選股列表
- 🗂️ **首頁三視圖** - 首頁提供「歷史 / 自選 / 今日」工作區，默認進入歷史視圖；移動端抽屜內三個列表均由各自的內層視口承接縱向觸摸滾動，外層卡片不會截斷手勢，桌面端仍保留卡片邊界裁剪；自選股行可用鼠標或鍵盤打開已確認的最新分析詳情，提示始終跟隨當前的查找中、查找失敗或確認無詳情狀態；任何 stock-bar 請求及完成任務後的數據刷新都會在開始時進入待確認狀態，重新確認或狀態未知期間不會開放舊 stock-bar 或 fallback 報告；自選頁刷新會同時重試列表和詳情狀態，逐股票詳情補查使用固定併發上限，並在刷新或頁面狀態切換時取消已失效批次；支持批量提交全部或僅提交“今日未分析”股票
- 📌 **任務面板摺疊** - 首頁任務面板可摺疊/展開，摺疊後保留 pending/processing 摘要並把更多側欄空間讓給自選股列表；摺疊狀態在當前頁面會話內保持
- 🧭 **界面語言切換** - 登錄態與退出態均支持界面語言快速切換（`zh` / `en`），獨立於 `REPORT_LANGUAGE`，用於靜態 UI 文案與導航骨架
- 🚀 **快速分析** - 通過 API 接口觸發個股分析；首頁也提供“大盤覆盤”按鈕和單次市場選擇器，可在 Docker/server 模式下按服務器默認或臨時選擇的單個/多個市場後臺觸發覆盤
- 🎯 **策略選擇** - 首頁支持顯式選擇分析策略 skill；不傳 `skills` 時按系統默認策略運行，便於保持與歷史行為兼容
- 🧪 **今日狀態/任務刷新防抖** - 首頁「今日」與「自選」通過帶有時區感知的歷史區間判斷併發起分頁歷史查詢；任務完成後由最新一次 stock bar 刷新成功才清除失敗態，避免舊請求亂序覆蓋新狀態導致重複提交
- 🧭 **首次配置提示** - 首頁會讀取只讀配置狀態，缺少 LLM 主渠道、自選股等基礎項時提示缺口並引導進入系統設置
- 📊 **實時進度** - 分析任務狀態實時更新，支持多任務並行；普通分析鏈路在進入 LLM 階段後會優先嘗試 LiteLLM 流式生成，並通過任務 SSE 回灌更細粒度的 `message/progress`
- 🧪 **選股任務可恢復** - 選股實現參考 AlphaSift；頁面提交後臺任務後輪詢快照、候選上下文、LLM 重排和最終增強等階段，切換頁面再返回會恢復當前任務進度或最終結果；熱點榜單刷新可與選股同時進行，詳情在選中題材後按需加載，成分股會並行嘗試東方財富與同花順，也可主動複用 DSA 搜索服務補充近期消息；5 分鐘內重複選股默認複用最近成功快照；每次運行可在分差有界的近分池中生成不同組合，明顯領先候選仍受保護，硬過濾、風險約束和評分不受影響
- 🗂️ **大盤覆盤任務可見性** - 首頁觸發大盤覆盤後會返回 `task_id` 並輪詢 `GET /api/v1/analysis/status/{task_id}`，在進行中/完成/失敗場景給出可見反饋，失敗時直接透出報錯內容
- 🗂️ **市場覆盤歷史獨立入口** - 大盤覆盤歷史通過專用入口與普通個股歷史隔離；建議通過 `stock_code=MARKET` + `report_type=market_review` 直接查詢與回放大盤覆盤記錄
- 🧾 **市場覆盤歷史可複用** - 大盤覆盤任務會持久化到分析歷史，`report_type` 為 `market_review`，可直接通過歷史列表/詳情打開對應 Markdown 或詳情頁，不會重新觸發分析重算
- 🧭 **市場位置卡片** - A 股普通分析報告會展示市場題材層和個股位置層，區分大盤主線、主關聯題材、題材階段、個股位置和缺失證據
- 🧩 **輸入數據塊可見** - 普通分析報告會在歷史詳情、同步響應和 completed 任務狀態中返回低敏 `AnalysisContextPack` overview，Web 報告頁在策略點位和資訊之後默認摺疊展示數據塊狀態、來源、缺失原因和降級摘要
- 💬 **問股主討論對象** - 服務端接受明確代碼或索引中唯一名稱後保存對象；普通追問、刷新、重開和切回會話從服務端恢復。明確切股才更新主對象，比較只擴大本輪範圍，首次比較不任選一隻；報告跳轉只是提示，不自行建立已確認狀態。模型失敗或停止不撤銷已接受的對象。
- 🧠 **會話級 Skill 選擇** - 問股會話會持久化當前 Skill 選擇；刷新或切換會話時恢復各自選擇，新會話繼續使用服務器默認 Skill
- 📈 **回測驗證** - 評估歷史分析準確率，查詢方向勝率與模擬收益
- 🔗 **API 文檔** - 訪問 `/docs` 查看 Swagger UI

### 與本變更相關的產品行為

- Web 語言狀態採用兩層機制：`dsa.uiLanguage`（瀏覽器持久化）與 `REPORT_LANGUAGE`（報告及問股默認輸出）解耦。
  - `dsa.uiLanguage` 只決定 WebUI 文案與導航語言（`zh` / `en`），取值優先級為本地持久化值 -> 瀏覽器語言 -> 默認 `zh`。
  - `REPORT_LANGUAGE` 控制報告文本、股票簡稱本地化、報告頁固定文案，以及未提供 `context.report_language` 的 Agent Chat 回覆（`zh` / `en` / `ko`）。
- 頁面語言切換為用戶體驗增強，不屬於迴歸驗證證據記錄範圍；截圖與命令請按 PR 流程在 PR 描述中單獨維護。
- 本改動僅新增請求級報告語言覆蓋參數，不改變 `provider`/`model`/`base_url` 的配置遷移與清理邏輯。

### API 接口

| 接口 | 方法 | 說明 |
|------|------|------|
| `/api/v1/analysis/analyze` | POST | 觸發股票分析 |
| `/api/v1/analysis/market-review` | POST | 後臺觸發大盤覆盤；請求體可傳 `{"send_notification": true, "region": "cn,us"}`；`region` 僅覆蓋本次請求，與 `main.py --market-review` 與 `bot` 複用同一套 `GeminiAnalyzer/SearchService/NotificationService` 組裝語義 |
| `/api/v1/analysis/tasks` | GET | 查詢任務列表 |
| `/api/v1/analysis/tasks/stream` | GET (SSE) | 訂閱任務實時狀態流；`task_progress` 可選攜帶 `flow_event` 增量運行流事件 |
| `/api/v1/analysis/tasks/{task_id}/flow` | GET | 查詢 active task 的運行流快照 |
| `/api/v1/analysis/status/{task_id}` | GET | 查詢任務狀態 |
| `/api/v1/screening/screen/tasks` | POST | 後臺提交選股任務（需先開啟 `SCREENING_ENABLED`） |
| `/api/v1/screening/screen/tasks/{task_id}` | GET | 查詢選股任務狀態與完成結果 |
| `/api/v1/history` | GET | 查詢分析歷史 |
| `/api/v1/history/{record_id}/share-image` | GET | 生成瀏覽器版歷史報告 PNG 分享圖，需要可用的 `MD2IMG_ENGINE` |
| `/api/v1/history/{record_id}/share-image-html` | GET | 生成供 Electron 桌面端內置 Chromium 截圖的受限分享圖 HTML |
| `/api/v1/history/{record_id}/diagnostics` | GET | 查詢歷史報告運行診斷摘要與脫敏複製文本 |
| `/api/v1/history/{record_id}/flow` | GET | 查詢歷史報告運行流快照，普通個股和 `MARKET/market_review` 大盤覆盤複用同一契約 |
| `/api/v1/decision-signals` | POST | 顯式創建或按同源鍵去重決策信號，返回 `{ item, created }` |
| `/api/v1/decision-signals` | GET | 分頁查詢決策信號，支持股票、市場、動作、階段、風格、來源、狀態、時間範圍和 cache-only 持倉過濾 |
| `/api/v1/decision-signals/outcomes/run` | POST | 顯式觸發信號後驗評估，默認跳過 completed/終態 unable、重算可恢復 unable，`force=true` 重算覆蓋 |
| `/api/v1/decision-signals/outcomes` | GET | 分頁查詢信號後驗結果 |
| `/api/v1/decision-signals/outcomes/stats` | GET | 查詢當前後驗引擎統計，默認排除 archived 信號 |
| `/api/v1/decision-signals/{signal_id}/outcomes` | GET | 查詢單個信號在當前後驗引擎下的結果 |
| `/api/v1/decision-signals/{signal_id}/feedback` | GET | 查詢單個信號的用戶反饋；無反饋時返回 `feedback_value=null` |
| `/api/v1/decision-signals/{signal_id}/feedback` | PUT | 寫入或更新單個信號的 `useful|not_useful` 反饋 |
| `/api/v1/decision-signals/{signal_id}` | GET | 查詢單條決策信號，讀取前執行懶過期 |
| `/api/v1/decision-signals/{signal_id}/status` | PATCH | 更新決策信號狀態和可選 metadata |
| `/api/v1/decision-signals/latest/{stock_code}` | GET | 查詢指定股票最新 active 決策信號 |
| `/api/v1/usage/summary?period=today|month|all` | GET | 按調用類型與模型維度彙總 LLM 調用次數和 Token 用量 |
| `/api/v1/usage/dashboard?period=today|month|all&limit=50` | GET | 返回 Token 用量看板數據：總量、Prompt/Completion 拆分、模型用量、調用類型分佈和最近調用明細；Web 側入口為左側導航“用量” |
| `/api/v1/backtest/run` | POST | 觸發回測 |
| `/api/v1/backtest/results` | GET | 查詢回測結果（分頁） |
| `/api/v1/backtest/performance` | GET | 獲取整體回測表現 |
| `/api/v1/backtest/performance/{code}` | GET | 獲取單股回測表現 |
| `/api/v1/stocks/extract-from-image` | POST | 從圖片提取股票代碼（multipart，超時 60s） |
| `/api/v1/stocks/parse-import` | POST | 解析 CSV/Excel/剪貼板（multipart file 或 JSON `{"text":"..."}`，文件≤2MB，文本≤100KB） |
| `/api/health` | GET | 健康檢查 |
| `/docs` | GET | API Swagger 文檔 |

> 說明：`POST /api/v1/analysis/analyze` 在 `async_mode=false` 時僅支持單隻股票；批量 `stock_codes` 需使用 `async_mode=true`。異步 `202` 響應對單股返回 `task_id`，對批量返回 `accepted` / `duplicates` 彙總結構。
> 說明：`POST /api/v1/analysis/analyze` 支持使用 `skills` 傳入策略 skill ID 列表；若未傳則按服務端默認策略執行。為兼容歷史調用，`strategies` 字段仍作為兼容別名保留。
> 說明：`POST /api/v1/analysis/analyze` 支持 `analysis_phase=auto|premarket|intraday|postmarket`，默認 `auto`。非 `auto` 只覆蓋本次分析階段與派生階段標記，不改寫真實交易日曆時間；accepted response、內存 task status、任務列表和 SSE 會回顯請求階段，最終報告階段以 `report.meta.market_phase_summary.phase` 為準。
> 說明：`POST /api/v1/analysis/analyze` 支持 `report_language=zh|en|ko`，併兼容 `reportLanguage` 作為別名；未傳時回退到全局 `REPORT_LANGUAGE`（或環境中的 `Config.report_language`）。該字段僅影響本次分析的報告文本、`report.meta.report_language` 與持久化展示，不會持久化為運行時配置。
> 說明：Web 側首頁策略下拉為顯式可選策略入口。用戶未手動選擇時不會攜帶 `skills`，與歷史客戶端行為一致；選擇策略後將透傳到該接口並在任務狀態與歷史快照中保留。
> 說明：`POST /api/v1/analysis/market-review` 採用後端與 CLI/Bot 共用的配置路徑（`GeminiAnalyzer(config=...)` 與同樣的搜索/提示詞構造入口）。Provider 兼容路由會優先識別並使用 `litellm_model`、`llm_model_list`，若未配置則回退 legacy `GEMINI_*`、`OPENAI_*`、`ANTHROPIC_*`、`DEEPSEEK_*` 鍵；不會新增/調整 provider、Base URL 或 LiteLLM 路由語義。
> 說明：`POST /api/v1/analysis/market-review` 額外支持 `report_language=zh|en|ko`（支持別名 `reportLanguage`）。未傳時同樣回退到全局 `REPORT_LANGUAGE`。該參數僅影響本次覆盤報告文本與結構化返回字段中的語言相關內容；Bot、schedule、CLI 或按鈕觸發的 `main.py --market-review` 仍沿用全局配置，未新增請求級覆蓋能力。
> 說明：`POST /api/v1/analysis/market-review` 可選傳入長度為 1–64 的字符串字段 `region`，支持 `cn`、`hk`、`us`、`jp`、`kr`、`both` 或逗號分隔的合法非空子集（如 `cn,us`）。請求層會規範大小寫、空格、重複項和市場順序；空字符串、空 token、未知 token、`both` 與其他市場混用會整體返回 4xx，不會部分執行或回退。省略字段時繼續讀取全局 `MARKET_REVIEW_REGION`。
> 說明：首頁市場選擇器只覆蓋本次 Web 觸發，不調用配置讀取/保存接口，也不寫入 LocalStorage；選擇“服務器默認”時請求會省略 `region`，UI 不會用 Web Settings 的 saved/display 值猜測運行時實際市場。後端會在任務提交邊界解析唯一的 canonical 實際執行值；accepted 響應、pending/processing/completed 狀態、任務列表、`task_created`/`task_started`/`task_progress`/`task_completed` SSE、完成態結構化 payload，以及 History 列表項的 `region` 與 `context_snapshot.market_review_region` 都複用該值。長期 `MARKET_REVIEW_REGION` 配置仍保留歷史寬鬆過濾/回退語義，CLI、Bot、schedule 與默認 `cn` 語義不變。
> 說明：`POST /api/v1/analysis/market-review` 是 Web / 桌面端的人工觸發入口，點擊後會直接提交大盤覆盤任務，不會因 `TRADING_DAY_CHECK_ENABLED=true` 或當日相關市場休市而短路跳過；定時任務、GitHub Actions 手動運行和 CLI 默認入口仍遵循交易日檢查，可用 `--force-run` 或 workflow `force_run` 覆蓋。
> 審計依據：優先級與回退語義以 `src/config.py` 的 `Config._load_from_env()` 為準（`LITELLM_CONFIG` > `LLM_CHANNELS` > legacy）。配套迴歸見 `tests/test_llm_channel_config.py`（配置源解析）與 `tests/test_market_review_runtime.py`（共享裝配路徑）。該接口當前僅提供單進程/單機級防重複能力，若為多實例部署需通過外部任務隊列或分佈式鎖補齊全局冪等。
> 說明：`POST /api/v1/analysis/market-review` 觸發後，報告會以 `report_type=market_review` 寫入歷史庫；你可直接查詢 `/api/v1/history` 或 `/api/v1/history/{record_id}` 獲取歷史 Markdown，避免再次觸發分析重算。
> 說明：歷史列表新增 `report_type` 查詢參數；通過 `stock_code=MARKET&report_type=market_review` 可單獨讀取大盤覆盤歷史集合，與普通個股歷史邏輯完全隔離。
> 說明：`POST /api/v1/analysis/market-review` 的任務狀態與歷史持久化都會包含 `market_review_payload`：其中 `region` 是本次實際執行的 canonical 市場字符串，另含 `market_scope`、`color_scheme`、`sections`、`sectors`、`concepts`、`news`、`market_light`、`indices` 等結構化字段；多市場結果按區域保存在 `markets`。Web 端 Markdown 渲染、歷史詳情和分享圖片會複用該結構化字段；若結構化字段為空或僅有部分字段則按字段回退到原始 Markdown。
> 說明：運行流快照接口返回 `lanes/nodes/edges/events/summary` 統一契約。active task 缺少 diagnostics 時返回 skeleton flow；若任務 SSE 已收到真實 `flow_event`，快照會包含最近增量事件。completed history 優先使用 `context_snapshot.diagnostics` 與 `analysis_context_pack_overview` 構建完整拓撲。`cancel_requested/cancelled` 是合法狀態，不會映射為 failed。
> 說明：`market_review_payload` 中的 `breadth` 僅在行情寬度數據真實可用時下發；當美股/港股或接口暫不可用時不下發該字段。前端顯示層需按“字段缺失”降級為“暫無數據”而不是展示 0。
> 說明：該端點若返回 `task_id`，WebUI 會輪詢 `GET /api/v1/analysis/status/{task_id}` 展示狀態。狀態為 `completed` 時給出完成提示（報告已生成並按配置推送），狀態為 `failed` 時在前端錯誤區域顯示 `error` 原因。
> 說明：`GET /api/v1/history/{record_id}/diagnostics` 支持歷史記錄主鍵 ID 或 `query_id`，返回 `normal/degraded/failed/unknown` 摘要、關鍵鏈路組件和可複製的脫敏 `copy_text`；舊報告缺少診斷快照時返回 `unknown`，不影響報告讀取。
> 說明：`GET /api/v1/history` 的列表摘要可按 `stock_code` 分頁查詢同一股票歷史，並返回趨勢判斷、分析摘要、模型名與分析時價格/漲跌幅等可選字段；舊記錄缺少快照字段時返回空值。`created_at` 與 `/api/v1/history/stocks` 的 `last_analysis_time` 使用帶服務器時區偏移的 ISO 8601 時間戳；日期篩選仍按服務器本地日期解釋。Web 報告頁的“歷史趨勢”抽屜複用該接口加載同股歷史。
> 說明：`GET /api/v1/usage/dashboard` 複用 `llm_usage` 審計表，不新增配置項或數據庫遷移。接口僅返回已落庫的調用次數、Prompt/Completion/Total Token 聚合、模型維度用量和最近調用記錄，不推導模型上下文窗口或 provider 元數據。
> 說明（Issue #1520）：列表中的模型名展示字段僅來源於歷史快照中的 `model_used`，僅用於歷史回溯展示，不影響運行時模型模型路由（`litellm_model`、`llm_model_list`）、Provider、Base URL 與配置遷移/清理語義。回退方式為回退本次提交，現網歷史查詢/抽屜/接口鏈路兼容性保持不變。
> 說明：歷史詳情、同步分析響應和 completed 任務狀態會在 `report.details.analysis_context_pack_overview` 返回低敏輸入數據塊 overview；其中同步分析響應依賴本次已持久化的 `analysis_history.context_snapshot`，`SAVE_CONTEXT_SNAPSHOT=false` 時新記錄不保證返回 overview。`details.context_snapshot` 會剝離該頂層字段，不返回完整 `AnalysisContextPack` 或 Prompt summary。
> 問股狀態：`POST /api/v1/agent/chat`、`/chat/stream` 由服務端會話快照確定主對象，不把 `context.stock_code` 當作事實；報告 hint 只有完整 canonical／股票或指數類型一致才複用。detail、accepted 和 non-stream 響應提供 `active_stock_context`（code/name/canonical/type）、`session_state_version`、`session_generation`；消息、顯式 Skill 與股票在同一接受事務提交，執行消費該快照而不回寫股票。明確切股清除舊對象的附帶數據；比較只擴大本輪明確 scope。金融縮寫／交易所片段誤作股票參數仍被真實 scope guard 拒絕，工具名稱仍精確匹配。缺少對象的普通策略問題使用空股票 scope，歧義或無法確認的切股返回普通澄清。`context.report_language` 仍優先於全局 `REPORT_LANGUAGE`。已知 generation 可隨請求發送，衝突在 SSE 返回 `session_state_conflict`、non-stream 返回 409；請刷新後手動重試，不自動重發。舊 API 新字段全缺時 Web 顯示未確認，不從文本推測；部分字段缺失是協議錯誤。舊歷史和非破壞升級／回滾見 [LLM 配置指南](LLM_CONFIG_GUIDE.md#問股會話狀態與升級)。

> Skill 會話狀態：頂層 `skills` 是請求選擇的唯一來源。省略／`null` 沿用已保存選擇，未選擇時使用運行時配置默認；顯式 `[]` 保存清空並使用內置默認，不啟用配置中的非空 Skill。非空列表按現有 catalog 清理去重，混合條目保留有效項，全無效則繼承且不寫空狀態。`context.skills/strategies` 被移除。接受事務同時寫消息、顯式 Skill 與股票，成功才發 accepted；detail 的 `session_state.selected_skill_ids` 仍分別返回未選擇 `null`、清空 `[]` 或已保存列表。Web 區分保存值與待提交草稿；未操作的追問省略選擇，衝突不把草稿冒充已保存。刪除會話同時刪除狀態。
> 說明：`POST /api/v1/backtest/run` 新增 `analysis_date_from` / `analysis_date_to`（`YYYY-MM-DD`）請求參數用於按歷史分析日期篩選候選；若 `analysis_date_from > analysis_date_to`，接口返回 400 `invalid_params`。
> 說明：回測執行成功但無新入庫結果時，`BacktestRunResponse.message` 返回可讀診斷說明，`diagnostics` 返回排查上下文（示例：`empty_reason`、`analysis_date_from`、`analysis_date_to`、`eval_window_days`、`min_age_days`、`limit`）。
> 說明：`GET /api/v1/backtest/results`、`GET /api/v1/backtest/performance`、`GET /api/v1/backtest/performance/{code}` 同步支持 `analysis_date_from`、`analysis_date_to`；不傳時保持歷史行為。

> 兼容性審計證據：
> - 官方來源：LiteLLM OpenAI-compatible provider 文檔 <https://docs.litellm.ai/docs/providers/openai_compatible>；OpenAI Chat API 文檔 <https://platform.openai.com/docs/api-reference/chat/create>；DeepSeek API 文檔 <https://api-docs.deepseek.com/>。
> - 依賴版本：項目約束為 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（見 `requirements.txt`），以上兼容語義迴歸測試在該版本窗口內執行。
> - 可複核測試：
>   - `tests/test_llm_channel_config.py`（配置源優先級與 provider/base url 映射）
>   - `tests/test_market_review_runtime.py`（`build_market_review_runtime` 複用裝配路徑）
>   - `tests/test_analysis_api_contract.py`（`/api/v1/analysis/market-review` 合約與任務狀態鏈路）
> - 回滾/回退：若新路徑有問題，可先恢復歷史 `LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS` 與 legacy `GEMINI_*` / `OPENAI_*` / `ANTHROPIC_*` / `DEEPSEEK_*`，或通過桌面端備份或已啟用管理員鑑權的 Web 端 `POST /api/v1/system/config/import` 回滾並重啟；在運行時級別可暫時清空 `LITELLM_CONFIG` / `LLM_CHANNELS` 觸發 legacy 回退。

> 進度流說明：`GET /api/v1/analysis/tasks/stream` 除 `task_created / task_started / task_completed / task_failed` 外，新增 `task_progress` 事件。普通分析鏈路會在“行情準備 / 新聞檢索 / 上下文整理 / LLM 生成 / 報告保存”等階段持續更新 `progress` 與 `message`。LiteLLM 流式返回僅在服務端累積完整文本，最終 JSON 解析成功後才會持久化歷史報告；若流式在首個 chunk 前不可用，會自動回退到原非流式調用；若已產生部分 chunk 後失敗，系統先嘗試同模型非流式重試，失敗後再按既有主模型->備用模型順序繼續嘗試。  
> 如果任務進度回調異常，主鏈路不會中斷，系統會提升告警為 warning 級別並在服務端日誌中輸出完整異常，便於排查 SSE 推送斷點。
>  
> 說明：該特性屬於運行時 SSE 與回退鏈路細節，優先記錄於完整指南（`full-guide*.md`），不在 `README.md` 中展開詳細行為分支。

**調用示例**：
```bash
# 健康檢查
curl http://127.0.0.1:8000/api/health

# 觸發分析（A股）
curl -X POST http://127.0.0.1:8000/api/v1/analysis/analyze \
  -H 'Content-Type: application/json' \
  -d '{"stock_code": "600519"}'

# 透傳策略（可選）
curl -X POST http://127.0.0.1:8000/api/v1/analysis/analyze \
  -H 'Content-Type: application/json' \
  -d '{"stock_code": "600519", "skills": ["bull_trend", "growth_quality"]}'

# 查詢任務狀態
curl http://127.0.0.1:8000/api/v1/analysis/status/<task_id>

# 查詢今日 LLM 用量
curl "http://127.0.0.1:8000/api/v1/usage/summary?period=today"

# 查詢今日 LLM 用量看板
curl "http://127.0.0.1:8000/api/v1/usage/dashboard?period=today&limit=50"

# 觸發回測（全部股票）
curl -X POST http://127.0.0.1:8000/api/v1/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"force": false}'

# 觸發回測（指定股票）
curl -X POST http://127.0.0.1:8000/api/v1/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"code": "600519", "force": false}'

# 觸發回測（按分析日期範圍）
curl -X POST http://127.0.0.1:8000/api/v1/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"analysis_date_from": "2026-05-01", "analysis_date_to": "2026-05-31", "limit": 100}'

# 觸發回測（指定股票 + 日期範圍 + 強制重跑）
curl -X POST http://127.0.0.1:8000/api/v1/backtest/run \
  -H 'Content-Type: application/json' \
  -d '{"code": "600519", "force": true, "analysis_date_from": "2026-05-01", "analysis_date_to": "2026-05-31"}'

# 查詢整體回測表現
curl http://127.0.0.1:8000/api/v1/backtest/performance

# 查詢單股回測表現
curl http://127.0.0.1:8000/api/v1/backtest/performance/600519

# 分頁查詢回測結果
curl "http://127.0.0.1:8000/api/v1/backtest/results?page=1&limit=20"
```

### 自定義配置

修改默認端口或允許局域網訪問：

```bash
python main.py --serve-only --host 0.0.0.0 --port 8888
```

### 支持的股票代碼格式

| 類型 | 格式 | 示例 |
|------|------|------|
| A股 | 6位數字 | `600519`、`000001`、`300750` |
| 北交所 | 8/4/92 開頭 6 位，支持 `BJ` 前綴或 `.BJ` 後綴 | `920748`、`BJ920493`、`920493.BJ` |
| 港股 | hk + 5位數字 | `hk00700`、`hk09988` |
| 美股 | 1-5 字母（可選 .X 後綴） | `AAPL`、`TSLA`、`BRK.B` |
| 日股 | Yahoo 後綴 `.T` | `7203.T`、`6758.T` |
| 韓股 | Yahoo 後綴 `.KS` / `.KQ` | `005930.KS`、`035720.KQ` |
| 美股指數 | SPX/DJI/IXIC 等 | `SPX`、`DJI`、`NASDAQ`、`VIX` |

### 注意事項

- 瀏覽器訪問：`http://127.0.0.1:8000`（或您配置的端口）
- 在雲服務器上部署後，不知道瀏覽器該輸入什麼地址？請看 [雲服務器 Web 界面訪問指南](deploy-webui-cloud.md)
- 分析完成後自動推送通知到配置的渠道
- 此功能在 GitHub Actions 環境中會自動禁用
- 另見 [openclaw Skill 集成指南](openclaw-skill-integration.md)

---

## 常見問題

### Q: 推送消息被截斷？
A: 企業微信/飛書有消息長度限制，系統已自動分段發送。如需完整內容，可配置飛書雲文檔功能。

### Q: 數據獲取失敗？
A: AkShare 使用爬蟲機制，可能被臨時限流。系統已配置重試機制，一般等待幾分鐘後重試即可。

### Q: 如何添加自選股？
A: 修改 `STOCK_LIST` 環境變量，多個代碼推薦用英文逗號分隔。系統也會識別中文逗號、頓號、分號、空格和換行，並在 Web 設置頁保存或自選增刪後規範為英文逗號。

自選增刪及僅保存 `STOCK_LIST` 時，只熱更新股票列表，保留其他運行時配置和容器環境覆蓋。部分配置保存不會被已有的無關 LLM 渠道或模型選擇錯誤阻斷；修改模型、渠道、路由文件或相關憑據時仍會檢查整個模型依賴關係。凡本次保存會啟用 Agent 路徑的也同樣檢查：把 `AGENT_BACKEND` / `AGENT_GENERATION_BACKEND` 切到 LiteLLM（含 `auto`）、設 `AGENT_MODE=true`、或配置非 `all` 的 `AGENT_SKILLS`——後兩者走普通分析的 Agent 分支，自帶 `LLMToolAdapter`，不受 `AGENT_BACKEND` 決定。僅關閉 `AGENT_MODE`、將 `AGENT_SKILLS` 設為 `all` 或空值、以及無關鍵保存不受 LLM 配置影響。已有的退役 `codex_app_server` 配置可保留，不阻斷無關保存；顯式保存或導入該退役值仍會被拒絕。已有模型錯誤需要另行修正，保存自選成功不代表模型配置有效。

### Q: GitHub Actions 沒有執行？
A: 檢查是否啟用了 Actions，以及 cron 表達式是否正確（注意是 UTC 時間）。

---

更多問題請 [提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues)

## Agent 工具數據緩存與持久化

- `get_daily_history` 會先嘗試複用本地 `stock_daily` 日線緩存；緩存新鮮且至少覆蓋首頁默認的 30 條記錄時，不再重複請求外部數據源。
- 當 Agent 請求的天數多於本地緩存記錄數時，工具會返回實際可用記錄，並通過 `partial_cache=true`、`requested_days`、`actual_records` 標明這是部分緩存命中。
- 緩存缺失或過期時，工具仍會按原邏輯從數據源獲取日線數據；獲取成功後會 best-effort 寫回 `stock_daily`，保存失敗不會阻斷 Agent 回覆。
- `search_stock_news` 與 `search_comprehensive_intel` 成功返回後會 best-effort 寫入 `news_intel`，複用現有 URL / fallback key 去重邏輯。
- `get_realtime_quote` 不復用 `stock_daily` 作為實時行情緩存，也不會把盤中實時行情寫入日線表；如需實時行情緩存，應單獨設計實時行情存儲。

## Agent 事件告警監控

`AGENT_EVENT_MONITOR_ENABLED=true` 後，schedule 模式會按 `AGENT_EVENT_MONITOR_INTERVAL_MINUTES` 運行告警 worker。worker 每輪讀取 Alert API 創建並啟用的持久化規則，同時繼續兼容 `AGENT_EVENT_ALERT_RULES_JSON` 中的 legacy 規則；觸發後仍發送到現有通知渠道。Alert API / Web 持久化規則支持實時價、漲跌幅、成交量、日線技術指標、`watchlist`、`portfolio_holdings`、`portfolio_account`，以及 `market` 大盤紅綠燈目標；legacy JSON 仍僅支持三類基礎規則。

> 兼容與遷移說明：本節記錄當前事件告警規則（含 `price_change_percent`）運行時行為，未變更模型名、provider、Base URL、LiteLLM、`OPENAI_*`、`DEEPSEEK_*`、`GEMINI_*` 等外部模型/API 配置語義。legacy JSON 不會被自動遷移、刪除或改寫；若需回退，刪除或關閉 `AGENT_EVENT_MONITOR_ENABLED` 即可停止後臺告警 worker。

| `alert_type` | 方向字段 | 閾值字段 | 說明 |
| --- | --- | --- | --- |
| `price_cross` | `above` / `below` | `price` | 當前價上破或下破指定價格 |
| `price_change_percent` | `up` / `down` | `change_pct` | 漲跌幅達到指定百分比 |
| `volume_spike` | - | `multiplier` | 最新成交量超過近 20 日均量的指定倍數 |
| `ma_price_cross` | `above` / `below` | `window` | 日線 close 相對 MA(window) 邊緣上穿或下穿 |
| `rsi_threshold` | `above` / `below` | `period`、`threshold` | RSI 邊緣上穿或下穿閾值 |
| `macd_cross` | `bullish_cross` / `bearish_cross` | `fast_period`、`slow_period`、`signal_period` | DIF/DEA 邊緣金叉或死叉 |
| `kdj_cross` | `bullish_cross` / `bearish_cross` | `period`、`k_period`、`d_period` | K/D 邊緣金叉或死叉 |
| `cci_threshold` | `above` / `below` | `period`、`threshold` | CCI 邊緣上穿或下穿閾值 |
| `portfolio_stop_loss` | `mode=near|breach` | - | 賬戶級止損接近或觸發 |
| `portfolio_concentration` | - | - | 賬戶級 symbol 集中度 |
| `portfolio_drawdown` | - | - | 賬戶級最大回撤告警 |
| `portfolio_price_stale` | - | - | 持倉價格 stale 或 missing |
| `market_light_status` | - | `statuses` | 當前大盤紅綠燈狀態命中 `red/yellow` 列表 |
| `market_light_score_drop` | - | `min_drop` | 相比上一交易日 Market Light score 下降達到閾值 |

示例：

```env
AGENT_EVENT_MONITOR_ENABLED=true
AGENT_EVENT_MONITOR_INTERVAL_MINUTES=5
AGENT_EVENT_ALERT_RULES_JSON=[{"stock_code":"600519","alert_type":"price_cross","direction":"above","price":1800},{"stock_code":"300750","alert_type":"price_change_percent","direction":"down","change_pct":3.0},{"stock_code":"000858","alert_type":"volume_spike","multiplier":2.5}]
```

worker 會把 `triggered`、`skipped`、`degraded`、`failed` 寫入 `alert_triggers` 作為評估歷史；正常未觸發不寫歷史。DB 持久化規則的 `triggered` 歷史按 `rule_id + target + data_source + data_timestamp` 對同一數據點做 best-effort 去重，重複命中會複用最早一條觸發記錄，`data_timestamp` 缺失時不去重。真實觸發後會把每個通知渠道的 attempt 寫入 `alert_notifications`，併為 Alert API 創建的持久化規則寫入 `alert_cooldowns` 業務冷卻狀態；若讀取持久化冷卻失敗，worker 會臨時使用進程內 fingerprint 防止 DB 異常期間重複推送。legacy `AGENT_EVENT_ALERT_RULES_JSON` 規則繼續使用進程內 fingerprint 抑制，不寫持久化冷卻；通知基礎設施的 `notification_noise.py` 降噪仍獨立生效。Web 規則列表使用後端返回的 `cooldown_active` 判斷冷卻狀態，避免瀏覽器本地時區解析影響展示。

技術指標規則只使用日線 close 的邊緣觸發，partial bar 處理是服務器本地時區 + 16:00 的啟發式，不做市場日曆精確判定。`watchlist` 每輪刷新 `STOCK_LIST` 後展開，`portfolio_holdings` 從持倉快照的非零持倉按 symbol 去重展開，`portfolio_account` 複用持倉風險服務做賬戶級聚合評估。`market` 規則的 target 僅支持 `cn|hk|us|jp|kr`，使用結構化 `MarketLightSnapshot`；`trade_date` 來自當次 market overview，`data_quality=unavailable` 會跳過觸發，非交易日會被交易日 gate 跳過，`market_light_score_drop` 只比較跨交易日 score。WebUI 的“告警”頁面可以管理持久化規則、執行一次性 dry-run 測試，並查看觸發歷史、通知嘗試結果和只讀冷卻狀態；批量規則的列表冷卻狀態是父規則摘要，子目標冷卻以觸發歷史為準。詳細邊界見 [實時告警中心](alerts.md)。

## 持倉管理說明

### `/portfolio` 頁面可做什麼

- 查看全量持倉或切換到單個賬戶視角。
- 在 `fifo` / `avg` 兩種成本法之間切換，查看快照 KPI、風險摘要和 Top Positions 集中度圖表。
- 直接在 Web 頁面新增賬戶、刪除誤建賬戶，或錄入交易、現金流水、公司行動等事件。
- 通過 CSV 導入持倉記錄，支持先 `dry_run` 預覽，再決定是否正式寫入。
- 在事件列表中按賬戶、日期、方向、代碼等條件篩選，並對單賬戶事件做刪除修正。

### 相關接口

| 接口 | 方法 | 說明 |
|------|------|------|
| `/api/v1/portfolio/snapshot` | GET | 查詢持倉快照 |
| `/api/v1/portfolio/risk` | GET | 查詢風險摘要 |
| `/api/v1/portfolio/trades` | GET | 分頁查詢交易記錄 |
| `/api/v1/portfolio/cash-ledger` | GET | 分頁查詢現金流水 |
| `/api/v1/portfolio/corporate-actions` | GET | 分頁查詢公司行動 |
| `/api/v1/portfolio/imports/csv/brokers` | GET | 查詢內建 CSV 券商解析器 |
| `/api/v1/portfolio/fx/refresh` | POST | 手動刷新匯率緩存 |
| `/api/v1/portfolio/accounts/{account_id}` | DELETE | 刪除/歸檔持倉賬戶 |
| `/api/v1/portfolio/trades/{trade_id}` | DELETE | 刪除交易記錄 |
| `/api/v1/portfolio/cash-ledger/{entry_id}` | DELETE | 刪除現金流水 |
| `/api/v1/portfolio/corporate-actions/{action_id}` | DELETE | 刪除公司行動 |

> 查詢類接口統一支持 `account_id`、`date_from`、`date_to`、`page`、`page_size` 等常見篩選參數；事件列表會返回統一的 `items`、`total`、`page`、`page_size` 結構。

### 使用行為說明

- CSV 導入內建 `huatai`、`citic`、`cmb` 解析器；若券商列表接口失敗，Web 端會自動回退到這些內建選項。
- 導入流程會先把 CSV 解析成標準化記錄，再逐條提交到持倉賬本；遇到忙碌行會計入 `failed_count`，不會因為單行衝突讓整批請求整體失敗。
- 刪除賬戶使用軟刪除語義：默認賬戶列表、快照、風險、錄入入口和事件列表不再顯示該賬戶，但交易、現金流水和公司行動不會被物理清理；如需糾正單條流水，需在賬戶歸檔前使用事件列表裡的刪除修正入口。
- 交易去重優先使用賬戶內唯一的 `trade_uid`，缺失時回退到基於日期、代碼、方向、數量、價格、費用、稅費、幣種的確定性哈希。
- 賣出會先校驗可用數量，超賣返回 `409 portfolio_oversell`；併發寫入衝突時可能返回 `409 portfolio_busy`。
- 持倉快照的 `positions[]` 會返回 `price_source`、`price_date`、`price_stale`、`price_available` 等價格元信息；當天快照默認會先嘗試實時行情，實時價不可用或非正值時再回退到 `as_of` 當天或之前最近的歷史收盤價；傳入 `include_realtime=false` 時會跳過實時行情並直接使用本地歷史收盤價回退路徑，Web 持倉頁用該模式優先渲染持倉列表，避免外部實時行情源變慢時阻塞首屏。歷史 `as_of` 快照不會拉取實時價，也不會再把成本價靜默當作現價；缺價持倉會標記 `price_available=false` 並從市值與未實現盈虧彙總中排除。
- 匯率刷新會先嘗試在線源；若在線獲取失敗，則回退到最近一次緩存並標記 `is_stale=true`，避免快照和風險頁整體不可用。
- 當 `PORTFOLIO_FX_UPDATE_ENABLED=false` 時，手動刷新接口會明確返回“在線刷新已禁用”，頁面不會誤導為“當前沒有可刷新的匯率對”。
- 風險摘要包含集中度、回撤、止損接近度等信息；`sector_concentration` 會優先嘗試按板塊歸類，失敗時降級到 `UNCLASSIFIED`，不會阻斷風險結果返回。成功獲取的所屬板塊會按股票代碼在進程內緩存 24 小時，重複打開持倉頁時不再逐只重新請求數據源；獲取失敗或為空的結果不緩存，下次請求會重試。

### Agent 讀取持倉

- Agent 可通過 `get_portfolio_snapshot` 獲取面向賬戶的緊湊持倉摘要，默認包含精簡風險塊，適合控制 Token 開銷。
- 可選參數包括 `account_id`、`cost_method`、`as_of`、`include_positions`、`include_risk`。
- 若風險塊生成失敗，快照仍會返回；若當前環境未啟用持倉模塊，工具會返回結構化 `not_supported`。
