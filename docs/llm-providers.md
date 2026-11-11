# LLM 服務商配置指南

本文面向首次配置用戶，說明如何選擇 LLM 配置方式、如何把 Web 設置頁「AI 模型配置」預設映射到 `.env` / GitHub Actions，以及如何處理常見檢測錯誤。

> 本頁未引入新的外部 provider、模型名或 Base URL 兼容行為，僅整理配置參考與官方來源；實際兼容性仍以倉庫當前運行時依賴與測試結論為準。

> - 運行時基礎：`requirements.txt` 當前鎖定 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`，兼容語義以該版本約束下實現為準。
> - 驗證閉環：系統配置鏈路迴歸見 `tests/test_system_config_service.py` 與 `tests/test_system_config_api.py`，`Web` 側配置頁交互迴歸見現有組件測試用例。
> - 回退路徑：保留舊變量不做自動遷移；可通過 Web/桌面導出備份後 `POST /api/v1/system/config/import` 回滾，或手動恢復歷史 `LLM_*` / `LITELLM_*` / `AGENT_*` / `VISION_MODEL` 配置。

實際可用模型、額度、區域限制和價格以各服務商控制檯為準；如果模型列表拉取失敗，可在 Web 中手動填寫模型名。Web 設置頁展示的 provider 能力標籤、官方來源鏈接和配置注意事項來自靜態 provider template，僅用於配置參考，不代表運行時能力已驗證通過。

## 先選配置方式

| 方式 | 適合誰 | 主要變量 | 說明 |
| --- | --- | --- | --- |
| 極簡 legacy | 只想快速跑通一個模型的用戶 | `LITELLM_MODEL` + 對應 provider key | 最少變量，適合本地快速開始；不適合複雜 fallback。 |
| Channels | 需要多個 provider、多個 key 或 fallback 的用戶 | `LLM_CHANNELS` + `LLM_<CHANNEL>_*` | 推薦默認路徑；Web 設置頁保存的也是這一層配置。 |
| YAML | 熟悉 LiteLLM 路由、負載均衡和企業網關的用戶 | `LITELLM_CONFIG` / `LITELLM_CONFIG_YAML` | 優先級最高；一旦有效生效，Channels 和 legacy 不再參與本次請求。 |

優先級保持不變：`LITELLM_CONFIG` / `LITELLM_CONFIG_YAML` > `LLM_CHANNELS` > legacy provider keys。P4 只補文檔，不遷移、不清空、不靜默改寫舊配置。

Generation backend 配置是更外層的運行時選擇契約。Phase 4 支持 `GENERATION_BACKEND=litellm|codex_cli|claude_code_cli|opencode_cli`，但本地 CLI backend 不是 LiteLLM provider；不要配置成 `LITELLM_MODEL=codex_cli/...`、`LITELLM_MODEL=claude_code_cli/...` 或 `LITELLM_MODEL=opencode_cli/...`。`codex_cli` preset 使用 `codex --ask-for-approval never exec --sandbox read-only --output-last-message <temp-file> -`，固定無人值守批准策略並保持只讀邊界；`claude_code_cli` preset 使用 `claude --safe-mode --tools "" --disallowedTools "mcp__*" --strict-mcp-config --no-session-persistence --output-format json -p <static instruction>`，完整 DSA prompt 走 stdin，並只從 JSON envelope 的 `result/success` 字段提取最終文本，參數依據見 [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference)；`opencode_cli` preset 使用 `opencode --pure run --format json [--model <OPENCODE_CLI_MODEL>] <static instruction> --file <temp prompt file>`，僅在顯式配置 `OPENCODE_CLI_MODEL` 時追加 `--model`，完整 DSA prompt 走權限受控的臨時文件，並只從無工具事件的 JSON event text 輸出提取最終文本，參數依據見 [OpenCode CLI reference](https://opencode.ai/docs/cli)，配置合併語義見 [OpenCode config reference](https://opencode.ai/docs/config)。診斷 stdout/stderr 與最終響應一起受 `GENERATION_BACKEND_MAX_OUTPUT_BYTES` 總上限約束，超限時返回結構化 `output_too_large`。`GENERATION_FALLBACK_BACKEND=` 空值會在本地 `.env` 禁用 backend-level fallback，未配置時默認回退到 `litellm`；默認 GitHub Actions workflow 未配置該變量時會顯式使用 `litellm`，如需禁用 fallback 可設為 primary backend 走 self no-op。Agent 工具調用仍使用 LiteLLM；Web 設置頁只暴露 `AGENT_GENERATION_BACKEND=auto|litellm`，手寫 `codex_cli|claude_code_cli|opencode_cli` 不會啟用 text-only Agent mode，只會返回明確 unsupported tool-calling 診斷。

生成後端狀態接口與 Web 面板會把輕量檢查和冒煙測試分開展示：快速檢查只讀取已保存 `.env`、運行時兜底值和當前草稿，不寫配置、不重載運行時，也不發起真實模型請求；只有 JSON 冒煙測試會使用固定的 JSON 提示詞和 schema 發起真實請求。`health_status` 與 `last_error_code/message` 是本次計算結果，不表示歷史最後錯誤。本地 CLI preset 的 `supports_tools=false` 僅表示不支持 DSA Agent 工具調用鏈路，不代表普通文本生成不可用。

Phase 6a Tool Surface 保留共享內部工具邊界：統一 DSA 工具 schema、public descriptor、MCP-compatible descriptor、scope guard、結構化錯誤、審計摘要和脫敏診斷。stock-scoped 工具調用必須顯式傳入 `ToolAccessContext.stock_scope`；有 `stock_code` 參數但未聲明 stock scope 的工具會 fail-closed。保留該共享邊界；`codex_cli` generation backend、MCP server、SDK 或最終文本 fallback 不作為 Agent 工具成功。

## Codex App Server 問股退役

Codex App Server 問股後端已移除。`AGENT_BACKEND` 僅支持 `auto`（推薦，保持默認 LiteLLM）或 `litellm`。舊 `codex_app_server` 可加載、顯示和導出，但執行請求在準備與接受提交前返回 `backend_removed`，不會自動切換模型、賬號或 provider。請在「設置 → Agent 設置 → 問股生成方式」主動選擇合法值並保存；已有舊值不阻止無關設置保存，顯式保存或導入舊值則拒絕且不部分寫入。狀態與草稿預覽只檢查配置，不啟動 Codex 命令或 schema/version 探針，也不調用模型。歷史會話、股票身份、Skill、單/多 Agent 與 provider trace 保持原契約。獨立 `GENERATION_BACKEND=codex_cli` 普通報告及其他 generation-only 不受此移除影響，仍需各自 CLI 及其原有依賴。

## Web 設置頁路徑

推薦優先使用 Web 設置頁完成 Channels 配置：

1. 打開設置頁的「AI 模型配置」。
2. 在「快速添加渠道」選擇服務商預設。
3. 填入 API Key，必要時點擊「獲取模型」。
4. 選擇主模型、Agent 主模型、備選模型和 Vision 模型後保存。
5. 點擊「測試連接」確認鑑權、模型名、額度和響應格式正常。
6. 如需確認 JSON / tools / stream / vision 能力，手動勾選「運行時能力檢測」後再觸發；該檢測會產生真實 LLM 請求，結果只代表當前賬號、模型和 endpoint 的一次 best-effort 檢測，不會寫回 `.env`，也不會阻止保存。

## Channels 示例

### Modelflare

[註冊 Modelflare](https://modelflare.dev/sign-up?utm_source=github&utm_campaign=daily_stock_analysis)，創建 API Key 後使用 OpenAI-compatible 渠道：

```env
MODELFLARE_KEY=sk-xxx
```

只需填寫 `MODELFLARE_KEY`，後端自動啟用 Modelflare，默認地址為 `https://modelflare.dev/v1`、模型為 `openai/gpt-6.1-sol`，無需填寫渠道名、地址或模型。顯式 YAML 或 `LLM_CHANNELS` 優先，Modelflare 顯式渠道 Key 優先於此簡寫；清空 Key 或禁用渠道即可停用。推導不改寫已保存配置。

