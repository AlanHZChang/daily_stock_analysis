# Grok Bot Skill 示例

給 2026-08-11 [Grok Bot](https://x.ai/bot) 用的最小 Skill 包。只調用 DSA 已有 REST，不引入新 API、環境變量或 MCP server。

把 [`SKILL.md`](SKILL.md) 拷進 Bot 的 Skills 目錄，設置 `DSA_BASE_URL`（例如 `http://127.0.0.1:8000`），並先讓 DSA 以 `python main.py --serve-only` 或 Docker 長期運行。

完整邊界、DecisionSignal Routine、認證限制見 [Grok Bot 集成](../../grok-bot-integration.md)。openclaw 用戶看 [openclaw Skill](../../openclaw-skill-integration.md)，契約相同。
