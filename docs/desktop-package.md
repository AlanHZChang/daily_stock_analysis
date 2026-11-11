# 桌面端打包說明 (Electron + React UI)

本項目可打包為桌面應用，使用 Electron 作為桌面殼，`apps/dsa-web` 的 React UI 作為界面。

## 架構說明

- React UI（Vite 構建）由本地 FastAPI 服務託管
- Electron 啟動時自動拉起後端服務，等待 `/api/health` 就緒後加載 UI
- Windows 便攜/安裝模式下，用戶配置文件 `.env` 和數據庫放在 exe 同級目錄；macOS 打包版使用 Electron 用戶數據目錄保存運行時配置
- 桌面端會自動從本機 `8000-8100` 選擇可用端口，並把實際選擇的端口同步給內置後端；桌面端不依賴 `.env` 裡的 `WEBUI_PORT` 來決定窗口連接地址，避免用戶改端口後 Electron 仍等待舊端口導致啟動超時
- Desktop backend 默認隨 `requirements.txt` 安裝並凍結 `futu-api==10.8.6808`；Windows/macOS 構建腳本會在源碼環境和 PyInstaller 產物中分別執行 `import futu`，防止發佈包只安裝但未攜帶 SDK。
- 籌碼分佈依賴的 `py_mini_racer` 按構建環境實際安裝版本完整收集 Python 模塊、原生庫和運行數據；不跨版本手工拼接 DLL、ICU 或 snapshot 文件。Windows/macOS 明確要求 `mini-racer>=0.13.2`，避免舊版凍結加載器從 bundle 根目錄尋找原生庫、與包目錄收集佈局不一致；Linux 繼續沿用 AkShare 原有依賴。Windows/macOS 構建腳本會在源碼環境和凍結後的後端中執行 `MiniRacer().eval('1 + 1')`，原生庫缺失或版本不匹配會阻斷打包。僅成功 `import py_mini_racer` 不足以驗收；這一離線檢查不代表在線東財接口一定可用。
- 報告“分享”按鈕使用 Electron 自帶的隱藏 Chromium 窗口渲染本地後端輸出的受限 HTML，並保存為 PNG；桌面安裝包無需額外攜帶 `wkhtmltoimage`、`markdown-to-file` 或 Playwright 瀏覽器。

## 本地開發

一鍵啟動（開發模式）：

```bash
powershell -ExecutionPolicy Bypass -File scripts\run-desktop.ps1
```

或手動執行：

1) 構建 React UI（輸出到 `static/`）

```bash
cd apps/dsa-web
npm install
npm run build
```

2) 啟動 Electron 應用（自動拉起後端）

```bash
cd apps/dsa-desktop
npm install
npm run dev
```

首次運行時會自動從 `.env.example` 複製生成 `.env`。

## 打包 (Windows)

### 前置條件

- Node.js 18+
- Python 3.10+
- 開啟 Windows 開發者模式（electron-builder 需要創建符號鏈接）
  - 設置 -> 隱私和安全性 -> 開發者選項 -> 開發者模式

### 一鍵打包

```bash
powershell -ExecutionPolicy Bypass -File scripts\build-all.ps1
```

該腳本會依次執行：
1. 構建 React UI
2. 安裝 Python 依賴
3. PyInstaller 打包後端
4. electron-builder 打包桌面應用

當前 Windows 安裝包使用 NSIS 嚮導式安裝流程，僅支持當前用戶安裝且已禁用管理員提權，安裝時可手動選擇目標目錄（例如非 C 盤）。安裝器通過 NSIS `.onVerifyInstDir` 回調在安裝器層面阻止選擇 `Program Files`、`Windows` 等系統保護目錄——選擇這些路徑時"下一步"按鈕會被自動禁用。安裝完成後，桌面端仍會按現有邏輯在安裝目錄旁生成/讀取 `.env`、`data/stock_analysis.db`（含 `data/stock_analysis.db-wal` / `data/stock_analysis.db-shm`）和 `logs/desktop.log`。推薦使用默認的 per-user 安裝目錄。如果不想安裝，仍可繼續分發 `win-unpacked` 免安裝包。

## GitHub CI 自動打包併發布 Release