只聲明 `modelflare` 一個渠道且未填渠道模型列表時，未配置主模型時默認使用 `openai/gpt-6.1-sol`；配置主模型後，後端複用 `LITELLM_MODEL` 和帶 `openai/` 前綴的備用模型；主模型使用 `openai/<模型名>`。顯式 `LLM_MODELFLARE_MODELS` 優先，多渠道仍需分別聲明模型。推導不改寫已保存配置或模型選擇。

渠道名為 `modelflare` 時，未填寫或留空的接入地址自動使用 `https://modelflare.dev/v1`；顯式 `LLM_MODELFLARE_BASE_URL` 優先。該地址默認識別為 `openai` 協議，接口默認為 `chat_completions`；未設置 `LITELLM_MODEL` 時使用首個渠道模型。默認模型仍需賬號有訪問權限，不自動補充 API Key。

`gpt-6.1-sol` 是本項目的 Modelflare 默認模型；實際模型列表與可用性以賬號權限、控制檯和 Web 設置頁「測試連接」結果為準。渠道模板僅決定新建配置的初始值，不會改寫已保存的渠道、主模型或 fallback。

### DeepSeek 官方渠道

```env
LLM_CHANNELS=deepseek
LLM_DEEPSEEK_PROTOCOL=deepseek
LLM_DEEPSEEK_BASE_URL=https://api.deepseek.com
LLM_DEEPSEEK_API_KEY=sk-xxx
LLM_DEEPSEEK_MODELS=deepseek-v4-flash,deepseek-v4-pro
LITELLM_MODEL=deepseek/deepseek-v4-flash
```

