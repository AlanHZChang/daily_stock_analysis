# 分享圖片模板與數據填充

分享圖片用於把個股分析和市場覆盤轉換為適合社交平臺傳播的 1080px 長圖。個股和大盤使用兩套獨立的信息結構，但共用 DSA 品牌、倉庫標識 `ZhuLinsen/daily_stock_analysis` 和風險聲明。GitHub 區不放二維碼；Web 與桌面端分享圖默認展示倉庫內置小紅書二維碼及暱稱 `@霸天土小豆`，部署配置可替換二維碼和賬號信息。

## 運行時如何填充

現有通知鏈路不需要手工組裝圖片數據：

```text
個股 AnalysisResult
  -> AnalysisResult.to_dict() 結構化 JSON + 穩定 Markdown
  -> share_image 優先讀取 JSON，Markdown 兼容回退
  -> 個股決策卡 HTML
  -> wkhtmltoimage / markdown-to-file / Playwright 輸出 PNG

大盤 MarketOverview + market_light + LLM 覆盤
  -> MarketAnalyzer 生成 market_review_payload + 穩定 Markdown
  -> share_image 優先讀取 payload，Markdown 兼容回退
  -> 市場覆盤卡 HTML
  -> wkhtmltoimage / markdown-to-file / Playwright 輸出 PNG
```

`MARKDOWN_TO_IMAGE_CHANNELS`、`MD2IMG_ENGINE`、`MARKDOWN_TO_IMAGE_MAX_CHARS` 繼續控制哪些通知渠道轉圖、使用哪個引擎以及最大輸入長度。轉換失敗時仍回退為文本通知。

分享圖需要運行環境提供對應語言字體。官方 Docker 鏡像已內置 Noto CJK 字體；Debian/Ubuntu 源碼部署使用默認 `wkhtmltoimage` 引擎時，應安裝 `wkhtmltopdf fonts-noto-cjk`。如果只安裝轉圖工具而缺少 CJK 字體，中文或韓文可能在 PNG 中消失，只剩數字、英文和邊框。
`fonts-noto-cjk` 是 Debian 字體包名，不代表新增日文報告語言。項目的報告輸出仍只支持 `REPORT_LANGUAGE=zh|en|ko`；日股個股和日本市場覆盤中的日文原生名稱由通用 Noto CJK fallback 覆蓋，頁面語言仍跟隨所選報告語言，不會根據 `7203.T` 或 `region=jp` 切換成未支持的 `ja` 輸出。

小紅書品牌使用以下可選配置。全部留空時展示倉庫內置二維碼及暱稱 `@霸天土小豆`；配置任一自定義值後僅使用這組自定義品牌信息，避免把自定義賬號與默認二維碼混合：

```dotenv
SHARE_IMAGE_XIAOHONGSHU_URL=https://example.com/my-xiaohongshu
SHARE_IMAGE_XIAOHONGSHU_HANDLE=@我的賬號
SHARE_IMAGE_XIAOHONGSHU_QR_PATH=assets/my-xiaohongshu-qr.png
```

二維碼路徑支持絕對路徑或相對項目根目錄路徑；凍結桌面後端也會從 PyInstaller 資源目錄解析相對路徑。賬號 URL 只接受 `http://` 或 `https://`。二維碼在轉圖時以內嵌 Data URI 渲染，不依賴運行時網絡。未配置 `SHARE_IMAGE_XIAOHONGSHU_QR_PATH` 時，統一回退到隨源碼和桌面包分發的 `src/assets/share_image/xiaohongshu_qr.jpg`，因此 Web PNG 與桌面 Electron PNG 都會保留二維碼。二維碼下方固定顯示小紅書暱稱，例如 `小紅書@霸天土小豆`；歷史配置中的數字 ID 不參與分享圖渲染。

## Web 一鍵分享

瀏覽器版歷史個股報告、市場覆盤和完整報告抽屜右上角都會顯示“分享”按鈕。頁面加載報告時不會生成圖片；只有用戶點擊“分享”後，頁面才調用 `GET /api/v1/history/{record_id}/share-image` 按需生成或讀取緩存 PNG。支持文件分享的瀏覽器會在圖片準備好後提示“再次點擊分享”，由第二次點擊同步打開系統分享面板，避免異步生成過程使瀏覽器的用戶激活狀態失效；其他瀏覽器會在首次生成完成後直接下載 PNG。如果系統分享面板打開失敗，除用戶主動取消外也會自動回退下載已經生成的 PNG。

