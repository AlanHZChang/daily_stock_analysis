# 實時告警中心

本文檔記錄 Issue #1202 告警中心的運行基線、數據契約、分階段實現範圍和兼容邊界。

## 當前基線

當前運行時告警由 `src/services/alert_worker.py` 中的後臺 worker 統一調度，底層規則評估複用 `src/services/alert_service.py` 與 `src/agent/events.py` 中的 EventMonitor 規則模型。

- 配置入口：`AGENT_EVENT_MONITOR_ENABLED`、`AGENT_EVENT_MONITOR_INTERVAL_MINUTES`、`AGENT_EVENT_ALERT_RULES_JSON`。
- 運行入口：`main.py` 在 schedule 模式中註冊 `agent_event_monitor` 後臺任務；後臺 worker 每輪讀取持久化 active rules，並繼續兼容 legacy `AGENT_EVENT_ALERT_RULES_JSON`。
- 通知投遞：觸發後複用 `NotificationService.send(..., route_type="alert")`，繼續遵守通知網關的 alert 路由配置。
- Web/System 配置校驗：`src/services/system_config_service.py` 會對 `AGENT_EVENT_ALERT_RULES_JSON` 做 JSON 與規則語義校驗。

當前 runtime 支持三類規則：

| `alert_type` | 方向字段 | 閾值字段 | 當前語義 |
| --- | --- | --- | --- |
| `price_cross` | `direction`: `above` / `below` | `price` | 實時價格上破或下破固定價格 |
| `price_change_percent` | `direction`: `up` / `down` | `change_pct` | 實時漲跌幅達到指定百分比 |
| `volume_spike` | - | `multiplier` | 最新成交量超過近 20 日均量的指定倍數 |

`sentiment_shift`、`risk_flag`、`custom` 等類型只作為未來擴展佔位；當前運行時不接受這些類型作為可執行規則。

## Legacy 配置兼容

規則列表現在返回只讀 `rule_sources`：`legacy_configured` 為校驗通過的環境規則條目數，`legacy_effective` 為與啟用數據庫規則按後臺 worker 原有邏輯去重後的環境規則數。它描述未篩選的配置加載結果，不代表輪詢已啟動；重複環境條目可能計入前者，但只計入後者一次。無效條目沿用 worker 的跳過規則。

來源統計保留後臺規則優先級、數據庫與展開目標數量上限及去重語義。持倉目標通過只讀賬本回放獲取，不查詢實時行情，也不重寫持倉緩存、批次或每日快照；同一次列表請求內，相同目標範圍和賬戶的規則複用展開結果，避免重複回放。展開失敗也僅嘗試一次，各規則仍保留獨立失敗載荷和數量佔位。緩存不跨請求，新請求仍讀取最新持倉並重試之前的失敗；列表篩選、翻頁及監控開關不改變這一邊界。後臺輪詢和規則試運行仍使用原有行情與快照加載方式。

Web 檢測到有效環境規則時始終顯示來源提示，即使數據庫列表為空或環境規則當前全部被同條件的啟用數據庫規則覆蓋。頁面刪除、禁用只操作數據庫，不修改環境規則；禁用或刪除數據庫規則後，同條件環境規則可能重新參與輪詢。需要停用環境規則時，在實際部署配置中修改 `AGENT_EVENT_ALERT_RULES_JSON` 並重新加載配置。本次不自動遷移配置，也不改變執行、冷卻或推送語義。

視覺迴歸：在 `apps/dsa-web` 運行 `npx playwright test --config playwright.fixture.config.ts`（無需後臺或登錄口令），使用受控 API 響應驗收數據庫空列表時的桌面/窄屏提示並生成 `test-results/fixtures/**/alerts-sources-*.png`。此測試驗證 UI，不替代後臺真實配置加載迴歸；專題文檔沒有英文對應版本。

`AGENT_EVENT_ALERT_RULES_JSON` 作為 legacy 運行時規則來源繼續保留，不自動遷移、刪除、覆蓋或改寫用戶已有 `.env` / Web 配置。

- 空字符串或空數組表示未配置 legacy 規則；schedule 模式仍會註冊後臺 worker，以便後續 API 創建的持久化 active rules 無需重啟即可被評估。
- Web/System 配置保存時執行嚴格校驗，JSON 無效、字段缺失、方向非法、閾值非法或 unsupported rule type 都應返回配置錯誤。
- 運行時加載時允許跳過單條無效規則，剩餘有效規則繼續工作，避免單條配置破壞整個 schedule 進程。
- 當前 worker 使用進程內 fingerprint 避免持續觸發條件重複推送；這不是告警中心冷卻模型，也不提供跨進程或重啟後的冷卻狀態。

## 數據契約

以下契約用於後續 P1+ API、worker、Web 和存儲實現對齊。P0 只定義字段和語義邊界，不代表當前已經存在這些持久化實體。

### `alert_rule`

可管理的告警規則。

| 字段 | 說明 |
| --- | --- |
| `id` | 規則 ID；legacy JSON 規則在 P0 中沒有持久化 ID |
| `name` | 用戶可讀名稱；沒有提供時可由規則類型和目標生成 |
| `target_scope` | 目標範圍，例如 single symbol、watchlist、portfolio、market |
| `target` | 目標標的或目標引用，例如股票代碼、watchlist ID、portfolio ID |
| `alert_type` | 規則類型；P1 初始只允許 `price_cross`、`price_change_percent`、`volume_spike` |
| `parameters` | 規則參數，例如 `direction`、`price`、`change_pct`、`multiplier` |
| `severity` | 告警等級，例如 info、warning、critical |
| `enabled` | 是否啟用 |
| `cooldown_policy` | 冷卻策略；P0 只定義字段，P4 才實現執行語義 |
| `notification_policy` | 通知策略；默認複用 `NotificationService` 的 alert 路由 |
| `source` | 創建來源，例如 legacy_env、web、api、import |
| `created_at` / `updated_at` | 創建和更新時間 |

### `alert_trigger`

一次真實或可記錄的規則觸發。