倉庫已支持通過 GitHub Actions 自動構建桌面端並上傳到 GitHub Releases：

- 工作流：`.github/workflows/desktop-release.yml`
- 觸發方式：
  - 推送語義化 tag（如 `v3.2.12`）後自動觸發
  - 在 Actions 頁面手動觸發並指定 `release_tag`
- 產物：
  - Windows 安裝包：Release 附件和本地 `apps/dsa-desktop/dist/` 中統一為 `daily-stock-analysis-windows-installer-<tag>.exe`
  - Windows 自動更新元數據：Release 附件會額外保留 `latest.yml` 和 `*.blockmap`，供安裝版桌面端後臺下載與校驗更新；普通用戶無需手動下載這些元數據。下載完成後用戶確認“重啟安裝”時，桌面端會先停止內置後端、備份運行時文件，並以靜默模式執行安裝器。
  - Windows 免安裝包：`daily-stock-analysis-windows-noinstall-<tag>.zip`
  - macOS Intel：`daily-stock-analysis-macos-x64-<tag>.dmg`
  - macOS Apple Silicon：`daily-stock-analysis-macos-arm64-<tag>.dmg`

### macOS 提示“應用已損壞，無法打開”

當前 macOS DMG 尚未使用 Apple Developer 證書籤名和公證。構建配置會顯式生成 unsigned 應用，在 PyInstaller 產物首次執行前清理殘缺簽名，並通過 electron-builder `afterPack` hook 在 DMG 創建前再次清理完整 `.app`；CI 還會檢查 Electron 原始 `.app` 和 DMG 掛載後的 `.app`，阻止再次發佈帶有 `code has no resources but signature indicates they must be present` 等損壞簽名的產物。該處理只能緩解 v3.27.0 的殘缺簽名缺陷，**不會讓應用獲得 Apple 信任**。通過瀏覽器下載後，macOS Gatekeeper 仍可能提示“無法驗證開發者”、阻止啟動，或要求用戶人工確認。

請按以下順序排查：

