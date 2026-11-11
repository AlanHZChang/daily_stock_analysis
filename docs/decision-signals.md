# DecisionSignal 決策信號專題

本頁收口 #1390 P7，說明 DSA 如何把個股分析、Agent、告警和組合風險中的 AI 建議沉澱為可查詢、可反饋、可後驗評估的 `DecisionSignal` 資產。它是報告之上的結構化索引，不替代 Markdown 報告、`operation_advice`、三態 `decision_type`、告警規則或真實交易系統。

## 能力邊界

- `DecisionSignal` 只記錄建議、證據摘要、風險、觀察條件、生命週期和來源，不執行下單或調倉。
- 寫入失敗、提取失敗、告警信號關聯失敗和通知發送失敗都不阻斷主分析、告警觸發或報告保存。
- #1756 已將 `decision_profile` 字段化並修正 server-side filter、去重、續期和 active 失效語義；#1757 在該正式字段契約上增加用戶確認後的 reassess persist。兩者都不新增環境變量、config registry 項或 `.env.example` 內容。
- 當前沒有 `DECISION_SIGNAL_*` 開關；信號功能的關閉或回滾通過 revert 對應代碼完成。

## 字段與枚舉

核心字段由 `api/v1/schemas/decision_signals.py` 定義，主要包括：

- 身份與來源：`stock_code`、`stock_name`、`market`、`source_type`、`source_agent`、`source_report_id`、`trace_id`、`decision_profile`、`trigger_source`。
- 建議語義：`action`、`action_label`、`confidence`、`score`、`horizon`、`market_phase`、`plan_quality`、`status`。
- 計劃與解釋：`entry_low`、`entry_high`、`stop_loss`、`target_price`、`invalidation`、`watch_conditions`、`reason`、`risk_summary`、`catalyst_summary`。
- 證據與質量：`evidence`、`data_quality_summary`、`metadata`。
- 生命週期：`expires_at`、`created_at`、`updated_at`。

枚舉取值：

| 字段 | 取值 |
| --- | --- |
| `market` | `cn`、`hk`、`us`、`jp`、`kr`、`tw` |
| `source_type` | `analysis`、`agent`、`alert`、`market_review`、`manual` |
| `market_phase` | `premarket`、`intraday`、`lunch_break`、`closing_auction`、`postmarket`、`non_trading`、`unknown` |
| `action` | `buy`、`add`、`hold`、`reduce`、`sell`、`watch`、`avoid`、`alert` |
| `horizon` | `intraday`、`1d`、`3d`、`5d`、`10d`、`swing`、`long` |
| `decision_profile` | `conservative`、`balanced`、`aggressive`；數據庫 `NULL` 表示 legacy / unknown |
| `plan_quality` | `complete`、`partial`、`minimal`、`unknown` |
| `status` | `active`、`expired`、`invalidated`、`closed`、`archived` |

Web 展示必須把這些 wire value 映射為當前 UI 語言的用戶可讀標籤；API 響應繼續保留原始枚舉值。

## Canonical 評分與 action 口徑

個股分析、技術評分 fallback、報告展示 fallback 與 `DecisionSignal` 提取共用 `decision-scale-v1` 口徑。`decision_type` 只保留 `buy|hold|sell` 兼容統計；更細的可執行語義以八態 `action` 為準。

- 用戶側可見面存在兩類字段：`operation_advice` 保留文本口徑（如“持有觀察”），`action` 作為統一 8 態決策口徑（如 `hold/watch/reduce`）用於風控、回測與列表展示。新生成或最終保存前重算的個股報告應優先讓兩者保持一致；歷史記錄或兼容載荷仍出現語義衝突時，默認以 `action` 為列表、回測、DecisionSignal 等結構化展示的優先字段，`operation_advice` 僅作說明文本保留。

