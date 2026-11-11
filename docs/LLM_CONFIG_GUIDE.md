# LLM (大模型) 配置指南

> **平臺邊界（2026-11-08）：** Gemini API 與 Vertex AI 的模型生命週期不同。Vertex AI 的 `gemini-3.6-flash` 佔位值僅為輸入示例；[Google Cloud 文檔](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-6-flash)列出的該平臺退役日期為 2026-11-19。請確認模型在你的項目和區域中可用；Gemini API 驗證通過不代表 Vertex AI 也已驗證。僅配置 DeepSeek Key 時會推斷使用 `deepseek/deepseek-v4-flash`；顯式模型及更高優先級配置仍然優先。

歡迎！無論你是剛接觸 AI 的新手小白，還是精通各種 API 的高玩老手，這份指南都能幫你快速把大模型（LLM）跑起來。

本項目對外提供統一的 AI 模型接入體驗，支持主流官方 API、OpenAI 兼容平臺以及本地模型。底層由 [LiteLLM](https://docs.litellm.ai/) 驅動，但大多數用戶只需要理解“選服務商、填 API Key、選主模型/渠道”這條默認路徑。為了照顧不同階段的用戶，我們設計了“三層優先級”配置，按需選擇最適合你的方式即可。

如果你正在選擇具體服務商、配置 GitHub Actions Secrets / Variables、排查 `details.reason` 錯誤或準備回滾配置，請優先查看 [LLM 服務商配置指南](./llm-providers.md)。該文檔集中維護 provider 預設、Actions 變量對照、運行時能力檢測邊界和常見錯誤處理建議。

> 本頁的 provider/model/Base URL 說明本次未新增外部兼容語義，僅用於同步現網約定；實際兼容判斷仍按當前倉庫鎖定依賴與運行時實現執行：
> - 依賴邊界：`litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（與 `requirements.txt` 一致）。
> - 兼容驗證入口：`tests/test_system_config_service.py`、`tests/test_system_config_api.py` 以及現有前端模型配置頁迴歸用例。
> - 回退路徑：優先使用 `.env` 配置備份 + `POST /api/v1/system/config/import` 恢復；也可在重啟前手動回填舊 `LITELLM_MODEL` / `LLM_*` / `AGENT_LITELLM_MODEL` / `VISION_MODEL` / `LLM_TEMPERATURE` / `LLM_USAGE_HMAC_*`。

> **說明**：本頁對 provider/model/base URL 的說明同步沿用當前依賴約束與歷史約定，僅做文檔補充，不引入新的運行時 provider、模型或 Base URL 行為變更。

---

## 快速導航：你應該看哪一節？

1. **【新手小白】** "我只想趕緊把系統跑起來，越簡單越好！" -> [指路【方式一：極簡單模型配置】](#方式一極簡單模型配置適合新手)
2. **【進階用戶】** "我有好幾個 Key，想配置備用模型，還要改自定義網址(Base URL)。" -> [指路【方式二：渠道(Channels)模式配置】](#方式二渠道channels模式配置適合進階多模型)
3. **【高玩老手】** "我要做複雜的負載均衡、請求路由、甚至多異構平臺高可用！" -> [指路【方式三：YAML 高級配置】](#方式三yaml-高級配置適合老手自定義)
4. **【本地模型】** "我想用 Ollama 本地模型！" -> [指路【示例 4：使用 Ollama 本地模型】](#示例-4使用-ollama-本地模型)
5. **【視覺模型】** "我想用圖片識別股票代碼！" -> [指路【擴展功能：看圖模型(Vision)配置】](#擴展功能看圖模型-vision-配置)

---

## Generation Backend（Phase 4）

Generation backend 是普通分析、大盤覆盤和 `generate_text()` 的外層運行時選擇。默認仍是 `litellm`，零配置路徑與歷史行為保持一致；`codex_cli` / `claude_code_cli` / `opencode_cli` 是顯式 opt-in 的本地 CLI backend，當前標記為 **experimental/limited**。

```env
GENERATION_BACKEND=litellm
GENERATION_FALLBACK_BACKEND=litellm
GENERATION_BACKEND_TIMEOUT_SECONDS=300
GENERATION_BACKEND_MAX_OUTPUT_BYTES=1048576
GENERATION_BACKEND_MAX_CONCURRENCY=1
LOCAL_CLI_BACKEND_MAX_CONCURRENCY=1
# 可選：留空時使用本機 OpenCode 默認模型；配置時作為 --model 覆蓋值傳給 OpenCode。
# OPENCODE_CLI_MODEL=provider/model
AGENT_BACKEND=auto
AGENT_GENERATION_BACKEND=auto
```

- `GENERATION_BACKEND=litellm|codex_cli|claude_code_cli|opencode_cli`。本地 CLI backend 是 generation backend，不是 LiteLLM provider；不要寫 `LITELLM_MODEL=codex_cli/...`、`LITELLM_MODEL=claude_code_cli/...` 或 `LITELLM_MODEL=opencode_cli/...`。
- `GENERATION_BACKEND=opencode_cli` 時默認不傳 `--model`，由本機 OpenCode 使用自身默認模型配置；`OPENCODE_CLI_MODEL` 只是可選覆蓋值，配置時才作為單個 `--model` 參數傳給 OpenCode。provider 認證、賬號和模型可用性由本機 OpenCode 自身配置負責；DSA 不接管這些配置。
- `GENERATION_FALLBACK_BACKEND` 未配置時默認 `litellm`；本地 `.env` 顯式空值 `GENERATION_FALLBACK_BACKEND=` 表示禁用 backend-level fallback；primary 與 fallback 相同時解析為 no-op。倉庫自帶 GitHub Actions workflow 未配置該變量時會顯式導出 `litellm`，如果要在 Actions 中禁用 backend fallback，請把 fallback 設為 primary backend，例如 `GENERATION_BACKEND=codex_cli` + `GENERATION_FALLBACK_BACKEND=codex_cli`。
- `GENERATION_BACKEND=codex_cli|claude_code_cli` 且沒有 Gemini/OpenAI/Anthropic/DeepSeek API Key 時，普通分析和大盤覆盤仍會嘗試本地 CLI backend；如果對應 executable 不存在，會返回結構化 `command_not_found`，不會報“API Key 未配置”。
- 當前 `codex_cli` preset 使用 `codex --ask-for-approval never exec --sandbox read-only --output-last-message <temp-file> -`：普通分析是無人值守生成任務，固定 `never` 可避免非交互運行停在人工批准請求，同時仍由 `read-only` 保持只讀邊界。DSA 從臨時文件讀取最終響應；Codex CLI 同時打印到 stdout 的重複內容會從診斷預覽和輸出大小統計中剔除，不參與主分析 JSON 解析。官方依據見 [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive) 與 [Codex CLI command line options](https://developers.openai.com/codex/cli/reference)。本倉庫當前真實驗證 `codex-cli 0.144.3`，不聲明更寬最低版本；如果 CLI 版本不支持 preset 參數，DSA 會返回結構化 `capability_unsupported` / `cli_contract_unsupported` 診斷，並在配置 backend fallback 時回退到 `litellm`。
- 當前 `claude_code_cli` preset 使用 `claude --safe-mode --tools "" --disallowedTools "mcp__*" --strict-mcp-config --no-session-persistence --output-format json -p <static instruction>`，完整 DSA prompt 通過 stdin 傳入。DSA 只從 Claude JSON envelope 的 `result/success` 最終字段提取文本；如果後續啟用 `--json-schema`，schema mode 必須提取 `structured_output`，並且仍會繼續經過 DSA 現有 JSON validator、minimal parser contract、`_parse_response()`、integrity retry、placeholder fill 和 usage telemetry。參數依據見 [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)；本 PR smoke 驗證版本為 `claude 2.1.177 (Claude Code)`，不聲明更寬最低版本。
- 當前 `opencode_cli` preset 使用 `opencode --pure run --format json [--model <OPENCODE_CLI_MODEL>] <static instruction> --file <temp prompt file>`；只有顯式配置 `OPENCODE_CLI_MODEL` 時才追加 `--model`，完整 DSA prompt 寫入權限受控的臨時文件，不進入 argv。DSA 只解析 OpenCode JSON event 輸出中無工具事件的 `text` 內容，並要求正常 `step_finish`；出現 `tool_use`、`error`、`question`、`permission` 等事件會結構化失敗。參數依據見 [OpenCode CLI reference](https://opencode.ai/docs/cli)，項目配置合併語義見 [OpenCode config reference](https://opencode.ai/docs/config)；本 PR smoke 驗證版本為 `opencode 1.17.11`，不聲明更寬最低版本。
- 本地 CLI backend 不支持 streaming。請求 stream 時會自動降級為 non-stream，不會因此返回 `capability_unsupported`。
- 本地 CLI usage 通常不可用，系統不會寫入 fake 0 token、fake cost 或 fake cache telemetry。
- 本地 CLI 執行上限有硬邊界：`GENERATION_BACKEND_TIMEOUT_SECONDS` 最大 `3600`，`GENERATION_BACKEND_MAX_OUTPUT_BYTES` 最大 `33554432`，`GENERATION_BACKEND_MAX_CONCURRENCY` 最大 `16`，`LOCAL_CLI_BACKEND_MAX_CONCURRENCY` 最大 `4`。診斷 stdout/stderr 與最終響應合計超過輸出上限時會返回結構化 `output_too_large`；對 `--output-last-message` preset，stdout 中重複打印的最終響應不會重複計入，也不會作為 `stdout_preview` 暴露。
- 本地 CLI 的 `stdout_preview` / `stderr_preview` 在寫入結構化 diagnostics 前會脫敏短憑證賦值，不依賴值長度：大寫環境變量賦值沿用 child-env 的 fail-closed 敏感名稱判定，JSON 與 YAML / 普通日誌中的標量賦值使用更窄的憑證字段 allowlist，URL 繼續使用獨立的 userinfo / webhook / 敏感參數規則。`token_budget`、`session_id`、`sort_key` 等普通排障字段不會僅因包含 `token`、`session` 或 `key` 子串而被刪除；但未加引號的 YAML 敏感標量沒有可靠的同行邊界，因此從該值起到行尾會 fail-closed 脫敏，同行後續字段也不會保留。
- 本地 CLI 默認併發為 1；有效併發為 `min(LOCAL_CLI_BACKEND_MAX_CONCURRENCY, GENERATION_BACKEND_MAX_CONCURRENCY)`，不繼承 `MAX_WORKERS`。
- `AGENT_GENERATION_BACKEND=auto` 不會繼承 `GENERATION_BACKEND` 的 local CLI 值；Agent 工具調用繼續使用 LiteLLM。Web 設置頁僅暴露 `auto|litellm`；手寫 `AGENT_GENERATION_BACKEND=codex_cli|claude_code_cli|opencode_cli` 不實現 text-only Agent mode，會返回明確 unsupported tool-calling 診斷。
- Phase 6a 的 DSA Tool Surface 保留工具 schema、權限元數據、scope guard、結構化錯誤和審計/脫敏能力；默認 LiteLLM 繼續使用原有 registry/runner，不因移除 runtime 改造工具入口。`codex_cli` / `claude_code_cli` / `opencode_cli` 仍是 generation-only，不能作為 Agent tool fallback。
- Web 設置頁的生成後端快速檢查只讀取已保存的 `.env`、運行時兜底值和未保存草稿；它不會寫配置、重載運行時，也不會發起真實模型請求。`available` 只表示當前配置具備嘗試運行的條件。JSON 冒煙測試是單獨的顯式操作，會使用服務端固定的 JSON 提示詞和 schema 發起一次真實的生成後端請求，用於驗證提取器、JSON 契約、超時、輸出限制和 usage-unavailable 語義。
- `GET /api/v1/system/config/generation-backends/status` 只讀取已保存配置；未保存草稿需調用 `POST /api/v1/system/config/generation-backends/status/preview` 或 `POST /api/v1/system/config/generation-backends/smoke-test`。被遮罩的密鑰字段會繼續沿用已保存值。`health_status` 與 `last_error_code/message` 只代表本次計算結果，不是歷史持久健康狀態。

### 問股會話狀態與升級

服務端統一保存主討論對象及會話 Skill；LiteLLM single／現有 multi 消費同一次接受快照。省略或 `null` Skill 沿用已保存選擇（未選擇時使用配置默認）；顯式 `[]` 保存清空選擇並使用內置默認，不啟用配置中的非空 Skill。名稱只在服務端索引唯一匹配時確認；比較不切股，模型失敗／停止不撤銷已接受狀態。併發或會話實例衝突時，請手動刷新後重試，頁面保留輸入與待提交選擇，不自動重發。

舊會話只恢復明確代碼，不從歷史名稱造新事實；“分析600519 → 改看寧德時代 → 風險呢”需要再確認，不能繼續沿用600519。升級自動追加狀態列，不刪除消息／Skill／報告。升級或回滾前停止後端，使用 SQLite backup 或停服完整備份（不能在 WAL 活躍時只複製主文件）；保留原配置、數據庫位置和數據目錄，更新配套後端／Web 後重啟，不手工刪表／刪列。回滾保留新增列，舊代碼仍可寫消息與 Skill；再次升級若發現回滾期間新增用戶消息，先顯示未確認，再由用戶明確確認對象。舊／新寫進程混跑不支持；分離部署升級先後端再 Web，回滾先 Web 再後端。

代碼與名稱混用時，比較範圍包含兩者；緊鄰的明確代碼可消除同名上市地歧義（如 `688981中芯國際`）。`從600519改看300750`／`把600519換成300750` 按操作詞關聯的目的地確認300750，不因當前已經是300750或重複發送而反向切回600519；每次接受仍保存消息並遞增版本。明確切股只開放新對象的工具範圍，並移除不匹配的舊報告提示；目的地含多個備選項時需澄清，不能任選最後一個或排除當前對象後猜選。

已有主對象時，`看看近期走勢`／`分析一下財務狀況`／`分析風險` 正常繼續分析，保留原確認來源和時間；`分析300750` 或唯一匹配名稱仍可確認新對象。單獨的“分析／看看”加尾隨文本不證明切股；明確但無法確認的“改看…”需澄清，不啟動分析。舊歷史沿用同一方向與動作判定，但只用有效明確代碼建立事實：普通追問保留候選，無法確認的新切換使舊候選失效，後續追問不能復活它；後續明確代碼可重新建立。歷史名稱僅作為目標變化證據，不補造確認事實；讀取恢復結果不寫回股票或遞增版本。

否定、詢問、條件或引用中的切換不作為肯定確認：`不要改看300750，繼續分析600519` 維持600519；`是否改看300750？` 保留對象並澄清，不開放300750。代碼和名稱按實際出現位置解釋；舊歷史只有目的地位置的有效代碼能確認，句子另一處同碼不能替歷史名稱造事實。首次單獨輸入有效代碼／唯一名稱仍可確認，但任意文本中的唯一提及不自動確認。

`如果600519下跌，就改看300750` 的相鄰條件與後件即使被逗號分隔，也只保存問題並澄清，不立即切股或啟動分析；舊歷史恢復同樣不把它當成新確認。被否定的強／弱／選擇比較不貢獻參與對象，例如 `不要研究600519和300750的區別，繼續分析600519` 仍正常分析600519，工具範圍只有600519。獨立分句中的肯定請求不被整條消息的條件／否定屏蔽。

問股個股回測工具的彙總、明細、總數與分頁共同使用 guard 已驗證的市場身份；合法前綴／後綴與現有 CN 寫入器的數字存儲鍵均可讀取，不重新按裸碼索引選擇其他市場。數字鍵僅由已驗證 SH／SZ／BJ 對象按原寫入規範生成；明細須關聯同對象分析來源，來源中的明確其他市場不被認領。數字彙總須有同一回測窗口／引擎的同對象明細依據，存在衝突數字來源時不認領該彙總；缺失可證明歸屬的數據正常返回無數據。沒有市場字段的正常舊 CN 分析沿用原裸碼存儲約定，不一律排除數字鍵。未提供嚴格目標的原 service／repository 入口保持 legacy 行為，不遷移或改寫歷史數據。此內部目標參數僅用於現有工具的彙總／明細讀取，不支持日期／phase 動態聚合；顯式請求不支持的組合會報錯，不丟棄身份約束。

普通追問中的順帶提及不擴展工具範圍。嚴格 Chat 的現有標的工具共用身份、scope 與適用性檢查，使用本次工具調用驗證好的目標讀取緩存及選擇數據源；日線、技術分析和實時行情保留股票／指數區分，緩存缺失不改查同碼股票。執行前必要身份失效只拒絕受影響對象，其他仍可確認的 scope 成員不連帶禁用；驗證後同一次調用不再讀取註冊表重新分類。籌碼、公司資料、資金流和個股回測不支持指數，明確返回不支持；原市場與 ETF 條件保留。嚴格自定義工具未聲明適用類型時只拒絕該調用。新聞對象由已確認身份／名稱決定，不採用模型猜測的另一股票名稱。

同名會話的當前 Bot 與 Web 可以繼續交替提問：Web 已確認對象後，Bot 普通追問使用該對象的嚴格工具範圍，合法比較只為本輪增加比較對象；兩者都保留 Web 主對象及其確認來源／時間，不遞增股票狀態版本。Bot 不獨立持久化新主對象；明確切股或無法安全維持舊對象時，Web 狀態進入待重新確認，不能繼續聲稱舊對象可靠。真正舊代碼／回滾期間的未知用戶寫入仍要求重新確認，不能當作當前狀態感知 Bot。當前 Bot 提交校驗準備快照的實例、版本和最新用戶消息錨點；期間已有新接受則拒絕舊提交，不追加舊問題或自動重試模型。回覆、provider trace 和摘要仍綁定該次讀取的會話實例與真實消息來源，刪除後重建不會接收舊實例的遲到寫入。Web 的遲到初始列表可以更新列表展示，不能清空新請求／新接受實例或取消其 stream；正常的無會話恢復、切換和新建仍使用既有邏輯。

會話狀態契約不改變模型路由或 Phase 2 generation-only 能力。Codex App Server 問股後端已移除，不再提供等待 Gate 解鎖的執行入口。歷史 Gate 0B 的 BLOCKED 記錄不因此變為通過；受控執行端的狀態驗證也不能證明真實運行層或所有平臺升級通過。

### Codex App Server 問股退役

Codex App Server 問股後端已移除。`AGENT_BACKEND` 僅支持 `auto`（推薦，保持默認 LiteLLM）或 `litellm`。舊 `codex_app_server` 可加載、顯示和導出，但執行請求在準備與接受提交前返回 `backend_removed`，不會自動切換模型、賬號或 provider。請在「設置 → Agent 設置 → 問股生成方式」主動選擇合法值並保存；已有舊值不阻止無關設置保存，顯式保存或導入舊值則拒絕且不部分寫入。狀態與草稿預覽只檢查配置，不啟動 Codex 命令或 schema/version 探針，也不調用模型。歷史會話、股票身份、Skill、單/多 Agent 與 provider trace 保持原契約。獨立 `GENERATION_BACKEND=codex_cli` 普通報告及其他 generation-only 不受此移除影響，仍需各自 CLI 及其原有依賴。

### Local CLI 本地 backend 隱私與邊界

- 本地 CLI Backend 不等於離線模型；Codex / Claude Code / OpenCode 背後的服務可能處理股票代碼、新聞、持倉上下文、分析 prompt、報告草稿等內容。
- Docker、雲服務器、CI 不天然擁有你本機的 CLI 登錄態。
- GitHub Actions 只負責透傳配置值，不安裝或登錄本地 CLI；如果在 Actions 中 opt-in local CLI backend，runner 上缺少可執行文件或登錄態時應看到結構化失敗。
- DSA 不讀取 Codex/Claude/OpenCode credential 文件，但子進程可能讀取 CLI 自身登錄態。
- macOS 從 Finder/Dock 啟動桌面端時不繼承 shell PATH；打包桌面端會在啟動後端時補入常見 Homebrew 路徑（如 `/opt/homebrew/bin`、`/usr/local/bin`）。如果設置檢查仍提示找不到 CLI 可執行文件，請完全退出並重開 DSA；打開 CLI 交互窗口不會改變已運行後端的 PATH。
- DSA 默認只繼承最小運行環境，並拒絕通配繼承 `CLAUDE_*`、`ANTHROPIC_*`、`OPENCODE_*`、`OPENAI_*`、`GOOGLE_*`、`GEMINI_*`、`AWS_*`、`AZURE_*`、`VERTEX_*`、`*_API_KEY`、`*_AUTH_TOKEN`、`*_ACCESS_TOKEN`、`*_SECRET`、`*_PASSWORD`，降低 DSA API keys、provider tokens 和 webhook tokens 洩漏風險。`CODEX_HOME` 是為兼容既有 Codex CLI 登錄目錄保留的精確例外；不會恢復 `CODEX_CLI_*` 通配。
- `opencode_cli` 會在臨時 cwd 寫入最小項目 `opencode.json` 以關閉分享、自動更新、快照和常見工具權限，但 OpenCode resolved config 仍可能包含用戶本機全局配置；運行時安全邊界同時依賴 `--pure`、env denylist、prompt file 權限和 event extractor fail-closed。
- Web 設置頁只暴露安全 preset，不允許提交任意 command / argv / shell string。
- `codex_cli` / `claude_code_cli` / `opencode_cli` 仍標記為 experimental/limited；如果你的 CLI 版本不支持本倉庫已驗證的非交互輸出契約，DSA 會返回結構化 `capability_unsupported`、`cli_contract_unsupported`、`invalid_json`、`schema_validation_failed` 或對應 backend error，並在配置 backend fallback 時回退到 `litellm`。無法接受該版本漂移風險時，請保持 `GENERATION_BACKEND=litellm`。
- `opencode_cli` 不支持 OpenCode serve / web / ACP / MCP / attach / `--dangerously-skip-permissions`；DSA 不把 OpenCode final text 當成 Agent tool success。

## 方式一：極簡單模型配置（適合新手）

**目標：** 只要記得填入 API Key 和對應的模型名就能立刻用。不需要折騰複雜概念。

如果你只打算用一種模型，這是最快捷的辦法。打開項目根目錄下的 `.env` 文件（如果沒有，複製一份 `.env.example` 並重命名為 `.env`）。

Modelflare 使用標準 Channels 配置，見下方 [Modelflare 示例](#示例modelflare)。本節保留單模型 legacy 配置，現有配置無需遷移。

### 示例 1：使用通用第三方平臺（兼容 OpenAI 格式，推薦）

現在市面上絕大多數第三方聚合平臺（例如硅基流動、AIHubmix、阿里百鍊、智譜等）都兼容 OpenAI 的接口格式。只要平臺提供了 API Key 和 Base URL，你都可以按照以下格式無腦配置：

```env
# 填入平臺提供給你的 API Key
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxx
# 填入平臺的接口地址 (非常重要：結尾通常必須帶有 /v1)
OPENAI_BASE_URL=https://api.siliconflow.cn/v1
# 填入該平臺上具體的模型名稱（非常重要：注意前面必須加上 openai/ 前綴幫系統識別）
LITELLM_MODEL=openai/deepseek-ai/DeepSeek-V3 
```

### 示例 2：使用 DeepSeek 官方接口
```env
# 填入你在 DeepSeek 官方平臺申請的 API Key
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```
*僅填這一行時，系統默認使用 `deepseek/deepseek-v4-flash`。*
`deepseek-chat` / `deepseek-reasoner` 已被 DeepSeek 官方公告於 2026/07/24 停用，舊配置請遷移；新配置建議通過 Web 快速渠道或顯式 `LITELLM_MODEL=deepseek/deepseek-v4-flash` 遷移到 `deepseek-v4-flash` / `deepseek-v4-pro`。

### 示例 3：使用 Gemini 免費 API
```env
# 填入你獲取的 Google Gemini Key
GEMINI_API_KEY=AIzac...
```

### 示例 4：使用 Ollama 本地模型
```env
# Ollama 無需 API Key，本地運行 ollama serve 後即可使用
OLLAMA_API_BASE=http://localhost:11434
LITELLM_MODEL=ollama/qwen3:8b
```

> **重要**：Ollama 必須使用 `OLLAMA_API_BASE` 配置，**不要**使用 `OPENAI_BASE_URL`，否則系統會錯誤拼接 URL（如 404、`api/generate/api/show`）。遠程 Ollama 時，將 `OLLAMA_API_BASE` 設為實際地址（如 `http://192.168.1.100:11434`）。當前依賴約束為 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（與 requirements.txt 一致）。

### Anspire Open legacy 兼容示例

現有 Anspire 搜索與 LLM 共用 Key 的兼容路徑繼續保留。以下為配置示例，模型與網關可用性以賬號權限和 Anspire 控制檯為準；可在 Web 設置頁點擊“測試連接”確認。

```env
# Anspire Open API Keys（支持多個，逗號分隔）
# 獲取: https://open.anspire.cn/dsa?share_code=QFBC0FYC
# 滿足默認優先級條件時，系統會複用該 Key 處理搜索與 LLM（僅限示例兜底路徑）。
# 示例模型：Doubao-Seed-2.0-lite；示例網關：https://open-gateway.anspire.cn/v6
ANSPIRE_API_KEYS=sk-xxxxxxxxxxxxxxxx
# 可選：按控制檯可用性切換模型或網關
# ANSPIRE_LLM_MODEL=Doubao-Seed-2.0-pro
# ANSPIRE_LLM_BASE_URL=https://open-gateway.anspire.ai/v6
```

> **恭喜！小白讀到這裡就可以去運行程序了！**
> 想測測看通沒通？在主目錄打開命令行輸入：`python scripts/check_env.py --llm`

---

## 方式二：渠道(Channels)模式配置（適合進階/多模型）

**目標：** 我有多個不同平臺的 Key 想要混著用，如果主模型卡了/網絡掛了，我希望它能自動切換到備用模型。

**網頁端可以直接配：** 你可以啟動程序後，在 **Web UI 的“系統設置 -> AI 模型 -> AI 模型接入”** 中非常直觀地進行可視化配置！

> **新版編輯體驗補充**：對於 DeepSeek、阿里百鍊（DashScope）以及其他兼容 OpenAI `/v1/models` 的渠道，設置頁現在支持直接點擊“獲取模型”，從 `{base_url}/models` 拉取可用模型並多選；底層仍會保存為原來的 `LLM_{CHANNEL}_MODELS=model1,model2` 逗號格式。若渠道不支持該接口、鑑權失敗或暫時不可達，仍可繼續手動填寫模型列表，不影響保存。

### 首次啟動配置狀態

後端提供只讀狀態接口 `GET /api/v1/system/config/setup/status`，用於判斷首次啟動閉環中最基礎的幾類配置是否已經就緒：LLM 主渠道、Agent 渠道、自選股、通知渠道和本地存儲。這個接口只讀取已保存的 `.env` 與當前進程環境變量，不會重載運行時配置、寫入 `.env`、測試真實模型或創建數據庫文件；前端嚮導和後續 smoke run 可以基於該接口逐步接入。

### Web 渠道編輯器的兼容性 / 遷移 / 回退規則

- 預設裡的 provider / API Surface / Base URL / 示例模型只用於**初始化表單**；真正落盤時仍是你當前輸入的 `LLM_{CHANNEL}_PROTOCOL`、`LLM_{CHANNEL}_API_SURFACE`、`LLM_{CHANNEL}_BASE_URL`、`LLM_{CHANNEL}_MODELS`、`LLM_{CHANNEL}_API_KEY(S)`，不會在後臺偷偷改成別的 provider 名、Surface 或 URL。
- `LLM_{CHANNEL}_API_SURFACE` 可選 `chat_completions`（默認）或 `responses`；Responses 當前只支持 OpenAI-compatible 協議，而且渠道內每個模型的實際 LiteLLM provider 都必須是 `openai`。系統從當前安裝的 LiteLLM provider registry 識別直連前綴，並通過 `GET /api/v1/system/config` 的 `llm_model_providers` 返回給 Web 編輯器；前後端不再各自維護 provider 表。因此 `anthropic/claude-*`、`xai/grok-*` 以及未來 LiteLLM 新增的直連 provider 不會因本地白名單滯後而被錯誤包裝成 OpenAI route；衝突配置會在保存、啟動、狀態診斷和篩選入口一致拒絕，不會生成 `anthropic/responses/...`。`deepseek-ai/DeepSeek-V3`、`Qwen/...` 這類不在 registry 中的網關自有模型 ID 會規範化為 `openai/<網關模型 ID>`。同一渠道中的模型必須使用同一種 Surface，並且同一個規範化 route alias 不能跨渠道混用 Chat 與 Responses，否則 Router 可能把同一次公開 alias 調度到錯誤 endpoint；需要兩種 Surface 時必須使用不同別名。設置頁的“獲取模型”仍只調用 `{base_url}/models`；“測試連接”會按選中的 Surface 對模型列表首項發起一次最小請求，並展示 `resolved_model` 與 `resolved_api_surface`，不會在失敗後靜默重試另一 endpoint。若返回 `details.reason=model_access_denied`（例如 Issue #1208 中已觀測到的 SiliconFlow / OpenAI Compatible 經 LiteLLM 返回 `Model disabled`），請把它視為基於 provider 文案的 best-effort 模型可用性診斷，優先確認該模型是否已在當前賬號/key 下開通，必要時調整模型順序或移除不可用模型後重試；未覆蓋或語義不同的 provider 文案會繼續走兜底診斷。可選的“運行時能力檢測”必須由用戶顯式選擇後觸發，會額外發起 JSON / tools / stream / vision smoke 請求，結果僅代表當前賬號、模型和 endpoint 的一次 best-effort 檢測。上述檢測返回的結構化診斷字段**不會寫回** `.env`，也不會阻止保存。
- 若返回 `details.reason=provider_blocked`，表示服務商或中轉網關明確攔截了本次請求；它區別於本地網絡 / TLS 異常和 `model_access_denied`，應優先檢查賬號風控、地域或請求來源限制、模型權限、代理商網關策略和內容安全策略。
- 運行時能力檢測會產生真實 LLM 請求，可能帶來 token / 圖像輸入費用、RPM/TPM 限流、餘額不足或超時。檢測失敗可能來自賬號權限、模型未開通、endpoint 區域、餘額、服務商兼容層或 LiteLLM 轉換路徑，不等於該 provider 全局不支持對應能力。P3 未對所有真實 provider 做在線 smoke；兼容依據來自當前依賴約束 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 下的 LiteLLM `completion()` / OpenAI I/O format / streaming / exception mapping，以及 OpenAI Chat Completions 的 JSON mode、tool calling、streaming 和 vision input 形狀。
- 相關外部來源：LiteLLM Python SDK / OpenAI I/O format / streaming / exception mapping：<https://docs.litellm.ai/>；LiteLLM OpenAI-compatible 路由：<https://docs.litellm.ai/docs/providers/openai_compatible>；OpenAI Chat Completions：<https://platform.openai.com/docs/api-reference/chat/create>；JSON mode：<https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat>；tool calling：<https://platform.openai.com/docs/guides/function-calling?api-mode=chat>；streaming：<https://platform.openai.com/docs/guides/streaming-responses?api-mode=chat>；vision input：<https://platform.openai.com/docs/guides/images-vision?api-mode=chat>。
- 保存渠道時，只會更新這次提交的 key；不會因為切換渠道模式而靜默遷移整個舊配置。唯一會被**同步清理**的是運行時模型引用：如果 `LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`VISION_MODEL` 或 `LITELLM_FALLBACK_MODELS` 指向了當前已啟用渠道里已經不存在的模型，設置頁會在保存前把這些失效引用清空/移除，避免運行時繼續指向無效模型；即使當前啟用渠道沒有任何可選模型，也會清理缺少 legacy Key 支撐的託管 provider 舊值。`cohere/*`、`google/*`、`xai/*` 這類直連模型僅用於說明歷史 `direct-env` 兼容保留語義，不等於可用性承諾，是否可用請按各廠商官方模型/API 文檔再做實際驗證。
- 後端一致性依據：配置校驗鏈路在 `SystemConfigService._validate_llm_runtime_selection`（`src/services/system_config_service.py`）中通過 `_uses_direct_env_provider`（`src/config.py`）判斷運行時來源；當前僅 `gemini`、`vertex_ai`、`anthropic`、`openai`、`deepseek` 屬於託管 key provider，`cohere`、`google`、`xai` 不在該白名單中，因此會保留為直連模型。
- 回退方式也保持最小：把對應渠道模型列表改回去後重新選擇主模型 / fallback，或直接用桌面端導出備份 / 手動 `.env` 還原之前的 `LLM_*`、`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`LLM_TEMPERATURE`、`LLM_USAGE_HMAC_*` 即可，不需要額外跑遷移腳本。Web 端如需恢復配置，也可在啟用管理員鑑權（`ADMIN_AUTH_ENABLED=true`）後通過 `POST /api/v1/system/config/import` 回滾。
- 當前倉庫對此鏈路的依賴約束是 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（見 `requirements.txt`）；迴歸覆蓋包括 `tests/test_system_config_service.py`、`tests/test_system_config_api.py` 和 `apps/dsa-web/src/components/settings/__tests__/LLMChannelEditor.test.tsx`。

> **外部 provider 示例模型說明**：`cohere/*`、`google/*`、`xai/*` 等 provider 前綴值僅用於說明當前保存清理語義，**不代表該依賴約束內的逐型號可用性保證**。文檔或測試中的具體模型名都是配置保留行為樣例，不是生產推薦；實際可用性請以對應官方模型文檔為準，並結合倉庫依賴約束 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 複核。

### 回退與兼容性證據

- 依賴約束與靜默清理範圍：在 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 下，保存僅清理失效的 runtime 模型引用（`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`LITELLM_FALLBACK_MODELS`），`cohere/*`、`google/*`、`xai/*` 等非渠道直連模型會被保留。
- 回退方式：可直接用桌面端導出備份後通過 `POST /api/v1/system/config/import` 恢復；也可手動把 `.env` 中歷史 `LITELLM_* / AGENT_LITELLM_MODEL / VISION_MODEL / LLM_TEMPERATURE / LLM_USAGE_HMAC_*` 回填後重啟生效。Web 端執行導入前請先開啟管理員鑑權（`ADMIN_AUTH_ENABLED=true`）。
- 回退回歸證據：`tests/test_system_config_service.py::test_import_desktop_env_restores_runtime_models_after_cleanup` 覆蓋“清理後用桌面導出備份恢復 runtime 引用”。
- 直連 provider 迴歸證據：`tests/test_system_config_service.py::SystemConfigServiceTestCase::test_validate_accepts_minimax_model_as_direct_env_provider`、`test_validate_accepts_cohere_model_as_direct_env_provider`、`test_validate_accepts_google_model_as_direct_env_provider`、`test_validate_accepts_xai_model_as_direct_env_provider` 覆蓋直連 provider 保留語義。
- 前端迴歸命令：`cd apps/dsa-web && npm run lint && npm run build && npm run test -- src/components/settings/__tests__/LLMChannelEditor.test.tsx`。
- 建議回退操作鏈路（含設置頁刷新）：先導出桌面備份，`POST /api/v1/system/config/import` 導入後，再通過 `GET /api/v1/system/config` 刷新頁面配置，再確認 `LITELLM_MODEL / AGENT_LITELLM_MODEL / VISION_MODEL / LLM_TEMPERATURE / LLM_USAGE_HMAC_*` 與模型列表一致後再繼續使用。

### 常用官方文檔來源（用於核對預設 provider / Base URL / 模型命名）

- Modelflare：[快速開始](https://docs.modelflare.dev/quickstart/)、[接入端點](https://docs.modelflare.dev/guides/endpoints/)、[模型與分組](https://docs.modelflare.dev/guides/models-and-groups/)
- OpenAI Compatible 規範（LiteLLM）：<https://docs.litellm.ai/docs/providers/openai_compatible>
- OpenAI 官方：<https://platform.openai.com/docs/api-reference/chat>
- DeepSeek 官方：<https://api-docs.deepseek.com/>
- Anspire Open：<https://open.anspire.cn/dsa?share_code=QFBC0FYC>
- 阿里百鍊 DashScope 兼容模式：<https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope>
- Moonshot / Kimi 官方：<https://platform.moonshot.ai/docs/guide/compatibility>
- Anthropic 官方：<https://docs.anthropic.com/en/api/messages>
- Gemini 官方：<https://ai.google.dev/gemini-api/docs/openai>
- Cohere 官方：<https://docs.cohere.com/>
- Cohere API 參考：<https://docs.cohere.com/reference/>
- Cohere LiteLLM Provider：<https://docs.litellm.ai/docs/providers/cohere>
- Google Gemini API 與模型：<https://ai.google.dev/gemini-api/docs/openai>、<https://ai.google.dev/gemini-api/docs/models>
- Google LiteLLM Provider：<https://docs.litellm.ai/docs/providers/gemini>
- xAI 官方：<https://docs.x.ai/docs>
- xAI LiteLLM Provider：<https://docs.litellm.ai/docs/providers/xai>
- Ollama 官方：<https://github.com/ollama/ollama/blob/main/docs/api.md>

如果不方便用網頁版，在 `.env` 文件中配置也非常絲滑，它能讓你同時管理多個第三方平臺。規則如下：

1. **先聲明你有幾個渠道**：`LLM_CHANNELS=渠道名稱1,渠道名稱2`
2. **給每個渠道分別填寫配置**（注意全大寫）：`LLM_{渠道名}_XXX`

### 示例：Modelflare

[註冊 Modelflare](https://modelflare.dev/sign-up?utm_source=github&utm_campaign=daily_stock_analysis)，在控制檯創建 API Key 後配置：

```env
MODELFLARE_KEY=sk-xxx
```

只需填寫 `MODELFLARE_KEY`，後端自動啟用 Modelflare，默認地址為 `https://modelflare.dev/v1`、模型為 `openai/gpt-6.1-sol`，無需填寫渠道名、地址或模型。顯式 YAML 或 `LLM_CHANNELS` 優先，Modelflare 顯式渠道 Key 優先於此簡寫；清空 Key 或禁用渠道即可停用。推導不改寫已保存配置。

只聲明 `modelflare` 一個渠道且未填渠道模型列表時，未配置主模型時默認使用 `openai/gpt-6.1-sol`；配置主模型後，後端複用 `LITELLM_MODEL` 和帶 `openai/` 前綴的備用模型；主模型使用 `openai/<模型名>`。顯式 `LLM_MODELFLARE_MODELS` 優先，多渠道仍需分別聲明模型。推導不改寫已保存配置或模型選擇。

渠道名為 `modelflare` 時，未填寫或留空的接入地址自動使用 `https://modelflare.dev/v1`；顯式 `LLM_MODELFLARE_BASE_URL` 優先。該地址默認識別為 `openai` 協議，接口默認為 `chat_completions`；未設置 `LITELLM_MODEL` 時使用首個渠道模型。默認模型仍需賬號有訪問權限，不自動補充 API Key。

`gpt-6.1-sol` 是本項目的 Modelflare 默認模型。請按賬號權限選擇實際可用模型，並通過 Web「獲取模型」和「測試連接」確認；Base URL 不要附加 `/chat/completions`。Modelflare 是新建渠道的首選模板，已保存的渠道和主模型不會因模板順序調整而改變。Anspire Search 仍通過 `ANSPIRE_API_KEYS` 獨立配置。

客戶端快速添加按鈕及渠道說明中的「Modelflare 專屬註冊」都使用 app UTM，README 使用 github UTM。新建渠道尚未填寫 Key，或主模型/備用模型不屬於當前啟用渠道時，狀態預覽會提示「配置需要調整」並列出具體字段；補填 Key、選擇可用模型或清空無效的備用模型後重試，預覽不會自動改寫已保存配置。

### 兼容示例：Anspire Responses API（GPT-5.6 名稱為觀測樣本）

```env
LLM_CHANNELS=anspire
LLM_ANSPIRE_PROTOCOL=openai
LLM_ANSPIRE_API_SURFACE=responses
LLM_ANSPIRE_BASE_URL=https://open-gateway.anspire.cn/v6
LLM_ANSPIRE_API_KEY=sk-xxx
LLM_ANSPIRE_MODELS=gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna
LITELLM_MODEL=openai/gpt-5.6-sol
LITELLM_FALLBACK_MODELS=openai/gpt-5.6-terra,openai/gpt-5.6-luna
```

Anspire 官方接入頁公開了 `https://open-gateway.anspire.cn/v6/responses` 調用方式：<https://open.anspire.cn/model?link=sample&tab=models>。Responses 路由不按模型名寫死；上面的 GPT-5.6 名稱只是當前網關觀測樣本，不作為長期模型清單承諾。模型、Surface 與賬號權限請以渠道實時 `/models` 返回、服務商說明和連接測試為準。

### 示例：同時配置 DeepSeek 和某中轉平臺，並設置備用切換
```env
# 1. 開啟渠道模式，聲明這裡有兩個渠道：deepseek 和 aihubmix
LLM_CHANNELS=deepseek,aihubmix

# 2. 渠道一：配置 DeepSeek 官方
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_API_KEY=sk-1111111111111
LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro

# 3. 渠道二：配置一個常用的聚合中轉 API
LLM_AIHUBMIX_BASE_URL=https://api.aihubmix.com/v1
LLM_AIHUBMIX_API_KEY=sk-2222222222222
LLM_AIHUBMIX_MODELS=gpt-6.1-sol,claude-sonnet-4-6

# 4. 【關鍵】指定主模型和備用模型列表
# 平時首選用 deepseek 這款模型：
LITELLM_MODEL=deepseek/deepseek-v4-flash
# 可選：Agent 問股單獨指定主模型（留空則繼承主模型）
AGENT_LITELLM_MODEL=deepseek/deepseek-v4-pro
# 主模型崩了立刻挨個嘗試下面這倆備用模型：
LITELLM_FALLBACK_MODELS=openai/gpt-6.1-terra,anthropic/claude-sonnet-4-6
```

### 示例：Ollama 渠道模式（本地模型，無需 API Key）
```env
# 1. 開啟渠道模式，聲明 ollama 渠道
LLM_CHANNELS=ollama

# 2. 配置 Ollama 地址（本地默認 11434 端口）
LLM_OLLAMA_BASE_URL=http://localhost:11434
LLM_OLLAMA_MODELS=qwen3:8b,llama3.2

# 3. 指定主模型
LITELLM_MODEL=ollama/qwen3:8b
```

### 示例：Hermes 本地 HTTP Generation（Phase 3）
```env
LLM_CHANNELS=hermes
LLM_HERMES_PROTOCOL=openai
LLM_HERMES_BASE_URL=http://127.0.0.1:8642/v1
LLM_HERMES_API_KEY=sk-local-hermes
LLM_HERMES_MODELS=hermes-agent
LITELLM_MODEL=openai/hermes-agent
```

Hermes 是保留渠道名，只支持本機 loopback `/v1` OpenAI-compatible generation。Phase 3 只驗證普通分析與 JSON 輸出；不支持 Stream/SSE、Tools、Vision、Agent tools、遠程 Hermes 或進程生命週期管理。Hermes API Key 只能使用單個 `LLM_HERMES_API_KEY`，不要配置 `LLM_HERMES_API_KEYS` 或 `LLM_HERMES_EXTRA_HEADERS`。如果 Hermes 配置非法，系統會阻止 legacy provider silent fallback，避免錯誤地改用外部模型。Web 設置頁保存 reserved Hermes 渠道時，會顯式清空舊的 `LLM_HERMES_API_KEYS` / `LLM_HERMES_EXTRA_HEADERS` 並返回 warning；如需恢復舊值，請從 `.env` 備份、Git 歷史或桌面端導出備份手動還原，但 Phase 3 仍會拒絕非空的多 Key / Extra Headers 配置。

### MiniMax 渠道模型填寫說明

- For the official OpenAI-compatible MiniMax channel, use `MiniMax-M3.1-Flash,MiniMax-M3`. Explicit saved provider-prefixed IDs such as `minimax/MiniMax-M3.1-Flash` remain supported.
- Web 設置頁裡的主模型、Agent 主模型、Fallback、Vision 下拉會保留這個值原樣展示，不會再錯誤改寫成 `openai/minimax/<模型名>`。

### 默認模型問股 / LiteLLM 配置兼容說明

- `AGENT_BACKEND=auto|litellm` 時，問股 Agent 沿用與普通分析相同的三層優先級：`LITELLM_CONFIG`（LiteLLM YAML）> `LLM_CHANNELS` > legacy provider keys。只要上層配置有效生效，下層配置就不會再參與本次請求。
- YAML 模式下，Agent 直接複用 LiteLLM `model_list` / `model_name` 路由語義；渠道模式下，優先讀取 `AGENT_LITELLM_MODEL`，留空時繼承 `LITELLM_MODEL`，再按 `LITELLM_FALLBACK_MODELS` 繼續 fallback。
- 如果你沒有啟用 YAML / Channels，且 `AGENT_LITELLM_MODEL` 也留空，但本地仍保留 legacy 環境變量，問股 Agent 依然會繼承舊配置：`GEMINI_API_KEY + GEMINI_MODEL` -> `gemini/<model>`，`OPENAI_API_KEY + OPENAI_MODEL` -> `openai/<model>`，`ANTHROPIC_API_KEY + ANTHROPIC_MODEL` -> `anthropic/<model>`。
- 該兼容邏輯只增強“失敗時保留後端真實錯誤原因”和“未配置 LLM 時給出更具體診斷”，**不會**靜默刪除、清空、遷移或改寫你現有的 `GEMINI_*` / `OPENAI_*` / `ANTHROPIC_*` / `LITELLM_*` 配置。
- 如果當前環境沒有任何有效 Agent 模型鏈路，問股頁面會繼續按失敗語義返回，並直接展示後端真實配置診斷；補齊任一有效模型來源後即可恢復，無需額外執行配置遷移腳本。
- 推薦的新配置方式仍然是顯式設置 `LITELLM_MODEL` / `AGENT_LITELLM_MODEL` 或使用 `LLM_CHANNELS`；legacy provider keys 目前保留為兼容回退路徑，方便舊 `.env`、本地 macOS 開發環境和歷史部署平滑繼續運行。

### 問股可見對話上下文壓縮

默認情況下，問股仍按歷史行為只注入最近 20 條可見對話。需要為默認模型長會話省 token 時，可開啟：

```env
AGENT_CONTEXT_COMPRESSION_ENABLED=true
AGENT_CONTEXT_COMPRESSION_PROFILE=balanced
# 留空則跟隨 profile preset
AGENT_CONTEXT_COMPRESSION_TRIGGER_TOKENS=
AGENT_CONTEXT_PROTECTED_TURNS=
```

壓縮只處理 `session_id` 下用戶可見的 `user` / `assistant` 文本歷史，不處理 provider trace、thinking blocks、tool calls 或 tool results，也不會改變同輪工具調用透傳。三檔 preset 分別是 `cost`（6000 tokens / 保護 2 輪）、`balanced`（12000 / 4）和 `long_context_raw_first`（24000 / 6）；trigger / protected 留空時跟隨當前 profile，顯式填寫時覆蓋 profile。

問股 single-agent 路徑會額外維護一條 provider-aware trace 分軌，用於 DeepSeek V4 thinking + tool-call 的跨輪協議回放：只有同一輪同時出現 `tool_calls` 與 `reasoning_content` 時才會按當前 `session_id + provider + model` 保存最近 3 條最小協議材料，並在下一輪按原始時序插回對應可見 assistant 回覆之前。該 trace 只能原樣保留或整段丟棄，不參與摘要、不寫入 Web 會話消息、不新增 `.env` 配置；model/provider 不匹配、錨點已被 summary 覆蓋或預算不足時會整段跳過。Claude extended thinking 本輪只覆蓋 adapter/storage 級 opaque `thinking` / `redacted_thinking` / `signature` blocks plumbing 與離線 fixture，不聲明生產端到端支持；multi-agent trace 注入仍是 follow-up。外部協議依據包括 DeepSeek thinking mode 文檔（<https://api-docs.deepseek.com/guides/thinking_mode>）和 Anthropic Claude extended thinking 文檔（<https://platform.claude.com/docs/en/docs/build-with-claude/extended-thinking>），LiteLLM 兼容窗口仍以 `requirements.txt` 的 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 為準。

### 嚴格 temperature 模型兼容說明

- Moonshot 官方說明 Kimi API 兼容 OpenAI 接口，Base URL 使用 `https://api.moonshot.ai/v1`：<https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart>
- LiteLLM 官方要求 OpenAI Compatible 渠道模型名使用 `openai/` 前綴：<https://docs.litellm.ai/docs/providers/openai_compatible>
- Moonshot 官方兼容性文檔區分兩種固定值：**thinking 模式固定 `1.0`，non-thinking 模式固定 `0.6`**；傳其它值會被接口拒絕：<https://platform.moonshot.ai/docs/guide/compatibility#parameters-differences-in-request-body>
- OpenAI Chat Completions 規範中 `temperature` 是可選參數；對 GPT-5 / GPT-6 / o 系列等只接受默認溫度的模型，本項目會在請求層省略 `temperature`，讓服務端使用默認值，而不是改寫你的 `LLM_TEMPERATURE`：<https://platform.openai.com/docs/api-reference/chat/create>
- 當前倉庫的運行時依賴約束是 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（見 `requirements.txt`）；本次兼容邏輯按該約束迴歸驗證了主分析、大盤覆盤、Agent 直連 LiteLLM，以及系統設置頁的渠道連通性測試。
- 因此本項目會在請求發出前按**實際請求模式**歸一化 `kimi-k2.6` 及其 `kimi-k2.6-*` 變體：默認 / thinking 路徑使用 `temperature=1.0`；如果你的 LiteLLM YAML 路由別名裡顯式寫了 `litellm_params.extra_body.thinking.type: disabled`（或等價 non-thinking 配置），則自動切到 `temperature=0.6`。你在 `.env` 或 Web 設置裡保存的 `LLM_TEMPERATURE` 不會被改寫。
- 如果兼容平臺對未收錄的新模型返回明確的參數錯誤（例如 `temperature` 不支持、只能使用默認 `1.0`、`top_p` 不支持），運行時會對**當前請求**做一次參數修正並重試；只有重試成功後才把該策略緩存在當前進程內。該緩存不會寫回 `.env`，服務重啟後會重新按配置與適配規則判斷。
- 對已經產生部分內容的流式響應，系統不會在半截輸出後切換參數；仍沿用原有“同模型非流式重試 / fallback 模型”的穩定路徑，避免拼接出不一致的回答。
- `SystemConfigService` 在 Web 設置保存 / 桌面端 `.env` 導入時只更新你提交的 key，不會因為切到嚴格 temperature 模型靜默清空、遷移或重寫已有 `LLM_TEMPERATURE`；渠道測試請求裡的臨時參數策略也不會回寫到配置文件。
- 非嚴格主模型、非嚴格 fallback 以及切回普通模型後的請求，仍繼續使用你配置的溫度；也就是說舊配置無需遷移，切換模型即可自動恢復原行為。
- 本倉庫兼容性迴歸覆蓋見：`tests/test_llm_channel_config.py`、`tests/test_market_analyzer_generate_text.py`、`tests/test_agent_pipeline.py`、`tests/test_system_config_service.py`。
- 最小回滾方式：直接回退本次 LLM 參數適配相關改動，無需單獨遷移已有 `LLM_TEMPERATURE` 配置。

### 兼容性與回退複核清單（按 PR 審核口徑）

- 運行時依賴約束：`litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（與 `requirements.txt` 一致）。
- 迴歸驗證入口：
  - 渠道模型發現與連接：`tests/test_llm_channel_config.py`
  - 運行時源清理與恢復（含桌面導出備份鏈路）：`tests/test_system_config_service.py`
  - 接口校驗與問題面向字段：`tests/test_system_config_api.py`
  - 設置頁交互與保存後提示：`apps/dsa-web/src/components/settings/__tests__/LLMChannelEditor.test.tsx`
- 舊配置回退路徑：`桌面端導出備份 -> /api/v1/system/config/import`，或手動恢復 `LLM_* / LITELLM_* / AGENT_LITELLM_MODEL / VISION_MODEL / LLM_TEMPERATURE / LLM_USAGE_HMAC_*`；Web 導入備份前同樣要求 `ADMIN_AUTH_ENABLED=true`，否則會返回 403。

> **致命避坑說明**：如果你啟用了 `LLM_CHANNELS`，那麼你直接寫在外面的 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` 將**全部失效（系統一律無視）**！二者**選其一即可**，千萬不要既寫了新手模式又寫了渠道模式結果產生衝突。
> **Docker 注意**：如果你在 `docker compose environment:` 或 `docker run -e` 中顯式傳入 `LITELLM_MODEL`、`LLM_CHANNELS`、`LLM_DEEPSEEK_MODELS` 等變量，容器重啟後這些環境變量會覆蓋 Web 設置頁寫入的 `.env`，需要同步修改部署配置。

### 兼容依據與回退審計說明（本次 PR 適配說明）

- 官方與運行時兼容依據採用兩層：第一層為官方接口語義（LiteLLM OpenAI-compatible 路由、OpenAI Chat Completions、Moonshot/Kimi 文檔與官方模型說明）；第二層為本倉庫當前運行時語義（`litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`）下的實際錯誤歸類。
- 本次兼容恢復只使用“本地運行時錯誤歸類 + 單請求修正重試 + 進程內緩存”策略，不寫入 `.env`、不做配置遷移，僅在執行路徑上動態規避不支持參數（`temperature`、`top_p`、`presence_penalty`、`frequency_penalty`、`seed`）。若要回退，不需要額外遷移命令，恢復舊值即可。
- 迴歸與證據：`tests/test_llm_param_recovery.py`、`tests/test_system_config_service.py`、`tests/test_llm_channel_config.py`、`tests/test_system_config_api.py`、`tests/test_market_analyzer_generate_text.py`、`tests/test_agent_pipeline.py`；桌面導入與運行時清理回退另有 `test_import_desktop_env_restores_runtime_models_after_cleanup` 直接覆蓋。

---

### LLM usage HMAC 遙測

P0a usage telemetry 會為實際發送的 message 生成 HMAC-SHA256 指紋，用於後續判斷相同 prompt/message 前綴是否穩定。該能力只寫入本地 `llm_usage` 記錄，不改變 prompt、provider 參數、cache hint、模型輸出或 fallback 順序。

Usage 來源按三層讀取：

- 優先讀取 provider / LiteLLM 公開響應字段 `usage`。
- 其次讀取 LiteLLM 公開響應字段 `usage_metadata`。
- 最後才讀取 `_hidden_params["usage"]`，這是 LiteLLM private/internal 的 best-effort fallback，不是穩定公共契約；缺失時只代表 usage/cache telemetry 可能不完整，不代表模型請求失敗。

Cache token 歸一化只做 allowlisted best-effort normalization。外部字段依據和運行時邊界如下，避免把官方穩定契約、LiteLLM 當前歸一化行為和本倉庫兼容 allowlist 混為一談：

| Provider / 來源 | 讀取字段 | 依據與邊界 | 覆蓋情況 |
| --- | --- | --- | --- |
| OpenAI | `usage.prompt_tokens_details.cached_tokens` | 官方 Prompt Caching 文檔說明 1024 tokens 以下也會返回 `cached_tokens=0`：<https://developers.openai.com/api/docs/guides/prompt-caching> | unit/mock 覆蓋；本 PR 未做 OpenAI live smoke |
| Anthropic | `cache_creation_input_tokens` / `cache_read_input_tokens` / `input_tokens` | 官方 Prompt Caching 文檔定義 `total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens`：<https://platform.claude.com/docs/en/build-with-claude/prompt-caching> | unit/mock 覆蓋；本 PR 未做 Anthropic live smoke |
| Gemini / Vertex AI | 官方字段為 `UsageMetadata.cachedContentTokenCount`；運行時消費 LiteLLM 暴露的 snake_case / normalized 字段，如 `cached_content_token_count`、`cache_read_input_tokens` 或 `prompt_tokens_details.cached_tokens` | Gemini `UsageMetadata` 官方字段見 <https://ai.google.dev/api/generate-content#UsageMetadata>；本倉庫不新增 native camelCase runtime fallback，運行時邊界以 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 為準 | unit/mock 覆蓋；本 PR 未做 Gemini / Vertex live smoke |
| DeepSeek | `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` | DeepSeek Chat Completion 文檔說明 `prompt_tokens = prompt_cache_hit_tokens + prompt_cache_miss_tokens`：<https://api-docs.deepseek.com/api/create-chat-completion> | unit/mock 覆蓋；本 PR 只做一次脫敏 DeepSeek smoke，不保存完整響應 |
| GLM / OpenAI-compatible / StepFun 等兼容平臺 | 已建模 token/cache count allowlist 中能映射到統一字段的值 | 不聲明官方穩定 cache telemetry contract；僅表示在當前 LiteLLM / OpenAI-compatible shape 下做 best-effort normalization，未建模 metadata 不持久化 | unit/fixture/mock 覆蓋；本 PR 未做這些 provider 的 live smoke |
| LiteLLM public response shape | `usage` / `usage_metadata` | 按當前依賴窗口 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 的 response / `Usage` object shape 消費；不作為 LiteLLM 2.x 兼容承諾 | Analyzer / Agent / usage tests 覆蓋 |
| LiteLLM private fallback | `_hidden_params["usage"]` | private/internal best-effort fallback，不是 LiteLLM 穩定公共契約；僅在 public usage zero-only/no-signal 等窄場景補足 streaming usage，不改變 provider 請求參數 | unit/mock 覆蓋；缺失時隻影響 telemetry 完整性，不代表模型請求失敗 |

```env
LLM_USAGE_HMAC_SECRET=
LLM_USAGE_HMAC_KEY_VERSION=local-v1
```

- `LLM_USAGE_HMAC_SECRET` 留空時，系統會在數據目錄生成 `.llm_usage_hmac_secret`，適合單部署本地比較。
- 只有需要跨部署比較 HMAC 時，才顯式配置同一個高熵隨機密鑰；建議使用 `openssl rand -hex 32` 生成。
- `.llm_usage_hmac_secret` 是本地 secret artifact，已在 `.gitignore` 中按文件名忽略。
- 輪換密鑰時同步更新 `LLM_USAGE_HMAC_KEY_VERSION`，避免不同密鑰生成的 HMAC 被誤比較。
- 不要複用登錄 session secret，也不要把真實密鑰提交到版本控制或暴露在 issue、日誌、截圖中。

### Provider prompt cache 配置（P1 / P1.5）

Prompt cache 配置只控制本項目是否記錄 cache usage / diagnostics，以及主分析路徑是否主動發送已驗證的 provider-specific hint；它不控制 OpenAI、Gemini、DeepSeek 等 provider 的 implicit / provider-managed cache。

```env
LLM_PROMPT_CACHE_TELEMETRY_ENABLED=true
LLM_PROMPT_CACHE_HINTS_ENABLED=false
LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL=off
```

- `LLM_PROMPT_CACHE_TELEMETRY_ENABLED=false` 時，不持久化 provider raw usage JSON、normalized cache fields 和 cache decision diagnostics；基礎 token usage 記錄保持兼容。
- `LLM_PROMPT_CACHE_HINTS_ENABLED=true` 只允許主分析 / analyzer LiteLLM 路徑向 registry 中已驗證或 smoke-tested 的 provider / route 發送 `prompt_cache_key`、`cache_control`、`user_id` 等 hint。問股 Agent 路徑當前只記錄 capability / usage diagnostics，不主動發送 provider-specific hints。未知 OpenAI-compatible gateway 默認 telemetry only。
- `LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL=basic` 只在 debug 日誌和測試可觀察對象中提供 provider、api surface、verification status、hint applied / disabled reason 等非敏感枚舉。`debug` 在同一範圍內額外提供 HMAC-derived route/cache diagnostics 和 matched caps id，但仍禁止 raw prompt、request body、message content、股票/用戶原文、webhook 或 API key；這些診斷不是公開 Usage API 或普通設置頁輸出。
- Provider Cache Capability Registry 是 `src/llm/provider_cache.py` 中的 code-level 手工能力表。條目帶 `doc_sources`、`last_verified_at` 和 `verification_status`；新增 provider 或升級 LiteLLM 後應同步更新條目與測試。
- Prompt cache key、route key 和 DeepSeek session isolation 複用 `LLM_USAGE_HMAC_SECRET` / `.llm_usage_hmac_secret` 做 domain-separated HMAC，不新增 prompt-cache 專用 secret。

### Legacy message stability audit（P0.5a）

P0.5a 在普通個股分析路徑為 legacy `[system, user]` message 追加內部穩定性審計字段，繼續寫入本地 `llm_usage`。它複用上面的 message HMAC，不修改 prompt 內容、message 順序、provider 請求參數、cache hint、模型輸出、fallback 順序，也不擴展公開 Usage API 或 Web 頁面。

新增字段只用於維護者診斷：

- `language`、`market_group`、`analysis_mode`、`legacy_prompt_mode`、`provider`、`transport`、`message_count` 描述本次普通個股分析調用的低敏路由上下文。
- `skill_config_hmac` 是基於已解析 skill prompt 片段、默認 skill 策略和 legacy prompt 模式生成的 HMAC-SHA256，用於判斷 system message 是否隨 skill configuration 變化；不會保存 skill 原文。
- `known_dynamic_marker_positions` 是 JSON string，只記錄 `marker_name`、`message_role`、`char_offset`；不會保存股票代碼、股票名稱、日期、新聞正文、行情值、headers、response text 或 prompt 片段。
- `estimated_total_prompt_tokens`、`approx_common_prefix_chars`、`approx_common_prefix_tokens` 基於項目內穩定 canonical render 估算：按 message 順序拼接 `role + "\n" + content`，並用固定分隔符連接。該口徑不聲稱等同 provider 真實 wire bytes。
- `char_offset` 是 marker 在對應 message `content` 內的位置；`approx_common_prefix_chars` 是 canonical render 起點到第一個已知動態 marker 之前的字符數。沒有 marker 時 common-prefix 字段為 `NULL`。
- token 估算使用 `ceil(chars / 3)`，只作 diagnostics，不替代 provider usage，也不參與 cache threshold 判定；中文場景可能偏低。

P0.5a 不引入 PromptBlock IR、`block_id`、`stability_class`、`static_prefix_hash` 或 `dynamic_context_hash`。Agent、research 與 market review 路徑暫不接入該審計。

---

## 方式三：YAML 高級配置（適合老手自定義）

**目標：** 我不在乎學習門檻，我要最高控制權，我要用原生規則做企業級高可用！

這一層會直接映射到底層 LiteLLM 路由能力，支持高併發、自動重試、按 RPM/TPM 負載均衡等操作。

### 本地運行 / Docker 部署模式配置說明

1. 在 `.env` 中只保留一行指向聲明：
   ```env
   LITELLM_CONFIG=./litellm_config.yaml
   ```
2. 在項目根目錄創建一個 `litellm_config.yaml`（可以參考自帶的 `docs/examples/litellm_config.example.yaml`）。

示例 `litellm_config.yaml`：
```yaml
model_list:
  - model_name: my-smart-model
    litellm_params:
      model: deepseek/deepseek-v4-flash
      api_base: https://api.deepseek.com
      api_key: "os.environ/MY_CUSTOM_SECRET_KEY"  # 從環境變量讀取 Key，安全防洩漏

  # Ollama 本地模型（無需 api_key）
  - model_name: ollama/qwen3:8b
    litellm_params:
      model: ollama/qwen3:8b
      api_base: http://localhost:11434
```

### GitHub Actions配置說明

1. `Settings` → `Secrets and variables` → `Actions`。非敏感配置（如模型名、開關、Base URL）可以放在 `Secret` 或 `Variables`；凡是 `*_API_KEY` / `*_API_KEYS` 以及 `LLM_<NAME>_API_KEY` / `LLM_<NAME>_API_KEYS` 這類密鑰字段，請統一放在 `Secret` 標籤頁的 `New repository secret`

2. 按下表配置，只有全部必填配置正確配置，YAML 高級配置模式才可以生效，YAML配置文件的寫法，可以參考自帶的 `docs/examples/litellm_config.example.yaml`

| Secret 名稱 | 說明 | 必填 |
|------------|------|:----:|
| `LITELLM_CONFIG` | 高級模型路由配置文件路徑，通常配置 `./litellm_config.yaml` | 必填 |
| `LITELLM_MODEL` | 默認主模型名稱或路由別名 | 必填 |
| `LITELLM_CONFIG_YAML` | 存放 YAML 配置文件內容，可不在倉庫中提交實體文件 | 可選 |
| `LITELLM_API_KEY` | 用於存儲API Key，可在配置文件中引用（環境變量引用方式）。由於GitHub Actions必須要指定導入的環境變量，因此你不能像本地運行模式那樣自由命名環境變量 | 可選，必須配置到repository secret中 |
| `ANTHROPIC_API_KEY` | 如果要多個API Key，這個變量名稱也能拿來用 | 可選，必須配置到repository secret中 |
| `OPENAI_API_KEY` | 同上，可以用來存儲API Key | 可選，必須配置到repository secret中 |

渠道模式無需上傳 YAML 文件。倉庫自帶 `00-daily-analysis.yml` 已顯式透傳以下常用字段：

- 運行時選擇：`GENERATION_BACKEND`、`GENERATION_FALLBACK_BACKEND`、`GENERATION_BACKEND_TIMEOUT_SECONDS`、`GENERATION_BACKEND_MAX_OUTPUT_BYTES`、`GENERATION_BACKEND_MAX_CONCURRENCY`、`LOCAL_CLI_BACKEND_MAX_CONCURRENCY`、`AGENT_GENERATION_BACKEND`、`LLM_CHANNELS`、`LITELLM_MODEL`、`LITELLM_FALLBACK_MODELS`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`VISION_PROVIDER_PRIORITY`、`LLM_TEMPERATURE`、`LLM_USAGE_HMAC_SECRET`、`LLM_USAGE_HMAC_KEY_VERSION`、`LLM_PROMPT_CACHE_TELEMETRY_ENABLED`、`LLM_PROMPT_CACHE_HINTS_ENABLED`、`LLM_PROMPT_CACHE_DIAGNOSTICS_LEVEL`
- 多 Key：`GEMINI_API_KEYS`、`ANTHROPIC_API_KEYS`、`OPENAI_API_KEYS`、`DEEPSEEK_API_KEYS`（當前 workflow 僅從 repository secrets 導入，不會讀取同名 Variables）
- 常用渠道名：`modelflare`、`primary`、`secondary`、`aihubmix`、`anspire`、`deepseek`、`dashscope`、`zhipu`、`moonshot`、`minimax`、`volcengine`、`siliconflow`、`openrouter`、`requesty`、`gemini`、`anthropic`、`openai`、`ollama`、`hermes`

例如在 GitHub Actions 中配置 `LLM_CHANNELS=primary,deepseek` 時，需同步配置 `LLM_PRIMARY_*` / `LLM_DEEPSEEK_*`。其中 `LLM_<NAME>_API_KEY` / `LLM_<NAME>_API_KEYS` 當前也僅從 repository secrets 導入；如果你把這些值放在 Variables，運行時不會生效。若使用自定義渠道名（如 `my_proxy`），GitHub Actions 還必須在 workflow `env:` 中顯式新增對應的 `LLM_MY_PROXY_*` 映射；本地 `.env` 和 Docker 不受這個限制。


> **三層配置互斥準則**：YAML 優先級最高！只要配置了 YAML，**渠道模式** 和 **新手極簡模式** 統統被忽略。系統優先級為：`YAML配置 > 渠道模式 > 極簡單模型`。

---

## 擴展功能：看圖模型 (Vision) 配置

系統中有些特定功能（比如上傳股票軟件截圖，讓 AI 提取出截圖裡的股票代碼並放入自選股池）必須用到具備“視覺能力”的模型。你需在 `.env` 單獨給它指派一個懂圖片的模型。

```env
# 指定你看圖專用的模型名
VISION_MODEL=openai/gpt-6.1-sol
# 別忘了填寫它對應提供商的 API KEY，如果是 OpenAI 兼容渠道就提供 OPENAI_API_KEY：
# OPENAI_API_KEY=xxx
```

**備用看圖機制：** 為了防止偶爾罷工，系統內置了切換策略。如果主視覺模型調用失敗，它會按照下方的順位嘗試尋找是否有其他看圖模型的 Key：
```env
# 默認的備用順序：
VISION_PROVIDER_PRIORITY=gemini,anthropic,openai
```

---

## 檢測與排錯 (Troubleshooting)

配好了之後心驚膽戰不知道對不對？在命令行（Terminal）裡敲入下面代碼幫你掛號問診：

- `python scripts/check_env.py --config` ：純檢測 `.env` 配置文件裡的邏輯寫得對不對，是不是少寫了什麼。（秒出結果，不調用網絡，純檢查本地文本拼寫）
- `python scripts/check_env.py --llm` ：系統會真的發一句問候語給大模型，讓你親眼看到他的回答。這能徹底測出你的**網絡通不通、賬號有沒有欠費**。

### 常見踩坑答疑臺

| 遇到了什麼詭異報錯？ | 罪魁禍首可能是啥？ | 該怎麼收拾它？ |
|----------------------|----------------------|------------------|
| **界面提示主模型未配置** | 系統不知道你到底想用哪家的哪個模型 | 在 `.env` 中寫上一句明白話：`LITELLM_MODEL=provider/你的模型名`。比如 `openai/gpt-6.1-sol` |
| **我寫了好幾家的Key，為什麼死活只有一個生效？修改還沒用？** | 你把 **極簡模式** 和 **渠道模式** 混著寫了！ | 想好一條路走到黑——只要簡單就刪掉 `LLM_CHANNELS` 開頭的；想要豐富備用切換就要全部轉投到 `LLM_CHANNELS` 下的編制裡。 |
| **錯誤碼報 400 或 401 或 Invalid API Key** | API Key 填錯、少複製了一截、賬號充值沒到賬、或者模型名字敲錯（極度常見）。 | 1. 檢查複製的 Key 前後是否有誤填空格。<br> 2. 檢查 Base URL 最後是不是少了一個 `/v1`。<br> 3. 檢查模型名是否少寫了 `openai/` 之類的前綴！ |
| **Kimi K2.6 報 `invalid temperature`（可能提示只允許 `1.0` 或 `0.6`）** | 該模型按 thinking / non-thinking 模式要求不同固定 temperature；舊配置或調用入口可能還在傳 `0.7`。 | 升級後系統會對 `kimi-k2.6` 默認 / thinking 請求自動使用 `temperature=1.0`；如果你在 LiteLLM YAML 路由裡顯式關閉 thinking，則自動改用 `0.6`。模型名建議寫成 `openai/kimi-k2.6` 並配合 Moonshot / 聚合平臺的 OpenAI 兼容 Base URL 與 API Key。非 Kimi fallback 仍會繼續使用你配置的 `LLM_TEMPERATURE`。 |
| **GPT-5 / GPT-6 / o 系列報 `temperature` 不支持或只允許默認值** | 這類模型只接受服務端默認採樣參數，但舊調用入口會顯式傳 `0.7`。 | 升級後請求層會省略 `temperature`，讓服務端使用默認值；`.env` / Web 設置中的 `LLM_TEMPERATURE` 不會被改寫，切回普通模型後仍按原值發送。 |
| **轉圈轉不停，最後報 Timeout / ConnectionRefused 等** | 1. 在國內使用國外原版（像 Google、OpenAI），沒開代理被牆了。<br>2. 你買的雲服務器壓根不能出境。 | 非常推薦使用**國內官方**（如DeepSeek、阿里）或者各種**兼容 OpenAI 的聚合中轉接口**。因為中轉站把網絡問題幫你解決好了。 |
| **Ollama 報 404、`Could not get model info` 或 `api/generate/api/show`** | 誤用 `OPENAI_BASE_URL` 配置 Ollama，系統會錯誤拼接 URL | 改用 `OLLAMA_API_BASE=http://localhost:11434` 或渠道模式（`LLM_CHANNELS=ollama` + `LLM_OLLAMA_BASE_URL`） |

*進階老手的叮囑：如果你開啟了 **Agent (深度思考網絡搜索問股) 模式**，這裡有個經驗之談，推薦選用如 `deepseek-v4-pro` 這種邏輯推導能力更強的大模型。如果為了省錢用小微模型跑 Agent，它邏輯能力大概率跟不上，不僅達不到預期，還會白跑一堆空流程。*
