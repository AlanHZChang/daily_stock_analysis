# Zeabur 部署指南

本指南詳細介紹如何在 Zeabur 上部署 A股自選股智能分析系統，包括 WebUI 和 Discord 機器人功能。

## 目錄

- [1. 部署前準備](#1-部署前準備)
- [2. 在 Zeabur 上部署](#2-在-zeabur-上部署)
- [3. 配置啟動命令](#3-配置啟動命令)
- [4. Discord 機器人部署](#4-discord-機器人部署)
- [5. 環境變量配置](#5-環境變量配置)
- [6. 掛載配置](#6-掛載配置)
- [7. 健康檢查](#7-健康檢查)
- [8. 常見問題](#8-常見問題)

## 1. 部署前準備

### 1.1 必要條件

- Zeabur 賬號
- GitHub 賬號（用於連接倉庫）
- Discord 開發者賬號（如需部署機器人）
- 相關 API 密鑰（如 Gemini API Key、搜索服務 API Key 等）

### 1.2 倉庫準備

確保你的倉庫包含以下文件：

- `.github/workflows/docker-publish.yml`（已自動創建）
- `docker/Dockerfile`（已存在）
- 完整的項目代碼

## 2. 在 Zeabur 上部署

### 2.1 連接 GitHub 倉庫

1. 登錄 Zeabur 控制檯
2. 點擊「新建項目」
3. 選擇「從 GitHub 導入」
4. 選擇你的倉庫和分支（推薦使用 `main` ）
5. 點擊「導入」

### 2.2 配置構建規則

Zeabur 會自動檢測 `.github/workflows/docker-publish.yml` 文件，並使用 GitHub Actions 構建鏡像。

如果沒有自動檢測到，可以手動配置：

1. 在項目頁面，點擊「構建規則」
2. 選擇「Dockerfile」
3. Dockerfile 路徑填寫：`docker/Dockerfile`
4. 點擊「保存」

### 2.3 啟動服務

1. 等待鏡像構建完成
2. 點擊「啟動服務」
3. 服務啟動後，你可以在「訪問」標籤頁獲取訪問地址

### 2.4 前端構建與靜態資源

FastAPI 會自動託管 `static/` 目錄下的前端資源。前端打包輸出位置由
`apps/dsa-web/vite.config.ts` 決定，默認輸出到項目根目錄 `static/`。

Dockerfile 已採用多階段構建，前端會在鏡像構建時自動打包。
如需覆蓋默認靜態資源，可在宿主機手動構建並掛載到容器內 `/app/static`。

### 2.5 資源配置建議

Zeabur 服務建議從 `1G` 內存起步；`512M` 僅適合輕量 Web/API、單股、低併發場景，並建議設置 `MAX_WORKERS=1`。

- 最低可嘗試：`512M`，不要同時運行多個重型任務。
- 推薦：`1G`，適合單服務常規分析。
- 高負載：`2G+`，適合同時運行 Web/API 與定時分析、多股票、大盤覆盤、新聞擴展、圖片報告或選股。

如果只能使用 `512M`，請避免同時部署等價於 `server + analyzer` 的多服務組合，並關閉非必要的大盤覆盤、新聞擴展和圖片報告能力。

## 3. 配置啟動命令

### 3.1 支持的啟動模式

系統支持多種啟動模式，你可以根據需要配置不同的啟動命令：

| 模式 | 啟動命令 | 描述 |
|------|----------|------|
| 定時任務模式（默認） | `python main.py --schedule` | 按計劃執行股票分析 |
| FastAPI 模式 | `python main.py --serve` | 啟動 FastAPI 並執行分析 |
| 僅 FastAPI 模式 | `python main.py --serve-only` | 僅啟動 FastAPI，不執行分析 |
| 僅大盤覆盤 | `python main.py --market-review` | 僅執行大盤覆盤分析 |

### 3.2 配置啟動命令

1. 在 Zeabur 控制檯，進入服務頁面
2. 點擊「設置」
3. 找到「啟動命令」配置項
4. 輸入你需要的啟動命令，例如：
    - 啟動 FastAPI：`python main.py --serve`
    - 僅啟動 FastAPI：`python main.py --serve-only --host 0.0.0.0 --port 8000`
    - 啟動定時任務：`python main.py --schedule`
5. 點擊「保存」
6. 重啟服務

## 4. Discord 機器人部署

### 4.1 準備工作

1. 創建 Discord 應用和機器人
   - 訪問 [Discord 開發者平臺](https://discord.com/developers/applications)
   - 點擊「New Application」創建新應用
   - 在「Bot」標籤頁，點擊「Add Bot」創建機器人
   - 複製機器人 Token

2. 配置機器人權限
   - 在「Bot」標籤頁，向下滾動到「Privileged Gateway Intents」
   - 啟用「Server Members Intent」和「Message Content Intent」
   - 在「OAuth2」→「URL Generator」中，選擇「bot」範圍
   - 選擇所需權限（如「Send Messages」、「Read Messages/View Channels」等）
   - 複製生成的邀請鏈接，將機器人添加到你的服務器

### 4.2 配置環境變量

在 Zeabur 控制檯的「環境變量」配置中，添加以下變量：

| 變量名 | 說明 | 示例值 |
|--------|------|--------|
| `DISCORD_BOT_TOKEN` | Discord 機器人 Token | `MTAxMjM0NTY3ODkwMTEyMzQ1Ng.GhIjKl.MnOpQrStUvWxYz1234567890` |
| `DISCORD_MAIN_CHANNEL_ID` | 主頻道 ID | `123456789012345678` |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL（可選） | `https://discord.com/api/webhooks/...` |

### 4.3 啟動機器人

機器人功能默認通過配置啟用，無需特殊啟動命令。確保你的配置文件中包含機器人相關配置，或通過環境變量設置。

## 5. 環境變量配置

### 5.1 基本環境變量

| 變量名 | 說明 | 默認值 |
|--------|------|--------|
| `PYTHONUNBUFFERED` | 啟用 Python 無緩衝輸出 | `1` |
| `LOG_DIR` | 日誌目錄 | `/app/logs` |
| `DATABASE_PATH` | 數據庫路徑 | `/app/data/stock_analysis.db` |

### 5.2 API 服務配置

| 變量名 | 說明 | 默認值 |
|--------|------|--------|
| `API_HOST` | API 服務監聽地址 | `0.0.0.0` |
| `API_PORT` | API 服務端口 | `8000` |

> 舊版 `WEBUI_HOST`/`WEBUI_PORT`/`WEBUI_ENABLED` 環境變量仍兼容，會自動轉發到 API 服務。

### 5.3 分析相關配置

| 變量名 | 說明 |
|--------|------|
| `AIHUBMIX_KEY` | AIHubMix API 密鑰（一 Key 多模型，推薦） |
| `GEMINI_API_KEY` | Gemini API 密鑰 |
| `OPENAI_API_KEY` | OpenAI 兼容 API 密鑰 |
| `SERPAPI_API_KEYS` | SerpAPI 密鑰（推薦） |
| `ANSPIRE_API_KEYS` | [Anspire](https://open.anspire.cn/dsa?share_code=QFBC0FYC) API Key（可選，模型與搜索共用；可用性以賬號權限為準） |
| `TAVILY_API_KEYS` | Tavily API 密鑰（用逗號分隔） |
| `BOCHA_API_KEYS` | Bocha API 密鑰（用逗號分隔） |
| `BRAVE_API_KEYS` | Brave Search API 密鑰（用逗號分隔） |
| `MINIMAX_API_KEYS` | MiniMax API 密鑰（用逗號分隔） |
| `SEARXNG_BASE_URLS` | SearXNG 實例地址（逗號分隔，無配額兜底，需在 settings.yml 啟用 format: json）；留空時僅在顯式啟用公共實例發現後使用 `searx.space` |
| `SEARXNG_PUBLIC_INSTANCES_ENABLED` | 是否在 `SEARXNG_BASE_URLS` 為空時自動從 `searx.space` 獲取公共實例（默認 `false`） |

### 5.4 配置方法

在 Zeabur 控制檯：

1. 進入服務頁面
2. 點擊「環境變量」
3. 點擊「添加環境變量」
4. 輸入變量名和值
5. 點擊「保存」
6. 重啟服務

## 6. 掛載配置

### 6.1 支持的掛載目錄

| 目錄 | 說明 |
|------|------|
| `/app/data` | 數據庫和數據文件 |
| `/app/logs` | 日誌文件 |
| `/app/reports` | 分析報告 |

### 6.2 配置掛載

1. 在 Zeabur 控制檯，進入服務頁面
2. 點擊「存儲」
3. 點擊「添加存儲卷」
4. 選擇「持久化存儲」
5. 配置掛載路徑：
   - 存儲卷路徑：`/app/data`
   - 容器內路徑：`/app/data`
6. 點擊「保存」
7. 對其他需要掛載的目錄重複上述步驟

### 6.3 注意事項

- 掛載後，數據會持久化保存，不會因容器重啟而丟失
- 建議至少掛載 `/app/data` 目錄，以保存數據庫

## 7. 健康檢查

系統內置了健康檢查機制，默認檢查：

- WebUI 模式：檢查 `http://localhost:8000/health` 端點
- FastAPI 模式：檢查 `http://localhost:8000/api/health` 端點
- 非服務模式：始終返回健康狀態

健康檢查配置如下：

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || curl -f http://localhost:8000/health \
    || python -c "import sys; sys.exit(0)"
```

## 8. 常見問題

### 8.1 API 服務無法訪問

- 檢查啟動命令是否包含 `--serve` 或 `--serve-only` 參數
- 檢查「訪問」標籤頁是否已配置域名
- 檢查防火牆設置

### 8.2 機器人不響應

- 檢查 Discord 機器人 Token 是否正確
- 檢查機器人是否已添加到服務器
- 檢查機器人權限是否足夠
- 檢查日誌文件，查看是否有錯誤信息

### 8.3 分析任務不執行

- 檢查定時任務配置是否正確
- 檢查 API 密鑰是否有效
- 檢查日誌文件，查看是否有錯誤信息

### 8.4 數據丟失

- 確保已掛載 `/app/data` 目錄
- 檢查存儲卷配置是否正確

## 9. 高級配置

### 9.1 多實例部署

你可以在 Zeabur 上部署多個實例，用於不同的功能：

1. 一個實例用於 API 服務（`python main.py --serve-only`）
2. 一個實例用於定時任務（`python main.py --schedule`）
3. 一個實例用於機器人（`python main.py --discord-bot`）

確保它們共享同一個 `/app/data` 存儲卷，以共享數據庫。

### 9.2 自定義域名

在 Zeabur 控制檯的「訪問」標籤頁，你可以：

1. 使用自動生成的域名
2. 綁定自定義域名
3. 配置 HTTPS

## 10. 更新部署

### 10.1 自動更新

當你向倉庫推送新代碼時：

1. GitHub Actions 會自動構建新鏡像
2. Zeabur 會檢測到新鏡像
3. 你可以選擇「自動部署」或手動觸發部署

### 10.2 手動更新

1. 在 Zeabur 控制檯，進入服務頁面
2. 點擊「部署歷史」
3. 選擇「重新部署」
4. 或點擊「更新鏡像」

## 11. 監控和日誌

### 11.1 查看日誌

在 Zeabur 控制檯，進入服務頁面，點擊「日誌」標籤頁，可以查看實時日誌和歷史日誌。

### 11.2 監控指標

Zeabur 提供了基礎的監控指標：

- CPU 使用率
- 內存使用率
- 網絡流量
- 磁盤使用率

在「監控」標籤頁查看詳細指標。

## 12. 故障排查

### 12.1 查看詳細日誌

```bash
# 進入容器
zeabur exec <服務名> bash

# 查看日誌文件
cat /app/logs/stock_analysis_20260125.log
```

### 12.2 檢查配置

```bash
# 進入容器
zeabur exec <服務名> bash

# 檢查環境變量
printenv | grep -i discord
printenv | grep -i webui
```

### 12.3 測試連接

```bash
# 測試網絡連接
zeabur exec <服務名> curl -I https://api.discord.com

# 測試 API 連接
zeabur exec <服務名> python -c "import requests; print(requests.get('https://api.discord.com').status_code)"
```

## 13. 最佳實踐

1. **使用持久化存儲**：始終掛載 `/app/data` 目錄，以保存數據庫
2. **配置合理的健康檢查**：根據實際情況調整健康檢查參數
3. **使用環境變量管理敏感信息**：不要將 API 密鑰硬編碼到代碼中
4. **定期備份數據**：定期下載 `/app/data` 目錄的內容進行備份
5. **使用合適的啟動模式**：根據需求選擇合適的啟動命令
6. **監控服務狀態**：定期檢查服務狀態和日誌
7. **按負載配置內存**：完整分析推薦 `1G` 起步；`512M` 低配環境設置 `MAX_WORKERS=1`，高負載場景使用 `2G+`

## 14. 聯繫方式

如有問題，歡迎聯繫項目維護者或在 GitHub Issues 中提問。