1. 只從項目的 [GitHub Releases](https://github.com/ZhuLinsen/daily_stock_analysis/releases) 下載附件，並確認安裝包架構與 Mac 一致：Apple 芯片（M1/M2/M3/M4 等）使用 `daily-stock-analysis-macos-arm64-<tag>.dmg`，Intel 芯片使用 `daily-stock-analysis-macos-x64-<tag>.dmg`。不要對第三方轉載或來源不明的安裝包繞過 Gatekeeper。
2. 打開 DMG，將 `Daily Stock Analysis` 拖入“應用程序”後嘗試啟動一次。若被攔截，進入“系統設置 -> 隱私與安全性”，在安全性提示處確認應用名稱，然後點擊“仍要打開”，按系統提示再次確認。較舊 macOS 的對應入口為“系統偏好設置 -> 安全性與隱私 -> 通用”。
3. 僅當安裝包確認來自上述官方 Release、且“仍要打開”仍無法放行時，打開“終端”清除該應用的下載隔離屬性，然後重新啟動：

```bash
xattr -dr com.apple.quarantine "/Applications/Daily Stock Analysis.app"
open "/Applications/Daily Stock Analysis.app"
```

如果應用不在 `/Applications`，請將命令中的路徑替換為實際 `.app` 路徑。不要對整個“應用程序”目錄執行 `xattr`，也不要對來源不明的應用執行此命令。不同 macOS 版本可能仍拒絕 unsigned 應用，清除 quarantine 不保證能夠放行。長期徹底消除該提示需要在發佈流程中接入 Apple Developer 簽名與 notarization（公證），不屬於上述臨時放行步驟。

維護者可用以下命令區分“預期的 unsigned 拒絕”和“不可發佈的殘缺簽名”：

```bash
codesign -d "/Applications/Daily Stock Analysis.app"
spctl --assess --type execute --verbose=4 "/Applications/Daily Stock Analysis.app"
```

當前 unsigned 產物的 `codesign -d` 預期包含 `code object is not signed at all`，`spctl` 預期拒絕；如果輸出 `code has no resources but signature indicates they must be present` 或其它簽名損壞信息，應視為發佈阻斷。

建議發佈流程：

1. 合併代碼到 `main`
2. 由自動打 tag 工作流生成版本（或手動創建 tag）
3. `desktop-release` 工作流自動構建並把兩個平臺安裝包附加到對應 GitHub Release

## 發版前可復現驗證（桌面更新鏈路）

桌面端自動更新鏈路依賴 Windows NSIS 安裝產物、`latest.yml` 與 `*.blockmap` 元數據。當前桌面 CI 不覆蓋 `desktop-release` 打包產物可發佈鏈路，提交前建議補充如下本地驗證：

說明：該清單專注於 Windows NSIS 安裝版與 `electron-updater` 發佈元數據。當前 Linux 環境無法直接產出 Windows 安裝包和 updater 元數據（`latest.yml` / `*.blockmap`），此類鏈路需在 Windows 發佈執行器或 Windows 本機環境複核。

若在非 Windows 環境無法完成上述驗證，請在 PR 驗收說明中明確補齊 Windows 發佈鏈路複核人、複核時間窗及 `desktop-release` 產物檢查結果（release/tag 與 `daily-stock-analysis-windows-installer-<tag>.exe`、`latest.yml`、`*.blockmap` 版本一致性與可下載性）。

1. 先構建 Web 靜態產物（桌面端主窗口與設置頁入口依賴）

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

2. 回到桌面端，補齊依賴、運行 preload 單測、再執行 Electron 打包

```bash
cd ../dsa-desktop
npm ci
npm test
npm run build
```

在 Windows 發佈複核環境，還可額外執行：

```powershell
./scripts/verify-desktop-updater-artifacts.ps1 -ReleaseTag v$(node -p "require('./apps/dsa-desktop/package.json').version")
```

> 預期當前執行環境不支持生成 Windows NSIS 安裝器時，請在交付說明中明確註明平臺限制，並要求指定的 Windows 發佈鏈路複核人補齊該項驗證。

3. 檢查更新元數據是否產出

```bash
ls -1 dist | sort
ls -1 dist/*.yml dist/*.blockmap 2>/dev/null || true
```

4. 強制對齊版本與發佈附件（可在 Windows 環境或能產出 NSIS 產物的執行器上覆核）

```bash
RELEASE_TAG="v$(node -p \"require('./package.json').version\")"
REPO="ZhuLinsen/daily_stock_analysis"

for f in dist/*latest.yml dist/*.blockmap dist/daily-stock-analysis-windows-installer-*.exe; do
  [ -f \"$f\" ] && echo \"[FOUND] $f\"
done

if [ -f dist/latest.yml ]; then
  echo \"---- latest.yml 版本片段 ----\"
  grep -E \"^version:|^files:|^sha512:\" dist/latest.yml
fi

echo \"---- Release 清單（人工核對）----\"
echo \"Release Tag: $RELEASE_TAG\"
echo \"Release 地址: https://github.com/$REPO/releases/tag/$RELEASE_TAG\"
echo \"應核對附件是否包含:\"
echo \"- daily-stock-analysis-windows-installer-*.exe\"
echo \"- latest.yml\"
echo \"- *.blockmap\"
echo \"並確保 latest.yml 中 version 與 tag 的語義化版本一致，path/url 與安裝包附件名一致\"
```

5a. 建議在 PR 描述裡記錄的“可複核輸出”（Windows）：

```bash
echo "release-tag=${RELEASE_TAG}"
echo "latest.yml version:"
grep -E "^version:" dist/latest.yml
echo "latest.yml files:"
sed -n '1,80p' dist/latest.yml
echo "packaging artifacts:"
ls -1 dist/*.yml dist/*.blockmap dist/*installer*.exe 2>/dev/null | sort
```

Windows 發佈鏈路複核清單（在 PR 後由發佈團隊/維護者執行）：

- release/tag 與 `daily-stock-analysis-windows-installer-<tag>.exe` 的版本號一致；
- `latest.yml`、`daily-stock-analysis-windows-installer-<tag>.exe`、`*.blockmap` 同 tag 同步出現且可下載；
- `latest.yml` 中 `version` 與 Release tag 語義一致（去掉 `v` 前綴後比對），且 `path` / `files.url` 與安裝包附件名一致；
- 如缺少上述文件或 `release-tag` 不匹配，需標註阻斷並補齊 `desktop-release` 打包流程。

5. Windows/NSIS 產物與發佈附件一致性請在 Windows 環境手動驗證（可人工觸發發佈流程），並在升級後核對運行時文件留存：

   1. 安裝前後分別記錄安裝目錄中的 `.env`、`data/stock_analysis.db`、`data/stock_analysis.db-wal`、`data/stock_analysis.db-shm`、`logs/desktop.log` 的 SHA256；
   2. 確認桌面端下一次啟動後，上述文件仍存在且與安裝前記錄一致；
   3. 如不一致，可在應用退出後檢查用戶數據目錄中的 `.dsa-desktop-update-backup` 是否清理完整，並結合最新日誌串聯排查。

Windows 平臺建議使用 PowerShell 執行：

```bash
Get-FileHash .env,data\\stock_analysis.db,data\\stock_analysis.db-wal,data\\stock_analysis.db-shm,logs\\desktop.log -Algorithm SHA256
```

說明：應用已在 Windows NSIS 安裝版的“重啟安裝”前停止內置後端、備份安裝目錄旁上述運行時文件，並以靜默模式運行更新安裝器，目的是避免安裝嚮導搶先覆蓋仍在運行的桌面端進程，同時降低更新過程中文件丟失風險；若恢復失敗，桌面端會顯示更新安裝錯誤並保留手動下載路徑供回退處理。此次修復僅改動 Windows 更新安裝鏈路與內置後端進程生命週期處理，不涉及設置保存語義、模型運行時清理策略或配置遷移行為。

### 分步打包

1) 構建 React UI