| score | signal key | `action` | legacy `decision_type` | 語義 |
| --- | --- | --- | --- | --- |
| 80-100 | `strong_buy` | `buy` | `buy` | 強烈買入，高勝率機會，可執行買入/加倉計劃 |
| 60-79 | `buy` | `buy` | `buy` | 偏積極機會，允許少量待確認項 |
| 40-59 | `watch` | `watch` | `hold` | 信號分歧或確認不足，等待觸發條件 |
| 20-39 | `reduce` | `reduce` | `sell` | 風險明顯抬升，優先降低暴露 |
| 0-19 | `sell` | `sell` | `sell` | 趨勢或風險顯著惡化，優先退出 |

如果 `score >= 60` 但最終 `action` 是 `hold/watch`，或 `score < 40` 但最終 `action` 仍是 `hold/watch`，必須有明確 guardrail 解釋，例如 `dashboard.decision_stability.reason`、`dashboard.decision_score_calibration.guardrail_reason` 或 `metadata.guardrail_reason`。風控降級會保留 `raw_score`、`adjusted_score`、`raw_action`、`final_action` 和原因；沒有明確原因的中性動作在 DecisionSignal 提取時會按 canonical score 對齊為 `buy/reduce/sell`。

## 生命週期、去重與狀態

`src/services/decision_signal_service.py` 是信號生命週期的主入口：

- `horizon` 和 `expires_at` 顯式傳入時優先。
- 未傳 `horizon` 時，`alert` 或盤前/盤中/午間休市/集合競價階段默認 `intraday`，盤後、非交易時段、未知階段或缺少階段時默認 `3d`。
- `intraday` 過期時間優先讀取低敏 `metadata.market_phase_summary.minutes_to_close/minutes_to_open`；缺失時按市場 fallback TTL。
- `expired`、`invalidated`、`closed`、`archived` 不能通過 `PATCH /status` 直接恢復為 `active`。
- 同源去重優先使用 `(source_report_id, source_type, market, stock_code, decision_profile, action, horizon, market_phase)`；沒有 report 但有 `trace_id` 時使用 trace 維度。
- `decision_profile` 參與信號身份：`NULL` 只與 `NULL` 匹配，非空 profile 只與相同 profile 匹配。Exact dedup、relaxed dedup、horizon/phase fill、expired refresh、active invalidation 和 stale backfill invalidation 都遵循該 same-profile 語義。
- 新的相反 active 信號只會把同 profile 的舊 active 信號標記為 `invalidated`，並把失效來源寫入 metadata。不同非 `NULL` profile 可並存，即使 action 相反。
- Expired duplicate refresh 不會改寫 `decision_profile`，只能刷新同 profile 記錄。

## API

當前公開接口由 `api/v1/endpoints/decision_signals.py` 和 `docs/architecture/api_spec.json` 描述：

- `POST /api/v1/decision-signals`：創建或按同源鍵去重，返回 `{ item, created }`。
- `GET /api/v1/decision-signals`：分頁查詢，支持市場、股票、動作、階段、`decision_profile`、來源、狀態、時間範圍和持倉過濾。省略或傳空 `decision_profile` 不加 profile 條件，返回所有 profile；`decision_profile=unknown` 查詢 `NULL` 行；合法 profile 精確匹配。
- `GET /api/v1/decision-signals/{signal_id}`：查詢單條。
- `PATCH /api/v1/decision-signals/{signal_id}/status`：更新狀態和可選 metadata。
- `GET /api/v1/decision-signals/latest/{stock_code}`：查詢股票最新 active 信號。
- `POST /api/v1/decision-signals/outcomes/run`：顯式觸發後驗評估。
- `GET /api/v1/decision-signals/outcomes`、`GET /api/v1/decision-signals/outcomes/stats`、`GET /api/v1/decision-signals/{signal_id}/outcomes`：查詢後驗結果與統計。
- `GET/PUT /api/v1/decision-signals/{signal_id}/feedback`：查詢或寫入 useful / not useful 反饋。
- `POST /api/v1/decision-signals/reassess`：基於來源歷史報告快照重新計算不同決策風格下的信號；`persist=false` 只預覽，`persist=true` 由服務端重算並保存通過 guardrail 的結果。

這些接口繼承現有 `/api/v1/*` 管理員鑑權；`ADMIN_AUTH_ENABLED=true` 時需要有效管理員會話 Cookie。