| 字段 | 說明 |
| --- | --- |
| `id` | 觸發記錄 ID |
| `rule_id` | 對應規則 ID；legacy env 規則可記錄臨時引用 |
| `target` | 實際觸發目標 |
| `observed_value` | 觀察值，例如現價、漲跌幅、成交量倍數 |
| `threshold` | 觸發閾值 |
| `reason` | 可讀觸發原因 |
| `data_source` | 數據源或 provider |
| `data_timestamp` | 數據時間；缺失時不得偽造為當前時間 |
| `triggered_at` | 觸發時間 |
| `status` | 觸發狀態，例如 triggered、skipped、degraded、failed |
| `diagnostics` | 脫敏後的診斷信息 |

### `alert_notification`

一次觸發對應的通知嘗試。

| 字段 | 說明 |
| --- | --- |
| `id` | 通知嘗試 ID |
| `trigger_id` | 對應觸發記錄 ID |
| `channel` | 通知渠道 |
| `attempt` | 第幾次嘗試 |
| `success` | 是否成功 |
| `error_code` | 結構化錯誤碼 |
| `retryable` | 是否建議重試 |
| `latency_ms` | 耗時 |
| `diagnostics` | 脫敏後的發送診斷，不得包含 token、完整 webhook URL、郵箱密碼或 bot secret |
| `created_at` | 嘗試時間 |

### `alert_cooldown`

規則或目標維度的冷卻狀態。

| 字段 | 說明 |
| --- | --- |
| `rule_id` | 對應規則 ID |
| `target` | 冷卻目標 |
| `severity` | 可選等級維度 |
| `last_triggered_at` | 最近觸發時間 |
| `cooldown_until` | 冷卻截止時間 |
| `reason` | 冷卻原因 |
| `state` | 當前狀態，例如 active、expired |
| `updated_at` | 更新時間 |

## 存儲方案評估

當前倉庫已有 SQLite 存儲層和 repository/service 分層：

- `src/storage.py` 管理 SQLite 連接、SQLAlchemy ORM 模型和 `DatabaseManager`。
- `src/repositories/` 放置數據訪問層，例如 `PortfolioRepository`。
- `src/services/` 放置業務服務層，例如 `PortfolioService`、`PortfolioRiskService`。
- 默認數據庫路徑跟隨現有配置，通常落在 `data/stock_analysis.db`。

P1/P2 實現告警持久化時，推薦優先複用以上模式：在 storage 層定義 alert ORM 模型，在 repository 層封裝 CRUD 和查詢，在 service 層處理規則校驗、評估狀態、通知結果和冷卻語義。P0 不新建表，不改變現有數據庫。

如果後續 PR 需要 schema 變更，必須同時給出：

- 冪等初始化：重複啟動或重複執行初始化時不得破壞已有數據。
- 向後兼容：未配置告警中心時不影響每日分析、問股、通知、大盤覆盤和持倉功能。
- 回滾說明：最小回滾方式至少包括 revert PR；若創建了新表或索引，需要說明是否保留數據、如何手動清理。
- 數據遷移邊界：不得自動遷移、刪除或覆蓋 `AGENT_EVENT_ALERT_RULES_JSON`，除非用戶顯式執行導入動作。

## P1 Alert API MVP

P1 新增後端 Alert API 與 schema，鎖定告警中心最小 API 契約，不接入 Web 頁面或後臺 worker。

- 新增 API 文件：`api/v1/endpoints/alerts.py`。
- 新增 schema 文件：`api/v1/schemas/alerts.py`。
- API 範圍：
  - `GET /api/v1/alerts/rules`
  - `POST /api/v1/alerts/rules`
  - `GET /api/v1/alerts/rules/{rule_id}`
  - `PATCH /api/v1/alerts/rules/{rule_id}`
  - `DELETE /api/v1/alerts/rules/{rule_id}`
  - `POST /api/v1/alerts/rules/{rule_id}/enable`
  - `POST /api/v1/alerts/rules/{rule_id}/disable`
  - `POST /api/v1/alerts/rules/{rule_id}/test`
  - `GET /api/v1/alerts/triggers`
  - `GET /api/v1/alerts/notifications`
- 首版規則仍只支持 `price_cross`、`price_change_percent`、`volume_spike`；`sentiment_shift`、`risk_flag`、`custom` 等未來類型返回結構化 unsupported 錯誤。
- `test` 接口只做一次性 dry-run 評估，不發送通知，不寫入真實觸發記錄或通知 attempt。
- `cooldown_policy` / `notification_policy` 在 P1 中只是保留字段：API 可存儲和返回這些 opaque 配置，但不執行冷卻或自定義通知語義。
- API 響應必須脫敏，不回顯 token、完整 webhook URL、郵箱密碼、cookie、bot secret。
- `AGENT_EVENT_ALERT_RULES_JSON` 繼續保留為 legacy 配置入口；P1 不自動遷移、刪除、覆蓋或改寫 legacy 配置。

P1 不做：

- 不新增 Web 告警中心頁面、路由或側邊欄入口。
- 不讓 schedule worker 加載持久化 active rules，也不實現持久化規則與 legacy JSON 的合併/去重。
- 不實現真實 `alert_trigger` / `alert_notification` 寫入；P1 只提供查詢接口和表結構。
- 不實現 `alert_cooldown` 執行語義。
- 不實現 MACD、KDJ、CCI、RSI、持倉風險或 Market Light 告警規則。

## P2 告警評估 Worker

P2 將 schedule 運行時從啟動時一次性構建 legacy `EventMonitor`，切換為每輪後臺 worker 評估持久化 active rules 與 legacy JSON 規則。

- `AGENT_EVENT_MONITOR_ENABLED` 繼續作為總開關，後臺任務名保持 `agent_event_monitor`。
- worker 每輪讀取 DB 中 `enabled=true` 的 `alert_rules`，並重新解析 `AGENT_EVENT_ALERT_RULES_JSON`；新增 API 規則不需要重啟 schedule 進程。
- DB 規則與 legacy 規則按 `target_scope + target + alert_type + canonical(parameters)` 去重，衝突時 DB 規則優先；legacy 配置不自動遷移、刪除或改寫。
- 每條規則獨立評估，單條失敗只寫 `failed` 評估狀態，不影響同輪其他規則或主分析流程。
- `alert_triggers` 在 P2 用於記錄最小評估歷史：`triggered`、`skipped`、`degraded`、`failed`；正常 `not_triggered` 不寫歷史，避免輪詢刷表。
- 實時行情缺失、字段缺失或非可評估場景記錄 `skipped`；日線數據不可用或結構不完整記錄 `degraded`；診斷信息會脫敏。
- 觸發後仍調用 `NotificationService.send(..., route_type="alert")`；進程內 fingerprint 只避免持續觸發條件重複推送，不執行 `cooldown_policy`。

