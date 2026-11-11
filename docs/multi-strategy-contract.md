# 多策略投資建議契約：Baseline 語義、Phase 1 收斂、Phase 2/3/4 邊界

本頁是 Issue #1964「多策略投資建議」的專題文檔，用於記錄 2 個及以上策略/技能（skill）觀點在系統內的**語義收斂邊界**：有效證據集合、無效觀點隔離、陣營分組、共識度、跨消費面一致性。Baseline 負責契約邊界和現狀盤點；Phase 1 只在 Baseline 契約內完成有效證據集合分揀、`strategy_synthesis` 確定性合成、DecisionAgent prompt 收斂、四條 renderer 一致性以及 E2E 反例覆蓋；Phase 1.5 在 Phase 1 契約上新增受控協同推理 v0（mediator_v0），只記錄衝突議題、策略回應、softened 修正和置信度折減原因；Phase 1.6 新增可注入 LLM mediator v1（llm_mediator_v1），只允許 schema 合法的結構化修訂，並在缺失、異常或越界時回退 v0；Phase 1.7 新增可注入 strategy self-review v2（self_review_v2），只允許衝突參與策略按固定 schema 自審，並在任一參與方越界時整輪迴退 baseline；Phase 1.8 新增修訂投影 v3（revision_projection），只預覽採納 softened 修訂後的綜合信號、置信度和衝突狀態，不覆蓋權威 `final_signal`；Phase 1.9 新增可配置多輪協同推理 v4（multi_round_v4），按 `max_rounds` 繼續結構化修訂並保留 `round_history`，任一輪越界時回到上一輪已驗證結果；Phase 2 只在 Phase 1/1.5/1.6/1.7/1.8/1.9 契約下新增 2–4 策略併發調度與階段調度；Phase 3 只在 Phase 2 之上補前端多語言完整展示；Phase 4 只在同一 `CONTRACT_VERSION = "1.0"` 內補真實 Skill Outcome 權重反饋閉環。Baseline 的所有約束對後續 Phase 均永久生效，Phase N 不得靜默降級 Baseline 中已經寫死的邊界。

## Skill opinion 樣本邊界（Issue #1904 P2 PR1）

`AgentRuntimeFacts.skill_opinions` 只投影 individual SkillAgent 的低敏字段：`skill_id`、canonical `signal`、`confidence` 和 opinion 時間。`skill_consensus` / `strategy_consensus`、DecisionAgent、基礎 Agent 以及 Invalid Opinion 均不得進入該集合；同一次運行出現同一 `skill_id` 的多條有效觀點時，只保留最後一條。SkillAgent 首次解析時必須拒絕非數字、非有限或超出 `[0, 1]` 的 confidence；AgentOpinion 保留輸入合法性標記供 RuntimeFacts 防禦校驗，禁止將非法輸入 clamp 後作為有效樣本繼續使用。

分析歷史成功保存後，Pipeline 以 best-effort 方式寫入 `skill_opinion_samples` sidecar。父歷史存在性檢查與樣本插入必須位於同一個 SQLite 原子寫事務中，歷史刪除複用相同的寫事務與 locked retry；無論插入或刪除誰先執行，均不得留下孤兒樣本。冪等鍵為 `(analysis_history_id, skill_id, sample_schema_version)`；重複執行不得覆蓋首次保存的不可變樣本。寫入失敗只記錄低敏錯誤類型，不得使報告、歷史記錄或 DecisionSignal 主流程失敗。

當前 `sample_schema_version=skill-opinion-sample-v1`。`skill_version` 與 `horizon` 僅保留為空值兼容位：現有 Skill 定義和 SkillAgent 輸出沒有可信的版本與週期契約，因此本階段不得從 LLM `raw_data` 猜測或偽造。PR1 不創建 outcome、不提供 skill 表現統計、不實現 `get_skill_summary()`，也不改變 `AgentMemory` / `SkillAggregator` 權重。

## Skill Opinion Outcome 邊界（Issue #1904 P2）

`skill_opinion_outcomes` 表示一條不可變 `skill_opinion_sample` 在一個 `horizon`、一個 `engine_version` 下的獨立後驗結果，唯一鍵為 `(skill_opinion_sample_id, horizon, engine_version)`。初始 horizon 僅允許 `1d`、`3d`、`5d`、`10d`；每次運行的 `limit` 限制待處理的 `sample × horizon` outcome key 數量，不是 sample 數量。顯式空 horizons、空白 skill/stock 篩選和越界 limit 必須 fail closed，不得退化為全量運行。

每條 outcome 只使用 sample 自己的 canonical `signal`，不得讀取最終 Agent decision、`skill_consensus` 或其他 skill 的 signal。`strong_buy` / `buy` 按 bullish 評價，`strong_sell` / `sell` 按 bearish 評價；方向收益嚴格大於零才是 `hit`，零收益是 `miss`。`hold` 在價格窗口完整後保存為 `observational`，不產生方向正確性。

歷史分析日期來自 `enhanced_context.date`，缺失時才回退到歷史記錄創建日期。Backtest 與 Outcome 共享股票身份解析、受支持的舊市場快照重建和權威起始 session 判定：優先使用市場一致且合法的 `market_phase_summary.effective_daily_bar_date`；缺少該字段時，只有 phase 與交易日曆能夠證明起點才進行推導，否則 fail closed，不允許選擇任意更早的本地日線。Outcome 只接受通過判定的 `expected_start_date`。Backtest 為兼容既有歷史，可在非 session `effective_daily_bar_date` 對應的精確本地 bar 已存在時，通過顯式 `backtest_start_date` 只讀回放；該 fallback 不屬於權威 Outcome 樣本，不觸發無效日期 refill，也不進入 Skill Outcome 統計或權重校準。共享窗口 resolver 在指定起點中優先完整窗口，且起始與 forward bars 必須來自同一 stored code shape，不得跨候選拼接。

對 Outcome 而言，權威起始 session 已確定、但對應起始 bar 尚未寫入，或未來本地日線不足時，保存為可重試 `pending`。候選 key 按上次嘗試時間（缺失 outcome 時按 sample 創建時間）公平調度；每次重試會刷新 `pending.updated_at` 並將其移至隊尾，避免持續新增的缺失 key 餓死舊重試，也避免重試反向阻塞新樣本。損壞或晚於分析日期的 `effective_daily_bar_date`、股票市場與快照市場衝突，以及無法由可信 phase 與交易日曆證明起點等永久無效元數據，保存為終態 `unable`，不得偽裝成 `missing_start_bar` 持續重試。同一 engine version 下只有 `pending` 可更新，`evaluated`、`observational`、`unable` 均不可覆蓋；規則變化必須提升 engine version。歷史刪除在同一寫事務內按 outcome → sample → history 顯式清理，不能依賴 SQLite 外鍵開關。

