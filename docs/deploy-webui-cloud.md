# 雲服務器 Web 界面訪問指南

如果你已經把項目部署到雲服務器，但不知道在瀏覽器裡輸入什麼地址才能打開 Web 管理界面，這篇教程就是為你準備的。

> 其實就兩步：讓服務監聽外網，再在瀏覽器裡輸入地址。

---

## 目錄

- [方式一：直接部署（pip + python）](#方式一直接部署pip--python)
- [方式二：Docker Compose](#方式二docker-compose)
- [如何在瀏覽器裡打開界面](#如何在瀏覽器裡打開界面)
- [如何確認 Docker 重建已生效](#如何確認-docker-重建已生效)
- [訪問不了？先檢查這幾項](#訪問不了先檢查這幾項)
- [可選：Nginx 反向代理（綁定域名 / 80 端口）](#可選nginx-反向代理綁定域名--80-端口)
- [安全建議](#安全建議)

---

## 方式一：直接部署（pip + python）

### 第一步：修改 .env 中的監聽地址

用編輯器打開 `.env`（在項目根目錄，即包含 `main.py` 的目錄），找到這一行：

```env
WEBUI_HOST=127.0.0.1
```

把 `127.0.0.1` 改成 `0.0.0.0`：

```env
WEBUI_HOST=0.0.0.0
```

> `127.0.0.1` 表示只有本機能訪問，`0.0.0.0` 表示允許任何來源訪問。雲服務器需要把 `.env` 中的 `WEBUI_HOST` 改成 `0.0.0.0`，或在啟動命令裡顯式傳入 `--host 0.0.0.0`，才能從外網打開界面。

### 第二步：啟動服務

在項目根目錄執行：

```bash
# 只啟動 Web 界面（不自動執行分析）
python main.py --webui-only

# 或者：啟動 Web 界面（啟動時執行一次分析；需每日定時分析請加 --schedule 或設 SCHEDULE_ENABLED=true）
python main.py --webui
```

啟動成功後，終端會輸出類似：

```
FastAPI 服務已啟動: http://0.0.0.0:8000
```

如果你想讓服務在退出終端後繼續運行，可以用 `nohup`：

```bash
nohup python main.py --webui-only > /dev/null 2>&1 &
```

> 日誌文件會由程序自動寫入 `logs/` 目錄，用 `tail -f logs/stock_analysis_*.log` 查看。

### 修改端口（可選）

默認端口是 8000。如果想改用其他端口，在 `.env` 裡設置：

```env
WEBUI_PORT=8888
```

然後重啟服務。

---

## 方式二：Docker Compose

### 第一步：確認已有 .env 配置

項目的 `docker/docker-compose.yml` 在容器內部已經自動設置了 `WEBUI_HOST=0.0.0.0`，你不需要在 `.env` 裡再改監聽地址，Docker 會自動處理。

Docker Compose 中的 `env_file: ../.env` 只會把 `.env` 作為**啟動環境變量**注入容器，不會在容器內創建 `/app/.env`，也不會讓 WebUI 保存配置時回寫宿主機 `.env`。新版 WebUI 會在活躍 `.env` 文件缺少某些鍵時展示啟動注入的同名環境變量作為兜底，因此頁面上能看到 Docker 啟動時注入的配置；但“導出 `.env`”仍只導出當前活躍配置文件內容。

如果希望 WebUI 中保存的配置在容器刪除、重建或升級後繼續保留，請把活躍配置文件放到已掛載的數據卷中，例如在 Compose 的 `environment` 中增加：

```yaml
- ENV_FILE=/app/data/runtime.env
```

同時保留 `../data:/app/data` 掛載。注意：如果啟動時的 `../.env`、`docker run -e` 或 Compose `environment:` 裡還保留同名舊值，容器重啟後這些啟動環境變量仍可能覆蓋運行時文件中的保存值；要讓 WebUI 保存值接管，請同步更新或移除啟動環境中的同名配置。

### 第二步：啟動服務

在項目根目錄執行：

```bash
# 同時啟動定時分析 + Web 界面（推薦）
docker-compose -f ./docker/docker-compose.yml up -d

# 或者只啟動 Web 界面服務
docker-compose -f ./docker/docker-compose.yml up -d server
```

啟動後查看狀態：

```bash
docker-compose -f ./docker/docker-compose.yml ps
```

看到 `server` 服務狀態為 `running` 就說明 Web 界面已經在運行了。

### 修改端口（可選）

默認端口是 8000。如果想改用其他端口，在 `.env` 裡設置：

```env
API_PORT=8888
```

然後重新啟動容器：

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml up -d
```

---

## 如何在瀏覽器裡打開界面

服務啟動後，在瀏覽器地址欄輸入：

```
http://你的服務器公網IP:8000
```

例如，如果你的服務器 IP 是 `1.2.3.4`，就輸入：

```
http://1.2.3.4:8000
```

如果你的域名已經解析到這臺服務器，也可以直接用域名訪問：

```
http://your-domain.com:8000
```

> **在哪裡查公網 IP？** 登錄你的雲服務器控制檯（阿里雲/騰訊雲/AWS 等），在實例列表裡可以看到「公網 IP」或「彈性 IP」。

---

## 如何確認 Docker 重建已生效

先區分兩件事：

1. **Docker 鏡像發佈版本**：看你部署時使用的鏡像 tag，例如 `ghcr.io/zhulinsen/daily_stock_analysis:v3.12.0`。倉庫的 Docker 發佈由 `.github/workflows/docker-publish.yml` 按 `v*.*.*` Git tag 觸發，所以 Docker 版本應以鏡像 tag / GitHub Releases 為準。
2. **當前頁面加載的前端構建**：看 WebUI “系統設置”頁裡的版本信息卡片，用來確認瀏覽器拿到的靜態資源是否已經更新。

也就是說，**“系統設置”裡的版本信息更適合判斷前端是否重建成功，不等同於 Docker 鏡像發佈版本**。

WebUI 現在會在“系統設置”頁展示只讀的“版本信息”卡片，包含：

- `WebUI 版本`
- `代碼版本`
- `構建時間`

正式 Docker / Desktop 發佈會把 release tag 注入為 `WebUI 版本`，並把對應 commit
顯示為 `代碼版本`。直接從 Git clone 構建時，WebUI 會使用 `git describe` 和當前
commit；如果構建環境既沒有發佈信息也沒有 Git 元數據，版本會明確顯示為
`development`，不會再用構建時間冒充發布版本。

當你重新執行 `docker-compose -f ./docker/docker-compose.yml up -d --build`，或者單獨重新執行前端 `npm run build` 後，可以刷新瀏覽器並進入“系統設置”，確認“代碼版本”和“構建時間”是否已經變化；兩者能共同確認瀏覽器當前加載的靜態資源來自哪次代碼和構建。

如果你想確認“我現在到底部署的是哪個正式版本”，優先用下面這些方式：

```yaml
# 方式 1：看 docker-compose / 部署腳本里的 image tag
image: ghcr.io/zhulinsen/daily_stock_analysis:v3.12.0
```

```bash
# 方式 2：回看你的拉取命令
docker pull ghcr.io/zhulinsen/daily_stock_analysis:v3.12.0
```

如果你一直使用 `latest`，建議改成顯式版本 tag；否則很難僅憑容器內頁面信息判斷自己是否已經重複更新到同一版本。

在確認本地前端打包鏈路時，建議執行以下命令作為最小驗證閉環：

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

其中 `build` 成功後，`static` 下生成的 `index.html`/JS/CSS 資源會包含本次版本、
commit、構建時間，並生成 `build-info.json`。啟動時會比較該文件中的源碼摘要，
因此即使 `rsync -a` 保留了舊時間戳，也能識別源碼與靜態產物不一致並重新構建。
刷新後在“版本信息”卡片中應能見到變化。

---

## 訪問不了？先檢查這幾項

### 1. 安全組 / 防火牆沒有放行端口

這是最常見的原因。雲服務器默認只開放 22（SSH）端口，需要手動放行 8000（或你改的端口）。

**操作方法**（以阿里云為例）：
1. 登錄阿里雲控制檯 → 雲服務器 ECS → 找到你的實例
2. 點擊「安全組」→「配置規則」→「添加安全組規則」
3. 方向選「入方向」，端口範圍填 `8000/8000`，授權對象填 `0.0.0.0/0`，點擊「確定」

騰訊雲、AWS 等雲廠商操作類似，找到「安全組」或「防火牆規則」，新增一條允許 TCP 8000 端口的入站規則即可。

### 2. 服務器系統防火牆攔截了

如果你的系統開啟了 `ufw` 或 `firewalld`，也需要放行端口：

```bash
# Ubuntu / Debian（ufw）
sudo ufw allow 8000

# CentOS / RHEL（firewalld）
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

### 3. 直接部署時 .env 裡的 WEBUI_HOST 沒改

這是第二常見原因。`.env` 裡默認是 `WEBUI_HOST=127.0.0.1`，這樣服務只監聽本機，外網根本連不上。

改法：打開 `.env`，把 `WEBUI_HOST=127.0.0.1` 改成 `WEBUI_HOST=0.0.0.0`，然後重啟服務；也可以在啟動命令裡顯式添加 `--host 0.0.0.0`。

> Docker 方式不需要改這個，可以跳過。

### 4. 端口號對不上

檢查訪問地址裡的端口是否和 `.env` / 啟動命令裡設置的端口一致。

- 直接部署：默認 8000，可通過 `WEBUI_PORT=xxxx` 修改
- Docker：默認 8000，可通過 `API_PORT=xxxx` 修改

### 5. 頁面能打開，但 UI 元素異常變大 / 佈局錯亂

**症狀**：瀏覽器能訪問到 8000 端口，頁面有內容，但文字、按鈕、卡片尺寸異常大，沒有正常佈局與配色。

**根因**：`static/index.html` 存在但 CSS/JS 資源缺失（`static/assets/` 為空或不存在），瀏覽器加載了 HTML 框架但無法拿到樣式與腳本，退化為裸 HTML 渲染。

可先用瀏覽器開發者工具（F12 → Network 標籤頁）檢查是否有 `/assets/index-*.js`、`/assets/index-*.css` 的 **404** 錯誤。若有，按以下方式修復：

**Docker 用戶**：

```bash
docker-compose -f ./docker/docker-compose.yml down
docker-compose -f ./docker/docker-compose.yml build --no-cache
docker-compose -f ./docker/docker-compose.yml up -d
```

重建完成後，用 `Ctrl+Shift+R` 強制刷新瀏覽器緩存，再訪問頁面。

**直接部署用戶**：先確保已安裝 Node.js 18+（推薦 20+），然後手動構建前端：

```bash
cd apps/dsa-web
npm ci
npm run build
cd ../..
python main.py --webui-only
```

---

## 可選：Nginx 反向代理（綁定域名 / 80 端口）

如果你有域名，或者不想在地址裡帶 `:8000`，可以用 Nginx 做反向代理，把 80/443 端口流量轉發給後端服務。

### 安裝 Nginx

```bash
# Ubuntu / Debian
sudo apt update && sudo apt install -y nginx

# CentOS
sudo yum install -y nginx
```

### 配置文件示例

新建文件 `/etc/nginx/conf.d/stock-analyzer.conf`，內容如下（把 `your-domain.com` 改成你的域名或 IP）：

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 支持 WebSocket（Agent 對話頁面需要）
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 啟用配置並重啟 Nginx

```bash
sudo nginx -t            # 檢查配置有沒有語法錯誤
sudo systemctl reload nginx
```

配置成功後，直接用 `http://your-domain.com` 訪問即可，不需要帶端口號。

> **使用 Nginx 後的注意事項**：
> - 如果你開啟了 Web 登錄認證（`ADMIN_AUTH_ENABLED=true`），建議在 `.env` 中把 `TRUST_X_FORWARDED_FOR=true` 一併打開，否則系統可能無法正確識別真實 IP。該選項適用於**單層可信反向代理**（Nginx → App）部署；如果使用多級代理或 CDN（CDN → Nginx → App），登錄限流的 key 可能退化為邊緣代理 IP 而非真實客戶端 IP，需根據實際拓撲評估。
> - 如需 HTTPS，可以用 [Certbot](https://certbot.eff.org/) 自動申請免費的 Let's Encrypt 證書。

---

## 安全建議

把 Web 界面暴露到公網之前，強烈建議開啟登錄密碼保護：

在 `.env` 中設置：

```env
ADMIN_AUTH_ENABLED=true
```

重啟服務後，第一次訪問網頁時會要求設置初始密碼。設置完成後，每次打開設置頁面都需要輸入密碼，可以防止 API Key 等敏感配置被他人看到。

> 如果忘了密碼，可以在服務器上執行：`python -m src.auth reset_password`

---

遇到其他問題？歡迎 [提交 Issue](https://github.com/ZhuLinsen/daily_stock_analysis/issues)。