### OpenAI-compatible 聚合或自定義網關

```env
LLM_CHANNELS=my_proxy
LLM_MY_PROXY_PROTOCOL=openai
LLM_MY_PROXY_API_SURFACE=chat_completions
LLM_MY_PROXY_BASE_URL=https://your-proxy.example.com/v1
LLM_MY_PROXY_API_KEY=sk-xxx
LLM_MY_PROXY_MODELS=gpt-6.1-sol,claude-sonnet-4-6
```

OpenAI-compatible Base URL 只填到服務商兼容入口，不額外拼接 `/chat/completions`。本地 `.env`、Docker 和自託管腳本可以直接使用自定義 channel；GitHub Actions 需要 workflow 顯式透傳同名 `LLM_MY_PROXY_*` 變量。
小米 MiMo 示例同理：適用於本地 `.env`、Docker 或自託管腳本；若在 GitHub Actions 使用 `LLM_CHANNELS=mimo`，需要在 workflow 中手動補齊 `LLM_MIMO_*` 映射後方可生效。

### Anspire Responses API（GPT-5.6 名稱為觀測樣本）

Anspire 官方接入頁公開了 `https://open-gateway.anspire.cn/v6/responses` 調用方式：<https://open.anspire.cn/model?link=sample&tab=models>。如果實時 `/models`、服務商說明和連接測試確認目標模型使用 Responses，可把模型放在同一渠道，並顯式把 API Surface 設為 `responses`。下面的 `gpt-5.6-sol`、`gpt-5.6-terra`、`gpt-5.6-luna` 是當前網關觀測樣本，不作為長期模型清單承諾：

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

這裡的能力不依賴 `gpt-5.6-*` 命名：任何服務商明確聲明為 Responses-only 的模型都可使用同一配置方式。模型清單和賬號權限可能變化，應以服務商 `/models` 返回、官方說明及實際連接測試為準。一個渠道只能使用一種 API Surface；若還要同時使用 Anspire 的 Chat Completions 模型，請為它們建立另一個 OpenAI-compatible 渠道，不要把兩類模型混在同一渠道中。Web 設置頁的「測試連接」會使用當前選擇的 Surface，運行時不會在失敗後靜默改用另一個 endpoint。

## 常用服務商預設

| 服務商 | 渠道名 | 協議 | Base URL | 模型示例 |
| --- | --- | --- | --- | --- |
| Modelflare | `modelflare` | `openai` | `https://modelflare.dev/v1` | `gpt-6.1-sol`（以賬號可用模型為準） |
| AIHubmix | `aihubmix` | `openai` | `https://aihubmix.com/v1` | `gpt-6.1-sol,claude-sonnet-4-6,gemini-3.6-flash` |
| OpenAI | `openai` | `openai` | `https://api.openai.com/v1` | `gpt-6.1-sol,gpt-6.1-terra` |
| DeepSeek | `deepseek` | `deepseek` | `https://api.deepseek.com` | `deepseek-v4-flash,deepseek-v4-pro` |
| Gemini | `gemini` | `gemini` | 留空 | `gemini-3.6-flash,gemini-3.5-flash-lite` |
| Anthropic Claude | `anthropic` | `anthropic` | 留空 | `claude-sonnet-4-6,claude-opus-4-7` |
| Kimi / Moonshot | `moonshot` | `openai` | `https://api.moonshot.cn/v1` | `kimi-k2.6,kimi-k2.5` |
| 通義千問 / DashScope | `dashscope` | `openai` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen3.6-plus,qwen3.6-flash` |
| 智譜 GLM | `zhipu` | `openai` | `https://open.bigmodel.cn/api/paas/v4` | `glm-5.1,glm-4.7-flash` |
| MiniMax | `minimax` | `openai` | `https://api.minimax.io/v1` | `MiniMax-M3.1-Flash,MiniMax-M3` |
| 小米 MiMo | `mimo` | `openai` | 官方控制檯提供（Actions 默認未映射） | 官方文檔/控制檯為準 |
| 火山方舟 / 豆包 | `volcengine` | `openai` | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-seed-1-6-251015,doubao-seed-1-6-thinking-251015` |
| 硅基流動 / SiliconFlow | `siliconflow` | `openai` | `https://api.siliconflow.cn/v1` | `deepseek-ai/DeepSeek-V3.2,Qwen/Qwen3-235B-A22B-Thinking-2507` |
| OpenRouter | `openrouter` | `openai` | `https://openrouter.ai/api/v1` | `~anthropic/claude-sonnet-latest,~openai/gpt-latest` |
| Requesty | `requesty` | `openai` | `https://router.requesty.ai/v1`（EU：`https://router.eu.requesty.ai/v1`） | `claude-sonnet-4-6,gpt-6.1-sol` |
| Anspire Open（兼容） | `anspire` | `openai` | `https://open-gateway.anspire.cn/v6`（示例） | `Doubao-Seed-2.0-lite,Doubao-Seed-2.0-pro,qwen3.5-flash`（示例） |
| Ollama | `ollama` | `ollama` | `http://127.0.0.1:11434` | `llama3.2,qwen2.5` |

