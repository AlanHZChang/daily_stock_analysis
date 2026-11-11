# Analyze PR

分析 GitHub Pull Request，評估必要性、描述完整性、驗證證據、主要風險與是否可直接合入。

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis/pulls

## Usage

```text
/analyze-pr <pr_number>
```

## Instructions

分析時使用簡潔中文，優先遵循倉庫根目錄 `AGENTS.md` 和 `.github/PULL_REQUEST_TEMPLATE.md`。

### Step 1: 同步最新代碼基線

分析 PR 前必須先刷新遠端狀態，並儘量把本地安全推進到最新基線：

```bash
git status --short
git fetch --all --prune
# 僅當工作區乾淨且當前分支可 fast-forward 時執行：
git pull --ff-only
```

- 只有在工作區乾淨、當前分支有可 fast-forward 的上游時，才執行並接受 `git pull --ff-only` 的結果。
- 如存在本地改動、衝突狀態、未跟蹤風險文件、無上游分支或無法 fast-forward，不要執行 `stash`、`reset`、強制切分支或覆蓋本地狀態；改用已 fetch 的 `origin/main`、PR head 或 GitHub diff 做分析。
- 在輸出文檔的 `Validation Evidence` 中記錄同步結果：本地 HEAD、使用的遠端基線，以及未更新本地工作樹的原因（如有）。

### Step 2: 拉取 PR 基本信息

```bash
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr view <pr_number> --repo ZhuLinsen/daily_stock_analysis --comments
gh pr checks <pr_number> --repo ZhuLinsen/daily_stock_analysis
gh pr diff <pr_number> --repo ZhuLinsen/daily_stock_analysis
```

如有失敗的 CI，優先查看失敗日誌，而不是立刻在本地重跑全部檢查：

```bash
gh run view <run_id> --log-failed
```

### Step 3: 檢查標題與描述完整性

先檢查 PR title 是否符合 `AGENTS.md` 的非阻斷建議：

- 格式應為 `<類型>: <修改內容>`，例如 `fix: 修復大盤分析歷史記錄丟失`
- 類型優先為 `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci`
- 不應包含 `[codex]`、`codex`、`autocode`、`copilot` 或其他工具/agent 來源前綴
- 標題應描述實際變更；若標題與 diff 不符，在描述完整性中指出，但不應單獨作為 review process blocker。

對照 `.github/PULL_REQUEST_TEMPLATE.md`，確認是否覆蓋：

- `PR Type`
- `Background And Problem`
- `Scope Of Change`
- `Issue Link`
- `Verification Commands And Results`
- `Visual Evidence`（僅當 PR 修改報告格式、報告渲染效果或 Web UI 界面時要求截圖或替代可視證據）
- `Compatibility And Risk`
- `Rollback Plan`

若 PR 涉及第三方模型 / API 兼容語義、請求參數固定值、OpenAI-compatible 路由、YAML alias、fallback 行為或運行時配置保存 / 清理 / 遷移邏輯，還要額外檢查描述裡是否明確寫出：

- 官方來源鏈接或公告
- 當前鎖定依賴 / 運行時兼容範圍（例如 LiteLLM 版本窗口）
- 已驗證的調用鏈路覆蓋面
- 舊配置是否會被靜默改寫、清空、遷移或保持不變
- 最小回滾路徑（通常是 revert 本 PR）

若 PR 修改報告格式、報告渲染效果或 Web UI 界面，還要檢查 `Visual Evidence` 是否附受影響報告 / 頁面截圖；涉及前後差異時優先檢查前後對比。若無法截圖，描述中應說明原因與替代可視證據。

### Step 4: 優先使用 CI / Diff 證據

- 先根據 `gh pr checks`、PR diff、現有測試與工作流日誌判斷問題
- 僅當 CI 未覆蓋改動面、CI 結果不足以定性問題、或需要驗證關鍵迴歸風險時，再補充本地最小驗證
- 不要默認切換當前分支或執行 `gh pr checkout`

如果必須補本地驗證，按改動面選擇最接近的檢查，例如：

- 後端：`./scripts/ci_gate.sh` 或 `python -m py_compile <changed_python_files>`
- 前端：`cd apps/dsa-web && npm ci && npm run lint && npm run build`
- 桌面端：先構建 Web，再構建 Electron

### Step 5: 評估正確性與風險

重點檢查：

- 是否解決了明確問題，且沒有夾帶無關改動
- 是否破壞 API / Schema / Web / Desktop 兼容性
- 是否破壞 fallback、降級路徑、通知鏈路或發佈流程
- 是否存在明顯邏輯錯誤、異常吞沒、安全問題、配置語義變化未同步文檔

### Step 6: 生成評審文檔

保存到 `.claude/reviews/prs/pr-<number>.md`

## Output Document Format

```markdown
# PR #<number> Analysis

**Date**: YYYY-MM-DD
**Status**: Pending Review

## Findings

- [嚴重級別] file:line - 問題描述

## Summary

- 必要性：
- 是否有對應 issue：
- PR 類型：
- PR title：
- description 完整性：
- 驗證情況：
- 主要風險：
- 是否可直接合入：

## Validation Evidence

- 代碼同步基線：
- CI 結論：
- 本地補充驗證（如有）：

## Compatibility And Risk

- API / Web / Desktop：
- 配置 / Docker / GitHub Actions：
- fallback / 通知 / 報告結構：
- 第三方依賴 / 官方約束來源：
- 運行時兼容窗口 / 已覆蓋鏈路：
- 舊配置遷移或靜默改寫風險：

## Draft Review Comment

<建議評論內容>
```

## Allowed Auto-Actions (No Confirmation Needed)

- 拉取 PR 元數據、diff、評論和 CI 狀態
- 執行 `git fetch --all --prune`，並在工作區乾淨且可 fast-forward 時執行 `git pull --ff-only`
- 閱讀相關代碼、模板、工作流與文檔
- 在必要時執行最小化本地驗證
- 生成評審文檔

## Actions Requiring Confirmation

執行以下動作前，先詢問用戶：

1. 發佈評論
2. Approve PR
3. Request changes
4. Merge PR
5. 關閉 PR