Electron 桌面端同樣展示“分享”按鈕，但不依賴額外分發 `wkhtmltoimage`、`markdown-to-file` 或 Playwright。用戶點擊後，桌面 preload 通過受限 IPC 讓主進程打開本地 `GET /api/v1/history/{record_id}/share-image-html`，使用 Electron 自帶的隱藏 Chromium 窗口按完整頁面高度截圖為 PNG，隨後走與瀏覽器一致的下載回退。IPC 只接受正整數記錄 ID，主進程只允許當前桌面窗口請求本次啟動時確定的後端 origin（包括顯式配置的局域網 `WEBUI_HOST`），HTML 響應使用 CSP 禁止腳本、外部資源和網絡加載。

Web 手工生成不受 `MARKDOWN_TO_IMAGE_CHANNELS` 限制，但服務端仍需配置可用的 `MD2IMG_ENGINE`。桌面端手工生成複用 Electron，不讀取 `MD2IMG_ENGINE`。Web 使用 Playwright 時先執行：

```bash
cd apps/dsa-web
npm ci
npx playwright install chromium
```

結構化數據用於精確填充名稱、動作、評分、價格、寬度和板塊等字段；Markdown 仍負責兼容舊調用以及計劃、風險等文本章節。部分歷史 JSON 只覆蓋其中實際存在的字段，不會清空 Markdown 中已有的行情、技術參考或執行點位。模板不根據分數自行推導操作，也不補造價格或指標。字段為 `N/A`、`-`、空值或沒有對應模塊時，相關卡片自動隱藏。

## 個股卡字段映射

| 圖片區域 | 項目字段 / 生成來源 | 填充規則 |
| --- | --- | --- |
| 股票名稱、代碼 | `AnalysisResult.name`、`AnalysisResult.code` | 直接讀取結構化字段，Markdown 標題僅作回退 |
| 操作、評分、趨勢 | `action_label` / `operation_advice`、`sentiment_score`、`trend_prediction`、`confidence_level` | 使用最終校準結果，評分範圍 0–100，並標明結論置信度 |
| 核心結論 | `dashboard.core_conclusion.one_sentence` | 沒有時隱藏 |
| 市場快照 | `market_snapshot` | 當前/收盤價、漲跌幅、量比、換手率按可用字段展示；數據源進入底部聲明 |
| 執行計劃 | `dashboard.battle_plan.sniper_points` | 只展示理想/確認買入、止損和首個目標價格；複雜觸發條件保留在完整報告 |
| 技術參考 | `dashboard.data_perspective` | 展示均線狀態、趨勢分、MA5 乖離、支撐和壓力；結構化量比/換手已進入快照時不重複展示冗長量能描述，舊記錄缺失結構化量能時仍保留 Markdown 兜底 |
| 下一步觀察 | `dashboard.phase_decision` | 展示行動窗口、下次檢查時間和最多兩條觀察條件 |
| 催化與風險 | `dashboard.intelligence` | `positive_catalysts` 與 `risk_alerts` 最多各展示 2 條短摘要 |
| 持倉建議 | `core_conclusion.position_advice` | 只區分未持倉和已持倉，倉位、建倉、風控長文保留在完整報告 |

模板支持項目當前的中文、英文和韓文報告標籤，海報欄目、指標標籤和底部聲明跟隨報告語言。一個“決策儀表盤”只有一隻股票時會自動使用個股卡；包含多隻股票時保留多股報告佈局，避免錯誤地把第一隻股票當成整份報告。`强烈买入`、`Strong Buy` 等複合動作會保留完整動作標籤。

## 大盤卡字段映射