P2 不做：

- 不新增 Web 告警中心頁面、路由或側邊欄入口。
- 不寫 `alert_notifications`，不記錄 per-channel notification attempt。
- 不實現 `alert_cooldown`、`cooldown_policy` 或 `notification_policy` 執行語義。
- 不實現 MACD、KDJ、CCI、RSI、持倉風險或 Market Light 告警規則。

## P3 Web 告警中心 MVP

P3 在 WebUI 中新增 `/alerts` 告警中心入口，讓用戶不需要直接編輯 legacy JSON 即可管理當前三類運行時規則。

- 側邊欄新增“告警”入口，頁面支持規則列表、分頁、啟停篩選和規則類型篩選。
- 規則創建表單只支持 `single_symbol` 目標範圍和當前已可執行的三類規則：
  - `price_cross`：`direction` 為 `above` / `below`，並填寫 `price`。
  - `price_change_percent`：`direction` 為 `up` / `down`，並填寫 `change_pct`。
  - `volume_spike`：填寫 `multiplier`。
- 規則操作支持啟用、停用、刪除和一次性 dry-run 測試。
- 創建、啟用、停用或刪除規則期間切換篩選或分頁，操作完成後的列表刷新會使用當前篩選條件；創建成功仍會返回當前篩選下的第一頁。
- dry-run 測試只展示 `AlertRuleTestResponse` 已聲明字段：規則 ID、狀態、是否觸發、觀察值和消息；`threshold`、`data_source`、`data_timestamp` 等擴展診斷字段需要後端 schema 明確暴露後再展示。
- 觸發歷史展示 P2 worker 已寫入的 `triggered`、`skipped`、`degraded`、`failed` 記錄；正常 `not_triggered` 仍不會寫入歷史。
- 通知嘗試區域只查詢現有 `GET /api/v1/alerts/notifications`；由於 P2 運行時不寫 per-channel notification attempt，當前通常顯示“暫無通知嘗試記錄”空態，不把觸發狀態推斷為通知投遞結果。
- Web 頁面不暴露 `AGENT_EVENT_ALERT_RULES_JSON` 編輯入口，不自動遷移、刪除或改寫 legacy 配置。

P3 不做：

- 不新增或修改後端 API、schema、storage 或 worker 行為。
- 不實現規則編輯、target/source 高級篩選、watchlist/portfolio 目標、技術指標規則或 Market Light 聯動。
- 不執行 `cooldown_policy` / `notification_policy`，不寫 `alert_notifications`。

## P4 通知結果與持久化冷卻

P4 讓真實告警觸發具備可排障的通知結果，並讓通過 Alert API 創建的持久化規則具備可重啟保持的業務冷卻狀態。

- DB 持久化規則的 `triggered` 歷史按 `rule_id + target + data_source + data_timestamp` 做同一數據點去重：同一觸發事件只保留最早一條 `alert_triggers`，重複輪詢命中會複用已有觸發記錄；`data_timestamp` 缺失時不做去重，避免誤合併無法證明同源的數據點。即使後續被冷卻或通知降噪抑制，仍通過 `alert_notifications` 記錄對應的通知嘗試或 synthetic 抑制狀態。
- `alert_notifications` 記錄真實 per-channel notification attempt，包括 `channel`、`success`、`error_code`、`retryable`、`latency_ms` 和脫敏後的 `diagnostics`。
- 非渠道發送狀態使用 synthetic channel 記錄：
  - `__cooldown__`：告警業務冷卻抑制，`error_code="cooldown_active"`。
  - `__cooldown_read_failed__`：讀取持久化冷卻狀態失敗後，由 worker 進程內臨時兜底抑制，`error_code="cooldown_read_failed"`。
  - `__noise_suppressed__`：通知基礎設施降噪抑制，`error_code="noise_suppressed"`。
  - `__no_channel__`：alert 路由未命中任何可用通知渠道。
  - `__dispatch__`：通知調度級 fallback 或異常。
- cooldown 分層：
  - DB 持久化規則正常路徑使用 `alert_cooldowns` 作為告警業務冷卻，不再由 worker 進程內 fingerprint 決定；僅當讀取持久化冷卻狀態失敗時，臨時使用進程內 fingerprint 防止同一規則在 DB 異常期間每輪重複推送。
  - legacy `AGENT_EVENT_ALERT_RULES_JSON` 規則繼續使用 worker 進程內 fingerprint，不寫 `alert_cooldowns`。
  - `notification_noise.py` 仍作為通知基礎設施層的全局安全網；它不是告警業務 cooldown，且被其抑制時不會寫入或延長 `alert_cooldowns`。
- DB 規則的 `cooldown_policy.cooldown_seconds` 歸一為非負整數；缺失時使用默認 24 小時業務冷卻，`0` 表示關閉 DB 業務冷卻。
- `GET /api/v1/alerts/rules` 會返回只讀 `last_triggered_at` / `cooldown_until` / `cooldown_active` 摘要；`cooldown_active` 由後端按同一冷卻時間語義計算，Web 不在瀏覽器本地解析 naive ISO 字符串來推斷狀態。
- Web 告警中心只讀展示冷卻狀態和通知結果，不提供 cooldown policy 編輯表單。

P4 不做：

- 不新增技術指標、持倉、自選股、portfolio、watchlist 或 Market Light 告警規則。
- 不實現 target-level 跨規則合併冷卻；目標級合併留到持倉/市場聯動階段。
- 不重寫通知渠道網關；`NotificationService.send()` 繼續保持布爾返回兼容，結構化結果通過新增兼容接口提供。
- 不自動遷移、刪除或改寫 legacy `AGENT_EVENT_ALERT_RULES_JSON`。