Outcome 核心階段（#2116）基於已合併的 #2073，只提供 Outcome evaluator、repository 和 service 核心，當時未包含表現統計、樣本充足度、排名或權重調整。其後的只讀統計階段在下節單獨定義；該階段仍不新增管理員 API、Schema、OpenAPI 或主 Pipeline 自動觸發，也不調整運行時權重。若後續需要運維入口，應以實際調用方和權限契約為依據獨立審查。

### Skill Opinion Outcome 表現統計

Outcome 統計是隻讀數據面，按 `skill_id + horizon + engine_version` 獨立分 bucket。任何 bucket 都不能借用同 skill 的其他 horizon、其他 skill、其他 engine version 或全局樣本解鎖指標。當前固定門檻為 `evaluated >= 30`；只有 individual skill opinion 自身 signal 產生的 `hit` / `miss` 計入 evaluated，`pending`、`observational` 和 `unable` 只保留計數，不計入樣本充足度。

樣本不足時，bucket 的 `sample_status` 為 `observational`，計數繼續返回，但 `hit_rate_pct`、`miss_rate_pct`、`avg_directional_return_pct` 和 `unable_rate_pct` 全部為 `null`，不得輸出排名或推導權重。樣本充足時，hit/miss rate 以 `hit + miss` 為分母，平均方向收益只使用 evaluated rows；unable rate 以終態記錄 `evaluated + observational + unable` 為分母，臨時 `pending` 不得稀釋永久失敗比例。

只讀統計階段（PR #2119）本身不修改 `BacktestService.get_skill_summary()`、`AgentMemory` 或 `SkillAggregator`，也不新增 API、Pipeline 自動觸發和 Web 展示；本頁後文的 Phase 4 在該統計契約之上獨立接入保守運行時權重。當前組合實現仍只讀消費已經持久化的 Outcome，不負責自動觸發 evaluator。

## 術語與邊界

當前倉庫裡有多種名為 opinion / signal / consensus / synthesis 的數據面，Baseline 必須先消歧，避免把現有運行時結構誤寫成未來 phase。

| 術語 | 當前含義 | 當前主要消費方 | Baseline 邊界 |
| --- | --- | --- | --- |
| `AgentOpinion` | `src/agent/protocols.py` 中所有 Agent（含 SkillAgent、TechnicalAgent、IntelAgent、RiskAgent、DecisionAgent）產出的觀點數據類，含 `agent_name` / `signal` / `confidence` / `reasoning` / `key_levels` / `raw_data`。 | Orchestrator、Aggregator、DecisionAgent、Disagreement、Renderer | 記錄為原始觀點承載體；Baseline 不新增字段，也不把 `AgentOpinion` 分裂成兩類。 |
| `StrategyOpinion` | `src/agent/protocols.py` 中的內部規範化視圖，含 `skill_id` / `signal` / `original_signal` / `invalid_signal`；只在 Aggregator/Synthesizer 內部使用。 | `SkillAggregator`、`ConflictDetector`、`StrategySynthesizer` | 記錄為內部計算的規範化視圖，不進入 `ctx.opinions`、不進入公共 payload、不進入 DecisionAgent prompt。 |
| Signal / Canonical Signal | 交易信號規範化標籤，Canonical 取值僅限 `strong_buy` / `buy` / `hold` / `sell` / `strong_sell` 五個小寫字符串。 | 全鏈路 | 記錄為下游所有計算的唯一允許輸入形式；大寫別名、`"strong buy"`、Signal 枚舉原值都必須先經 `normalize_strategy_signal()` 轉成 canonical 再參與計算。 |
| Valid Opinion / Invalid Opinion | 通過 `is_valid_strategy_signal(signal) == True` 且未標記 `invalid_signal=True` 的觀點為 Valid，其餘為 Invalid。 | Orchestrator 分揀、Aggregator、DecisionAgent | 記錄為契約層的合法/非法判定；Baseline 只定義判定函數與語義，不預設分揀位置。 |
| Evidence Chain | 進入 DecisionAgent prompt 與 `strategy_synthesis` 數值計算的**有效觀點集合**。 | DecisionAgent、Aggregator | 記錄為決策輸入面；Baseline 規定 Evidence Chain 只由 Valid Opinion 組成，Invalid 不得混入。 |
| Diagnostics | 無效觀點的診斷收納位，僅供日誌、調試、用戶可見的“另有 N 個策略解析失敗”計數使用。 | Renderer 展示、日誌 | 記錄為診斷面；Baseline 規定 Invalid 必須落到 Diagnostics，不得被靜默轉成 `hold` 混入 Evidence Chain。 |
| `strategy_synthesis` | `dashboard.strategy_synthesis` 頂層 payload，含 `final_signal` / `consensus_level` / `conflict_severity` / `supporting_skills` / `opposing_skills` / `summary_params`。 | Markdown、WeChat、Notification、History 四條 renderer | 記錄為公共低敏 payload；Baseline 規定該 payload 是**唯一權威合成來源**，LLM dashboard 不得反向覆蓋。 |
| `disagreement_summary` | `ctx.meta["agent_disagreement_summary"]`，低敏跨 Agent 分歧摘要，來自 `build_agent_disagreement_summary()`。 | DecisionAgent prompt、日誌 | 記錄為決策路徑提示面；Baseline 規定只從 Valid Opinion 建桶，Invalid 不得進入 `bullish_agents` / `bearish_agents` / `neutral_agents`。 |
| Consensus Level | `strategy_synthesis.consensus_level`，取值 `high` / `medium` / `low` / `insufficient`。 | Renderer 展示、Aggregator 內部判定 | 記錄為共識度枚舉；Baseline 規定 ≤ 1 valid 或 `sum(confidence) == 0` 時強制 `insufficient`，不得輸出 `high`。 |

## Baseline 範圍與非目標

Baseline 的目標是讓 Phase 1/2/3/4 都基於同一份語義契約設計運行時改動，而不是每一輪 PR 重新定義"有效觀點"、"共識"、"支持方"。

- Baseline 覆蓋 SkillAgent → Orchestrator → Aggregator → Synthesizer → DecisionAgent → Disagreement → Renderer 七條消費面的語義收斂邊界。
- Baseline 固定 Canonical Signal 枚舉、Valid/Invalid 判定函數、Evidence Chain / Diagnostics 分離原則、動態二分陣營語義、共識門檻梯度、`strategy_synthesis` payload schema、不變量清單和反例矩陣；Phase 1 是這些邊界的第一版代碼化實現。
- Baseline 不引入併發調度、不引入前端多語言完整展示、不引入權重回測反饋；這些留給 Phase 2/3/4。
- Baseline 不改變現有 `AgentOpinion` 字段、不新增數據庫字段、不改變 API 返回結構（`strategy_synthesis` 已在此前 PR 加入）、不新增配置項。
- Baseline 不把契約擴展成通用 opinion registry；`AgentOpinion` 結構由現有代碼維護，本契約只規範其**語義處置流程**。

## Baseline 內部契約

### Canonical Signal 與 Valid 判定