## 決策風格歷史表現

#1758 在現有 `GET /api/v1/decision-signals/outcomes/stats` 響應中追加 `profile_calibration`，沒有新增 endpoint、數據庫表、配置項或行情請求。舊的全局統計字段和八類單維 breakdown 保持原口徑；一條樣本仍是一條 `(signal_id, horizon, engine_version)` outcome 記錄，同一信號的不同覆盤週期會分別計數，不能理解成獨立信號數量。

`profile_calibration.minimum_completed_sample_size` 固定為 `30`，breakdowns 包含：

- `decision_profile`
- `decision_profile_action`
- `decision_profile_horizon`
- `decision_profile_market_phase`
- `decision_profile_data_quality_level`
- `profile_source`

每個 bucket 的 `dimensions` 都是結構化字段，不使用拼接字符串。Profile 校準按以下來源解釋：

- `decision_profile` 讀取關聯信號的當前正式字段；`NULL` 或非法值歸入 `unknown`，不會回退為 `balanced`。
- `profile_source` 讀取關聯信號的當前 metadata，只接受 `auto_default`、`backfill_defaulted`、`legacy_unknown`、`user_selected`，其他情況歸入 `unknown`。這是當前歸因而非 outcome 時點快照，metadata 被合法替換後統計歸屬可能變化。
- `action`、`horizon`、`market_phase`、`data_quality_level` 讀取 outcome 已凍結字段。新建 outcome 時 data quality 優先使用 `data_quality_summary` 的顯式 level；summary 缺失或有效 JSON 中沒有顯式 level 時，才使用規範化後的 `metadata.data_quality_level`。已存在的 outcome 不會被這項讀取規則靜默重寫。

每個 bucket 獨立使用 `completed >= 30` 的門檻，父 bucket、全局樣本或其他 sibling bucket 都不能解鎖它。樣本不足時 counts 仍返回，但 `hit_rate_pct`、`avg_stock_return_pct`、`miss_rate_pct`、`unable_rate_pct`、`max_adverse_excursion_pct` 全部為 `null`；Web 只展示樣本量和“樣本不足，僅供觀察。”。樣本充足時：

- 命中率為 `hit / (hit + miss)`，未命中率為 `miss / (hit + miss)`，neutral 不進入這兩個分母。
- 無法評估率為 `unable / total`。
- 標的平均區間漲跌沿用已有 completed outcome 的 `stock_return_pct` 平均值，不代表策略或組合收益。
- 最大不利波動只使用 outcome 已保存的價格。`buy/add/hold/watch/alert` 按 `(start_price - min_low) / start_price`，`sell/reduce/avoid` 按 `(max_high - start_price) / start_price`，結果不小於 0；價格缺失、非有限或起始價非正時該行不可計算。Bucket 返回可計算行中的最大值；沒有可計算行時為 `null`，不會為補齊指標讀取行情。

Web 在原有“信號表現統計”卡片內提供“保守 / 均衡 / 進取”三個用戶入口，固定默認選擇均衡，並只提供“按建議動作”和“按覆盤週期”兩個細分視圖。它不排名、不推薦風格，也不增加請求、路由、導航或設置項；舊後端沒有 `profile_calibration` 時仍顯示原統計卡片。

## Reassess preview 與 persist

`reassess` 只使用 `source_report_id` 對應的持久化歷史報告快照。`persist=false` 用於用戶確認前預覽；`persist=true` 會以相同 `source_report_id + decision_profile` 在服務端重新計算，不信任之前 preview 或客戶端緩存的任何決策字段。

請求只支持：

```json
{
  "source_report_id": 123,
  "decision_profile": "aggressive",
  "persist": false
}
```

契約邊界：