## P5 技術指標規則

P5 在現有 Alert API、Web 告警中心和 `src/services/alert_worker.py` 評估鏈路中新增日線技術指標規則。規則仍寫入 `alert_rules`，觸發、降級、失敗、通知結果和持久化冷卻繼續複用 P2-P4 的 `alert_triggers`、`alert_notifications` 與 `alert_cooldowns` 語義。

P5 支持的 `alert_type` 與 `parameters`：

| alert_type | parameters | 觸發語義 |
| --- | --- | --- |
| `ma_price_cross` | `direction=above|below`，`window` 默認 `20`，整數 `[2,250]` | close 相對 MA(window) 邊緣上穿/下穿 |
| `rsi_threshold` | `direction=above|below`，`period` 默認 `12`，整數 `[2,250]`，`threshold` 必填且 `0..100` | RSI 相對閾值邊緣上穿/下穿 |
| `macd_cross` | `direction=bullish_cross|bearish_cross`，`fast_period=12`，`slow_period=26`，`signal_period=9`，均為 `[2,250]` 且 `fast_period < slow_period` | DIF/DEA 邊緣金叉/死叉 |
| `kdj_cross` | `direction=bullish_cross|bearish_cross`，`period=9`，`k_period=3`，`d_period=3`，均為 `[2,250]` | K/D 邊緣金叉/死叉 |
| `cci_threshold` | `direction=above|below`，`period` 默認 `14`，整數 `[2,250]`，`threshold` 必填且為有限數值 | CCI 相對閾值邊緣上穿/下穿 |

評估規則：

- 首版統一使用日線 close，不做分鐘線。
- 邊緣觸發只比較最近兩根已收盤日線；非邊緣但當前 level 已滿足閾值時仍返回 `not_triggered`，避免規則創建首日把歷史狀態誤報為新觸發。
- 邊緣觸發包含前一根剛好等於閾值或零軸的情況：`above` / `bullish_cross` 使用 `prev <= threshold < current`，`below` / `bearish_cross` 使用 `prev >= threshold > current`。
- partial bar 只使用服務器本地時區啟發式：當前本地時間早於 16:00 時，最後一行日期等於本地今天或日期不可判定都會保守丟棄；不區分 A 股、港股、美股市場時區或交易日曆。Issue #1386 P0 的市場階段基線暫不接入技術指標規則，告警 partial bar 精確判定留到後續階段。
- `src/services/alert_indicators.py` 自行歸一化 OHLCV 並計算 MA、RSI、MACD、KDJ、CCI，不依賴 fetcher 預計算的 MA5/MA10/MA20。
- RSI 使用 Wilder's EMA / SMMA：`avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()`，`avg_loss` 同理，不使用 rolling SMA。
- MACD 使用 `EMA(fast_period) - EMA(slow_period)` 得到 DIF，DEA 為 DIF 的 `EMA(signal_period)`；金叉/死叉比較 DIF-DEA 相對 0 的邊緣穿越。
- KDJ 使用最近 `period` 日最高/最低價計算 RSV，並用 `alpha=1/k_period`、`alpha=1/d_period` 的 EMA 得到 K/D；金叉/死叉比較 K-D 相對 0 的邊緣穿越。
- CCI 使用典型價格 `(high + low + close) / 3`，按 `period` 日均值和平均絕對偏差計算 `(TP - MA(TP)) / (0.015 * mean_deviation)`。
- `compute_required_bars(alert_type, params)` 定義最少有效 closed bars：MA=`window+1`，RSI=`period+1`，MACD=`slow_period+signal_period+1`，KDJ=`period+k_period+d_period+1`，CCI=`period+1`。
- 拉取天數使用 `requested_days = min(max(required_bars * 3, required_bars + 30), 365)`；API 會拒絕 `required_bars > 365` 的組合週期，避免創建永久樣本不足的規則；同一 worker 輪次按 `(stock_code, requested_days)` 緩存日線數據，輪次結束釋放。
- 缺數據、缺列或有效樣本少於 `required_bars` 寫入 `degraded`；數據源異常沿用 `volume_spike` 語義返回 `evaluation_error` / `failed`，不發送通知。

兼容邊界：

- `AGENT_EVENT_ALERT_RULES_JSON` 仍是 legacy JSON 路徑，只支持 `price_cross`、`price_change_percent`、`volume_spike` 三類規則；P5 技術指標只通過 Alert API / Web 創建。
- 不擴展 `src/agent/events.py` 的 legacy `AlertType` 或 `_RUNTIME_SUPPORTED_ALERT_TYPES`。
- P5 創建/更新參數錯誤沿用現有 Alert API 錯誤契約：HTTP 400 + `validation_error`；unsupported 類型返回 HTTP 400 + `unsupported_alert_type`。
- Web 告警中心只擴展現有創建表單、列表展示、類型篩選和 dry-run 測試，不新增規則編輯器；dry-run 測試不寫觸發歷史，且 API 響應仍沿用 `triggered` / `not_triggered` / `evaluation_error` 三態，worker 寫入的 `degraded` 狀態通過觸發歷史查看。
- 回滾 P5 PR 後，數據庫中已創建的技術指標規則記錄會保留；舊代碼在 worker 加載階段遇到 unsupported `alert_type` 會 skip，不影響 legacy 三類規則繼續執行。如需清理，需要維護者確認後手動刪除相關 `alert_rules` 記錄。

P5 不做：

- 不支持 MACD 柱體放大/收縮。
- 不支持 KDJ 超買/超賣區規則。
- 不支持 MA 與 MA 雙均線交叉。
- 不支持分鐘線、市場日曆精確判定或多市場時區精確 partial bar。
- 不支持 legacy `AGENT_EVENT_ALERT_RULES_JSON` 技術指標規則。
- 不引入 DSL、規則引擎、新數據庫表或分析報告 pipeline 內的技術指標規則引擎。

## P6 持倉與自選股聯動