Canonical Signal 是 Baseline 允許的**唯一評分/加權/分組輸入形式**。規範化入口是 `src/agent/protocols.py` 中的兩個函數：

- `normalize_strategy_signal(signal)` 返回 `(canonical, invalid, original)` 三元組。它接受 `Signal` 枚舉、大小寫字符串、`"strong buy"` / `"strong-buy"` 別名，統一映射到 canonical 集合。無法映射時 `invalid=True`，`canonical` 退化為 `default`（默認 `"hold"`）但**必須**配合 `invalid=True` 一併傳遞到下游，不得被單獨使用。
- `is_valid_strategy_signal(signal)` 是 Baseline 全鏈路合法性判定的**單一真源**：任何模塊判斷“這條 opinion 是否有資格進入 Evidence Chain”都必須調用此函數。

Baseline 禁止在 `_STRATEGY_SIGNAL_ALIASES` 之外再維護第二份 canonical 映射表；ConflictDetector 與 Synthesizer 內部的 `strategy_signal_score(canonical)` 只接受 canonical 值，禁止用 `op.original_signal` 或大小寫變體查表。

### Evidence Chain 與 Diagnostics 分離

Baseline 規定：

- **Evidence Chain 是且僅是 Valid Opinion 集合**。DecisionAgent prompt、`strategy_synthesis` 數值計算、`disagreement_summary` 建桶都必須從同一個 Evidence Chain 讀取。
- **Invalid Opinion 必須落到 Diagnostics**（`ctx.meta["invalid_opinions"]` 或等價字段），僅用於日誌、診斷、用戶可見的“另有 N 個策略解析失敗”計數。
- 兩個集合**互斥且並集窮盡**：一條 opinion 要麼在 Evidence Chain，要麼在 Diagnostics，不得同時出現或都不出現。
- Invalid Opinion **不得**被靜默轉換成 `hold` / `confidence` 保留原值 / 匿名混入 `bullish_agents` / `bearish_agents` / `neutral_agents` 桶。

Diagnostics 結構：

```python
ctx.meta["invalid_opinions"] = [
    {
        "agent_name": str,          # 原始 agent_name
        "raw_signal": str | None,   # 原始 signal 字面量（未歸一化）
        "confidence": float,        # 原始 confidence，僅診斷，不參與任何計算
        "reason": str,              # "missing_signal" | "unrecognized_signal" | "invalid_flag"
    },
    ...
]
```

Baseline 只規定該結構，不規定分揀發生的**代碼位置**——Phase 1 會把分揀落到 Orchestrator。

### 動態二分陣營（Supporting / Opposing）

給定最終信號 `final_signal` 與 canonical score `final_score = strategy_signal_score(final_signal)`，對每個 Valid Opinion `op` 計算 `op_score = strategy_signal_score(op.signal)`：

- **當 `final_signal == "hold"`（即 `final_score == 3.0`）時**：
  - `op_score == 3.0` → `supporting_skills`
  - `op_score != 3.0` → `opposing_skills`（作為異議與分歧收納，保證觀望與分歧觀點不被靜默丟棄，避免展示時丟失異議背景）

- **當 `final_signal` 為方向性信號（`strong_buy` / `buy` / `sell` / `strong_sell`）時**：
  - 同向（都看漲 或 都看跌）且 `abs(op_score - final_score) ≤ 1.0` → `supporting_skills`
  - 反向 且 `abs(op_score - final_score) ≥ 2.0` → `opposing_skills`
  - 其餘（`abs(diff) < 2.0` 且非同向）→ `opposing_skills`（併入異議，杜絕第三陣營 `neutral_skills`）

Baseline 明確 **`neutral_skills` 不作為 payload 的正式字段**。每個 Valid Opinion 必須**恰好**落入 `supporting_skills` 或 `opposing_skills` 其一，分組結果總數必須等於 `summary_params.opinion_count`。

### 共識度門檻

Baseline 固定共識度按 valid 樣本數梯度判定：

| valid 數量 | consensus_level | 說明 |
| --- | --- | --- |
| 0 | `insufficient` | 無證據可綜合，final_signal 強制 `hold`，`confidence=0.0` |
| 1 | `insufficient` | 單樣本不構成"共識"，即使與 final 完全一致也不得輸出 `high` |
| ≥ 2，`sum(confidence) == 0` | `insufficient` | 有效證據的置信度為零，無從建立共識 |
| ≥ 2，`sum(confidence) > 0` | 進入 aligned_ratio 判定 | 見下表 |

Aligned Ratio 判定（valid ≥ 2 且 `sum(confidence) > 0`）：

| 條件 | consensus_level |
| --- | --- |
| `conflict_severity == "high"` | `low` |
| `aligned_ratio ≥ 2/3` 且 `conflict_count == 0`（等價 `conflict_severity == "none"`） | `high` |
| `conflict_severity == "medium"` 且 `aligned_ratio < 0.5` | `low` |
| 其餘 | `medium` |

其中 `aligned = 與 final_signal 同向且 score 距離 ≤ 1.0 的 valid 數量`，`aligned_ratio = aligned / len(valid)`。

Baseline 禁止使用 `sum(...) or 1.0` 之類的兜底把零權重掩蓋成分母 1；零權重必須顯式走 `insufficient` 分支，並讓 `final_signal` 退回 `hold`。

### `strategy_synthesis` Payload Schema

```json
{
  "final_signal": "hold",                 // canonical signal
  "weighted_score": 3.0,                  // 保留 4 位小數
  "confidence": 0.72,                     // 折減後的置信度
  "original_confidence": 0.80,            // 折減前的加權置信度
  "conflict_count": 0,
  "conflict_severity": "none",            // none | low | medium | high
  "conflicts": [ /* ConflictDetector 輸出的 dict 列表 */ ],
  "supporting_skills": [ /* opinion item */ ],
  "opposing_skills":   [ /* opinion item */ ],
  "consensus_level": "high",              // high | medium | low | insufficient
  "summary_key": "strategy_synthesis.no_conflicts",   // 動態 i18n 摘要鍵名，隨共識和衝突狀態確定
  "summary_params": {
    "opinion_count": 2,                   // valid 樣本數（Evidence Chain 大小）
    "total_opinion_count": 4,             // valid + invalid（分揀前原始輸入總數）
    "invalid_opinion_count": 2,           // Diagnostics 長度
    "final_signal": "hold",
    "consensus_level": "high",
    "conflict_severity": "none",
    "conflict_count": 0
  },
  "deliberation": {                       // 可選；僅 material conflicts 觸發
    "status": "completed",
    "mode": "multi_round_v4",
    "rounds": 2,
    "agenda": [ /* conflict agenda item */ ],
    "responses": [ /* per-agenda participant response */ ],
    "summary": {
      "resolution_status": "partially_resolved",
      "resolved_conflict_count": 0,
      "unresolved_conflict_count": 1,
      "minority_view_preserved": true,
      "confidence_adjustment": -0.06,
      "confidence_adjustment_reason_key": "deliberation.confidence.high_partially_resolved"
    },
    "round_history": [
      {
        "round": 1,
        "source_mode": "mediator_v0",
        "status": "baseline",
        "changed_response_count": 2,
        "confidence_adjustment": -0.06
      },
      {
        "round": 2,
        "source_mode": "multi_round_v4",
        "status": "accepted",
        "changed_response_count": 1,
        "confidence_adjustment": -0.09
      }
    ]
  },
  "revision_projection": {                // 可選；僅 deliberation 存在時生成的 preview
    "status": "computed",
    "mode": "preview_only",
    "source_mode": "mediator_v0",
    "projected_signal": "hold",
    "projected_weighted_score": 3.0,
    "projected_confidence": 0.6696,
    "projected_original_confidence": 0.72,
    "projected_conflict_count": 1,
    "projected_conflict_severity": "medium",
    "projected_consensus_level": "low",
    "changed_skill_count": 2,
    "changed_skills": ["trend_v1", "theme_v1"],
    "final_signal_overridden": false
  }
}
```

