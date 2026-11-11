# 文檔中心

這裡是項目文檔入口。README 負責項目概覽和快速開始；更完整的配置、部署、功能說明和排障內容從這裡進入。

## 按場景選擇

| 我想要 | 先看 | 繼續看 |
| --- | --- | --- |
| 快速瞭解項目能做什麼 | [README](../README.md) | [完整配置與部署指南](full-guide.md) |
| 第一次把項目跑起來 | [小白客戶端安裝與配置](beginner-client-setup.md) | [完整配置與部署指南](full-guide.md) |
| 配置大模型渠道 | [LLM 配置指南](LLM_CONFIG_GUIDE.md) | [LLM 服務商配置指南](llm-providers.md)（含 xAI Grok 直連） |
| 配置推送通知 | [通知能力基線](notifications.md) | [完整配置與部署指南](full-guide.md) |
| 部署到服務器或雲平臺 | [部署指南](DEPLOY.md) | [雲端 WebUI 部署](deploy-webui-cloud.md)、[Zeabur 部署](docker/zeabur-deployment.md) |
| 使用 Bot / IM 接入 | [Bot 命令與接入](bot-command.md) | [Bot 平臺配置](bot/)、[Grok Bot 集成](grok-bot-integration.md) |
| 排查運行問題 | [FAQ](FAQ.md) | [更新日誌](CHANGELOG.md) |
| 處理數據源失敗或降級 | [數據源穩定性與故障處理圖示](data-source-stability.md) | [FAQ](FAQ.md) |
| 確認某個市場支持哪些數據 | [市場支持與邊界](market-support.md) | [數據中心](data-center-diagnostics.md) |
| 參與開發或提交 PR | [貢獻指南](CONTRIBUTING.md) | [API 規格](architecture/api_spec.json) |

## 快速開始

| 文檔 | 內容 |
| --- | --- |
| [README](../README.md) | 項目定位、核心能力、快速開始、推送效果 |
| [小白客戶端安裝與配置](beginner-client-setup.md) | 面向不會代碼用戶的客戶端下載、AIHubMix 等模型配置、新聞源配置和常見問題 |
| [完整配置與部署指南](full-guide.md) | 環境準備、運行方式、配置說明、部署路徑和常見問題 |
| [FAQ](FAQ.md) | 常見配置、模型、通知、部署和運行問題 |
| [數據源穩定性與故障處理圖示](data-source-stability.md) | Tushare、TickFlow、AkShare、Efinance、YFinance、Longbridge 等已接入源的使用場景、fallback 鏈路和推薦配置 |
| [數據中心](data-center-diagnostics.md) | 只讀 Provider 能力、數據集質量、精確市場支持與運行時優先級 |
| [市場支持與邊界](market-support.md) | A股/港股/美股/日股/韓股/臺股的可用數據、suffix 規則、降級邊界與不承諾項 |
| [更新日誌](CHANGELOG.md) | 版本變化、能力調整和遷移說明 |

## 配置

| 文檔 | 內容 |
| --- | --- |
| [LLM 配置指南](LLM_CONFIG_GUIDE.md) | 大模型渠道、三層配置、Web 設置頁和常見模型配置 |
| [LLM 服務商配置指南](llm-providers.md) | Provider 預設、Actions 映射、錯誤分類和診斷建議 |
| [LiteLLM YAML 示例](examples/litellm_config.example.yaml) | LiteLLM 多渠道配置示例 |
| [Grok Bot Skill 示例](examples/grok_bot/README.md) | 給 Grok Bot 粘貼的最小 Skill，調用現有 REST |
| [通知能力基線](notifications.md) | 企業微信、飛書、Telegram、Discord、Slack、郵件等通知渠道配置 |
| [Tushare 股票列表指南](TUSHARE_STOCK_LIST_GUIDE.md) | Tushare 股票列表相關配置和使用說明 |

## 使用專題

| 文檔 | 內容 |
| --- | --- |
| [自選股變化狀態與下一步](watchlist-next-action.md) | 首頁自選股列表的變化、狀態、下一步三段信號、映射規則和後續擴展邊界 |
| [Bot 命令與接入](bot-command.md) | Bot 命令、Webhook、平臺接入和回調說明 |
| [Bot 平臺配置](bot/) | 飛書、釘釘、Discord 等 Bot 配置截圖和補充說明 |
| [實時告警中心](alerts.md) | EventMonitor 基線、Web 規則管理、通知結果、冷卻狀態和 Phase 邊界 |
| [個股研究聚合 API](stock-profile-api.md) | 單一 stock-profile 契約、分塊質量狀態、代碼歸一與後續 Web 邊界 |
| [DecisionSignal 決策信號專題](decision-signals.md) | AI 建議池字段語義、API、Web 展示、告警/通知/組合風險聯動、後驗評估、脫敏、遷移與回滾 |
| [ETF 輪動](etf-rotation.md) | `--etf-rotation` 規則化雙動量輪動：規則、配置、報告章節、參數平原解讀與數據告警邊界 |
| [ResearchArtifact 結構化研究產物](research-artifact.md) | structured_report 字段、Thesis / Evidence / Invalidation / Next Action / Data Quality 契約和舊報告兼容邊界 |
| [組合風險與暴露看板](portfolio-risk-exposure-dashboard.md) | 持倉頁風險旗標、市場暴露、幣種暴露和價格質量聚合展示 |
| [選股解釋契約](screening-explanations.md) | Why Selected / Why Now 的後端確定性解釋、來源、質量狀態與缺失值邊界 |
| [資訊 / 情報源](intelligence-sources.md) | RSS/Atom 合規資訊源配置、測試、拉取、去重、存儲、查詢與安全邊界 |
| [分析上下文包契約、運行態消費與可見性](analysis-context-pack.md) | AnalysisContextPack 首版範圍、字段質量狀態、P1/P2 內部契約、P3 Prompt 摘要消費、P4 歷史/API/Web 低敏可見性、P5 數據質量評分、P6 遷移回滾與源碼錨點；完整指南補充 #1386 階段感知分析、遷移與回滾入口 |
| [圖片識別 Prompt](image-extract-prompt.md) | 圖片識別股票信息的 Prompt 與使用邊界 |
| [OpenClaw Skill 集成](openclaw-skill-integration.md) | OpenClaw / Skill 外部集成說明 |
| [Grok Bot 集成](grok-bot-integration.md) | 2026-08-11 Grok Bot（AI teammate）與 DSA REST / DecisionSignal / Skill 的對接邊界 |

## 部署與打包

| 文檔 | 內容 |
| --- | --- |
| [部署指南](DEPLOY.md) | 服務器部署、Docker、systemd、Supervisor 等部署方式 |
| [雲端 WebUI 部署](deploy-webui-cloud.md) | 雲服務器訪問 WebUI 的部署說明 |
| [Zeabur 部署](docker/zeabur-deployment.md) | Zeabur 平臺部署說明 |
| [桌面端打包說明](desktop-package.md) | Electron 桌面端和 Web 構建產物打包說明 |

## 參考與開發

| 文檔 | 內容 |
| --- | --- |
| [API 規格](architecture/api_spec.json) | FastAPI OpenAPI 規格產物 |
| [貢獻指南](CONTRIBUTING.md) | Issue、PR、測試、文檔同步和協作要求 |

## 多語言

| 文檔 | 內容 |
| --- | --- |
| [英文文檔索引](INDEX_EN.md) | English documentation index |
| [英文 README](README_EN.md) | English project overview and quick start |
| [繁中 README](README_CHT.md) | 繁體中文項目概覽與快速開始 |