P6 在現有 Alert API、Web 告警中心和 `src/services/alert_worker.py` 評估鏈路中新增 `watchlist`、`portfolio_holdings`、`portfolio_account` 三類目標範圍。規則仍寫入 `alert_rules`，觸發、降級、失敗、通知結果和持久化冷卻繼續複用 P2-P4 的 `alert_triggers`、`alert_notifications` 與 `alert_cooldowns` 語義，不新增表或遷移。

### P6 scope/type 矩陣

| `target_scope` | `target` | 允許的 `alert_type` | 評估方式 |
| --- | --- | --- | --- |
| `single_symbol` | 股票代碼 | P1 三類價格/成交量規則 + P5 技術指標 | 單規則單標的 |
| `watchlist` | `default` | P1 三類價格/成交量規則 + P5 技術指標 | 每輪刷新並讀取當前 `STOCK_LIST`，按股票代碼展開 |
| `portfolio_holdings` | `all` 或 active account ID | P1 三類價格/成交量規則 + P5 技術指標 | 從持倉 snapshot 的非零持倉展開 symbol，按 symbol 去重 |
| `portfolio_account` | `all` 或 active account ID | `portfolio_stop_loss`、`portfolio_concentration`、`portfolio_drawdown`、`portfolio_price_stale` | 賬戶級風險評估，不展開為單標的 |

創建/更新規則時，`watchlist` / `portfolio_holdings` 不把父級 `target` 當股票代碼校驗；`portfolio_account` 禁止 price/volume/技術指標類型；`portfolio_holdings` 和 `portfolio_account` 在 `target=<id>` 時會校驗賬戶存在且 active，不存在返回 HTTP 400 + `validation_error`。legacy `AGENT_EVENT_ALERT_RULES_JSON` 不支持 watchlist、portfolio 或技術指標擴展，繼續僅支持 `single_symbol` 的 `price_cross`、`price_change_percent`、`volume_spike`。

### Target Identity Contract

P6 將可展示目標與可持久化目標分離：

| 場景 | `effective_target` | `display_target` |
| --- | --- | --- |
| `single_symbol` | `<symbol>` | `<symbol>` |
| `watchlist` 展開子目標 | `<symbol>` | `自選股 - <symbol>` |
| `portfolio_holdings` 展開子目標 | `<symbol>` | `持倉 - <symbol>` |
| `portfolio_account target=all` | `account:all` | `全部賬戶` |
| `portfolio_account target=<id>` | `account:<id>` | `賬戶 <id>` |

- `alert_triggers.target`、`alert_cooldowns.target`、P4 `rule_id + target + data_source + data_timestamp` 去重全部使用 `effective_target`。
- `RuntimeAlertRule.key` 對展開後的子目標使用 `{parent_key}|{effective_target}`，避免 DB cooldown 讀取失敗時的進程內 fallback 把同一父規則下的不同子目標互相 suppress。
- `display_target` 不寫入 `alert_triggers.target`，僅用於通知標題、dry-run `target_results` 和 Web 展示。
- P6 不做跨規則同標的通知合併；同一股票若同時命中 watchlist 子規則和獨立 `single_symbol` 規則，會按每條規則獨立記錄和通知。

### Dry-run 聚合

- `POST /api/v1/alerts/rules/{rule_id}/test` 對批量規則返回聚合字段：`evaluated_count`、`triggered_count`、`degraded_count`、`skipped_count`、`target_results`。
- 展開目標 soft cap 為 100；dry-run 中超過 soft cap 的目標記為 `degraded` 聚合結果並寫日誌。worker 運行時只評估前 100 個展開目標並寫 warning，不為 overflow 本身寫 `alert_triggers` 歷史。
- dry-run 使用受限併發評估，單目標超時 10 秒，總評估超時 30 秒；未完成目標記為 `skipped`。
- 任一目標 triggered 時頂層 `status=triggered`；無觸發但存在成功評估、skipped 或 degraded 時頂層 `status=not_triggered`；無法展開或全部失敗時才返回 `evaluation_error`。
- 空 watchlist / 空 holdings：dry-run 返回 `not_triggered` 並在 `target_results` 中給出 `record_status=skipped`；worker 會寫 `skipped` 歷史。
- `degraded_count` 統計全部展開評估結果中 `record_status=degraded` 的條目；`target_results` 僅展示前 20 條，排序為 triggered 優先，其次 degraded/failed，再按 target 排序。

### 持倉風險規則

| `alert_type` | 參數 | 觀察值 | 觸發語義 |
| --- | --- | --- | --- |
| `portfolio_stop_loss` | `mode=near|breach`，默認 `near` | 受影響標的最大 `loss_pct` | `near` 使用 `stop_loss.near_alert`，`breach` 只統計 `is_triggered=true` 的 items；每賬戶每輪最多一條 trigger |
| `portfolio_concentration` | - | `concentration.top_weight_pct` | `top_weight_pct >= portfolio_risk_concentration_alert_pct` |
| `portfolio_drawdown` | - | `drawdown.max_drawdown_pct` | 複用 `PortfolioRiskService` 的 `drawdown.alert`；`current_drawdown_pct` 寫 diagnostics |
| `portfolio_price_stale` | - | stale/missing 價格持倉數量 | 任一 position `price_stale=true` 或 `price_available=false` |

portfolio diagnostics 必含 `account_id`（或 `all`）、`currency`、`as_of`、`price_stale`、`fx_stale`、`data_available`、`top_affected_symbols`。`portfolio_stop_loss`、`portfolio_concentration`、`portfolio_drawdown` 複用 `PortfolioRiskService.get_risk_report()`；`portfolio_price_stale` 複用 `PortfolioService.get_portfolio_snapshot()` 的 position price metadata。

### Web 與 cooldown 摘要

- Web 創建表單新增目標範圍選擇；`watchlist` / `portfolio_holdings` 只顯示 price/volume/P5 技術指標類型，`portfolio_account` 只顯示四類 portfolio 風險類型。
- `portfolio_holdings` / `portfolio_account` 加載賬戶列表失敗時，表單保留 `all` 選項並展示錯誤。
- 規則列表上的 `cooldown_active` 對 `single_symbol` 和 `portfolio_account` 準確；`watchlist` / `portfolio_holdings` 是父規則摘要，不代表每個子目標的冷卻狀態，子目標冷卻以觸發歷史和 `effective_target` 為準。
- dry-run UI 展示聚合計數和最多 20 條 `target_results` 明細。