Opinion Item 結構（`supporting_skills` / `opposing_skills` 每個元素）：

```json
{
  "skill_id": "trend_v1",
  "agent_name": "skill_trend_v1",
  "signal": "hold",              // canonical
  "confidence": 0.80,            // 保留 4 位小數
  "reasoning": "...",
  "score_adjustment": 0,
  "conditions_met": []
}
```

Baseline 明確 `strategy_synthesis` 是**由 SkillAggregator 確定性算法產出的唯一權威合成結果**。Orchestrator 的 `_collect_strategy_synthesis()` 必須優先使用 `ctx.get_data("skill_consensus")` 中的 synthesis，只有在 SkillAggregator 未產出時才允許回退到 `ctx.opinions` 中的 `skill_consensus` opinion。**LLM 返回的 dashboard 不得覆蓋或修改 `dashboard.strategy_synthesis`**；`normalize_dashboard_payload` 收到 LLM 輸出時應剝離 LLM 側的 `strategy_synthesis` 字段，避免 LLM 幻覺汙染權威合成結果。

### Strategy Deliberation v0（Phase 1.5）

`strategy_synthesis.deliberation` 是可選協同推理塊，只在中高強度衝突或明確關鍵衝突類型出現時生成。v0 使用確定性 `mediator_v0`，不調用 LLM、不讓策略自由聊天、不修改原始 opinion、不重新計算 `final_signal`。它的職責是把衝突轉成可審計議題，並記錄策略回應、輕量修正與綜合置信度折減原因。

觸發條件：

- `len(valid_opinions) >= 2`
- 且存在 `severity in {"medium", "high"}` 的 conflict，或 conflict type 屬於 `directional_opposition` / `high_confidence_dissent`

v0 revision 只允許：

- `unchanged`：堅持原觀點。
- `softened`：僅降低 confidence，或將 `strong_buy -> buy`、`strong_sell -> sell`；`buy` / `sell` / `hold` 不反轉，只可降低 confidence。

v0 明確禁止：

- `reversed`：不得反轉觀點。
- 重新計算 `final_signal`。
- 引入多輪 debate、併發調度、前端展示或新配置項。

`deliberation.summary.confidence_adjustment` 只作為 `StrategySynthesizer` 在原 conflict severity 折減後的額外保守折減。高衝突部分緩解時默認約 `-0.06`，未緩解時約 `-0.08`；中衝突部分緩解時默認約 `-0.04`，未緩解時約 `-0.05`。該字段必須保留在 payload 中，方便後續 renderer 或 Web UI 展示“為什麼置信度被繼續下調”。

### LLM Mediator v1（Phase 1.6）

`llm_mediator_v1` 是 `StrategyDeliberation` 的可注入增強模式，不是默認運行時行為。調用方可以向 `StrategySynthesizer(deliberation_mediator=...)` 注入 `LLMDeliberationMediator`，由它先生成 v0 baseline agenda，再把低敏結構化 opinions/conflicts/baseline payload 發送給 LLM callable。LLM 只能返回同 schema 的 JSON 對象；返回文本、壞 JSON、缺字段、ID 漂移或越界 revision 時，必須無條件回退 v0。

v1 schema guard：

- `agenda` 必須保留 v0 的 `agenda_id` 集合；不得新增、刪除或替換參與方。
- `responses` 必須覆蓋 v0 的 `(agenda_id, skill_id)` 集合；不得新增未參與策略。
- `revision` 只允許 `unchanged` / `softened`；`reversed` 繼續禁止。
- v0 baseline 已經 `softened` 的 response 必須繼續保持 `softened`，不得恢復 original signal，且 `revised_confidence` 不得高於 baseline 的已驗證值。
- v0 baseline 為 `unchanged` 的 response 可以保持不變，也可以按原規則繼續 `softened`；不得反轉 signal 或提高 confidence。
- `summary.confidence_adjustment` 不得比 v0 baseline 更樂觀，且單次額外折減下限為 `-0.10`，避免 LLM 撤銷確定性折減。

v1 輸出通過校驗時 `deliberation.mode="llm_mediator_v1"`；否則保持 `mediator_v0` 輸出。v1 仍不調用策略 agent 自審、不多輪 debate、不重算 `final_signal`，也不新增配置項。

### Strategy Self-Review v2（Phase 1.7）

`self_review_v2` 是 `StrategyDeliberation` 的可注入自審模式，不是默認運行時行為。調用方可以向 `StrategySynthesizer(deliberation_mediator=...)` 注入 `StrategySelfReviewMediator`，由它先獲取 baseline deliberation（可以是 `mediator_v0` 或通過校驗的 `llm_mediator_v1`），再按每個 baseline response 的 `(agenda_id, skill_id)` 調用自審 callable。未來該 callable 可以由真實衝突參與 strategy agent 執行；當前契約只規定輸入/輸出與降級行為。

v2 self-review guard：

- 每個 baseline response 必須返回且只返回自己的 response JSON；不得修改其它策略回應。
- 返回的 `agenda_id` / `skill_id` 必須與 baseline response 完全一致。
- `revision` 仍只允許 `unchanged` / `softened`；`reversed` 繼續禁止。
- baseline 已經 `softened` 時不得改回 `unchanged`、恢復 original signal 或提高 baseline `revised_confidence`。
- baseline 為 `unchanged` 時可以保持不變，也可以按原規則繼續 `softened`；不得反轉 signal 或提高 confidence。
- v2 根據通過校驗的 responses 重算 summary 時，最終 `confidence_adjustment` 不得比輸入 baseline 更樂觀。
- 任一參與方缺失、壞 JSON、ID 漂移、越權修改或試圖 `reversed`，整輪 self-review 回退到 baseline deliberation，禁止混合部分有效自審。

v2 輸出通過校驗時 `deliberation.mode="self_review_v2"`。v2 仍只做一輪、不新增併發調度、不重算 `final_signal`、不改變原始 opinion，也不新增配置項。