```bash
cd apps/dsa-web
npm install
npm run build
```

2) 按現有腳本打包 Python 後端（腳本會收集 DSA 選股引擎、Futu SDK 與 AkShare 數據文件）

- Windows：

```bash
powershell -ExecutionPolicy Bypass -File scripts\build-backend.ps1
```

- macOS：

```bash
bash scripts/build-backend-macos.sh
```

macOS 後端打包會顯式加入 `src/services/screening/strategies` YAML 資源目錄；PyInstaller 參數數組迴歸測試通過真實 Bash 驗證隱藏導入與獨立 `main.py` 入口。

該腳本會在安裝依賴後執行 `--collect-all src.services.screening`、`--collect-all futu` 和 `--collect-data akshare`。構建完成後會通過凍結可執行文件校驗 `src.services.screening.pipeline`、`futu`、`orjson` 均可導入，核對選股策略數量，並確認 AkShare 的 `file_fold/calendar.json` 已進入凍結產物，避免發行包在選股、熱點題材、Futu 持倉導入或日線增強路徑中因缺少模塊/package data 降級。選股實現參考 AlphaSift。PR 主 CI 在 `requirements.txt`、Futu broker、Desktop 打包入口或相關 workflow 變化時，會分別運行 `desktop-futu-package-windows` 與 `desktop-futu-package-macos` 阻斷檢查。

3) 打包 Electron 桌面應用

```bash
cd apps/dsa-desktop
npm install
npm run build
```

打包產物位於 `apps/dsa-desktop/dist/`。Windows 安裝器會生成 `daily-stock-analysis-windows-installer-<tag>.exe`，安裝嚮導中可選擇安裝目錄。

## 目錄結構

Windows 安裝包模式下，安裝器僅支持當前用戶安裝且已禁用管理員提權，用戶可在安裝嚮導中選擇安裝目錄；安裝器會在安裝器層面阻止選擇 `Program Files`、`Windows` 等系統保護目錄（選擇時"下一步"按鈕自動禁用），安裝完成後，應用會在安裝目錄旁生成/讀取 `.env`、`data/stock_analysis.db`（含 `data/stock_analysis.db-wal` / `data/stock_analysis.db-shm`）和 `logs/desktop.log`。請保留默認的 per-user 安裝位置或選擇其他用戶可寫目錄。

`win-unpacked` 免安裝模式下，目錄結構如下：