| 圖片區域 | 項目字段 / 生成來源 | 填充規則 |
| --- | --- | --- |
| 日期、市場範圍 | `MarketOverview.date`、覆盤區域 | 生成 A股/美股/港股/日股/韓股市場覆盤標題；多市場報告逐段匹配 `market_review_payload.markets` |
| 市場信號 | `market_light.score`、`temperature_label`、`label`、`guidance` | 使用確定性市場燈號結果，不由模板二次評分 |
| 指數表現 | `MarketOverview.indices`、`color_scheme` | 最多展示 4 個主要指數的最新值和漲跌幅；結構化 payload 持久化生成時的 `green_up` / `red_up` 顏色語義 |
| 市場寬度 | `up_count`、`down_count`、`limit_up_count`、`limit_down_count`、`total_amount` | 僅在數據源支持且報告包含結構化數據時展示 |
| 信號拆解 | `market_light.dimensions` | 只展示 `available != false` 的確定性評分；不把不支持的維度佔位分 50 當作真實數據 |
| 強弱板塊 | `sectors.top`、`sectors.bottom` | 領漲、領跌各展示 Top 3；沒有板塊榜的市場自動隱藏 |
| 資金觀察 | 覆盤“資金與情緒”章節 | 提煉漲跌比、增量成交和資金風格，不把成交額或新聞推斷偽裝成淨流入 |
| 重點跟蹤 | 覆盤“明日交易計劃”的關注/迴避方向 | 最多各展示 2 個板塊或主題；當前 payload 沒有 `leader_stocks`，因此不編造重點個股 |
| 明日策略 | 覆盤“明日交易計劃”章節 | 展示結論、倉位區間和失效條件，不與重點跟蹤重複 |
| 風險提示 | 覆盤“風險提示”章節 | 最多展示 2 條，過濾重複免責聲明 |

## 手工填充或本地預覽

模板仍接受項目生成的 Markdown；新鏈路會額外傳入 `AnalysisResult.to_dict()` 或 `market_review_payload`。僅調試兼容回退時，可以準備一份最小個股報告：

```markdown
## 🟢 貴州茅臺 (600519)

> 2026-07-31 15:00 | 評分: **72** | 看多

### 📌 核心結論

**買入**: 趨勢偏強，等待回踩支撐後分批執行。

| 持倉情況 | 操作建議 |
| --- | --- |
| 空倉者 | 等待回踩確認，不追高。 |
| 持倉者 | 繼續持有，跌破止損位退出。 |

### 🎯 作戰計劃

| 點位類型 | 價格 |
| --- | --- |
| 理想買入點 | 1420-1450 |
| 次優買入點 | 1380-1400 |
| 止損位 | 1350 |
| 目標位 | 1580 |
```

生成 HTML 預覽：

```python
from pathlib import Path
from src.share_image import ShareImageBranding, build_share_image_html

markdown_text = Path("reports/example.md").read_text(encoding="utf-8")
branding = ShareImageBranding(
    xiaohongshu_url="https://example.com/my-xiaohongshu",
    xiaohongshu_handle="@我的賬號",
    xiaohongshu_qr_path="assets/my-xiaohongshu-qr.png",
)
html = build_share_image_html(markdown_text, branding=branding)
Path("share-preview.html").write_text(html, encoding="utf-8")
```

按真實運行數據預覽時傳入結構化結果：

```python
html = build_share_image_html(
    markdown_text,
    structured_payload=analysis_result.to_dict(),
)
```

實際通知轉 PNG 仍調用：

```python
from src.md2img import markdown_to_image

png_bytes = markdown_to_image(
    markdown_text,
    structured_payload=analysis_result.to_dict(),
)
```

大盤報告應沿用 `MarketAnalyzer` 生成的“盤面信號、指數結構、板塊主線、消息催化、明日交易計劃、風險提示”章節；不建議在外部另造一套字段名稱，否則模板會按缺失字段處理。

## 視覺與內容邊界

- 漲跌顏色優先使用結構化 payload 持久化的 `color_scheme`，舊記錄則從最終報告顏色標記恢復；模板不按市場地區硬編碼漲跌色。
- 分享圖中的買入、止損和目標只保留可掃描的價格或“等待企穩”；完整條件始終保留在原報告中。
- 沒有真實價格序列時不繪製偽 K 線；頂部僅保留非數據化的品牌光暈。
- 小紅書 URL、暱稱和二維碼路徑可由運行時配置覆蓋；二維碼下只顯示暱稱，不顯示數字 ID。全部留空時使用內置暱稱 `@霸天土小豆` 和倉庫內置二維碼。GitHub 固定展示倉庫標識 `ZhuLinsen/daily_stock_analysis`，不生成二維碼。
- 大盤報告在核心模塊已成功提取時不重複附加完整 Markdown；額外的詳情章節保留在原報告中，分享圖只呈現結構化摘要。
- 圖片底部固定說明“AI 生成，僅供研究交流，不構成投資建議”。