### Revision Projection v3（Phase 1.8）

`strategy_synthesis.revision_projection` 是可選預覽塊，只在 `deliberation` 存在時由 `StrategySynthesizer` 計算。它讀取已經通過 v0/v1/v2 schema guard 的 `responses`，把 `revision="softened"` 的回應應用到臨時 `StrategyOpinion` 副本上，再用 confidence-weighted score 預覽新的綜合結果。

v3 輸出邊界：

- `revision_projection.mode` 固定為 `preview_only`。
- `source_mode` 記錄投影來源：`mediator_v0` / `llm_mediator_v1` / `self_review_v2`。
- `projected_signal` / `projected_weighted_score` / `projected_confidence` 只描述採納 softened 修訂後的預覽結果。
- `projected_conflict_count` / `projected_conflict_severity` / `projected_consensus_level` 基於臨時修訂副本重新檢測，不改寫原始 conflicts。
- `changed_skill_count` / `changed_skills` 只統計實際 softened 的策略。
- `final_signal_overridden` 必須固定為 `false`，用於明確 v3 不覆蓋權威最終信號。

v3 明確禁止：

- 把 `projected_signal` 回寫到頂層 `final_signal`。
- 把 `projected_weighted_score` 回寫到頂層 `weighted_score`。
- 把 `projected_confidence` 回寫到頂層 `confidence`。
- 在沒有 `deliberation` 的場景輸出空 projection。
- 接受未經 v0/v1/v2 guard 的自由文本、反轉信號或新增策略回應。

v3 在投影入口還會重新核對 `original_signal`、允許的 softened signal 與 `revised_confidence` 上界；即使調用方注入了未使用內置 mediator guard 的自定義結果，也不會把更激進的 response 應用到臨時 opinion 副本。

### Configurable Multi-Round Deliberation v4（Phase 1.9）

`multi_round_v4` 是 `StrategyDeliberation` 的可注入多輪增強模式，不是默認運行時行為。調用方可以向 `StrategySynthesizer(deliberation_mediator=...)` 注入 `MultiRoundDeliberationMediator`，並通過構造參數配置：

- `fallback`：第一輪 baseline mediator，可為 `mediator_v0`、`llm_mediator_v1` 或 `self_review_v2`。
- `max_rounds`：總輪數上限，範圍 `1–4`；`1` 等價只保留 fallback baseline。
- `stop_when_stable`：當某輪沒有任何 response 變化時是否提前停止，默認開啟。
- `round_completion(round_index, messages)`：下一輪結構化修訂 callable，只能返回同 schema JSON。

v4 round guard：

- 每輪必須保留上一輪的 `agenda_id` 集合和 `(agenda_id, skill_id)` response 集合；不得新增、刪除或替換參與方。
- `revision` 仍只允許 `unchanged` / `softened`；`reversed` 繼續禁止。
- 上一輪已經 `softened` 的 response 不能回到 `unchanged`。
- 上一輪已經 `softened` 的 response 不能更換 `revised_signal`，也不能提高 `revised_confidence`。
- 上一輪 `unchanged` 的 response 可以繼續 `unchanged`，也可以按原規則 `softened`。
- `summary.confidence_adjustment` 不能為正數，也不能比上一輪更樂觀；單輪下限仍按 v1 guard 鉗制到 `-0.10`。
- 任一輪壞 JSON、ID 漂移、越界 revision、撤銷 softened 或提高 confidence 時，停止後續輪次並返回上一輪已驗證結果；如果第 2 輪即失敗，則保持 fallback baseline。

v4 輸出：

- 至少接受一輪額外修訂時，`deliberation.mode="multi_round_v4"`。
- `deliberation.rounds` 記錄實際接受到的總輪數。
- `deliberation.round_history` 記錄 baseline 與每個已接受輪次的 `round`、`source_mode`、`status`、`changed_response_count` 和 `confidence_adjustment`。
- v4 仍不重算頂層 `final_signal`，不改變原始 opinion，不直接覆蓋頂層 `weighted_score` 或 `confidence`；頂層 confidence 只繼續讀取最終 `deliberation.summary.confidence_adjustment` 做保守折減。

### 關鍵不變量

Baseline 的語義邊界收斂為九條不變量。所有 Phase N 的實現必須同時滿足這九條，任一違反視為契約破壞。

| ID | 不變量 | 場景 | 期望 |
| --- | --- | --- | --- |
| I-1 | Evidence Chain 排他性 | 任何模塊讀取 Evidence Chain | 集合內每一條都必須 `is_valid_strategy_signal == True`；Invalid 不允許出現 |
| I-2 | 禁止靜默轉換 | 缺失或無法識別的 signal | 歸入 Diagnostics，不得轉換成 `hold` 後混入 Evidence Chain 或建桶 |
| I-3 | 零證據 → insufficient | 任意有效信號但 `sum(confidences) == 0`，或 valid 數量 = 0 | `final_signal="hold"`, `weighted_confidence=0.0`, `consensus_level="insufficient"`；禁止輸出 `strong_sell` 或任何方向性信號 |
| I-4 | 單樣本 → insufficient | 恰好 1 個 valid opinion | `consensus_level="insufficient"`，即使與 final 完全一致 |
| I-5 | Hold-final 一致性 | `final_signal == "hold"` 且存在 ≥ 2 個 hold valid opinion | 全部 hold opinion 必須歸入 `supporting_skills`；consensus_level 與 supporting_skills 數量關係必須自洽（`high` 時 supporting 覆蓋 ≥ 2/3） |
| I-6 | Payload 與 renderer 語義一致 | `dashboard.strategy_synthesis` 值 | 四條 renderer（Markdown / WeChat / Notification / History）實際文本必須與 payload 完全一致，不得出現"共識度：高 + 支持策略：無"等自相矛盾組合 |
| I-7 | Canonical-First 評分 | Aggregator / ConflictDetector / Synthesizer 內部的評分、加權、衝突判定、分組 | 必須使用 `normalize_strategy_signal()` 返回的 canonical 小寫值；禁止用大寫 `"BUY"`、別名等原始字符串直接查 `strategy_signal_score` |
| I-8 | 多語言空佔位符 | `supporting_skills` / `opposing_skills` 為空時的展示 | 必須通過 `labels.none_label` 按 `report_language` 查表；禁止在代碼或模板中硬編碼中文 `"无"` / 英文 `"None"` / 韓文 `"없음"` 字面量 |
| I-9 | Deliberation 單調保守 | v1/v2/v4 基於上一層已驗證 baseline 修訂，v3 應用 projection | 不得撤銷已有 `softened`、恢復 original signal、提高 baseline revised confidence 或提高 baseline confidence adjustment；越界結果回退上一層 |

## Phase 1 語義收斂（本 PR 交付範圍）

