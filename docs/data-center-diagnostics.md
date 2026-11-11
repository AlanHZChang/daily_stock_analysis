# 數據中心

Web 數據中心位於 `/data`，用於只讀查看數據源能力、數據集質量與運行時優先級。頁面只消費 `GET /api/v1/data/overview`，不讀取系統配置原始值，也不自行拼接 screening、provider 或配置探針。

## 頁面內容

- Provider 能力：卡片展示運行狀態及 `dataset_markets` 給出的精確數據集/市場支持關係；頁面頂部彙總已配置的 Provider 數量，不在卡片中單獨展示 enabled/configured 標誌。
- 數據集質量：`ok`、`degraded`、`partial`、`unconfigured`、`unavailable`、`unknown`、`stale`，以及當前來源、最近成功時間和脫敏診斷。
- 路由優先級：每個運行場景的 provider 順序及其配置來源。
- Overview warnings：接口認為需要關注、但不應阻斷其他塊展示的警告代碼。

## 狀態邊界

- 頁面不會根據“已知 provider 名稱”把冷啟動狀態推斷為 `ok`；後端返回 `unknown` 時原樣展示。
- 頁面不會把 Provider 的 `markets` 與 `datasets` 計算笛卡爾積；精確支持範圍以 `dataset_markets` 為準。
- 多市場數據集使用不同 provider 時，頂層 `source` 合法地為空；頁面會讀取 `coverage.markets`，按市場展示實際來源，而不是顯示成 `--`。
- Overview 請求失敗時整頁顯示可重試錯誤；接口成功但 provider/dataset 均為空時顯示 empty 狀態。
- 單個 provider 或 dataset 的 `partial`、`unknown`、`stale`、`unavailable` 隻影響對應條目，其餘條目繼續展示。

## 安全邊界

該頁面不調用 `/api/v1/system/config`，不展示 API Key、Token、Cookie 或原始環境變量。需要修改配置時僅跳轉到 Settings，由現有配置脫敏和權限邊界負責處理。

## 驗證與回滾

前端測試使用與 `DataCapabilityOverviewResponse` 同形的 payload，覆蓋 success、cold-start unknown、warning、empty、error 和 retry。回滾頁面時可移除 `/data` 路由、導航、API/type、頁面及文檔；後端 capability 契約不受影響。

## 瀏覽器驗收

`cd apps/dsa-web && npx playwright test --config playwright.fixture.config.ts` 使用固定 API fixture 渲染真實頁面，不依賴後端服務或密鑰。CI 的 `web-gate` 安裝 Chromium、執行驗收，並將截圖上傳為 `web-ui-evidence-<head SHA>` artifact（保留 30 天）；截圖不提交到倉庫。該驗收驗證頁面交互和展示，不代表實時 provider/LLM 可用性。

桌面導航在短窗口中僅滾動鏈接列表，主題、語言與退出控件保留在可見區域；主題菜單不進入滾動裁剪容器。瀏覽器驗收包括 1280×720、認證與選股均開啟時的設置/退出可達性、主題菜單及取消退出。