P6 不做：

- 不做 P7 Market Light。
- 不做財報日前、分紅除權日前提醒；這類規則需要穩定日期契約後另起 follow-up。
- 不做 sector 級集中度告警；P6 集中度使用 symbol 維度 `top_weight_pct`。
- 不做跨規則同標的通知合併、分鐘線、多市場時區精確判定或 legacy JSON 擴展。

## 階段感知與公開摘要聯動（Refs #1386 P6）

本節描述 #1386 P6 的告警可見性聯動，區別於上面的“P6 持倉與自選股聯動”。本聯動不新增告警表、不做 migration、不自動觸發輕量 LLM 分析，只把觸發當時可公開的 phase/pack 摘要寫入既有觸發歷史。

- `AlertTriggerItem` 保留 `diagnostics` 字符串，並新增派生字段 `market_phase_summary`、`analysis_context_pack_overview`、`analysis_visibility_source`。
- 真實 `status=triggered` 的 worker 記錄會在 JSON diagnostics 中合併 sibling key `analysis_visibility`，包含 `market_phase_summary`、`analysis_context_pack_overview`、`source`。舊純文本 diagnostics 保留原文，API 派生字段返回 `null`，source 返回 `legacy_text`。
- `analysis_visibility_source` 取值為 `alert_trigger_market_context`、`analysis_history_snapshot`、`evaluator_snapshot`、`legacy_text` 或 `null`。
- symbol 目標使用 `get_market_for_stock(normalize_stock_code(effective_target))` 構造觸發時 phase；`target_scope=market` 直接用 `normalize_market_region(target)`，不會把 `cn|hk|us|jp|kr` 當作股票代碼推斷；賬戶級無法唯一定位市場時允許 summary 落為 `unknown`。
- `analysis_context_pack_overview` 只來自 evaluator 已帶 overview 或最近 30 天內的歷史 snapshot。最近歷史查詢複用歷史服務的代碼變體候選，並以 best-effort + 批內短緩存方式執行；缺失或解析失敗返回 `null`，不偽造 pack。
- 告警通知只輸出公開摘要：階段標籤、trigger source、partial-bar warning、數據質量等級和前兩條 limitations。通知不得輸出 raw context pack、Prompt、新聞正文、完整 diagnostics JSON、webhook URL、token 或持倉敏感細節。
- Web 告警歷史展示 phase badge、數據質量等級和 limitations 空態；舊觸發記錄缺少公開摘要時不影響列表讀取。
- #1390 P6 進一步複用 `DecisionSignal`：股票級真實觸發會優先關聯同標的 latest active 信號，並把低敏 `decision_signal_summary` 寫入 diagnostics；無 active 信號時只創建最小 `source_type=alert/action=alert` 信號。`trace_id=alert-rule-<hash>` 只用於同源重試的 best-effort 冪等去重，不覆蓋 active 信號；新建告警信號不寫 `market_phase`，避免同一規則跨階段重複創建。`market`、`portfolio_account`、overflow 或無法解析為具體股票的觸發不會創建個股信號。

DecisionSignal 字段、脫敏、遷移與回滾邊界見 [DecisionSignal 決策信號專題](decision-signals.md)。

#1386 P7 的用戶邊界：告警聯動只解釋觸發時已經可公開的階段和數據質量摘要，不會自動發起輕量 LLM 盤中分析，也不會新增告警表、規則類型、環境變量或 migration。需要階段化分析時，仍應通過分析 API / Web 手動分析入口觸發；告警通知只保留階段標籤、trigger source、partial-bar warning、數據質量等級和前兩條 limitations。

回滾本聯動只需要 revert 對 worker/API/Web 的改動；已有 `diagnostics.analysis_visibility` 會作為普通 JSON diagnostics 保留，舊代碼不會讀取該 sibling key。

## P7 大盤紅綠燈結構化告警

P7 在現有 Alert API、Web 告警中心和 `src/services/alert_worker.py` 中新增 `target_scope=market`，消費結構化 `MarketLightSnapshot`，不解析 Markdown，不擴展 legacy `AGENT_EVENT_ALERT_RULES_JSON`，不新增表。大盤覆盤歷史仍寫一條 `analysis_history(code=MARKET, report_type=market_review)`；多市場覆盤通過 `context_snapshot.market_light_snapshots` 按 region 保存本次實際覆盤的快照 map。

### P7 scope/type 矩陣

| `target_scope` | `target` | 允許的 `alert_type` | 參數 | 觸發語義 |
| --- | --- | --- | --- | --- |
| `market` | `cn` / `hk` / `us` / `jp` / `kr` | `market_light_status` | `statuses=["red","yellow"]`，只允許 `red/yellow`，默認 `["red","yellow"]` | 當前 `MarketLightSnapshot.status` 命中列表時觸發 |
| `market` | `cn` / `hk` / `us` / `jp` / `kr` | `market_light_score_drop` | `min_drop > 0` | `prev.score - current.score >= min_drop`，且 `prev.trade_date < current.trade_date` |

scope/type 校驗是雙向約束：`target_scope=market` 只能使用兩類 Market Light 規則；`market_light_*` 規則也只能使用 `target_scope=market`。`target` 會 `strip().lower()` 後嚴格限定為 `cn|hk|us|jp|kr`，非法 target 返回 HTTP 400 + `validation_error`。

### `MarketLightSnapshot` 契約

結構化快照字段為：`region`、`trade_date`、`status`、`score`、`label`、`temperature_label`、`reasons`、`guidance`、`dimensions`、`data_quality`。`trade_date` 首版固定取 `MarketOverview.date`；P7 不解析 provider quote as-of。

`dimensions` 使用 canonical scorer 單一來源，`build_market_light_snapshot()`、大盤覆盤注入塊和告警 service 不重複實現 scoring。`_build_market_temperature()` 只是 thin wrapper；紅綠燈 `status` 閾值保持 `60/40`，temperature label 閾值保持 `70/55/40`。