Phase 1 是 Baseline 契約的第一版代碼化實現。Phase 1 **不新增契約條款**，只把 Baseline 已經寫死的邊界落到具體代碼：Orchestrator 分揀、Aggregator/Synthesizer 計算收斂、DecisionAgent prompt 收斂、Disagreement 收斂、四條 renderer 一致性、E2E 反例覆蓋。

Phase 1 涉及的入口：

- `src/agent/protocols.py`：新增 `is_valid_strategy_signal()` 單一真源，`normalize_strategy_signal()` 保留 invalid 狀態位。
- `src/agent/skills/engine.py`：`StrategyEngine.process()` 通過 `partition_only()` 完成唯一權威分揀，再由 `process_partition()` 驅動聚合與合成；Valid 保留在 Evidence Chain，Invalid 寫入 Diagnostics。
- `src/agent/orchestrator.py`：在 DecisionAgent 運行前調用 `_run_strategy_engine(ctx)`；timeout / budget-skip 早退路徑調用 `_apply_partition_fallback(ctx)`，只分揀、不合成，避免 Invalid 迴流證據鏈。
- `src/agent/skills/aggregator.py`：`StrategyEngine` 把 `valid_skill_opinions` 交給 `SkillAggregator.calculate()`；數學計算只使用 valid opinion，對 `valid_weight_sum == 0` 顯式走 `insufficient` 分支。
- `src/agent/skills/synthesis.py`：`ConflictDetector` / `StrategySynthesizer` 使用 canonical signal 計算；`_group_opinions()` 按 §"動態二分陣營" 實現；`_consensus_level()` 按 §"共識度門檻" 實現；`summary_params` 補齊 `invalid_opinion_count` / `total_opinion_count`。
- `src/agent/agents/decision_agent.py`：`build_user_message()` 直接消費 `ctx.opinions`，不再二次過濾；在 prompt 中如實展示 `ctx.meta["invalid_opinions"]` 數量。
- `src/agent/disagreement.py`：`build_agent_disagreement_summary()` 直接消費 `ctx.opinions`（因 StrategyEngine 已完成分揀並由 Orchestrator 寫回），Invalid 完全不出現在 `bullish_agents` / `bearish_agents` / `neutral_agents` 三桶中。
- `src/services/report_renderer.py`、`templates/report_markdown.j2`、`templates/report_wechat.j2`、`src/notification.py`、`src/services/history_service.py`：讀取 `strategy_synthesis.supporting_skills` / `opposing_skills` / `consensus_level` / `summary_params.invalid_opinion_count`；空列表通過 `labels.none_label` 輸出；不再消費 `neutral_skills`。
- `src/report_language.py`：`labels.none_label` 在 zh/en/ko 三語中完備；共識度、診斷計數文案完備。
- `tests/test_multi_agent.py`：新增 E2E-A..G 反例矩陣，從 SkillAgent 輸入 → StrategyEngine 分揀/聚合 → DecisionAgent prompt → dashboard payload → renderer 實際文本全鏈路斷言。

Phase 1 不改變 `AgentOpinion` 字段、不改變 API 返回結構、不改變數據庫 schema、不新增配置項、不改變現有 skill 的執行方式。

## Phase 2 併發調度

Phase 2 只在 Phase 1/1.5/1.6/1.7/1.8/1.9 契約下新增 2–4 策略併發調度與階段調度：

- `src/agent/skills/scheduler.py::AgentSkillScheduler` 使用 thread pool 併發執行 specialist skill agents；每個 skill 使用 `AgentContext` 副本運行，並通過獨立的 `copy_context()` 把主管線凍結的 target date 等 `ContextVar` 狀態傳播到 worker，主線程按路由順序合併結構化 opinion，避免多個 skill 同時寫共享 `ctx.opinions`。
- specialist 最終入口最多選擇 4 個策略；`AGENT_SKILL_CONCURRENCY` 控制同時運行的 worker 數，默認 `3`，範圍 `1–4`。默認值下第 4 個策略進入下一 concurrency wave，不會被路由層靜默丟棄。
- `AGENT_SKILL_AGENT_TIMEOUT_S` 繼續作為單個 skill 的獨立超時上限；Pipeline 總預算開啟時，`_run_stage_agent()` 仍取 Pipeline 剩餘預算與 skill 獨立上限的較小值。
- 單個 skill 超時或異常，走 Diagnostics 路徑（`reason="skill_timeout"` / `"skill_error"`），進入 `ctx.meta["invalid_opinions"]`，不阻塞其他 skill 與主流程。
- Phase 2 不改變 Baseline Evidence Chain / Diagnostics 分離原則、不改變陣營語義、不改變共識門檻、不改變 `strategy_synthesis` payload schema。
- Phase 2 不改變 renderer 展示邏輯；scheduler timeout/error/no-opinion 與 signal 校驗失敗統一進入 StrategyEngine 的 authoritative Diagnostics，`invalid_opinion_count` / `total_opinion_count` 覆蓋這些失敗 skill。
- `ctx.meta["skill_scheduler"]` 僅作為運行時診斷，記錄調度模式、併發數、單 skill timeout、調度數量、完成數量和 invalid 數量；不得參與綜合評分。

## Phase 3 前端多語言完整展示（本 PR 不做）

Phase 3 只在 Phase 2 之上補前端（`apps/dsa-web/`、`apps/dsa-desktop/`）對 `strategy_synthesis` 的完整多語言展示：

- Web 報告詳情頁展示 `final_signal` / `consensus_level` / `supporting_skills` / `opposing_skills` / `conflicts` / `invalid_opinion_count`。
- 桌面端複用 Web 展示邏輯。
- 多語言 label 表複用 `src/report_language.py` 已有的 zh/en/ko 三語；前端只做投影，不重新定義。
- Phase 3 不改變 Baseline 契約、不新增 payload 字段、不新增 API 端點。

## Phase 4 Skill Outcome 權重反饋閉環

Phase 4 在同一 `CONTRACT_VERSION = "1.0"` 內只使用真實、可歸因的
individual Skill Outcome 調整運行時相對權重。權重統計繼續嚴格按
`skill_id + horizon + engine_version` 分 bucket；每個 horizon 必須獨立滿足
`evaluated >= 30`，不得跨 horizon、skill 或 engine version 拼接樣本解鎖權重。

單個充足 bucket 使用對稱 `Beta(15, 15)` 先驗做命中率收縮：

```text
n = hit + miss
posterior_hit_rate = (hit + 15) / (n + 30)
direction_score = 2 * posterior_hit_rate - 1
unable_rate = unable / (evaluated + observational + unable)
bucket_score = clamp(direction_score - 0.25 * unable_rate, -1, 1)
evidence_strength = n / (n + 30)
```

`pending` 不進入 unable rate 分母，`observational` / `unable` 不能補足
evaluated 門檻。當前 opinion 沒有可信 horizon，因此只對已經各自滿足門檻的
bucket 做證據強度加權模型平均：

