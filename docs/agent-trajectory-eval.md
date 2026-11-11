# Agent Trajectory 評估(最小版,Refs #1956)

## 定位

`evals/agent_trajectory/` 提供一套**離線可運行的最小軌跡評估管線**:用真實 `tool_calls_log + AgentResult` 跑一個 golden 樣例,輸出結構化 JSON 報告與簡短可讀文本摘要。評估結果是 **reporter 而非 gate** —— 指標違規只反映在報告裡,不會讓進程失敗,也不進入 CI 門禁。

- 指標層(`metrics.py`)是純函數:只消費軌跡日誌與 golden 樣例,不 import `src/`,不觸網、不調 LLM,可離線單測。
- 入口(`run_eval.py`)通過 `build_agent_executor()` 構建真實執行器,與 `src/core/pipeline.py` 使用同一個執行捕獲鉤子,消費真實產物。
- 入口支持**單 agent 與多 Agent 運行**(`AGENT_ARCH=single|multi`,默認仍為 single):多 Agent 結果保留原有扁平 `tool_calls_log` 指標,並通過顯式 `stage_trajectories` 快照增加階段狀態與局部/累計步數報告。沒有階段快照時,單 agent 命令保持不變;JSON 僅追加股票範圍診斷字段。
- 入口用真實工具註冊表校驗 golden:`expected_tools` 拼錯或過期會被判為無效樣例(退出碼 1),而不是靜默按低命中繼續評分。
- 保留原有**最小指標契約**,另以 `stock_scope_metrics` 報告股票範圍診斷(Refs #2394);Codex `arguments_summary` 與嚴格 Chat 身份判定仍留給後續 PR。

## 快速開始

```bash
# 跑單個樣例(真實 LLM,依賴本地已配置的模型)
python evals/agent_trajectory/run_eval.py --sample 600519_technical

# 跑全部樣例,並輸出結構化 JSON(按樣例 id 鍵控)
python evals/agent_trajectory/run_eval.py --all --json-out eval_report.json
```

參數:

| 參數 | 說明 |
| --- | --- |
| `--sample ID` / `--all` | 二選一必填:跑單個 golden 樣例或全部 |
| `--golden-path PATH` | 自定義 golden JSON 路徑(默認模塊旁 `golden_samples.json`) |
| `--json-out PATH` | 寫結構化 JSON 報告(`--all` 時為鍵控對象) |

退出碼:`0` 運行成功(含違規);`1` golden 加載(含 `expected_tools` 不在真實工具註冊表)/ 樣例選擇 / 工具註冊表加載失敗 / 執行器構建 / 運行失敗(含執行器返回 `success=false`,如 provider 未配置、LLM 錯誤、超時、max_steps 耗盡、dashboard 解析失敗);`2` 用法錯誤。Multi-Agent 結果若在失敗時帶有階段快照,入口會先輸出並寫入可檢查的失敗軌跡報告,再以退出碼 `1` 表示運行失敗;單 Agent 失敗行為不變。

## 凍結的最小指標契約

對每條 `tool_calls_log`(runner 契約:每項含 `step / tool / arguments / success / duration / result_length / cached`,可選 `timeout` / `guarded`),只統計:

| 指標 | 定義 |
| --- | --- |
| `expected_hit_rate` / `missing_expected` | 期望工具仍按**工具名**命中(股票範圍另行報告);`expected_total` 為去重後的期望數 |
| `optional_tools_used` | 期望集合之外實際調用的工具;`allow_optional_tools=false` 時記為違規 |
| `redundant_calls` | 同一 (tool, args-key) 對在首次出現之後的每一次出現(不論成敗)。args-key = `json.dumps(arguments, sort_keys=True, default=str)`,與運行時緩存鍵同思路 |
| `retries` | 緊跟**失敗**之後重試同一 (tool, args-key) 對;`retries ⊆ redundant_calls`。成功會清除該對的失敗態:`fail → success → success` 只計 1 次 retry(後一次 success 僅計冗餘) |
| `failed_calls` | `success=false` 的條目數 |
| `cached_calls` | `cached=true` 的條目數(runner 語義:複用不可重試的失敗結果) |
| `distinct_steps` / `max_steps_touched` | 日誌 step 與 `AgentResult.total_steps` 取較大者(最後純回答輪不產生工具調用,日誌會低估);`max_steps_touched` 為 `max(step) >= allowed_max_steps` 的啟發式 |

## Multi-Agent 階段軌跡

當執行器結果攜帶非空 `stage_trajectories` 時,入口在上述工具指標之外輸出 `stage_metrics`。每個階段快照是穩定的 JSON-safe 白名單對象:

| 字段 | 說明 |
| --- | --- |
| `stage_name` | 階段或 specialist 名稱 |
| `status` | `completed` / `failed` / `skipped` 等階段狀態 |
| `total_steps` | 該階段自己的局部 agent-loop 步數,不是全局階段計數 |
| `tool_calls_log` | 該階段的原始工具調用日誌;空日誌也會保留階段 |
| `failure_reason` | `stage_failure` / `timeout` / `budget_skip` 等降級原因 |

評估層按快照列表順序把局部步數累加為 `cumulative_steps`,因此不同階段從 1 重新計步不會碰撞。該累計值也作為整條 Multi-Agent 軌跡的 agent-loop 步數傳給頂層指標；`AgentResult.total_steps` 在 orchestrator 中保留原有階段數語義,不用於軌跡 loop 預算評分。報告同時包含期望階段命中率、缺失/額外階段、完成/失敗/跳過計數,以及每個階段的狀態、失敗原因、局部/累計步數和工具調用/失敗/重試指標。階段 `tool_metrics` 僅統計該階段日誌中的調用數、工具名、冗餘、緩存、失敗和重試,不含期望工具命中率、缺失工具、期望外工具違規或 max-steps 違規。Golden 的 `expected_tools`、`allow_optional_tools`、`allowed_max_steps` 屬於整條樣例,只對彙總工具軌跡評估一次；當前不支持按階段定義工具合規期望。關鍵階段失敗後,仍使用已返回的快照生成階段報告;配置了 `expected_stages` 時,尚未執行的後續階段會列入缺失階段。specialist 併發執行後的快照由 scheduler 恢復為選中順序,不依賴完成先後。

golden 樣例可選增加 `expected_stages` 字段:

```json
{
  "expected_stages": ["technical", "intel", "decision"]
}
```

未配置時仍會報告實際階段和狀態,但階段命中率顯示為未配置;這不會改變現有單 agent 樣例的原指標字段。

## Golden 樣例 schema

`golden_samples.json` 是一個數組,字段:

| 字段 | 類型 | 說明 |
| --- | --- | --- |
| `id` | string | 唯一樣例 id(必填) |
| `task_description` | string | 交給執行器的任務文本(必填) |
| `stock_code` | string | 原樣傳入 runner context(`{"stock_code": ...}`);空串 = 無 context;默認作為股票範圍,不改變原工具命中率 |
| `allowed_stock_codes` | string[] / null | 可選允許股票列表;省略或 null 使用 `stock_code`;顯式列表必須非空、無空白項或重複項,支持多股對比並覆蓋默認範圍 |
| `expected_tools` | string[] | 期望工具名(必填,非空、無重複) |
| `allowed_max_steps` | int | 步數預算啟發式(默認 10,>= 1) |
| `allow_optional_tools` | bool | 是否容忍期望外工具(默認 true) |
| `expected_stages` | string[] | 多 Agent 階段期望列表(可選、非空名稱且不重複);用於統計命中與缺失階段 |

校驗:加載路徑(`load_golden_samples`)直接拒絕非法樣例;直接構造路徑(`compute_trajectory_metrics`)以 validator 完全相同的措辭逐條上報違規,兩條路徑的契約按構造保持一致。`known_tool_names` 可注入真實工具註冊表做成員校驗(metrics 層自身不 import `src/`);`run_eval.py` 入口會自動注入真實工具註冊表。

## JSON 報告 schema

單個樣例:

```json
{
  "sample_id": "600519_technical",
  "task_description": "…",
  "stock_code": "600519",
  "metrics": { "expected_hit_rate": …, "expected_total": …, "…": "… 共 11 個字段" },
  "violations": ["…"],
  "stock_scope_metrics": { "enabled": true, "allowed_stock_codes": ["600519"], "…": "…" }
}
```

`--all --json-out` 時外層為 `{sample_id: <上述對象>}` 鍵控對象。

含階段快照的多 Agent 報告會在上述對象中追加 `run_status` (`completed` / `failed`) 與 `stage_metrics` 字段;原有 `metrics` 字段繼續表示扁平工具軌跡指標。運行失敗但攜帶階段快照時,JSON 報告仍會寫出,進程退出碼為 1。

## 股票範圍診斷(Refs #2394)

`run_eval.py` 仍調用 `executor.run()`，不會為了評估建立 Chat 運行時 guard。因此診斷直接檢查工具參數，不依賴 `guarded` 是否存在。原有 `metrics`、`violations`、工具名命中率和退出碼保持原語義；越界先作為獨立報告項，不升級為 gate，也不改變線上分析/攔截邏輯。

入口通過真實工具定義和 `_is_stock_scoped_tool` 注入受限工具集合，並通過 `_normalize_guard_stock_code` 與同一指數註冊表注入歸一化函數。`metrics.py` 仍不 import `src/`。例如 `600519` / `SH600519`、`HK00700` / `0700.HK` 視為同一標的，註冊指數與同數字股票仍分開；`get_market_indices` 等沒有 `stock_code` 參數的大盤工具不參與範圍判定。

單樣例 JSON 頂層追加 `stock_scope_metrics`，多 Agent 的每個 `stage_metrics.stage_metrics[]` 也追加同名局部診斷：

| 字段 | 說明 |
| --- | --- |
| `enabled` / `allowed_stock_codes` | 是否配置了可評估範圍及歸一化後去重的允許代碼；無 `stock_code` 且未聲明列表時為 false，不把未知範圍當成零違規證明 |
| `evaluated_calls` / `in_scope_calls` | 有顯式 `arguments.stock_code` 的受限工具調用數 / 其中落在允許範圍的次數 |
| `out_of_scope_calls` / `out_of_scope_details` | 越界請求次數及每次的 `step`、`tool`、歸一化 `requested_stock_code`、允許代碼和 `guarded`；失敗、緩存和已攔截請求都計數 |
| `unscorable_calls` | 配置範圍後，受限工具缺少結構化 `arguments` 或 `stock_code` 的次數；不從查詢文本、`arguments_summary` 或日誌允許範圍猜測；顯式 null/空標的會被評估為越界 |
| `guarded_calls` | 日誌中 `guarded=true` 的次數，獨立於越界數；身份不可用、資產不支持等原因也可能觸發 guard，不能直接等同越界 |
| `validation_issues` | 直接構造非法 golden 範圍時的校驗問題；禁用該非法範圍的評分，避免靜默放寬；文件加載路徑直接拒絕非法 golden |

同一調用在頂層按扁平日誌統計一次，在所屬階段按該階段日誌統計一次；不要把頂層與階段數相加。階段明細保留局部 step，累計 step 仍由原有階段報告提供。顯式允許列表覆蓋默認 `stock_code`；它只定義評分期望，不改變執行器 context 或注入運行時權限。

新增 `600519_ignore_distractor` 樣例要求只查詢茅臺，文本中另提平安銀行作為干擾。以下命令會使用真實模型/數據源，可能產生費用；離線測試不調用這些服務：

```bash
python evals/agent_trajectory/run_eval.py --sample 600519_ignore_distractor --json-out scope_report.json
python -m pytest tests/test_agent_trajectory_metrics.py tests/test_agent_trajectory_run_eval.py -q
```

## 不在範圍(後續 PR)

- 按股票維度重定義期望工具命中率,或把越界請求提升為原有 `violations` / CI 門禁
- 改走 Chat 入口、嚴格 Chat 身份/資產支持校驗,以及從自然語言查詢推斷股票範圍
- Codex App Server 的 `arguments_summary` 方言識別
- 任何 `.env` / 運行時配置與 CI 門禁(本 PR 不改變現有分析流程、調度語義或 CI 阻斷規則)