- `source_report_id` 是唯一事實來源，重評估只讀取對應持久化歷史報告快照。
- Request 只允許 `source_report_id`、`decision_profile`、`persist`。不支持 `signal_id`，也不接受客戶端提交 `action`、`score`、`confidence`、`horizon`、`invalidation`、`stop_loss`、`target_price`、`metadata`、`scoring_breakdown` 或 `guardrail_result` 等權威字段；額外字段會返回 HTTP 422，不會被靜默忽略。
- 重評估不會靜默抓取實時行情，也不會用當前市場數據補齊歷史快照。
- 來源報告內容驗證在 preview/persist 中一致：缺失或非法 `source_report_id` 返回 HTTP 422；報告不存在返回 HTTP 404 `source_report_not_found`；非個股報告返回 HTTP 400 `unsupported_report_type`；持久化快照不足以生成決策信號時返回 HTTP 400 `unsupported_report_snapshot`。Persist 還要求來源報告具有有效 `created_at`，否則返回 HTTP 400 `unsupported_report_snapshot` 且不寫庫；preview 不依賴該存儲生命週期字段。
- data quality 會歸一為 `high`、`medium`、`low`、`poor`、`unknown`，guardrail 只使用歸一化後的等級。
- Preview 成功返回 `preview`、`item=null`、`created=false`；它不寫庫，也不進入列表、latest 或時間線。
- Persist 成功返回 `preview=null`、後端權威 `item` 和 `persist_status`。`persist_status=created` 表示新建；`existing` 表示同一字段化 identity 的記錄已存在且未被改寫；`refreshed` 表示按既有 expired refresh / dimension-fill 語義複用並刷新記錄。兼容字段 `created` 只在 `created` 時為 `true`。`persist_status` 只描述本次寫入 disposition，不代表 `item.status` 必然為 active；新建的歷史信號也可能因到期或被較新相反信號取代而以 `expired/invalidated` 返回。
- Reassess persist 與 lazy backfill 使用同一歷史生命週期：`created_at` 錨定來源報告時間，`expires_at` 從報告時間、horizon、market 及持久化的 `market_phase_summary` 計算。階段摘要只保留 `phase/session_date/minutes_to_open/minutes_to_close`；不會用保存當天或實時行情重新賦予有效期。
- 同 profile 相反信號的失效順序同樣按歷史信號不可變的 `created_at` 判斷，expired refresh 的 `updated_at` 不改變歷史優先級。保存舊報告不得淘汰較新的相反信號；仍在有效期內但已被較新相反信號取代的歷史 item 會以 `invalidated` 返回，且 API 返回失效處理後的最終數據庫狀態。
- `created` item 寫入 `source_type=analysis`、原 `source_report_id`、`source_agent=decision_profile_reassess`、`trigger_source=web:decision_profile_reassess` 和正式 `decision_profile`；metadata 保存 `profile_source=user_selected`、`profile_policy_version`、`signal_generation_version`、`scoring_version`、`scoring_breakdown`、`data_quality_level` 和完整 `guardrail_result`。
- `existing` item 原樣保留最初的 source fields 和 metadata。例如普通分析已經自動生成同 identity 的 `balanced/auto_default` 信號時，用戶再次確認 balanced reassess 會返回該記錄，不覆蓋為 `user_selected`，也不會聲稱新建成功。終態 existing 不會重新激活。
- `refreshed` item 保留不可變的原始創建 provenance（`source_type`、`source_report_id`、`source_agent`、`trigger_source`、`created_at` 等），並沿用 #1756 repository 的兩個既有子語義：expired refresh 會更新允許變化的決策字段、有效期和本次 reassess audit metadata；active relaxed dimension-fill 只補齊缺失的 horizon/market phase，保留原 metadata。客戶端必須以後端返回 item 為準，不能僅憑 `refreshed` 推斷 metadata 已被替換。
- `guardrail_result` 是機器審計數據，記錄 `raw_action`、`final_action`、`passed`、`violations`、`adjustments`、`adjusted`；`warnings` 是用戶可讀摘要。測試和客戶端邏輯應優先依賴 warning 的穩定 `code`，`message` 只用於首版展示。
- `MIN_ACTIONABLE_CONFIDENCE = 0.5`。所有 `buy/add` 還必須具備 horizon、invalidation 或 stop loss、合法價格關係，且 data quality 不能是 `poor/unknown`；aggressive `buy/add` 額外要求明確 invalidation，且不接受 `long` horizon。
- 缺失置信度/invalidation 或數據質量不足時，可審計地降級為 `watch`，並記錄 `passed=true, adjusted=true`。價格關係互相矛盾時無法在不改寫歷史快照語義的前提下保存有效計劃，因此記錄 `passed=false`。
- Preview-only 的 `passed=false` 仍以 HTTP 200 展示，UI 必須突出 `blocked_reason`。Persist 重算得到 `passed=false` 時返回 HTTP 400 `guardrail_blocked`，包含 `blocked_reason` 和結構化 `warnings`，不寫庫，也不返回 `created=true`。
- 每次 persist 重算都必須先滿足 `guardrail_result.passed=true` 才能進入寫入鏈；`created/refreshed` 的 `item.action` 等於本次 `guardrail_result.final_action`。`existing` 返回原記錄及其原始 metadata，不偽造本次 guardrail audit。
- 默認分析和 lazy backfill 仍只自動生成 `balanced`；用戶可顯式選擇並確認保存 balanced、conservative 或 aggressive，其中 conservative/aggressive 不會自動生成。
- aggressive 不是模型採樣溫度語義，也不會自動生成三套 profile 信號。