```
win-unpacked/
  Daily Stock Analysis.exe    <- 雙擊啟動
  .env                        <- 用戶配置文件（首次啟動自動生成）
  data/
    stock_analysis.db         <- 數據庫主文件
    stock_analysis.db-wal     <- WAL 日誌文件（更新備份/恢復）
    stock_analysis.db-shm     <- WAL 共享元文件（更新備份/恢復）
  logs/
    desktop.log               <- 運行日誌
  resources/
    .env.example              <- 配置模板
    backend/
      stock_analysis.exe      <- 後端服務
```

## 配置文件說明

- Windows 桌面端的 `.env` 放在 exe 同目錄下
- macOS 打包版的 `.env`、`data/` 和 `logs/` 放在 Electron 用戶數據目錄，避免替換 `.app` 時丟失
- 首次啟動時自動從 `.env.example` 複製生成
- 從舊版本升級時，如果舊 `.app` 包內部的 `.env`、`data/stock_analysis.db` 或日誌文件仍可訪問，新版本會在目標文件不存在時自動遷移到用戶數據目錄；已有目標文件不會被覆蓋
- 用戶需要編輯 `.env` 配置以下內容：
  - `GEMINI_API_KEY` 或 `OPENAI_API_KEY`：AI 分析必需
  - `STOCK_LIST`：自選股列表（逗號分隔）
  - 其他可選配置參考 `.env.example`

### 配置備份 / 恢復 `.env`

- WebUI 與桌面端都可以從 `系統設置 -> 配置備份` 看到 `導出 .env` 和 `導入 .env` 按鈕
- WebUI 非桌面運行時需要先開啟管理員認證並完成登錄；未開啟認證時按鈕會禁用，API 返回 `403`
- `導出 .env` 會導出當前**已保存**的 `.env` 備份文件；頁面上尚未點擊“保存配置”的本地草稿不會被導出
- `導入 .env` 會讀取備份文件中的鍵值併合併到當前配置中，導入後會立即觸發配置重載
- 導入是“鍵級覆蓋”而不是整文件替換：備份文件中出現的鍵會覆蓋當前值，未出現的鍵保持不變
- 如果當前頁面還有未保存草稿，導入前會先提示確認，避免把本地草稿和已保存配置混在一起
- Web 端默認 `ADMIN_AUTH_ENABLED=false` 時，設置頁會展示按鈕為禁用態並提示先啟用管理員鑑權；桌面端不受該配置影響，仍可直接使用配置備份/恢復能力。

> 建議：從舊版本升級的 macOS 用戶仍可在升級前執行一次 `導出 .env` 作為保險；如果舊 `.app` 已經被整體替換，包內舊文件無法憑空恢復，只能通過備份導入。

### 設置頁版本信息

- `系統設置 -> 版本信息` 中的“桌面端版本”由 Electron 主進程的 `app.getVersion()` 提供，並通過 preload bridge 暴露給前端
- 開發態 `npm run dev` 與打包態 `npm run build` / 安裝包都會複用同一條版本注入鏈路，不再在 `preload.js` 裡維護獨立硬編碼版本號
- `README.md` 繼續保留安裝和運行入口說明；這類桌面端運行時細節統一落在本專題文檔維護，避免入門文檔膨脹

### 局域網訪問 Windows 桌面端 WebUI

- 桌面端默認仍按 `WEBUI_HOST=127.0.0.1` 只允許本機訪問，避免安裝後無意暴露後端服務
- 如需讓同一局域網內其他設備訪問，在桌面端 `.env` 或 `系統設置 -> WebUI 監聽地址` 中設置 `WEBUI_HOST=0.0.0.0`，保存後重啟桌面端
- 桌面端會自動選擇 `8000-8100` 中可用端口並傳給後端；常見情況下仍是 `8000`，若端口被佔用，可在 `logs/desktop.log` 查看 `Using port ...` 和 `Backend launch command=...`
- Windows 防火牆或服務器安全組仍需放行實際監聽端口；對外暴露前建議同時啟用 `ADMIN_AUTH_ENABLED`
- 即使後端綁定 `0.0.0.0`，桌面窗口自身仍會使用本機可訪問地址完成健康檢查和頁面加載

### 桌面端更新提醒

