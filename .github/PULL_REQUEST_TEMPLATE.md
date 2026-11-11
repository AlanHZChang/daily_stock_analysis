<!--
For Chinese contributors: 請直接用中文填寫。
For English contributors: please fill in English. All fields marked (EN) accept English.
-->

## PR Type

- [ ] fix
- [ ] feat
- [ ] refactor
- [ ] docs
- [ ] chore
- [ ] test

## Background And Problem

請描述當前問題、影響範圍與觸發場景。  
*(EN) Describe the problem, its impact, and what triggers it.*

## Scope Of Change

請列出本 PR 修改的模塊和文件範圍。  
*(EN) List the modules and files changed in this PR.*

> 注意：請按實際 `git diff` 全量列出文件範圍（建議註明文件總數），避免遺漏文檔/後端/API/前端文件導致描述不一致。

> 若本 PR 修改了 `.github/PULL_REQUEST_TEMPLATE.md`、`.github/copilot-instructions.md`、`AGENTS.md`、`.github/instructions/*` 或 `.claude/skills/**` 等協作與治理文件，請補充“變更原因 + 影響面 + 回滾方式（默認 revert）”到 Summary / Compatibility / Rollback，避免 Scope 與描述不一致。

> 建議先執行並粘貼以下命令輸出，避免與實際 diff 不一致：

```bash
BASE_REF=$(git merge-base HEAD origin/main)
git diff --stat "$BASE_REF"..HEAD
git diff --name-only "$BASE_REF"..HEAD
```

- 文件總數 / 變更行數（建議粘貼 `git diff --stat "$BASE_REF"..HEAD`）：
- 文件清單（按實際 diff 全量，逐項列出）：
- 文檔更新文件（`docs/*`）：

## Issue Link

必須填寫以下之一 / Fill in one of:
- `Fixes #<issue_number>`
- `Refs #<issue_number>`
- 無 Issue 時說明原因與驗收標準 / If no issue, explain the motivation and acceptance criteria

## Verification Commands And Results

請填寫你實際執行過的命令和關鍵結果（不要只寫"已測試"）。  
*(EN) Paste the commands you actually ran and their key output (don't just write "tested"):*

```bash
# example
./scripts/ci_gate.sh
python -m pytest -m "not network"
```

> `Full-suite note` 必須與當次 PR 的當前 Head CI 結果保持一致；若本地復現存在環境相關失敗，請明確標註“本地環境差異”並給出 GitHub CI 的結論與鏈接。  
> 請避免保留與本 PR 無關的歷史失敗措辭，按本次實際結果填報。
> 如歷史描述中仍保留 `./scripts/ci_gate.sh` 失敗記錄，請先改為當前 Head CI 狀態或說明與 Head CI 的差異來源。
> 若 `Full-suite note` 與當前 Head CI 不一致，PR 文本不完整，請先更新 PR 描述後再提交。

- 請在下面按實際結果填寫並與 `Full-suite note` 保持一致（任一未填視為信息缺失）：
  - ai-governance：`pass` / `fail`，附鏈接
  - backend-gate：`pass` / `fail`，附鏈接
  - docker-build：`pass` / `fail` / `skipped`，運行時附鏈接
  - web-gate：`pass` / `fail` / `skipped`，運行時附鏈接
  - 若本 PR 修改 `.github/PULL_REQUEST_TEMPLATE.md` 等流程模板協作文件，請先說明變更必要性、影響邊界，並明確回滾方式（默認 `revert this PR`）；否則請在下一版中拆為單獨 chore PR。

關鍵輸出/結論 / Key output & conclusion:

- 【必填】當前 Head CI：`ai-governance:pass / backend-gate:pass / docker-build:pass / web-gate:pass`（按實際結果替換）並附對應鏈接；按路徑未運行的 Docker/Web 檢查寫為 `skipped`。
- 若需保留本地失敗現象，請在同段寫明“本地環境差異 + 當前 CI 通過/失敗結果 + CI 鏈接”。  
- 若全部通過，需補充一句：`當前狀態：全部通過（pass）`，並明確 Head CI 全部為 pass。  

- 建議將本行直接粘貼到 PR 描述正文首段：`當前 Head CI：ai-governance:pass / backend-gate:pass / docker-build:pass / web-gate:pass`（僅示例，按實際結果替換）。

> 若上述核驗項與 PR 文本衝突，建議先更新 PR 描述再提交，避免審查因狀態不一致被阻塞。

## Visual Evidence (if applicable)

【必填】若本 PR 修改報告格式、報告渲染效果或 Web UI 界面，請在此處附受影響報告 / 頁面截圖；涉及前後差異時，優先附前後對比。Issue / PR 過程截圖、審查截圖、一次性驗收截圖和臨時可視證據請放在 PR 描述、PR 評論、GitHub 附件、Actions artifact 或外部可訪問鏈接中，不要作為倉庫文件合入。
*(EN) If this PR changes report formatting, report rendering, or Web UI, attach screenshots of the affected report/page here; before/after screenshots are preferred when relevant. Issue/PR process screenshots, review screenshots, one-off acceptance screenshots, and temporary visual evidence should be linked from the PR body/comments, GitHub attachments, Actions artifacts, or external accessible evidence; do not commit them as repository files.)*

