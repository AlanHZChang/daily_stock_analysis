# 組合風險與暴露看板

Web 持倉頁新增“風險與暴露看板”，放在組合總覽指標和持倉明細之間，用於提供一眼可讀的組合風險狀態。

## 風險旗標

| 旗標 | 數據來源 | 觸發語義 |
| --- | --- | --- |
| 個股集中 | `risk.concentration` | Top1 個股權重觸發 concentration alert |
| 行業集中 | `risk.sectorConcentration` | Top1 行業權重觸發 sector alert |
| 回撤 | `risk.drawdown` | 當前或最大回撤觸發 drawdown alert |
| 止損 | `risk.stopLoss` | 存在接近或已觸發止損標的 |
| AI 信號 | `risk.decisionSignalRisk` | 存在 sell / reduce / alert 等防禦型建議 |
| 價格質量 | `snapshot.accounts[].positions[]` | 缺價或價格過期 |

## 暴露看板

| 暴露維度 | 聚合方式 |
| --- | --- |
| 市場暴露 | 先將 `position.marketValueBase` 從賬戶基準幣折算到快照聚合幣種，再按 `position.market` 聚合 |
| 幣種暴露 | 先將 `position.marketValueBase` 從賬戶基準幣折算到快照聚合幣種，再按 `position.currency` 聚合 |

權重使用當前快照 `totalMarketValue` 作為分母。快照請求失敗時，看板總市值、持倉數量、明細數量和賬戶數顯示 `--`，匯率狀態不可用，持倉區域提示快照不可用，不將未知數據當作空組合；成功加載的空組合仍顯示零與真正空態。
市場與幣種暴露渲染全部非零分組，不截斷 Top N，保證頁面展示的權重不會因靜默丟棄尾部分組而少於實際覆蓋。
合法零市值賬戶不會阻斷其他賬戶的暴露展示；持倉估值缺失、非有限或為負時，整個暴露降級為不可用，避免靜默丟棄異常持倉。
缺價、過期匯率、缺少換算證據等降級場景顯示“暴露不可用”；成功加載且匯率證據完整的空組合顯示“暫無暴露數據”。

## 邊界

