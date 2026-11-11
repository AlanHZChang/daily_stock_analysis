# Fix Issue

基於 issue 分析結果實現修復，並按倉庫規則補齊驗證、風險與回滾說明。

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis

## Usage

```text
/fix-issue <issue_number>
```

## Prerequisites

優先先完成 `/analyze-issue <issue_number>`，確保問題成立且邊界清晰。

## Instructions

### Step 1: 確認分析基線

檢查 `.claude/reviews/issues/issue-<number>.md` 是否存在；如果不存在，先補做 issue 分析或在本次修復中補齊最小分析結論。

### Step 2: 同步最新代碼基線並選擇安全的工作方式

開始修復或準備創建 / 更新 PR 前，先按 `AGENTS.md` 拉新：

```bash
git status --short
git fetch --all --prune
# 僅當工作區乾淨且當前分支可 fast-forward 時執行：
git pull --ff-only
```

- 默認基於當前工作樹做最小相關改動
- 只有在工作區乾淨、當前分支有可 fast-forward 的上游時，才執行並接受 `git pull --ff-only` 的結果
- 如存在本地改動、衝突狀態、未跟蹤風險文件、無上游分支或無法 fast-forward，不要執行 `stash`、`reset`、強制切分支或覆蓋本地狀態；先記錄本地 HEAD、使用的遠端基線與無法更新本地工作樹的原因
- 若後續要創建 / 更新 PR，先說明當前分支與目標基線差異；必要時請求用戶確認 rebase、merge 或繼續基於當前分支推進
- 不要默認切換分支或改寫用戶當前工作狀態
- 如果用戶明確要求建分支，再執行最小必要的分支操作

### Step 3: 實施修復

- 根據 issue 結論定位相關文件
- 優先複用現有模塊、配置入口、腳本和測試
- 保持默認行為向後兼容，避免破壞 fallback / fail-open
- 如果修復涉及用戶可見行為、配置語義、CLI/API、部署、通知、報告結構，要同步更新相關文檔、`docs/CHANGELOG.md`、`.env.example`
- 向 `docs/CHANGELOG.md` 寫入條目時，在 `[Unreleased]` 段追加一行，格式為 `- [類型] 描述`，其中 `[類型]` 從 `[新功能]/[改进]/[修复]/[文档]/[测试]/[chore]` 中按本次變更內容選擇；只有修復 bug 時才使用 `[修复]`；**不要**在 `[Unreleased]` 內新增 `### 類目標題`
- `README.md` 只承載項目定位、核心能力、快速開始、主要入口、贊助/合作等首頁級信息；非必要不更新 README，避免持續膨脹
- 更細的模塊行為、頁面交互、專題配置、排障說明、字段契約、實現語義和邊界條件，優先更新對應 `docs/*.md`

### Step 4: 按改動面驗證

按 `AGENTS.md` 的驗證矩陣執行最接近的檢查：

- 後端優先：`./scripts/ci_gate.sh`
- 最低後端要求：`python -m py_compile <changed_python_files>`
- 前端：`cd apps/dsa-web && npm ci && npm run lint && npm run build`
- 桌面端：先構建 Web，再構建桌面端

如無法完成完整驗證，必須記錄缺口、原因與潛在風險。

### Step 5: 更新 issue 分析文檔

在 `.claude/reviews/issues/issue-<number>.md` 中補充：

```markdown
## Fix Implementation

**Date**: YYYY-MM-DD

### Changes Made

- 文件與改動點：

### Validation

- 已執行：
- 未執行：

### Risks

- 風險點：

### Rollback

- 回滾方式：
```

### Step 6: 需要確認的後續動作

如用戶要求創建 PR、生成 PR 標題或整理 PR 描述，PR title 建議遵循 `AGENTS.md`：

- 使用 `<類型>: <修改內容>` 格式，例如 `fix: 修復大盤分析歷史記錄丟失`
- 類型優先使用 `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`
- 標題只描述實際改動，建議不添加 `[codex]`、`codex`、`autocode`、`copilot` 或其他工具/agent 來源前綴
- 該約定僅用於協作一致性，不應被單獨當作 process blocker

只有在用戶明確確認後，才執行：

- 建分支
- `git commit`
- `git push`
- 創建 PR
- 在 issue 下回復或關閉 issue

## Allowed Auto-Actions (No Confirmation Needed)

- 閱讀和分析代碼
- 執行 `git fetch --all --prune`，並在工作區乾淨且可 fast-forward 時執行 `git pull --ff-only`
- 應用與當前任務直接相關的最小修復
- 運行非破壞性的本地驗證
- 更新本地 issue 分析文檔

## Actions Requiring Confirmation

1. 切換或創建分支
2. `git commit`
3. `git push`
4. 創建 PR
5. 回覆或關閉 issue