> 如截圖無法獲取，請在“原因”中明確寫明替代證據（如 Playwright/e2e 產物路徑、審查鏈接）及其可追溯命令，不得留空。涉及 Web 設置/報告渲染變更時，需確保截圖或替代證據明確指向變更項。
>
> 若本 PR 修改 Web UI，建議至少補一條可復現路徑，例如（優先 settings page）：
>
> - Playwright 截圖產物：`apps/dsa-web/e2e/smoke.spec.ts`（`cd apps/dsa-web && npx playwright test e2e/smoke.spec.ts --grep "settings page renders title and save actions after login"`）
> - 審查證據鏈接：可直接使用 Actions 產物、GitHub 評論附件或外部可訪問鏈接。

> 替代證據模板（設置頁變更建議）：
> - 命令：`cd apps/dsa-web && npx playwright test e2e/smoke.spec.ts --grep "settings page"`
> - 產物路徑：`apps/dsa-web/test-results/**/smoke-settings-page-*.png`
> - 說明：截圖中應可見本次修改的系統設置項（字段、標籤、幫助文案）

- 截圖鏈接 / Screenshot links（Web UI/報告改動項必填，未提供請在下方“不適用原因”給出替代證據）：
- settings 頁建議命名：`smoke-settings-page-zh` / `smoke-settings-page-en`
- 前後對比 / Before & After（如有）：
- settings 字段變更說明：截圖或產物應明確包含 `MARKET_REVIEW_REGION` 字段與幫助文案區塊（中文/英文）。
- 不適用原因 / Reason if not applicable（若未附截圖，此項務必填寫，且包含可復現證據與命令）：
  - Playwright 命令（無截圖時）：`cd apps/dsa-web && npx playwright test e2e/smoke.spec.ts --grep "settings page"`
  - 產物路徑（無截圖時）：`apps/dsa-web/test-results/**/smoke-settings-page-*.png`
  - 說明：截圖（或產物）必須可見本次修改的設置字段文案與幫助信息。

> 若本 PR 修改 Web 設置字段（字段、文案或幫助文案），截圖或替代證據必須可定位到對應設置項區域並可追溯至變更項；該項為必填。

> 若本 PR 修改 Web UI 或報告展示且無法獲取截圖，原因欄必須給出可復現替代證據（例如 Playwright 截圖產物路徑 + 命令），且不得留空。

## Compatibility And Risk

請說明兼容性影響、潛在風險（如無請寫 `None`）。  
*(EN) Describe compatibility impact and potential risks (write `None` if not applicable).*

- 若本 PR 修改第三方模型 / API 的兼容語義、請求參數、路由前綴或 provider fallback，請提供**官方來源鏈接或公告**，並說明這是長期約束、當前運行時約束還是臨時兼容處理。  
  請在下方補充所影響外部 API/服務、迴歸範圍與回退方式。  
  *(EN) If this PR changes third-party model/API compatibility, request parameters, routing prefixes, or provider fallback behavior, include an **official source link or announcement** and clarify whether the rule is permanent, runtime-specific, or a temporary compatibility workaround.)*