## Web 展示

Web 入口位於 `/decision-signals`：

- 默認查詢 `status=active`。
- 頁面頂部提供頁面級“當前股票”主路徑，獨立於高級列表篩選。用戶提交主股票、選擇自動補全候選或點擊候選 chip 後，latest active 與時間線共用同一個已應用股票上下文；只修改輸入草稿不會觸發 latest 或時間線查詢。
- 當前股票候選優先展示最近分析過的股票；如果沒有歷史候選，或歷史候選加載失敗，則降級展示股票索引中 active 且 popularity 較高的熱門股票。候選只作為手動點擊入口，頁面加載時不會自動提交查詢；歷史和股票索引都不可用時僅顯示無候選降級文案。
- 當前股票上下文會顯示已應用的代碼、名稱和可推導市場，並提供清空入口。清空會讓 latest 與時間線回到引導態，不影響高級列表篩選或列表來源詳情抽屜。
- 支持按市場、股票代碼、動作、市場階段、來源、來源報告 ID 和狀態進行高級列表篩選；這些篩選不等同於當前股票上下文，也不會汙染 latest active 查詢。
- 單支股票信號時間線複用現有 `GET /api/v1/decision-signals` list API，不新增 timeline endpoint。時間線必須先應用非空當前股票後才會查詢；沒有當前股票時只顯示引導態，不拉取 market-only 或 global timeline。
- 時間線只支持 `30d`、`90d`、`180d` 三個時間範圍，默認 `90d`；每次最多請求 100 條。若返回 `total > items.length`，Web 會顯示“僅展示最近 100 條信號，請縮小時間範圍”，避免靜默展示不完整軌跡。
- 時間線篩選保留獨立的 market、range、status 表單和查詢按鈕。選擇新當前股票時，如果能推導市場，只在這一次初始化時間線 market；用戶之後可以手動改 market，查詢以按鈕提交時的表單快照為準。
- 時間線 status filter 只支持 `all` 與 `active`：`all` 不傳 `status`，`active` 傳 `status=active`。P1 不提供 terminal status filter，也不做前端 terminal 過濾。
- 時間線支持 profile filter，複用 list API 的 server-side `decision_profile` 查詢；`unknown` 只用於篩選和展示 legacy `NULL` 行。普通高級列表不新增 profile filter。
- 信號表現統計保持全局已覆盤 outcome 口徑，不等於當前可見信號數量，也不隨當前股票或高級列表篩選變化；當已覆盤樣本數為 0 時，Web 顯示零樣本空狀態而不是一組 `0/-` 指標。
- Web 展示優先讀取正式 `decision_profile` 字段，只有字段缺失時才回退 legacy metadata；歷史缺失或非法 profile 的信號顯示為 `unknown`，不會誤標為 `balanced`。
- market filter 在 API / 服務層與 Web 前端均已支持 `cn/hk/us/jp/kr/tw`；`jp/kr/tw` 的前端本地化標籤均已補齊，`tw` 信號可經 API 正常寫入、按 `market=tw` 查詢，並可在 Web DecisionSignal 頁面通過市場篩選項選擇臺股（tw）；告警（大盤紅綠燈）市場支持 `cn/hk/us/jp/kr`。
- 詳情抽屜展示動作、狀態、評分、置信度、週期、計劃質量、市場階段、價格計劃、風險、觀察條件、證據、數據質量和 metadata。
- 詳情抽屜或已有來源報告 ID 的頁面上下文可以發起 reassess preview；沒有可用來源報告 ID 時入口禁用。Preview 本身不加入列表、latest 或時間線；通過 guardrail 後可由用戶二次確認保存。保存會重新請求 `persist=true`，成功後只使用響應中的後端 `item`；`created`、`existing`、`refreshed` 使用不同反饋，existing 不會被描述為新建，終態 existing 不會被樂觀注入 active latest/時間線，created/refreshed 才按返回狀態更新並刷新相關視圖。Web 不會把 preview 拼成本地信號。
- 保存時的 guardrail 調整 warning 會保留顯示。如果 persist 重算被 guardrail 阻斷，Web 會顯示 `blocked_reason` 和結構化 warning，保留 preview 供用戶理解，且不會把失敗結果加入時間線。
- 首頁分析表單不提供 `decision_profile`；默認自動生成路徑仍只使用 `balanced`。
- Web 只能把信號標記為 `closed`、`invalidated` 或 `archived`，不提供 terminal 狀態恢復為 active。
- 歷史報告詳情不再內嵌展示報告綁定的 `source_type=analysis` 信號，也不會因打開報告詳情觸發 `source_report_id` 信號查詢；需要查看報告來源信號時統一進入 `/decision-signals` 頁面按來源報告 ID 精確篩選，或打開 `/decision-signals?sourceReportId=<recordId>` deep link。該篩選和 deep link 都會使用 `source_type=analysis + source_report_id` 的精確查詢，以保留舊報告的 best-effort 懶回填入口。
- 持倉頁異步查詢每個唯一持倉的 latest active 信號，單隻查詢失敗只顯示降級提示，不阻斷組合快照或其他持倉信號。

