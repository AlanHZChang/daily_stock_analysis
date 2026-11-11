# Repository Claude Skills

本目錄存放倉庫級協作 skills，屬於版本庫資產。

- 規則真源：倉庫根目錄 `AGENTS.md`
- 兼容入口：根目錄 `CLAUDE.md`（應為指向 `AGENTS.md` 的軟鏈接）
- 本目錄中的 skill 需要與 `AGENTS.md` 保持一致
- `.claude/reviews/` 屬於本地分析產物，不作為規則真源

如果未來需要兼容其他 agent 目錄（如 `.agents/skills/` 或 `.github/skills/`），應先明確單一真源，再通過腳本或鏡像同步，而不是手工長期維護多份同義內容。