- 若本 PR 未觸及第三方模型/API、provider/model/base URL 或運行時配置保存/清理/遷移邏輯，請在此段直接按以下文案確認（無須再次展開）：  
  `本 PR 未變更 provider/model/base URL、運行時配置清理遷移語義；歷史配置保持不變；回滾方式為 revert 本提交。`
- 若本 PR 修改 `.github/PULL_REQUEST_TEMPLATE.md` / PR 流程模板類文件，請在此明確：僅影響協作流程與模板維護，不改 runtime 行為；回退方式為 revert；並補充是否影響自動化提交流程。  
  *(EN) If this PR changes `.github/PULL_REQUEST_TEMPLATE.md` or other PR workflow files, state that it only affects contribution governance templates (no runtime behavior), provide rollback by revert, and note any CI/checklist impact.)*
- 若本 PR 依賴特定運行時 / 鎖定依賴窗口（例如 LiteLLM 版本範圍、OpenAI-compatible 路由、YAML alias 行為），請寫明當前驗證過的兼容範圍與覆蓋路徑。  
  *(EN) If this PR depends on a specific runtime or pinned dependency window (for example a LiteLLM version range, OpenAI-compatible routing, or YAML alias behavior), state the compatibility window you verified and which code paths were covered.)*
- 若本 PR 觸及運行時配置保存、清理、遷移或回填邏輯，請明確說明舊配置是否會被自動改寫、清空、遷移或保持不變，以及用戶如何恢復原行為。  
  *(EN) If this PR touches runtime config save/cleanup/migration/backfill logic, explicitly describe whether existing config is rewritten, cleared, migrated, or left intact, and how users can restore the previous behavior.)*
- 若本 PR **未觸及** provider/model/base URL 或運行時配置保存/清理/遷移邏輯（本條僅作為聲明），請明確寫：`本 PR 未變更 provider/model/base URL、運行時配置清理遷移語義；歷史配置保持不變；回滾方式為 revert 本提交。`

## Rollback Plan

請至少寫一句可執行的回滾方案（必填）。  
*(EN) Provide at least one actionable rollback step (required).*

- 如果是兼容性修復，默認應寫出**最小回滾方式**（例如 `revert this PR`），並說明是否需要額外回滾配置或數據遷移。  
  *(EN) For compatibility fixes, include the **minimal rollback path** (for example `revert this PR`) and whether any additional config or data rollback is required.)*

## EXTRACT_PROMPT Change (if applicable)

若本 PR 修改了 `src/services/image_stock_extractor.py` 中的 `EXTRACT_PROMPT`，請在此處粘貼完整變更後的 prompt。  
*If this PR changes `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, paste the full updated prompt here:*

<details>
<summary>展開 / Expand: Full EXTRACT_PROMPT</summary>

```
(paste full prompt here)
```

</details>

## Checklist

- [ ] 本 PR 有明確動機和業務價值 / This PR has a clear motivation and value
- [ ] 已提供可復現的驗證命令與結果 / Reproducible verification commands and results are included
- [ ] 已評估兼容性與風險 / Compatibility and risk have been assessed
- [ ] 已提供回滾方案 / A rollback plan is provided
- [ ] 若修改報告格式或 Web UI 界面，已在 PR 描述/評論附受影響報告 / 頁面截圖，且未把一次性驗收截圖作為倉庫文件合入 / If report formatting or Web UI changed, affected report/page screenshots are linked in the PR body/comments and one-off acceptance screenshots are not committed as repository files
- [ ] 若本 PR 修改 Web 設置字段（字段、文案或幫助文本），請補充設置頁截圖；無法截圖時需提供替代可視證據（命令 + 產物路徑），並指向對應變更項 / If Web settings fields changed (labels or help text), screenshots of the settings page are required; if unavailable, provide alternative visual evidence with command + artifact path that points to the changed item.
- [ ] 若涉及用戶可見變更，已同步更新相關文檔與 `docs/CHANGELOG.md`；`README.md` 僅在首頁級信息變化時更新，細節優先寫入 `docs/*.md` / If user-visible changes are included, relevant docs and `docs/CHANGELOG.md` are updated; `README.md` is updated only for homepage-level changes, with details kept in `docs/*.md`