所有用戶可見枚舉必須使用 i18n 標籤；技術 ID、股票代碼、API 字段名、env key、URL 示例可以保留英文。

## Decision profile identity

#1756 後 `decision_profile` 是 `decision_signals` 的正式 nullable 字段，同時 metadata 保留兼容字段：

- `decision_profile=balanced`
- `profile_source=auto_default`：普通新分析生成路徑。
- `profile_source=backfill_defaulted`：歷史報告 lazy backfill 路徑。
- `profile_policy_version=decision-profile-v1`
- `signal_generation_version=legacy-report-extractor-v1`
- `decision_signal_metadata_version=decision-signal-metadata-v1`

- 新寫入時，頂層合法 `decision_profile` 優先；頂層顯式 `null`、空值或非法值直接拒絕。頂層缺失時才 fallback 合法 `metadata.decision_profile`；二者都缺失或 metadata profile 非法時默認寫入 `balanced`。
- 新寫入會同步 `metadata.decision_profile` 為正式字段值，避免雙源衝突；metadata 省略或顯式 `null` 均按無 metadata 處理，object 會淺複製，非 object 會被拒絕。
- PATCH metadata 省略時保留原值，顯式 `null` 時清空為 SQL `NULL`，object 時整包替換。正式 profile 非 `NULL` 時會覆蓋 metadata 中的衝突值；正式 profile 為 legacy `NULL` 時會移除請求 object 中的 profile key，且不會提升正式字段。
- 自動失效寫入同樣遵循正式字段權威語義：正式 profile 非 `NULL` 時同步 metadata profile；legacy `NULL` 時只追加失效信息，保留原 legacy metadata，不注入或刪除 profile。
- Legacy / unknown 只用數據庫 `NULL` 表示。普通自動生成與 lazy backfill 不寫入 `scoring_version` 或 `scoring_breakdown`；只有用戶顯式發起的 reassess 路徑根據 profile policy 生成並審計這些字段。這不代表自動生成三套 profile，也不包含 #1758 的 profile-aware outcome calibration。
- Lazy backfill 語義：省略 profile 保留舊的 `source_type=analysis + source_report_id` 懶回填；`decision_profile=balanced` 可生成 balanced 回填；`decision_profile=unknown`、`conservative`、`aggressive` 不自動創建行。回填與 reassess persist 共享來源報告時間、歷史 TTL 和 superseded 判斷，不存在第二套歷史生命週期。

