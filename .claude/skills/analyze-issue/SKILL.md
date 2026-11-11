# Analyze Issue

分析 GitHub Issue，判斷其真實性、優先級、倉庫責任邊界與建議動作。

**Repository**: https://github.com/ZhuLinsen/daily_stock_analysis/issues

## Usage

```text
/analyze-issue <issue_number>
```

## Instructions

分析時使用簡潔中文，優先遵循倉庫根目錄 `AGENTS.md`。

### Step 1: 同步最新代碼基線

分析 issue 前必須先刷新遠端狀態，並儘量把本地安全推進到最新基線：

```bash
git status --short
git fetch --all --prune
# 僅當工作區乾淨且當前分支可 fast-forward 時執行：
git pull --ff-only
```

- 只有在工作區乾淨、當前分支有可 fast-forward 的上游時，才執行並接受 `git pull --ff-only` 的結果。
- 如存在本地改動、衝突狀態、未跟蹤風險文件、無上游分支或無法 fast-forward，不要執行 `stash`、`reset`、強制切分支或覆蓋本地狀態；改用已 fetch 的 `origin/main` 或相關遠端 refs 做分析。
- 在輸出文檔的 `Evidence` 中記錄同步結果：本地 HEAD、使用的遠端基線，以及未更新本地工作樹的原因（如有）。

### Step 2: 拉取 Issue 信息

```bash
gh issue view <issue_number> --repo ZhuLinsen/daily_stock_analysis
gh issue view <issue_number> --repo ZhuLinsen/daily_stock_analysis --comments
```

如為 bug，優先核對 issue 模板中是否提供了以下信息：

- 是否已同步到最新版本
- commit hash / 版本基線
- 運行環境與復現步驟
- 日誌或報錯信息

### Step 3: 回答 4 個核心問題

1. 版本是否明確
2. 問題是否真實且可驗證
3. 是否屬於倉庫責任邊界
4. 是否值得立即處理

### Step 4: 結合倉庫現狀做證據檢查

- 閱讀相關代碼、配置、測試、腳本、工作流與文檔
- 如果問題涉及 API、數據源 fallback、報告生成、通知發送、認證、桌面端、發佈流程，明確寫出影響面
- 判斷是實際 bug、環境配置問題、使用方式問題、還是外部依賴問題
- 如懷疑已被修復，檢查當前代碼而不是隻看 issue 描述

### Step 5: 形成結論

至少給出以下字段：

- `版本基線`：最新 / 非最新 / 未提供
- `是否合理`：是/否 + 理由
- `是否是 issue`：是/否 + 理由
- `是否好解決`：是/否 + 難點
- `结论`：`成立 / 部分成立 / 不成立`
- `分類`：`bug / feature / docs / question / external`
- `優先級`：`P0 / P1 / P2 / P3`
- `難度`：`easy / medium / hard`
- `建議動作`：`立即修復 / 排期修復 / 文檔澄清 / 關閉`

### Step 6: 生成分析文檔

保存到 `.claude/reviews/issues/issue-<number>.md`

## Output Document Format

```markdown
# Issue #<number> Analysis

**Date**: YYYY-MM-DD
**Status**: Pending Review

## Summary

- 版本基線：
- 是否合理：
- 是否是 issue：
- 是否好解決：
- 結論：
- 分類：
- 優先級：
- 難度：
- 建議動作：

## Evidence

- 代碼同步基線：
- 關鍵 issue 信息：
- 關鍵代碼/腳本/工作流證據：

## Impact Scope

- 受影響模塊：
- 受影響運行路徑（本地 / Docker / GitHub Actions / API / Web / Desktop）：

## Root Cause / Main Reasoning

<根因或主要判斷依據>

## Proposed Handling

<建議修復、澄清或關閉方式>

若建議後續創建 PR，給出的 PR title 建議符合 `AGENTS.md`：使用 `<類型>: <修改內容>`，不添加 `[codex]`、`codex`、`autocode`、`copilot` 或其他工具/agent 來源前綴；該約定僅用於協作一致性提醒，不應單獨作為 review process blocker。

## Risks And Rollback

- 風險點：
- 若修復，回滾方式：

## Draft Reply

<建議回覆內容>
```

## Allowed Auto-Actions (No Confirmation Needed)

- 拉取 issue 詳情與評論
- 執行 `git fetch --all --prune`，並在工作區乾淨且可 fast-forward 時執行 `git pull --ff-only`
- 閱讀相關代碼、配置、腳本、工作流和文檔
- 生成分析文檔

## Actions Requiring Confirmation

執行以下動作前，先詢問用戶：

1. 添加或修改標籤
2. 在 issue 下評論
3. 關閉 issue
4. 開始修復 issue