```text
combined_score =
    sum(bucket_score * evidence_strength)
    / sum(evidence_strength)
performance_factor = exp(ln(1.2) * combined_score)
effective_weight = opinion.confidence * performance_factor
```

`performance_factor` 被限制在乘法對稱區間 `[1 / 1.2, 1.2]`。沒有充足
bucket、統計讀取失敗、bucket 損壞、數值非有限或
`AGENT_SKILL_AUTOWEIGHT=false` 時必須返回中性因子 `1.0`；權重失敗不得中斷
分析。運行時不再使用 `BacktestService` 的全局或不可歸因 summary 冒充 Skill
表現。本階段只讀消費已經持久化的 Outcome，不新增 evaluator 的 Pipeline、API
或定時觸發入口。

`avg_directional_return_pct` 當前仍是隻讀描述指標，不參與權重。只有平均值而
沒有離散度或標準誤時，直接加入公式會製造偽精確；後續若要使用收益，必須先
建立版本化的風險調整收益契約。

Phase 4 不改變 Baseline canonical signal / valid 判定 / 共識門檻 / 陣營語義；
權重變化隻影響 `weighted_score` 與 `confidence`，不影響 `consensus_level`
判定路徑。`AGENT_ARCH=single` 不經過 `SkillAggregator`，保持兼容。

## 消費面盤點

Baseline 的七條消費面必須嚴格按下表分工，不得越界互相消費對方的內部數據。

### SkillAgent

各 skill 通過 `src/agent/skills/skill_agent.py` 產出 `AgentOpinion`。Baseline 允許 skill 輸出任意 signal 字面量（含大寫、別名、`Signal` 枚舉），也允許 skill 因數據不足產出 `signal=None` / 缺失字段——這些情況由下游分揀處理，skill 本身不做自我過濾。

### StrategyEngine / Orchestrator（分揀與接線）

Phase 1 在 DecisionAgent 運行前由 Orchestrator 調用 `_run_strategy_engine(ctx)`：

- `StrategyEngine.partition_only()` 遍歷所有 `agent_name` 命中 `is_skill_agent_name()` 的觀點，並使用 `normalize_strategy_signal()` 保留 canonical signal。
- Invalid 從 Evidence Chain 移除，寫入 `StrategyResult.invalid_records`；Orchestrator 再把它賦給 `ctx.meta["invalid_opinions"]`。
- `StrategyEngine.process_partition()` 只把 `valid_skill_opinions` 交給 Aggregator/Synthesizer；產出的 consensus opinion 和 `skill_consensus` 由 `_run_strategy_engine()` 一次寫回 context。
- timeout / budget-skip 發生在完整 engine 運行前時，`_apply_partition_fallback()` 複用 `partition_only()`，只完成分揀和 Diagnostics 寫回，不生成 consensus。

Baseline 規定 `StrategyEngine.partition_only()` 是**唯一權威分揀實現**。Aggregator / DecisionAgent / Disagreement 不再各自定義 Valid/Invalid 規則，直接消費 engine 收斂後的 Evidence Chain；Orchestrator 中保留的舊 wrapper 僅用於兼容現有內部調用/測試，不屬於正常運行時鏈路。

### SkillAggregator

正常運行時由 `StrategyEngine` 調用 `SkillAggregator.calculate(valid_skill_opinions)`。Aggregator 把輸入轉換為內部 `StrategyOpinion`，數學計算只使用 valid opinion，並嚴格使用 canonical signal 查 `strategy_signal_score`；兼容入口即使收到未分揀輸入也不得讓 Invalid 參與權重。對以下三種狀態顯式走 `insufficient` 分支：

- `len(valid) == 0`：`final_signal="hold"`, `confidence=0.0`。
- `len(valid) == 1`：按該 opinion 的 canonical signal 輸出 `final_signal`，但 `consensus_level="insufficient"`。
- `len(valid) ≥ 2` 且 `sum(confidence) == 0`：`final_signal="hold"`, `confidence=0.0`。

產出的 `strategy_synthesis` 由 `StrategyEngine` 裝入 `StrategyResult.skill_consensus_data`，再由 Orchestrator 掛到 `ctx.set_data("skill_consensus", {...})`；`_collect_strategy_synthesis()` 從這裡讀取，作為 dashboard 的權威合成源。

### DecisionAgent

`build_user_message()` 從 `ctx.opinions` 讀取觀點寫入 prompt。因為 Orchestrator 分揀已保證 `ctx.opinions` 只含 Valid，DecisionAgent **不再**做二次過濾。Prompt 中"另有 N 個策略解析失敗"的展示直接讀取 `ctx.meta["invalid_opinions"]` 長度。

DecisionAgent 輸出的 dashboard JSON 不得覆蓋 `dashboard.strategy_synthesis`；如果 LLM 返回中含有該字段，`normalize_dashboard_payload()` 必須剝離，保留 Aggregator 側的權威合成。

### Disagreement

`build_agent_disagreement_summary()` 只從 `ctx.opinions` 建 `bullish_agents` / `bearish_agents` / `neutral_agents` 三桶。因為 `ctx.opinions` 已只含 Valid，Invalid 完全不出現在三桶中，也不會被 `_normalize_signal()` 靜默兜底為 `hold`。

`ctx.meta["invalid_opinions"]` 長度作為 `disagreement_summary.diagnostics.invalid_count` 單獨暴露給 DecisionAgent prompt，供 LLM 生成 `data_limitations` 文案參考。

### Renderer（四條）

所有 renderer 讀取 `dashboard.strategy_synthesis` 展示：

- `final_signal` / `consensus_level` / `conflict_severity` / `conflict_count`。
- `supporting_skills` / `opposing_skills`（不再消費 `neutral_skills`）。
- `summary_params.invalid_opinion_count` → 按語言展示"另有 N 個策略無效/解析失敗"。

空列表佔位符必須通過 `labels.none_label`（按 `report_language` 查表）輸出。四條 renderer 展示的最終文本必須與 payload 完全一致，不得出現"共識度：高 + 支持策略：無"這類內部矛盾。

歷史記錄和外部調用方可能保留契約落地前的寬鬆 shape。四條 renderer 必須先通過 `normalize_strategy_synthesis_payload()` 把非 dict 頂層值視為缺失，並過濾非 dict 的策略/衝突列表項；`strategy_invalid_opinion_count()` 統一讀取診斷計數，只對純十進制正整數字符串做窄轉換，其餘壞值降級為 0。禁止在 History、Notification 或模板中保留平行的手寫讀取邏輯。

### Diagnostics

`ctx.meta["invalid_opinions"]` 只允許被以下三類消費：

- 日誌：記錄 `agent_name` / `raw_signal` / `reason`，供排障。
- DecisionAgent prompt：作為"另有 N 個策略解析失敗"的計數來源。
- Renderer：作為 `summary_params.invalid_opinion_count` 的來源。

禁止把 Diagnostics 裡的 `confidence` 參與任何加權計算；禁止把 `raw_signal` 塞回 `ctx.opinions`。