## 市場結構 metadata

普通個股分析和 Agent 個股分析如果攜帶 `market_structure_context`，自動提取 `DecisionSignal` 時會把以下低敏字段追加到 metadata：

- `market_structure_version`
- `market_theme_version`
- `stock_market_position_version`
- `market_structure_status`
- `primary_theme`
- `theme_phase`
- `stock_role`
- `market_structure_risk_tags`

這些字段只用於解釋信號所處題材背景，不參與 `action`、`score`、`horizon`、同源去重鍵或生命週期計算。它們也不是題材龍頭證明；當 `market_structure_risk_tags` 或缺失證據顯示成分股、leader stocks 不完整時，客戶端和後驗分析應按降級題材證據處理。

快照字段中的 `provider` / `dataset` 來自市場結構抽取鏈路元數據，屬於運行後持久化證據，不參與 LLM provider/model 路由、`base URL` 解析、`.env` 寫回或配置遷移；可核驗範圍見 `src/schemas/market_structure.py`。

## 告警、通知與組合風險

- 股票級真實告警觸發會優先關聯同標的 latest active 信號，並把低敏 `decision_signal_summary` 寫入 `alert_triggers.diagnostics`。
- 沒有 active 信號時，告警 worker 只創建最小 `source_type=alert/action=alert` 信號。
- 告警信號的 `trace_id=alert-rule-<hash>` 只用於同源重試的 best-effort 去重，不覆蓋 active 信號本體。
- 通知只引用公開摘要字段：`action`、`horizon`、`reason`、`watch_conditions`、`risk_summary`、`source_report_id`。
- 通知中的 `reason` 在脫敏後完整展示，避免固定字符數在句中截斷；`watch_conditions` 和 `risk_summary` 仍保持緊湊摘要上限。
- 通知不得輸出 signal `metadata`、`evidence`、raw diagnostics、webhook URL、token 或 cookie。
- `GET /api/v1/portfolio/risk` 的 `decision_signal_risk` 只統計當前持倉中的 active `sell/reduce/alert` 信號，查詢失敗時 fail-open。

更多告警和通知細節見 `docs/alerts.md` 與 `docs/notifications.md`。

## 後驗評估與反饋

P5 通過 sidecar 表保存用戶反饋和後驗結果，不擴展 `decision_signals` 主表：

- `decision_signal_feedback` 保存每個信號最新的 `useful|not_useful` 反饋、可選原因/備註和來源。
- `decision_signal_outcomes` 按 `(signal_id, horizon, engine_version)` 冪等保存後驗評估結果。
- 當前 `engine_version=decision-signal-v1`。
- 後驗評估只支持日線可驗證的 `1d/3d/5d/10d`；`intraday/swing/long`、非方向動作、缺價和 forward bars 不足會寫入 `eval_status=unable` 與明確 `unable_reason`。
- 評估時凍結 action、market、market_phase、source_type、source_agent、plan_quality、data_quality_level、holding_state 等統計維度，歷史統計不依賴後續 live join。

## 單票覆盤摘要（ReviewMemory）

#1903 在 P5 後驗數據之上增加只讀、低敏的單票覆盤摘要，把"已計算但從未被消費"的 outcome/feedback 聚合回 Agent 記憶，形成結果層反饋閉環：