## 官方來源與兼容性

| 服務商 | 官方來源 | 兼容說明 |
| --- | --- | --- |
| Modelflare | [快速開始](https://docs.modelflare.dev/quickstart/)、[接入端點](https://docs.modelflare.dev/guides/endpoints/)、[模型與分組](https://docs.modelflare.dev/guides/models-and-groups/) | 使用 OpenAI-compatible Base URL `https://modelflare.dev/v1` 和標準 `LLM_MODELFLARE_*` 渠道配置；本項目默認模型為 `gpt-6.1-sol`，模型列表以賬號權限與控制檯為準。 |
| OpenAI | [模型列表](https://platform.openai.com/docs/models) | 官方模型頁建議從 `gpt-6.1-sol` 開始，低延遲/低成本場景使用 `gpt-6.1-terra`。 |
| DeepSeek | [快速開始](https://api-docs.deepseek.com/) | 官方 OpenAI Base URL 為 `https://api.deepseek.com`；`deepseek-chat` / `deepseek-reasoner` 將於 2026-07-24 棄用，當前模板直接使用 `deepseek-v4-flash` / `deepseek-v4-pro`。 |
| Gemini | [模型列表](https://ai.google.dev/gemini-api/docs/models) | Gemini 3.1 Pro / Gemini 3 Flash 仍為 preview；如需生產穩定性，可在控制檯改回 2.5 穩定模型。 |
| Anthropic Claude | [模型概覽](https://docs.anthropic.com/en/docs/about-claude/models/all-models) | Claude 當前 API ID 包含 `claude-sonnet-4-6`、`claude-opus-4-7`；Sonnet 更適合作為默認性價比入口。 |
| Kimi / Moonshot | [Kimi K2.6 快速開始](https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart)、[模型列表](https://platform.kimi.com/docs/models) | 官方推薦 `kimi-k2.6`；`kimi-k2` 系列將在 2026-05-25 下線，舊 `moonshot-v1-*` 僅保留為穩定舊工作負載選擇。 |
| 通義千問 / DashScope | [文本生成](https://help.aliyun.com/zh/model-studio/text-generation-model/) | 百鍊推薦 `qwen3.6-plus`，確認效果後可用 `qwen3.6-flash` 降低成本。 |
| 智譜 GLM | [模型概覽](https://docs.bigmodel.cn/cn/guide/start/model-overview)、[GLM-5.1](https://docs.bigmodel.cn/cn/guide/models/text/glm-5.1) | `glm-5.1` 是當前旗艦；`glm-4.7-flash` 作為輕量/免費模型示例。 |
| MiniMax | [Chat API](https://platform.minimax.io/docs/api-reference/text-chat)、[Models](https://platform.minimax.io/docs/guides/models-intro)、[Pricing](https://platform.minimax.io/docs/guides/pricing-paygo) | New channels recommend `MiniMax-M3.1-Flash` first, then `MiniMax-M3`, using `https://api.minimax.io/v1`. Discovery hides older MiniMax text recommendations without rewriting saved or manual IDs. Flash supports image input, 1,000,000 context tokens and 524,288 output tokens; standard input/output/cache-read prices are $0.15/$0.60/$0.015 per million tokens. Flash uses adaptive thinking by default: do not disable thinking or request effort `none`; supported effort values are `low`, `medium`, `high`, `xhigh`, `max` (default). M3 fallback estimates use the standard <=512K rate ($0.30/$1.20/$0.06); longer prompts and priority requests cost more and are not tiered by this fallback estimator. Legacy pricing remains for saved configurations. Subscription and regional access must be checked with the provider. |
| 小米 MiMo | 官方文檔 / 控制檯 | 當前按 OpenAI-compatible 方式接入，Base URL、模型名與權限以 MiMo 官方文檔/控制檯為準；`mimo` 渠道在倉庫默認 workflow 中未顯式映射，Actions 使用請按本文“GitHub Actions 配置”補齊自定義映射。 |
| 火山方舟 / 豆包 | [在線推理（常規）](https://www.volcengine.com/docs/82379/2121998)、[模型列表](https://www.volcengine.com/docs/82379/1949118) | 官方示例使用 `https://ark.cn-beijing.volces.com/api/v3` 與 `doubao-seed-1-6-251015`；如使用 Coding Plan，請改用其專用 Base URL 和模型名，不要套用本表的在線推理模板。 |
| SiliconFlow | [模型列表](https://docs.siliconflow.cn/quickstart/models)、[獲取模型列表 API](https://docs.siliconflow.cn/cn/api-reference/models/get-model-list) | 平臺模型實時更新且 `/models` 需要 API Key；模板只給常見新模型示例，保存前建議在 Web 設置頁點擊「獲取模型」確認賬號可見性。 |
| OpenRouter | [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models) | OpenRouter 支持 `~anthropic/claude-sonnet-latest`、`~openai/gpt-latest` 等 latest router alias；2026-05-03 的一次手動 live smoke 以 Claude Sonnet latest 作為默認示例通過，GPT latest 保留為可按賬號權限切換的備選。 |
| Requesty | [Models API](https://docs.requesty.ai/api-reference/endpoint/models-list)、[EU Routing](https://docs.requesty.ai/features/eu-routing) | 模板示例為無斜槓的 managed 模型 ID，運行時按 `openai/<model>` 路由；Base URL 為 `requesty.ai` 域名時，Web「獲取模型」返回的 vendor/model ID 會保存為 `openai/<vendor>/<model>`（如 `openai/openai/gpt-4o-mini`、`openai/anthropic/claude-sonnet-4-6`），手動填寫的 `anthropic/...`、`vertex/...` 也會自動補上 `openai/` 網關路由，完整 ID 原樣發送給 Requesty；僅 `openai/` 開頭的 ID 與 LiteLLM 路由前綴重名，手動填寫時需寫成 `openai/openai/gpt-4o-mini`。同一 API Key 可用於 EU 端點 `https://router.eu.requesty.ai/v1`。 |
| Anspire Open（兼容） | [Anspire Open](https://open.anspire.cn/dsa?share_code=QFBC0FYC) | `ANSPIRE_API_KEYS` 在未配置更高優先級 OpenAI-compatible 來源時可用於大模型網關與搜索；兼容示例為 `openai/Doubao-Seed-2.0-lite` + `https://open-gateway.anspire.cn/v6`，是否可用以控制檯與模型權限為準。 |
| LiteLLM | [OpenAI-Compatible Endpoints](https://docs.litellm.ai/docs/providers/openai_compatible) | OpenAI-compatible 端點需要把運行時模型寫成 `openai/<model>`，Base URL 只填到服務商兼容入口，不額外拼接 `/chat/completions`。 |

本頁預設只保證配置形狀與當前依賴的 OpenAI-compatible 路由規則一致；實際連通性仍取決於服務商賬號權限、地域、額度和模型開通狀態。當前 LiteLLM 版本約束為 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（見 `requirements.txt`），保留歷史最低版本、顯式排除 PyPI 事故版本，並將上界收斂到已驗證的 `<1.99.0`，避免未來大版本自動進入。

## OpenAI-compatible 與 LiteLLM 規則

- OpenAI-compatible provider 的 channel `protocol` 通常是 `openai`。
- `LLM_<CHANNEL>_API_SURFACE` 默認是 `chat_completions`；Responses-only 模型顯式設為 `responses`。Responses 渠道要求協議及每個模型的實際 LiteLLM provider 都是 `openai`；直連 provider 從當前安裝的 LiteLLM registry 獲取，並由系統配置 API 返回給 Web 編輯器作為共同真源。因此顯式 `anthropic/`、`gemini/`、`xai/` 以及未來新增的衝突前綴都會在所有配置入口被一致識別，網關自有的 `deepseek-ai/...`、`Qwen/...` 等帶斜槓模型 ID 則會規範化到 `openai/<model>`。同一個規範化公開 alias 不得跨渠道混用 Chat 與 Responses，避免 Router 在不同 Surface deployment 間負載均衡。運行時保留公開模型別名 `openai/<model>`，並通過 LiteLLM 的 `openai/responses/<model>` 橋接調用 `/responses`。
- 該設計與主流項目的顯式路由方式一致：[LiteLLM](https://github.com/BerriAI/litellm/blob/main/litellm/responses/main.py) 提供 Chat-to-Responses bridge，[OpenAI Agents SDK](https://openai.github.io/openai-agents-python/models/) 使用獨立 Responses/Chat 模型類，[LangChain](https://docs.langchain.com/oss/python/integrations/chat/openai) 使用 `use_responses_api` 顯式選擇並僅在已知條件下自動路由。DSA 不在請求失敗後猜測 endpoint，避免雙請求、重複計費及掩蓋真實服務端錯誤。
- 運行時模型名通常寫成 `openai/<model>`；例如自定義網關裡的 `gpt-6.1-sol` 可以作為 `openai/gpt-6.1-sol` 被 LiteLLM 路由。
- `Qwen/...`、`deepseek-ai/...` 這類是服務商或模型倉庫組織名前綴，不等同於 LiteLLM provider prefix；不要因為它們包含斜槓就誤判為 `provider/model` 路由。
- Base URL 只填官方或網關給出的兼容入口，通常到 `/v1`、`/api/v3` 或廠商文檔指定路徑；不要手動追加 `/chat/completions`。
- 如果使用 YAML 模式，按 LiteLLM `model_list` / `litellm_params` 的原生語義配置；YAML 有效時優先級高於 Channels。

## GitHub Actions 配置

倉庫自帶 `.github/workflows/00-daily-analysis.yml` 只會透傳 workflow 中顯式列出的環境變量。Modelflare 單 Key 接入只需在 Secrets 中設置 `MODELFLARE_KEY`。使用顯式渠道模式時，先在 Repository Variables 或 Secrets 中設置 `LLM_CHANNELS`，再按渠道名補齊對應 `LLM_<CHANNEL>_*`。

| 字段 | 建議位置 | 說明 |
| --- | --- | --- |
| `MODELFLARE_KEY` | Secrets | Modelflare 單 Key 接入，自動補齊默認地址與模型。 |
| `LLM_CHANNELS` | Variables 或 Secrets | 逗號分隔渠道名，例如 `deepseek,minimax,volcengine`。 |
| `LLM_<CHANNEL>_PROTOCOL` | Variables 或 Secrets | 非敏感，通常為 `openai`、`deepseek`、`gemini`、`anthropic` 或 `ollama`。 |
| `LLM_<CHANNEL>_API_SURFACE` | Variables 或 Secrets | 可選；`chat_completions`（默認）或 `responses`。Responses 當前只支持 `openai` 協議。 |
| `LLM_<CHANNEL>_BASE_URL` | Variables 或 Secrets | 非敏感時優先放 Variables；私有網關地址可放 Secrets。 |
| `LLM_<CHANNEL>_MODELS` | Variables 或 Secrets | 非敏感模型列表，逗號分隔。 |
| `LLM_<CHANNEL>_ENABLED` | Variables 或 Secrets | 可選，未配置時默認啟用；設為 `false` 可跳過該渠道。 |
| `LLM_<CHANNEL>_API_KEY` / `LLM_<CHANNEL>_API_KEYS` | Secrets | 密鑰字段必須放 Repository Secrets；同名 Variables 不會被 workflow 讀取。 |
| `LLM_<CHANNEL>_EXTRA_HEADERS` | Secrets 或 Variables | JSON 字符串；只要包含鑑權、租戶、組織或私有網關信息，就應放 Secrets。 |
| `LITELLM_CONFIG` | Variables 或 Secrets | YAML 文件路徑；配合 `LITELLM_CONFIG_YAML` 使用時，workflow 會寫入該路徑。 |
| `LITELLM_CONFIG_YAML` | Secrets 優先 | YAML 內容本身可能包含私有網關或 header，建議放 Secrets。 |
| `LLM_USAGE_HMAC_SECRET` | Secrets | 可選；只有需要跨部署比較 usage message HMAC 時才配置同一個高熵隨機密鑰，例如 `openssl rand -hex 32`；不要放 Variables 或提交到版本控制。 |
| `LLM_USAGE_HMAC_KEY_VERSION` | Variables 或 Secrets | 可選；輪換 `LLM_USAGE_HMAC_SECRET` 時同步更新版本標籤，避免誤比較不同密鑰生成的 HMAC。 |

默認 workflow 已顯式映射 `modelflare`、`primary`、`secondary`、`aihubmix`、`anspire`、`deepseek`、`dashscope`、`zhipu`、`moonshot`、`minimax`、`volcengine`、`siliconflow`、`openrouter`、`requesty`、`gemini`、`anthropic`、`openai`、`ollama`、`hermes`；`mimo` 未在默認 workflow 中映射。若使用 `mimo`（或任何未列渠道名），除了在 Variables/Secrets 配置同名 `LLM_<CHANNEL>_*` 外，還需在 workflow 中同步補齊對應 env 映射；本地 `.env`、Docker 和自託管腳本不受這個限制。

回滾 HMAC 遙測顯式配置時，可移除 `LLM_USAGE_HMAC_SECRET` 並恢復或刪除 `LLM_USAGE_HMAC_KEY_VERSION`；留空後系統會回到本地生成 `.llm_usage_hmac_secret` 的默認行為。

Ollama 默認 Base URL `http://127.0.0.1:11434` 主要面向本地、Docker 或能訪問該服務的 self-hosted runner。GitHub-hosted runner 通常沒有本地 Ollama 服務，直接配置 `LLM_CHANNELS=ollama` 大概率會連接失敗。

### Hermes 本地 HTTP generation（Phase 3）

Hermes 是 reserved 本地 HTTP generation preset，只通過 `LLM_CHANNELS=hermes` 啟用。默認協議為 `openai`，默認地址為 `http://127.0.0.1:8642/v1`，默認模型為 `hermes-agent`：

```env
LLM_CHANNELS=hermes
LLM_HERMES_PROTOCOL=openai
LLM_HERMES_BASE_URL=http://127.0.0.1:8642/v1
LLM_HERMES_API_KEY=sk-local-hermes
LLM_HERMES_MODELS=hermes-agent
LITELLM_MODEL=openai/hermes-agent
```

Phase 3 只支持普通分析 / JSON generation，不支持 stream/SSE、tools、Vision、Agent tools、remote Hermes 或進程生命週期管理。`LLM_HERMES_API_KEY` 應來自本地 `.env`、運行時配置或 GitHub Secrets；不要寫入倉庫。Hermes 只允許 loopback `/v1` endpoint，`localhost` 會按 `127.0.0.1` 規範化，`LLM_HERMES_API_KEYS` 與 `LLM_HERMES_EXTRA_HEADERS` 不受支持。Web 設置頁保存 reserved Hermes 渠道時會清空這兩個舊字段並顯示 warning；恢復舊值請使用 `.env` 備份、Git 歷史或桌面端導出備份，但非空多 Key / Extra Headers 仍會被後端拒絕。

在 GitHub Actions 中，GitHub-hosted runner 的 `127.0.0.1` 是 runner 自身，不是用戶電腦。只有 self-hosted runner 或同機服務能訪問本地 Hermes；否則會連接失敗。

## 常見錯誤與處理建議

| `details.reason` / 現象 | 常見原因 | 建議處理 |
| --- | --- | --- |
| `missing_api_key` | API Key 為空，或 `API_KEYS` 逗號分隔後沒有任何非空片段。 | 填入至少一個有效 key；本地 Ollama 或 localhost 兼容服務除外。 |
| `api_key_rejected` | 服務商返回 401 / 403，key 無效、權限不足或項目未開通。 | 重新複製 key，檢查賬號項目、組織、區域和模型權限。 |
| `insufficient_balance` | 餘額不足、賬單未開通或套餐額度耗盡。 | 到服務商控制檯確認餘額、賬單狀態和模型套餐。 |
| `quota_exceeded` | 賬號或組織配額耗盡。 | 檢查套餐、項目額度、組織額度和服務商賬單頁。 |
| `rate_limit` | RPM / TPM / 併發限制觸發。 | 降低併發，換輕量模型，或在控制檯提升限額。 |
| `timeout` | 請求超時，可能是網絡慢、服務商響應慢或本地服務無響應。 | 檢查代理、防火牆、Base URL、模型冷啟動和 timeout 設置。 |
| `dns_error` | 域名無法解析。 | 檢查 Base URL 拼寫、DNS、代理和運行環境網絡。 |
| `tls_error` | TLS 證書、代理或中間人證書異常。 | 檢查 HTTPS 證書鏈、公司代理、自簽證書和系統時間。 |
| `connection_refused` | 目標端口無服務，或本地服務未啟動。 | 檢查 Base URL、端口、防火牆；Ollama 確認本機或 runner 能訪問服務。 |
| `endpoint_not_found` | `/models` 或 chat endpoint 路徑不存在。 | 確認 Base URL 是否填到兼容入口，不要多拼或少拼廠商要求的路徑。 |
| `invalid_url` | base_url 包含不受支持形態（空白/控制字符、反斜槓、`userinfo@host` 等）或解析語義不安全。 | 清理 `LLM_<CHANNEL>_BASE_URL`（建議先置空/刪除該變量），保持 provider 默認入口；如需固定網關請先按官方兼容示例填寫。 |
| `model_access_denied` | 基於已觀測 provider 文案的 best-effort 模型可用性歸類：模型可能被禁用、未開通、賬號不可見或當前 key 無權限訪問。 | 先查看測試結果裡的“本次測試模型”，在服務商控制檯確認該模型已開通；必要時調整模型順序、移除不可用模型，或點擊「獲取模型」核對賬號可見模型。 |
| `provider_blocked` | 服務商或中轉網關明確攔截了本次請求，可能來自賬號風控、地域、請求來源、模型權限、代理商策略或內容安全策略。 | 先查看測試結果裡的“本次測試模型”和服務商控制檯日誌；檢查賬號/項目狀態、地域或來源限制、網關策略和內容安全規則，而不是優先排查 Base URL、TLS 或本地網絡。 |
| `provider_prefix_mismatch` | LiteLLM provider prefix 與渠道協議不匹配。 | OpenAI-compatible 渠道通常使用 `openai/<model>`；不要把 `Qwen/...`、`deepseek-ai/...` 誤當 provider prefix。 |
| `non_json` | 服務商返回非 JSON 或代理返回 HTML / 文本錯誤頁。 | 檢查 Base URL、網關路徑、代理錯誤頁和 Chat Completions 兼容入口。 |
| `null_response` | LiteLLM 沒有返回可解析響應對象。 | 檢查 provider 是否兼容 Chat Completions，必要時換模型或 endpoint 重試。 |
| `null_content` | Chat completion 返回成功但 `content` 為空。 | 換用兼容文本輸出的模型，或檢查是否強制 tool / vision 響應。 |
| `malformed_choices` | 響應缺少兼容的 `choices` 結構。 | 確認 endpoint 是 Chat Completions 兼容接口，不是 Embeddings、Responses 或其它協議入口。 |
| `capability_unsupported` | JSON / tools / stream / vision smoke 參數不被當前模型或 endpoint 支持。 | 換支持該能力的模型，或把結果視為當前賬號、模型和 endpoint 的一次能力診斷，不代表 provider 全局不支持。 |
| `unknown_error` | 服務商或客戶端拋出未能細分的異常。 | 先查看 `details.message` / 日誌中的原始錯誤，再按網絡、鑑權、模型名和額度逐項排查。 |

完整分類邏輯以 `src/services/system_config_service.py` 中的錯誤分類實現為準。

`model_access_denied` 不是跨 provider 的官方錯誤碼映射。該分類的可複核依據包括：

- SiliconFlow 官方錯誤處理文檔要求接口錯誤排查時記錄 HTTP 錯誤碼和 `message`，說明 403 表示餘額不足或權限不夠，其他情況參考報錯 `message`，並建議換一個模型確認問題是否仍存在（中文：<https://docs.siliconflow.cn/cn/faqs/error-code>；英文：<https://docs.siliconflow.cn/en/faqs/error-code>）。
- Issue #1208 中真實脫敏樣例來自 SiliconFlow / OpenAI Compatible 渠道測試，經 LiteLLM 返回 `litellm.APIError: APIError: OpenAIException - Model disabled.`。
- 線上複核記錄（2026-05-06T16:21:21Z）：在 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0` 約束下，本地驗證環境為 Python `3.13.12`、LiteLLM `1.82.3`、Base URL `https://api.siliconflow.cn/v1`、模型 `Qwen/Qwen3-235B-A22B-Thinking-2507`。直連 SiliconFlow Chat Completions 返回 HTTP `403`，響應體為 `{"code":30003,"message":"Model disabled.","data":null}`；同一模型通過 LiteLLM `completion(model="openai/Qwen/Qwen3-235B-A22B-Thinking-2507")` 返回 `APIError: OpenAIException - Model disabled.`。

因此當前運行時把該已觀測 provider `message` 作為 best-effort 模型可用性診斷，而不是把它聲明為官方跨 provider 錯誤碼。實現僅在錯誤文本同時包含 `model` 和明確權限、禁用或不可用信號時進入該診斷；未覆蓋或語義不同的 provider 文案會繼續走既有兜底診斷。`provider_blocked` 同樣是基於明確攔截文案的 best-effort 診斷，用於區分服務商/網關策略攔截與本地網絡、TLS 或模型不可用問題。

## 運行時能力檢測邊界

- JSON / tools / stream / vision smoke 必須在 Web 中顯式觸發。
- 檢測會產生真實 LLM 請求，可能帶來 token / 圖像輸入費用、RPM/TPM 限流、餘額不足或超時。
- 檢測結果只代表當前賬號、模型和 endpoint 的一次 best-effort 運行時結果。
- 檢測結果不會寫回 `.env`，也不會阻止保存配置。
- 能力檢測失敗不等於 provider 全局不支持；失敗可能來自賬號權限、模型未開通、endpoint 區域、餘額、服務商兼容層或 LiteLLM 轉換路徑。
- 當前實現未對所有真實 provider 做在線 smoke，兼容依據是 `litellm>=1.80.10,!=1.82.7,!=1.82.8,<1.99.0`（見 `requirements.txt`）、[LiteLLM Python SDK / OpenAI I/O format](https://docs.litellm.ai/)、[LiteLLM OpenAI-compatible 路由](https://docs.litellm.ai/docs/providers/openai_compatible)，以及 OpenAI Chat Completions 的 [JSON mode](https://platform.openai.com/docs/guides/structured-outputs?api-mode=chat)、[tool calling](https://platform.openai.com/docs/guides/function-calling?api-mode=chat)、[streaming](https://platform.openai.com/docs/guides/streaming-responses?api-mode=chat) 和 [vision input](https://platform.openai.com/docs/guides/images-vision?api-mode=chat) 請求形狀。

## 回滾方式

- Web 設置頁：刪除或禁用對應 channel，重新選擇舊的主模型 / Agent 模型 / fallback。
- `.env`：恢復備份中的 `LLM_*`、`LITELLM_MODEL`、`AGENT_LITELLM_MODEL`、`VISION_MODEL`、`LITELLM_FALLBACK_MODELS`。
- 從 Channels 回到 legacy：刪除或清空 `LLM_CHANNELS`，保留 legacy provider key 和 `LITELLM_MODEL`。
- 從 YAML 回到 Channels / legacy：移除 `LITELLM_CONFIG` / `LITELLM_CONFIG_YAML`，重啟後下層配置重新生效。
- WebUI / 桌面端：使用系統設置中導出的配置備份恢復。
- PR 回滾：revert 對應 docs PR；P4 不涉及配置、數據或代碼遷移。