- 數據來自 snapshot 和 risk 響應。snapshot 追加可選字段 `accounts[].totalMarketValueAggregate`（API 原始字段 `total_market_value_aggregate`），複用現有匯率換算結果，表示該賬戶以頂層 `snapshot.currency` 計價的市值；原有賬戶與持倉本幣金額保持不變，無數據庫變更。
- `/api/v1/portfolio/risk` 不可用或返回空風險塊時，依賴服務端風險結果的旗標顯示為“不可用”，不偽裝成“正常”。
- 個股集中度只有在 `topWeightPct`、block-level `alert`、數組 `topPositions` 以及完整有效的 `topPositions` 同時存在時才可用：每行必須有有效 symbol 和有限非負權重，首行權重必須為正；後臺四位小數舍入後的零權重尾行仍有效（繪圖時省略零面積扇區），權重不超過 100，按權重降序排列，首行權重必須與 `topWeightPct` 一致；不得過濾壞行後將另一隻股票冒充 Top1；不得在顯示 `Top1: --` 時宣稱“正常”或“需處理”。`UNCLASSIFIED`、非數組 `topSectors`、無效行業標籤、非 number/非有限/負數的 `weightPct`、`coverage.unclassifiedCount`、`coverage.failedCount` 或行業錯誤表示行業分類覆蓋不完整，不作為完整行業風險展示；`coverage.classifiedCount` 必須為正數，`unclassifiedCount` 和 `failedCount` 必須為零，三個 coverage counter 與 `errors` 數組都必須顯式存在，缺字段也按不可用處理。全未分類、無效行或部分覆蓋時，僅在個股集中度塊自身完整可用時回退到個股餅圖；個股集中度也缺字段時顯示空態，避免把局部 `topPositions` 偽裝成有效圖表。行業行同樣必須按權重降序，首行權重與 `sectorConcentration.topWeightPct` 一致且每行權重不超過 100，允許有效分類的舍入零權重尾行；亂序或不一致時行業旗標/圖表降級，並僅在個股證據完整時顯示個股餅圖。行業風險 badge 與詳情統一使用已校驗的 block-level `sectorConcentration.alert`，不依賴可能缺失或不一致的 top-row `isAlert`。
- 市場與幣種暴露在多賬戶基準幣混合時，使用各賬戶 `totalMarketValueAggregate` 與持倉本幣市值合計的比例，逐賬戶折算後聚合；單一估值幣種兼容舊響應，使用快照總市值與持倉市值合計推算換算比例。僅在 `snapshot.fxStale=false`、每個 `snapshot.accounts[].fxStale=false`，並且所有持倉都顯式滿足 `priceAvailable=true`、`priceSource` 不是 `missing`、`lastPrice` 為有限正數時展示；多基準幣賬戶的換算字段缺失（例如舊版後端）、持倉估值幣種與賬戶基準幣不一致，或任一持倉缺價時，暴露行降級為不可用；有效 CNY/USD 混合賬戶正常展示各市場和幣種金額及權重。個股與行業集中度同樣要求完整價格覆蓋：後端會把缺價持倉用零市值佔位，前端不能據此把剩餘持倉誤報為完整 Top1/行業風險。多基準幣但 FX 和持倉價格證據完整時仍可展示；頂層或任一賬戶 FX stale 時均降級，避免 aggregate 未傳播子賬戶質量時展示 fallback 1:1 產生的錯誤權重或告警。
- 原有持倉明細、集中度餅圖、回撤、止損、AI 風險小卡繼續保留。
- 價格質量使用與集中度、暴露及止損一致的報價校驗：`priceAvailable=true`、`priceSource` 不是 `missing`、`lastPrice` 為有限正數；不滿足時計為缺價，可用但 `priceStale=true` 時計為過期價。同一持倉只按“缺價或過期”計數一次，不額外請求行情；快照不可用時價格質量也顯示“不可用”，不以空持倉誤報為零問題。
- 止損計數只有在當前作用域內每個持倉都顯式滿足 `priceAvailable=true`、`priceSource` 不是 `missing`、`lastPrice` 為有限正數時展示；任一持倉缺價都會讓止損旗標和詳情降級為“不可用”，避免把佔位價 `0` 誤報為觸發止損。歷史收盤價仍屬於可用但可能過期的證據，其時效性由獨立價格質量旗標披露。
- 回撤至少需要兩個估值觀測點且歷史估值未使用 stale/fallback FX；零個、單個觀測點或 `fxStale=true` 都無法形成可靠比較，統一顯示“不可用”。

## 後續擴展

- 按賬戶、行業、貨幣和市場增加可切換暴露視圖。
- 接入 PersonalFinanceCalendar 後，在旗標中顯示即將到期的分紅、財報、期權或融資事件。
- 接入 ResearchArtifact 後，展示每隻重倉股的 thesis 是否被風險旗標觸發。

## 確定性視覺驗證

`cd apps/dsa-web && npx playwright install chromium && npx playwright test --config playwright.fixture.config.ts`
運行真實組合頁面的 mock API 瀏覽器用例，覆蓋完整多市場數據、缺價、快照失敗、錯誤個股/行業 Top1、真實空組合以及合法零權重尾行。
每種狀態生成 1440px 桌面與 390px 窄屏截圖，校驗無頁面橫向溢出。截圖前逐個驗證完整數據、無效行業回退及舍入零尾行的扇區數量與最終 SVG 弧長，避免 Recharts JavaScript 動畫的中間幀進入證據；無有效集中度的狀態必須沒有扇區。
產物在 `apps/dsa-web/test-results/fixtures/`，CI 的 `web-gate` 同步上傳 `web-ui-evidence-<head SHA>` artifact；一次性截圖不入庫。