- 只讀接口 `GET /api/v1/decision-signals/stocks/{stock_code}/review`（可選 `horizon=1d/3d/5d/10d` 過濾）返回 `DecisionSignalReviewMemory` 契約：`stock_code`、`scope`、`sample_size`、`completed`、`hit_rate_pct`、`avg_return_pct`、`common_miss_reasons`、`confidence_adjustment`、`notes`；聚合在 `decision_signal_outcome_service.py` / `decision_signal_outcome_repo.py` 完成，不進入 agent 層。
- 低敏邊界：契約只含聚合值與 feedback `reason_code` 標籤，不暴露 raw evidence、prompt 文本、診斷信息、持倉或 feedback 備註原文。
- 保守判定：completed 樣本 < 10、unable 率 > 50%、或主導數據質量為 `low/poor` 時，`confidence_adjustment` 固定為 `observe` 且 `notes` 給出原因提示，不產生任何置信度偏移；樣本充足時按命中率給出 `upgrade`（≥60%）/`downgrade`（≤40%）/`neutral` 方向建議，仍僅供觀察。
- Agent 消費：`AGENT_MEMORY_ENABLED=true` 時，`AgentMemory.get_decision_signal_review()` 讀取該預摘要，`BaseAgent` 以獨立的 `[Memory: decision-signal review]` section 注入 prompt（不混入 AnalysisHistory 文本），並附帶"僅供觀察、不作為買賣強度依據"聲明；flag 關閉時全鏈路行為與此前完全一致。
- 不改變 DecisionSignal 非交易邊界：歷史命中率不得變相成為倉位或買賣強度信號。

## 脫敏與低敏邊界

信號寫入和狀態更新使用 `src/utils/sanitize.py` 中的 `sanitize_decision_signal_text()` 與 `sanitize_decision_signal_payload()`：

- 文本字段、JSON 字段和展示型短文本寫入前會脫敏。
- 覆蓋敏感 key、Bearer、Authorization/Cookie header 或賦值、token-like 字符串、webhook URL、URL userinfo，以及帶敏感 query/fragment 參數的 URL。
- 普通證據 URL 會保留，保證來源可追溯。
- `trace_id` 是同源去重身份字段；如果包含會被脫敏的 credential，API 會拒絕請求，而不是保存被 redaction 破壞後的身份值。
- Web 的 JSON 展示只顯示後端已脫敏數據，不應重新拼接 raw diagnostics 或配置值。

P7 的全局驗收是確認信號池、通知摘要和 Web 展示不洩露 token、cookie、webhook URL、API key、郵箱密碼等敏感信息。

## 遷移與回滾

#1756 對 SQLite 執行非破壞性 migration。

遷移說明：

- 升級後無需新增 `.env`、`.env.example` 或 Web 設置項。
- Existing SQLite 只在缺列時 `ALTER TABLE ADD COLUMN decision_profile`，不會 drop/rebuild `decision_signals`，也不會刪除舊 index。
- Migration 會冪等創建 profile-aware indexes，並 row-by-row 防禦解析 `metadata_json`：僅合法 `metadata.decision_profile` 回填到正式字段；invalid JSON、非 object 或非法 profile 保持 `NULL`。啟動日誌會記錄 backfilled、invalid JSON、non-object、invalid profile 和 skipped existing profile 統計，這些統計只用於診斷，不阻斷啟動。
- 舊歷史報告不會批量回填。只有顯式調用信號列表接口或在 Web AI 建議頁按來源報告 ID 觸發精確查詢 `source_type=analysis + source_report_id` 且無命中時，才會 best-effort 懶回填。
- 已存在的 `decision_signals`、feedback 和 outcome 數據保持兼容。

回滾說明：

- 當前沒有 `DECISION_SIGNAL_*` 開關；關閉信號提取/寫入的回滾方式是 revert 相關代碼。
- 回滾後，普通報告保存、告警觸發、通知發送和組合風險主流程仍按既有路徑運行。
- 回滾不會自動刪除歷史 `decision_signals`、`decision_signal_feedback` 或 `decision_signal_outcomes` 數據；如需清理，應由維護者單獨制定數據清理策略。