| dimension | `available=true` 條件 | fallback score |
| --- | --- | --- |
| `breadth` | `has_market_stats && (up_count + down_count) > 0` | `50` |
| `index` | 排除 `VIX` / `^VIX` 後，至少一個指數的 `change_pct != None` | `50` |
| `limit` | `has_market_stats && (limit_up_count + limit_down_count) > 0` | `50` |

指數維度與中英文「主要指數平均漲跌幅」使用同一份方向性指數數據。VIX 的漲跌幅表示波動率變化，不混入股票指數收益率均值；按 `code` 識別 `VIX` / `^VIX`（忽略大小寫和首尾空白），其原始行情仍保留在報告指數表、模型上下文和結構化 `indices` 中。僅有 VIX、其餘指數漲跌幅均缺失或指數列表為空時，`index.available=false`；普通指數的真實 `0.0` 漲跌幅仍計入均值。評分權重和狀態閾值保持不變。

`data_quality=unavailable` 表示 `index.available=false`，兩類 market rule 都返回 `skipped` 且不觸發通知；`partial` 表示至少一個維度 fallback，`ok` 表示三項均 available。`market_light_status` 在 `ok/partial` 下可觸發；`partial` 觸發時 diagnostics 必含 `missing_dimensions`。`market_light_score_drop` 直接比較 canonical aggregate score；任一側 `partial` 仍允許比較，但 diagnostics 必含 `partial_comparison=true` 和 `missing_dimensions`。

VIX 口徑修復不重寫已有報告或歷史快照。升級後的首次分數下降比較可能使用舊口徑歷史分數；需要完全同口徑的比較時，應以兩個不同交易日按新口徑生成的快照為基線。

### 基線、交易日與去重

- 大盤覆盤持久化必須使用與報告生成共用的同一份 `MarketOverview` 生成 `MarketLightSnapshot`，禁止 persist 階段二次拉行情。
- `load_previous_snapshot(region, before_trade_date)` 掃描 `analysis_history(code=MARKET, report_type=market_review)`，跳過缺少 `context_snapshot.market_light_snapshots[region]` 的 legacy 記錄，先選出小於 `before_trade_date` 的最大 `snapshot.trade_date`，再在同一 `trade_date` 內按 `created_at DESC, id DESC` 取最新 valid 快照；更晚插入的舊交易日 backfill 不會覆蓋正確基線。
- 若目標 `trade_date` 只有損壞快照，`market_light_score_drop` 返回 `degraded`，不會自動退回更舊交易日做 best-effort 比較。
- `market_light_score_drop` 首版只做跨交易日比較；無上一交易日基線或同日基線返回 `skipped`，查詢/解析異常返回 `degraded`。
- worker 對 `target_scope=market` 做 region 交易日 gate，並尊重 `TRADING_DAY_CHECK_ENABLED` / `config.trading_day_check_enabled`；檢查關閉時允許評估，檢查開啟且 region 非交易日時返回 `skipped`，不拉取當前快照。
- 觸發歷史寫 `target=<region>`、`observed_value=<score>`、`data_source=market_light`、`data_timestamp=<trade_date 00:00:00>`，繼續複用 P4 的 `rule_id + target + data_source + data_timestamp` 去重。

### Web 與回滾邊界

- Web 告警中心新增 `market` scope、region 選擇、兩類 market rule 參數控件、類型篩選、region 展示和參數展示；API snake_case 映射使用 `statuses` 與 `min_drop`。
- legacy `AGENT_EVENT_ALERT_RULES_JSON` 不支持 market 規則；P7 不更新 `.env.example`，因為沒有新增配置項。
- P7 不做指數跌幅、板塊異動、漲跌停結構惡化、分鐘線、多市場時區精確 quote as-of 解析，也不新增 DSL/規則引擎。

## P8 用戶配置與部署邊界

P8 不新增規則類型、API、表結構或 worker 行為；它把 P0-P7 已合併能力整理成面向用戶和部署者的配置說明。告警 worker 只在 schedule 模式註冊，核心開關仍是 `AGENT_EVENT_MONITOR_ENABLED`，輪詢間隔仍是 `AGENT_EVENT_MONITOR_INTERVAL_MINUTES`。通知渠道繼續走 alert 路由，詳見 [通知配置](notifications.md) 中的 `NOTIFICATION_ALERT_CHANNELS` 與 `route_type=alert`。

### 本地配置

本地運行 `python main.py --schedule`、`python main.py --serve --schedule` 或等價內置調度模式時，設置 `AGENT_EVENT_MONITOR_ENABLED=true` 後會啟動後臺告警 worker；`AGENT_EVENT_MONITOR_INTERVAL_MINUTES` 控制輪詢間隔。

規則來源有兩類：

- Alert API / Web 告警中心持久化規則：推薦入口，支持 `single_symbol`、`watchlist`、`portfolio_holdings`、`portfolio_account`、`market`，覆蓋實時價、漲跌幅、成交量、日線技術指標、持倉風險與大盤紅綠燈規則。
- legacy `AGENT_EVENT_ALERT_RULES_JSON`：只兼容 `single_symbol` 的 `price_cross`、`price_change_percent`、`volume_spike` 三類基礎規則；不支持 P5 技術指標、P6 watchlist/portfolio 或 P7 market light。系統不會自動遷移、刪除或改寫 legacy JSON。

### Docker

倉庫 `docker/Dockerfile` 默認命令是 `python main.py --schedule`，因此容器內只要配置 `AGENT_EVENT_MONITOR_ENABLED=true` 就會在 schedule 模式中啟用告警 worker。Web/API 持久化規則依賴應用數據庫；Docker 部署時需要保留 `data/` 數據庫卷，避免容器重建後丟失規則、觸發歷史、通知嘗試和冷卻狀態。legacy JSON 仍通過環境變量注入，不是 Docker 專用配置體系。

### GitHub Actions

