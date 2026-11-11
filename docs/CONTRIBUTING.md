# 貢獻指南

感謝你對本項目的關注！歡迎任何形式的貢獻。

## 🐛 報告 Bug

1. 先搜索 [Issues](https://github.com/ZhuLinsen/daily_stock_analysis/issues) 確認問題未被報告
2. 使用 Bug Report 模板創建新 Issue
3. 提供詳細的復現步驟和環境信息

## 💡 功能建議

1. 先搜索 Issues 確認建議未被提出
2. 使用 Feature Request 模板創建新 Issue
3. 詳細描述你的使用場景和期望功能

## 🔧 提交代碼

### 開發環境

```bash
# 克隆倉庫
git clone https://github.com/ZhuLinsen/daily_stock_analysis.git
cd daily_stock_analysis

# 創建虛擬環境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 安裝依賴
pip install -r requirements.txt

# 配置環境變量
cp .env.example .env
```

### 提交流程

1. Fork 本倉庫
2. 創建特性分支：`git checkout -b feature/your-feature`
3. 提交改動：`git commit -m 'feat: add some feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 創建 Pull Request

### Commit 規範

使用 [Conventional Commits](https://www.conventionalcommits.org/) 規範：

```
feat: 新功能
fix: Bug 修復
docs: 文檔更新
style: 代碼格式（不影響功能）
refactor: 重構
perf: 性能優化
test: 測試相關
chore: 構建/工具相關
```

示例：
```
feat: 添加釘釘機器人支持
fix: 修復 429 限流重試邏輯
docs: 更新 README 部署說明
```

### 代碼規範

- Python 代碼遵循 PEP 8
- 函數和類需要添加 docstring
- 重要邏輯添加註釋
- 新功能需要更新相關文檔

### CI 自動檢查

提交 PR 後，CI 會自動運行以下檢查：

僅修改普通 `docs/**`、非治理類 Markdown 或 `LICENSE` 時，CI 保留輕量的變更檢測、治理校驗和門禁彙總，但跳過 3 個後端測試 shard、Docker、Web 與桌面打包。被離線測試直接讀取的契約文檔、靜態 API 規格與 Markdown fixture 仍會觸發後端測試。`AGENTS.md`、`.github/instructions/**`、`.claude/skills/**` 等治理資產仍會由 `ai-governance` 校驗；配置、依賴、工作流等會影響運行的文本文件仍執行對應完整檢查。

| 檢查項 | 說明 | 必須通過 |
|--------|------|:--------:|
| backend-gate | `scripts/ci_gate.sh`（py_compile + flake8 嚴重錯誤 + 本地核心腳本 + offline pytest） | ✅ |
| docker-build | Docker 鏡像構建與關鍵模塊導入 smoke | ✅ |
| web-gate | 前端變更時執行 `npm run lint` + `npm run build` | ✅（觸發時） |
| pr-review | 暫停 PR 自動觸發，僅保留維護者通過 `workflow_dispatch` 按 PR 編號手動運行；通過 GitHub API 讀取 PR 元數據和 diff，不檢出或執行 fork PR 代碼 | ❌（輔助項） |
| network-smoke | 定時/手動執行 `pytest -m network` + `scripts/test.sh quick`（非阻斷） | ❌（觀測項） |

**本地運行檢查：**

```bash
# backend gate（推薦）
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh

# 前端 gate（如修改了 apps/dsa-web）
cd apps/dsa-web
npm ci
npm run lint
npm run build
```

## 📋 優先貢獻方向

查看 [README](../README.md) 瞭解項目當前的核心能力與主要入口：

- 🔔 新通知渠道（釘釘、飛書、Telegram）
- 🤖 新 AI 模型支持（GPT-4、Claude）
- 📊 新數據源接入
- 🐛 Bug 修復和性能優化
- 📖 文檔完善和翻譯

## ❓ 問題解答

如有任何問題，歡迎：
- 創建 Issue 討論
- 查看已有 Issue 和 Discussion

再次感謝你的貢獻！ 🎉