## 反例矩陣

Phase 1 必須提供如下 E2E 反例覆蓋。E2E 定義為：從 SkillAgent 輸入進，穿過 Orchestrator 分揀 → SkillAggregator → DecisionAgent prompt → 最終 dashboard payload → 四條 renderer 實際文本輸出。禁止用局部單元測試冒充 E2E。

| 編號 | 輸入 | 斷言點 | 覆蓋的不變量 |
| --- | --- | --- | --- |
| E2E-A | 1 valid `buy/0.8` + 2 invalid `moon/0.9` | ① DecisionAgent prompt 不含 `moon` 字面量、不含 invalid `agent_name`、不含 `0.9` 上下文；② `ctx.meta["invalid_opinions"]` 長度 = 2；③ `strategy_synthesis.summary_params.opinion_count == 1`、`invalid_opinion_count == 2`；④ `consensus_level == "insufficient"`；⑤ 四條 renderer 輸出文本包含"另有 2 個策略無效/解析失敗"（按語言）；⑥ `disagreement_summary.bullish_agents` / `neutral_agents` / `bearish_agents` 中都不出現 moon 轉成的 hold/0.9 | I-1, I-2, I-4 |
| E2E-B | 2 valid `hold/0.0` | `final_signal="hold"`、`weighted_confidence=0.0`、`consensus_level="insufficient"`、**絕不**出現 `strong_sell`；所有 renderer 展示"證據不足（觀望）"（按語言） | I-3 |
| E2E-C | 1 valid `buy/0.0` + 1 valid `hold/0.0` | 混合零權重場景：`final="hold"`、`confidence=0.0`、`consensus="insufficient"`、無 `strong_sell` | I-3 |
| E2E-D | 2 valid `hold/0.8` | ① `final_signal="hold"`、`consensus_level="high"`；② `supporting_skills` 長度 = 2、`opposing_skills` 長度 = 0；③ 四條 renderer 實際文本同時包含"高共識"和兩個 skill 名，不得出現"支持策略：無"配"共識度：高"的組合 | I-5, I-6 |
| E2E-E | 1 valid `buy/0.8` + 9 invalid | `consensus_level="insufficient"`（**不得** high）；四條 renderer 展示"基於 1 個有效策略判斷（另有 9 個策略無效/解析失敗）" | I-4, I-6 |
| E2E-F | 2 valid opinion，其中一個 `signal="BUY"`（大寫） | Aggregator 內部計算 `weighted_score` 時使用 canonical `buy` 查分（4.0），**不得**因大寫查表失敗得到 0；`strategy_synthesis.final_signal` 輸出 canonical 小寫 | I-7 |
| E2E-G | 空 `supporting_skills` + `report_language="en"` | 四條 renderer 輸出中不出現中文 `"无"`，而是 `"None"`（或對應語言 `labels.none_label`） | I-8 |

## 源碼錨點

| 域 | 錨點 |
| --- | --- |
| Signal 規範化與 Valid 判定 | `src/agent/protocols.py::normalize_strategy_signal`, `is_valid_strategy_signal`, `strategy_signal_score` |
| StrategyEngine 分揀與合成門面 | `src/agent/skills/engine.py::StrategyEngine.partition_only`, `process`, `process_partition` |
| Orchestrator 接線與早退分揀 | `src/agent/orchestrator.py::_run_strategy_engine`, `_apply_partition_fallback` |
| SkillAggregator | `src/agent/skills/aggregator.py::SkillAggregator.calculate`, `aggregate`（兼容入口） |
| ConflictDetector / StrategySynthesizer | `src/agent/skills/synthesis.py::ConflictDetector`, `StrategySynthesizer` |
| DecisionAgent prompt | `src/agent/agents/decision_agent.py::build_user_message` |
| Disagreement | `src/agent/disagreement.py::build_agent_disagreement_summary` |
| Dashboard 合成掛載 | `src/agent/orchestrator.py::_collect_strategy_synthesis` |
| Renderer · Markdown | `src/services/report_renderer.py::render`, `templates/report_markdown.j2` |
| Renderer · WeChat | `templates/report_wechat.j2` |
| Renderer · Notification | `src/notification.py`（策略綜合行渲染） |
| Renderer · History | `src/services/history_service.py`（歷史詳情策略綜合塊） |
| 多語言與寬鬆 payload 防腐 | `src/report_language.py::_REPORT_LABELS`, `normalize_strategy_synthesis_payload`, `strategy_invalid_opinion_count`, `localize_strategy_synthesis_summary`, `labels.none_label` |
| E2E 反例矩陣 | `tests/test_multi_agent.py::TestP1SemanticConvergence`, `TestStrategyEngineE2E` |

## 兼容與回滾

### 已廢棄行為（Phase 1 落地後）

| 舊行為 | 契約後 |
| --- | --- |
| `normalize_strategy_signal` 對未知信號靜默返回 `default="hold"` 並混入證據鏈 | 未知信號必須歸入 Diagnostics，`ctx.opinions` 中不允許出現 |
| Aggregator 通過 `sum(...) or 1.0` 掩蓋零權重 | 顯式判 `valid_weight_sum == 0`，走 `insufficient` 分支，`final_signal="hold"` |
| Renderer 硬編碼 `"无"` 展示空陣營 | 通過 `labels.none_label` 按語言查表 |
| DecisionAgent 在 prompt 層自己過濾 invalid | 分揀在 Orchestrator 完成，DecisionAgent 直接消費 `ctx.opinions` |
| `strategy_synthesis` 輸出 `neutral_skills` | 契約後該字段不存在，renderer 不再消費 |
| LLM dashboard 覆蓋 `strategy_synthesis` | 權威合成來自 Aggregator，LLM 側字段被 `normalize_dashboard_payload` 剝離 |

### 已新增字段

- `ctx.meta["invalid_opinions"]`：Diagnostics 收納位（結構見"Evidence Chain 與 Diagnostics 分離"）。
- `strategy_synthesis.summary_params.invalid_opinion_count`：Diagnostics 長度。
- `strategy_synthesis.summary_params.total_opinion_count`：valid + invalid 的原始總數。

### 回滾方式

| 手段 | 作用 | 不能做什麼 |
| --- | --- | --- |
| 版本回退 Phase 1 相關提交 | 移除 Orchestrator 分揀、Aggregator/Synthesizer 收斂、renderer 一致性改動 | 無法只回退部分不變量；契約是整體收斂 |
| 只保留契約文檔、回退代碼 | 保留 Baseline 文本、回到舊行為 | 只有文檔意義，無運行時收益；不推薦 |
| Phase 2/3/4 獨立回退 | 各自 Phase 的運行時改動獨立回退 | 不能回退 Baseline，任何 Phase 都必須始終滿足 Baseline 八條不變量 |

Baseline 不新增配置項，因此無 env-level 回滾開關；這是刻意選擇——契約邊界應在代碼中恆定生效，不通過環境變量降級。
