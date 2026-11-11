<div align="center">

# 📈 股票智能分析系統

[![GitHub stars](https://img.shields.io/github/stars/ZhuLinsen/daily_stock_analysis?style=social)](https://github.com/ZhuLinsen/daily_stock_analysis/stargazers)
[![arXiv](https://img.shields.io/badge/arXiv-2608.26990-b31b1b.svg)](https://arxiv.org/abs/2608.26990)
[![CI](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ZhuLinsen/daily_stock_analysis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Ready-2088FF?logo=github-actions&logoColor=white)](https://github.com/features/actions)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://hub.docker.com/r/zhulinsen/daily_stock_analysis)

<p align="center">
  <img src="https://trendshift.io/api/badge/trendshift/repositories/18527/daily?language=Python" alt="#1 Python Repository Of The Day | Trendshift" width="250" height="55"/>&nbsp;<a href="https://hellogithub.com/repository/ZhuLinsen/daily_stock_analysis" target="_blank"><img src="https://api.hellogithub.com/v1/widgets/recommend.svg?rid=6daa16e405ce46ed97b4a57706aeb29f&claim_uid=pfiJMqhR9uvDGlT&theme=neutral" alt="Featured｜HelloGitHub" width="230" /></a>
</p>

> 🤖 基於 AI 大模型的 A股/港股/美股/日股/韓股/臺股自選股智能分析系統，每日自動分析並推送「決策儀表盤」到企業微信/飛書/Telegram/Discord/Slack/郵箱

[**產品預覽**](#-產品預覽) · [**功能特性**](#-功能特性) · [**快速開始**](#-快速開始) · [**推送效果**](#-推送效果) · [**文檔中心**](docs/INDEX.md) · [**完整指南**](docs/full-guide.md)

簡體中文 | [English](docs/README_EN.md) | [繁體中文](docs/README_CHT.md)

</div>

<details open>
<summary><strong>💖 贊助商 (Sponsors)</strong></summary>
<hr>
<div align="center">
  <p><a href="https://modelflare.dev/sign-up?utm_source=github&amp;utm_campaign=daily_stock_analysis"><img src="./docs/assets/modelflare_banner_zh.png" alt="Modelflare" width="720"></a><br>感謝 <strong>Modelflare</strong> 贊助本項目！由美國 Havenbyte LLC 運營，滿血穩定不摻水，低成本接入 GPT、Claude、Gemini、Grok 及 40+ 圖片/視頻模型。指定 OpenAI 分組提供 <strong>65% / 75% / 85% 每日緩存命中率保障</strong>；單筆充值 <strong>US$20 解鎖 GPT 0.015x</strong>，<strong>US$50 解鎖 Claude 0.03x</strong>。<a href="https://modelflare.dev/sign-up?utm_source=github&amp;utm_campaign=daily_stock_analysis">專屬鏈接註冊</a></p>
  <hr>
  <p>
    <a href="https://serpapi.com/github-daily-stock-analysis" target="_blank"><img src="./docs/assets/serpapi_banner_zh.png" alt="輕鬆抓取搜索引擎上的實時金融新聞數據 - SerpApi" width="300" height="141" style="width: 300px; height: 141px; object-fit: contain;"></a>
  </p>
</div>
</details>


## 🖥️ 產品預覽

<p align="center">
  <img src="docs/assets/readme_workspace_tour_20260510.gif" alt="DSA Web 工作臺演示" width="720">
</p>

## ✨ 功能特性

| 能力 | 覆蓋內容 |
|------|------|
| AI 決策報告 | 核心結論、評分、趨勢、買賣點位、風險警報、催化因素、操作檢查清單 |
| 多市場數據聚合 | 覆蓋 A股、港股、美股、日股、韓股、臺股和 ETF，支持行情、K 線、技術指標、新聞、公告、基本面與報告輔助數據；不同市場的數據源和能力邊界見 [市場支持邊界](docs/market-support.md) |
| Web / 桌面工作臺 | 手動分析、任務進度、歷史報告、完整 Markdown、回測、持倉、配置管理、淺色 / 深色主題 |
| Agent 策略問股 | 多輪追問，支持均線、纏論、波浪、趨勢、熱點、事件、成長、預期等 15 種內置策略，覆蓋 Web/Bot/API |
| 智能導入與補全 | 圖片、CSV/Excel、剪貼板導入；股票代碼/名稱/拼音/別名補全 |
| 自動化與推送 | GitHub Actions、Docker、本地定時任務、FastAPI 服務和企業微信/飛書/Telegram/Discord/Slack/郵件推送 |

> 功能細節、字段契約、基本面 P0 超時語義、交易紀律、數據源優先級、Web/API 行為請看 [完整配置與部署指南](docs/full-guide.md)。

### 技術棧與數據來源

| 類型 | 支持 |
|------|------|
| AI 模型 | [Modelflare](https://modelflare.dev/sign-up?utm_source=github&utm_campaign=daily_stock_analysis)、[AIHubMix](https://inferera.com/?aff=CfMq)、Gemini、OpenAI 兼容、DeepSeek、通義千問、Claude、Ollama 本地模型等 |
| 行情數據 | AkShare、Tushare、Pytdx、Baostock、YFinance、Longbridge |
| 新聞搜索 | [SerpAPI](https://serpapi.com/github-daily-stock-analysis)、[Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC)、[Tavily](https://tavily.com/)、[Bocha](https://open.bocha.cn/)、[Brave](https://brave.com/search/api/)、[MiniMax](https://platform.minimaxi.com/)、SearXNG |
| 社交輿情 | [Stock Sentiment API](https://api.adanos.org/docs)（Reddit / X / Polymarket，僅美股，可選） |

> 項目默認內置 AkShare、Baostock、YFinance 等免費行情源，可零配置運行；免費源受上游限流、接口變動和網絡波動影響，穩定性不保證。長期定時、批量分析或更穩定行情建議配置 Tushare、Longbridge 等 token 型數據源，適用市場、Actions 映射和 fallback 規則見 [數據源配置](docs/full-guide.md#數據源配置)。

## 🚀 快速開始

### 方式一：[GitHub Actions（推薦）](https://www.bilibili.com/video/BV11FEb66EXG/)

> 5 分鐘完成部署，零成本，無需服務器。


#### 1. Fork 本倉庫

點擊右上角 `Fork` 按鈕（順便點個 Star⭐ 支持一下）

#### 2. 配置 Secrets

`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

**AI 模型配置（至少配置一個）**

默認先選一個模型服務商並填寫 API Key；需要多模型、圖片識別、本地模型或高級路由時，再參考 [LLM 配置指南](docs/LLM_CONFIG_GUIDE.md)。

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `MODELFLARE_KEY` | [Modelflare](https://modelflare.dev/sign-up?utm_source=github&utm_campaign=daily_stock_analysis) API Key，低成本接入全球熱門大模型 | **推薦** |
| `AIHUBMIX_KEY` | [AIHubMix](https://inferera.com/?aff=CfMq) API Key，一Key切換使用全系模型，無需科學上網，本項目可享 10% 優惠 | **推薦** |
| `GEMINI_API_KEY` | Google Gemini API Key | 可選 |
| `ANTHROPIC_API_KEY` | Anthropic Claude API Key | 可選 |
| `OPENAI_API_KEY` | OpenAI 兼容 API Key（支持 DeepSeek、通義千問等） | 可選 |
| `OPENAI_BASE_URL` / `OPENAI_MODEL` | 使用 OpenAI 兼容服務時填寫 | 可選 |

> Ollama 更適合本地 / Docker 部署，GitHub Actions 推薦使用雲端 API。

**通知渠道配置（至少配置一個）**

| Secret 名稱 | 說明 |
|------------|------|
| `WECHAT_WEBHOOK_URL` | 企業微信機器人 |
| `FEISHU_WEBHOOK_URL` | 飛書機器人 |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram |
| `DISCORD_WEBHOOK_URL` | Discord Webhook |
| `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` | Slack Bot |
| `EMAIL_SENDER` + `EMAIL_PASSWORD` | 郵件推送 |

更多渠道、簽名校驗、分組郵件、Markdown 轉圖片等配置見 [通知渠道詳細配置](docs/full-guide.md#通知渠道詳細配置)。

**自選股配置（必填）**

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `STOCK_LIST` | 自選股代碼，如 `600519,hk00700,AAPL,7203.T,005930.KS,2330.TW`；已登記指數顯式代碼（如 `sh000016`、`930606.CSI`）經一次性 `--stocks` 或 GitHub Actions 入口支持，規則見 [指數自選股配置](docs/full-guide.md#指數自選股配置) | ✅ |

**新聞源配置（推薦）**

新聞源會顯著影響輿情、公告、事件和催化因素質量，建議至少配置一個搜索服務。

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `SERPAPI_API_KEYS` | [SerpAPI](https://serpapi.com/github-daily-stock-analysis)：搜索引擎結果補強，適合實時金融新聞 | **推薦** |
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC) 搜索 API Key，可與其模型網關共用 | 可選 |
| `TAVILY_API_KEYS` | [Tavily](https://tavily.com/)：通用新聞搜索 API | 可選 |
| `BOCHA_API_KEYS` | [博查搜索](https://open.bocha.cn/)：中文搜索優化，支持 AI 摘要 | 可選 |
| `BRAVE_API_KEYS` | [Brave Search](https://brave.com/search/api/)：隱私優先，美股資訊補強 | 可選 |
| `MINIMAX_API_KEYS` | [MiniMax](https://platform.minimaxi.com/)：結構化搜索結果 | 可選 |
| `SEARXNG_BASE_URLS` | SearXNG 自建實例：無配額兜底，適合私有部署 | 可選 |

更多搜索源、社交輿情和降級規則見 [搜索服務配置](docs/full-guide.md#搜索服務配置)。

**行情數據源配置（可選）**

> 默認使用 AkShare、Baostock、YFinance 等免費數據源，日誌中"未配置"的提示不影響運行。
> 如需更穩定的行情，可按市場配置以下 Secret：

| Secret 名稱 | 適用市場 | 說明 |
|------------|:--------:|------|
| `TUSHARE_TOKEN` | A 股 | 提升歷史行情穩定性 |
| `LONGBRIDGE_OAUTH_CLIENT_ID` + `LONGBRIDGE_OAUTH_TOKEN_CACHE_B64` | 港股/美股 | 補齊量比、換手率、PE 等字段 |

> 詳見 [數據源配置](docs/full-guide.md#數據源配置)。

#### 3. 啟用 Actions

`Actions` 標籤 → `I understand my workflows, go ahead and enable them`

#### 4. 手動測試

`Actions` → `每日股票分析` → `Run workflow` → `Run workflow`

#### 完成

默認每個**工作日 18:00（北京時間）**自動執行，也可手動觸發。默認非交易日（含 A/H/US 節假日）不執行；強制運行、交易日檢查、斷點續傳等規則見 [完整指南](docs/full-guide.md#定時任務配置)。

### 方式二：[客戶端配置教程](https://www.bilibili.com/video/BV11FEb66Eyr/) / 本地運行 / Docker 部署

```bash
# 克隆項目
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git && cd daily_stock_analysis

# 安裝依賴
pip install -r requirements.txt

# 配置環境變量
cp .env.example .env && vim .env

# 運行分析
python main.py
```

常用命令：

```bash
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL,2330.TW
python main.py --market-review
python main.py --schedule
python main.py --serve-only
```

> Docker 部署、定時任務、雲服務器訪問請參考 [完整指南](docs/full-guide.md)；桌面客戶端打包請參考 [桌面端打包說明](docs/desktop-package.md)。

## 📱 推送效果

### 決策儀表盤
```
🎯 2026-02-08 決策儀表盤
共分析3只股票 | 🟢買入:0 🟡觀望:2 🔴賣出:1

📊 分析結果摘要
⚪ 中鎢高新(000657): 觀望 | 評分 65 | 看多
⚪ 永鼎股份(600105): 觀望 | 評分 48 | 震盪
🟡 新萊應材(300260): 賣出 | 評分 35 | 看空

⚪ 中鎢高新 (000657)
📰 重要信息速覽
💭 輿情情緒: 市場關注其AI屬性與業績高增長，情緒偏積極，但需消化短期獲利盤和主力流出壓力。
📊 業績預期: 基於輿情信息，公司2025年前三季度業績同比大幅增長，基本面強勁，為股價提供支撐。

🚨 風險警報:

風險點1：2月5日主力資金大幅淨賣出3.63億元，需警惕短期拋壓。
風險點2：籌碼集中度高達35.15%，表明籌碼分散，拉昇阻力可能較大。
風險點3：輿情中提及公司歷史違規記錄及重組相關風險提示，需保持關注。
✨ 利好催化:

利好1：公司被市場定位為AI服務器HDI核心供應商，受益於AI產業發展。
利好2：2025年前三季度扣非淨利潤同比暴漲407.52%，業績表現強勁。
📢 最新動態: 【最新消息】輿情顯示公司是AI PCB微鑽領域龍頭，深度綁定全球頭部PCB/載板廠。2月5日主力資金淨賣出3.63億元，需關注後續資金流向。

---
生成時間: 18:00
```

### 大盤覆盤
```
🎯 2026-01-10 大盤覆盤

📊 主要指數
- 上證指數: 3250.12 (🟢+0.85%)
- 深證成指: 10521.36 (🟢+1.02%)
- 創業板指: 2156.78 (🟢+1.35%)

📈 市場概況
上漲: 3920 | 下跌: 1349 | 漲停: 155 | 跌停: 3

🔥 板塊表現
領漲: 互聯網服務、文化傳媒、小金屬
領跌: 保險、航空機場、光伏設備
```

## ⚙️ 配置說明

完整環境變量、模型渠道、通知渠道、數據源優先級、交易紀律、基本面 P0 語義和部署說明請參考 [完整配置指南](docs/full-guide.md)。

## 🖥️ Web 界面

Web 工作臺提供配置管理、任務監控、手動分析、歷史報告、完整 Markdown 報告、Agent 問股、回測、持倉管理、智能導入和淺色 / 深色主題。啟動方式：

```bash
python main.py --webui
python main.py --webui-only
```

訪問 `http://127.0.0.1:8000` 即可使用。認證、智能導入、搜索補全、歷史報告複製、雲服務器訪問等細節見 [本地 WebUI 管理界面](docs/full-guide.md#本地-webui-管理界面)。

## 🤖 Agent 策略問股

配置任意可用 AI API Key 後，Web `/chat` 頁面即可使用策略問股；如需顯式關閉可設置 `AGENT_MODE=false`。

- 支持均線金叉、纏論、波浪理論、多頭趨勢、熱點題材、事件驅動、成長質量、預期重估等內置策略
- 支持實時行情、K 線、技術指標、新聞和風險信息調用
- 支持多輪追問、會話導出、發送到通知渠道和後臺執行
- 支持自定義策略文件與多 Agent 編排（實驗性）

> Agent 具體參數、`skill` 命名兼容、多 Agent 模式和預算護欄見 [完整指南](docs/full-guide.md#本地-webui-管理界面) 與 [LLM 配置指南](docs/LLM_CONFIG_GUIDE.md)。

## 🧩 相關項目 (Related Projects)

> DSA 聚焦日常分析報告；選股實現參考 AlphaSift，AlphaEvo 用於策略驗證與進化。

| 項目 | 定位 |
|------|------|
| [AlphaSift](https://github.com/ZhuLinsen/alphasift) | DSA 選股實現的參考項目 |
| [AlphaEvo](https://github.com/ZhuLinsen/alphaevo) | 策略回測與自我進化，用於驗證策略規則，並通過迭代探索策略參數與組合 |

## 📬 聯繫與合作

<table>
  <tr>
    <td width="92" valign="top"><strong>合作郵箱</strong></td>
    <td valign="top">
      <a href="mailto:zhuls345@gmail.com">zhuls345@gmail.com</a><br>
      項目諮詢、部署支持與功能擴展
    </td>
    <td align="center" rowspan="3" valign="middle" width="148">
      <a href="http://xhslink.com/m/tU520DWCKT" target="_blank"><img src="./docs/assets/xiaohongshu_tick.jpg" width="112" alt="小紅書二維碼"></a><br>
      <sub>掃碼關注小紅書</sub>
    </td>
  </tr>
  <tr>
    <td width="92" valign="top"><strong>小紅書</strong></td>
    <td valign="top"><a href="http://xhslink.com/m/tU520DWCKT">歡迎關注小紅書</a></td>
  </tr>
  <tr>
    <td width="92" valign="top"><strong>問題反饋</strong></td>
    <td valign="top"><a href="https://github.com/ZhuLinsen/daily_stock_analysis/issues">提交 Issue</a></td>
  </tr>
</table>

## 📄 License

[MIT License](LICENSE) © 2026 ZhuLinsen

歡迎在二次開發或引用時註明本倉庫來源，感謝支持項目持續維護。

## ⚠️ 免責聲明

本項目僅供學習和研究使用，不構成任何投資建議。股市有風險，投資需謹慎。作者不對使用本項目產生的任何損失負責。

---