倉庫自帶 `.github/workflows/00-daily-analysis.yml` 是一次性分析 workflow，實際調用 `python main.py`、`python main.py --market-review` 或 `python main.py --no-market-review`，不運行 `--schedule` 後臺 alert worker，也沒有映射 `AGENT_EVENT_*` 變量。僅在 repository Secrets / Variables 中新增 `AGENT_EVENT_MONITOR_ENABLED` 或 `AGENT_EVENT_ALERT_RULES_JSON` 不會讓默認 Actions 開始持續輪詢告警。

如需 GitHub Actions 裡的告警輪詢，需要後續單獨 PR 明確 schedule 啟動方式、env 映射、規則來源和持久化數據庫策略；P8 不改變現有 workflow。

### Web 與 Desktop

Web 告警中心 `/alerts` 是持久化規則的主要入口：可以創建、啟停、刪除規則，執行一次性 dry-run 測試，查看觸發歷史、通知嘗試和只讀冷卻狀態。批量規則的列表冷卻狀態是父規則摘要，子目標是否冷卻以觸發歷史中的 `target` / `effective_target` 為準。

Desktop 不新增原生告警管理界面；桌面用戶複用內置或外部 WebUI 的 `/alerts` 頁面。Desktop 回滾不需要清理額外狀態。

### 狀態、通知與回滾

worker 會把 `triggered`、`skipped`、`degraded`、`failed` 寫入 `alert_triggers` 作為評估歷史；正常未觸發不寫歷史。`skipped` 表示規則本輪沒有可評估條件，例如 market 非交易日或缺少上一交易日基線；`degraded` 表示數據源、持倉快照、歷史快照或解析過程出現異常，結果不可用於觸發通知。

真實觸發後會寫入 `alert_notifications` 和 `alert_cooldowns`；DB 持久化規則按 `rule_id + target + data_source + data_timestamp` 對同一數據點做 best-effort 去重。legacy JSON 規則繼續只使用進程內 fingerprint，不寫持久化冷卻。

回滾 P8 只需 revert 文檔、配置說明和 Web 文案改動；沒有數據庫遷移或用戶數據清理。回滾早期 Phase 時，已創建的持久化規則不會自動刪除，按下方 Phase 回滾說明處理。

## Phase 邊界

- P0：本文檔、契約、存儲評估和兼容測試。
- P1：Alert API MVP，首版只覆蓋現有三類 runtime 規則。
- P2：告警評估 worker 與 runtime 統一，讓持久化 active rules 與 legacy JSON 共存。
- P3：Web 告警中心 MVP。
- P4：觸發歷史、通知結果與冷卻狀態。
- P5：技術指標規則。
- P6：持倉與自選股聯動。
- P7：大盤紅綠燈與市場聯動。
- P8：文檔、遷移與收口。

## P0 不做

- P0 階段不新增 `api/v1/schemas/alerts.py` 或 Alert API。
- P0 階段不新增 Web 告警中心頁面、路由或側邊欄入口。
- P0 階段不新增數據庫表、repository 或 migration。
- P0 階段不實現觸發歷史、通知結果或冷卻狀態寫入。
- P0 階段不自動遷移、刪除或覆蓋 `AGENT_EVENT_ALERT_RULES_JSON`。
- P0 階段不實現 MACD、KDJ、CCI、RSI、持倉風險或 Market Light 告警規則。
- P0 階段不重寫 `NotificationService` 或通知路由框架。

## 回滾

- P0 是文檔和測試收口。若只回滾 P0，revert 對應 PR 即可；沒有數據庫、配置或用戶數據遷移需要額外處理。
- P1 新增 Alert API 代碼和 `alert_rules` / `alert_triggers` / `alert_notifications` SQLite 表。最小回滾方式是 revert P1 PR；revert 會移除 API、service、repository、schema 和 ORM 定義，但已經由 `Base.metadata.create_all()` 創建的 SQLite 表與數據不會自動刪除。如需清理，需要維護者在確認不再需要歷史數據後手動刪除相關表。
- P3 是 Web 和文檔改動。最小回滾方式是 revert P3 PR；不會刪除已有規則、觸發歷史或 legacy JSON 配置。
- P4 新增 `alert_cooldowns` SQLite 表並開始寫入 `alert_notifications`。最小回滾方式是 revert P4 PR；已經創建的 `alert_cooldowns`、`alert_triggers`、`alert_notifications` 數據不會自動刪除。如需清理，需要維護者確認後手動刪除對應表或記錄。
- P5 新增 Alert API/Web 支持的技術指標規則。最小回滾方式是 revert P5 PR；已創建的 P5 `alert_rules` 記錄不會自動刪除，舊代碼會在 worker 加載階段 skip unsupported `alert_type`，不影響 legacy 三類規則執行。如需清理，需要維護者確認後手動刪除相關規則記錄。
- P6 新增 Alert API/Web 支持的 watchlist、portfolio holdings 與 portfolio account 規則。最小回滾方式是 revert P6 PR；沒有新表或遷移，已創建的 P6 `alert_rules` 會保留。回滾前建議 disable/delete 非 `single_symbol` 的 P6 規則；否則舊 worker 可能把 `watchlist` / `portfolio_holdings` 的父級 `target` 當作股票代碼評估併產生 failed/skipped 噪聲，portfolio 專用 `alert_type` 會在 worker 加載階段被 skip。
- P7 新增 Alert API/Web 支持的 `market` 規則和大盤覆盤 `market_light_snapshots` 歷史快照。最小回滾方式是 revert P7 PR；沒有新表或遷移，已創建的 P7 `alert_rules` 會保留。回滾前建議 disable/delete `target_scope=market` 規則；舊 worker 會 skip unsupported `market_light_*` 類型或因 scope/type 不識別產生配置噪聲。

### 頁面來源提示的視覺驗證

運行 `cd apps/dsa-web && npx playwright install chromium && npx playwright test --config playwright.fixture.config.ts`，使用真實告警頁面與攔截 API fixture，無需後臺或登錄口令。空數據庫仍顯示 2 條有效環境配置、1 條去重後規則及停用邊界；覆蓋 1440px 桌面和 390px 窄屏，無橫向溢出。截圖保存在 `apps/dsa-web/test-results/fixtures/`，由 web-gate 上傳 `web-ui-evidence-<head SHA>` artifact，不入庫。