- 應用在主界面加載完成後會後臺檢查 GitHub Releases 的最新正式版，並與當前 `app.getVersion()` 做語義化版本比較
- Windows NSIS 安裝版會通過內置 GitHub 更新源自動下載新版本；下載完成後彈出一次性提醒，用戶確認後靜默重啟並安裝
- 自動更新靜默安裝會複用當前安裝目錄；如果用戶安裝時選擇了非默認目錄或帶空格目錄，後續自動更新仍會覆蓋同一目錄
- 桌面運行時會在全局右上角顯示更新入口，可查看狀態、手動檢查、打開 Release 頁或在更新已下載後執行“重啟安裝”；普通瀏覽器 WebUI 不顯示該入口
- `系統設置 -> 版本信息` 中的“桌面端更新”區域仍可作為詳細入口和兜底；全局入口與設置頁共用同一套更新狀態，檢查中、下載中或安裝中時兩側入口都會禁用，不會重複發起手動檢查
- 主進程手動檢查路徑同樣有 in-flight 防重，避免併發請求 GitHub Releases
- Windows 免安裝包、開發態和 macOS DMG 仍保持“提醒 + 跳轉下載頁”的兼容路徑，不會因為網絡失敗而阻斷桌面端啟動
- 版本檢查失敗、GitHub API 超時、更新元數據缺失或下載安裝異常時，會記錄到 `logs/desktop.log`，設置頁或右上角入口手動檢查時會展示錯誤狀態

## 常見問題

### 啟動後一直顯示 "Preparing backend..."

1. 檢查 `logs/desktop.log` 查看錯誤信息
2. 確認 `.env` 文件存在且配置正確
3. 確認端口 8000-8100 未被佔用；桌面端會自動選擇其中一個可用端口，無需通過 `.env` 手動改 `WEBUI_PORT`
4. 如果日誌裡顯示 Electron 等待的端口和後端實際監聽端口不一致，優先升級到包含桌面端端口同步修復的版本

### 後端啟動報 ModuleNotFoundError

PyInstaller 打包時缺少模塊，需要在 Windows 與 macOS 後端構建腳本中同步增加 `--hidden-import`，並對凍結產物執行運行時導入校驗。當前腳本會顯式安裝、凍結並探測 LiteLLM 運行路徑需要的 `orjson`；若日誌包含 `No module named 'orjson'`，請升級到修復版本並重新構建，不能只在已發佈目錄中手工安裝依賴。

如果日誌提示缺少 `akshare/file_fold/calendar.json`，說明後端凍結產物沒有完整收集 AkShare package data。請使用倉庫當前的 `scripts/build-backend.ps1` 或 `scripts/build-backend-macos.sh` 重新構建；腳本會在生成桌面包前檢查該文件，缺失時直接終止構建。

### UI 加載空白

確認 `static/index.html` 存在，如不存在需重新構建 React UI。

### macOS 升級後配置遷移

舊版本曾把運行時 `.env`、數據庫和日誌寫在 `.app` 包內部。新版本改為使用 Electron 用戶數據目錄，並在舊 `.app` 包內文件仍可訪問時做一次性遷移。遷移規則是“目標不存在才複製”，避免覆蓋用戶已經在新版本中保存的配置。

如果舊 `.app` 已經被整體替換，舊包內 `.env` 無法由新版本自動恢復。此時可使用升級前導出的 `.env` 在 `系統設置 -> 配置備份` 中手動導入；完成一次遷移或重新配置後，後續版本會繼續複用用戶數據目錄，不再隨 `.app` 替換丟失。

## 分發給用戶

Windows 分發現在有兩種方式：

1. 安裝包：分發 `apps/dsa-desktop/dist/` 下的 `daily-stock-analysis-windows-installer-<tag>.exe`，用戶安裝時可自行選擇目標目錄
2. 免安裝包：將 `apps/dsa-desktop/dist/win-unpacked/` 整個文件夾打包發給用戶

使用 `win-unpacked` 免安裝包時，用戶只需：

1. 解壓文件夾
2. 編輯 `.env` 配置 API Key 和股票列表
3. 雙擊 `Daily Stock Analysis.exe` 啟動
