#!/usr/bin/env python3
"""
AI code review script used by GitHub Actions PR Review workflow.
"""
import fnmatch
import json
import os
import subprocess
import traceback
import urllib.error
import urllib.request


MAX_DIFF_LENGTH = 18000
REVIEW_PATHS = [
    '*.py',
    '*.md',
    '*.ts',
    '*.tsx',
    'README.md',
    'AGENTS.md',
    'docs/**',
    '.github/PULL_REQUEST_TEMPLATE.md',
    'requirements.txt',
    '.github/requirements-ci.txt',
    'pyproject.toml',
    'setup.cfg',
    '.github/workflows/*.yml',
    '.github/workflows/*.yaml',
    '.github/scripts/*.py',
    'apps/dsa-web/**',
    'docker/Dockerfile',
    'docker-compose.yml',
]

GITHUB_API_PAGE_SIZE = 100
GITHUB_API_MAX_PAGES = 30


def run_git(args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"⚠️ git command failed: {' '.join(args)}")
        print(result.stderr.strip())
        return ''
    return result.stdout.strip()


def _event_payload():
    """Read GitHub Actions event payload from ``GITHUB_EVENT_PATH``.

    Returns an empty dict when the file is missing, unreadable, or contains
    invalid JSON, preserving the prior graceful-degradation behaviour, but
    emits a warning distinguishing the three failure modes so the failure
    no longer silently collapses into "PR number is unavailable" downstream.
    The warning records the exception type and the source path only; it
    never prints the payload content.
    """
    event_path = os.environ.get('GITHUB_EVENT_PATH')
    if not event_path:
        return {}
    if not os.path.exists(event_path):
        print(f"⚠️ GITHUB_EVENT_PATH 指向的文件不存在: {event_path}，事件載荷降级為空對象")
        return {}
    try:
        with open(event_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except UnicodeDecodeError as exc:
        # 文件可讀但字節序列不是合法 UTF-8(open 默認會拋 UnicodeDecodeError,
        # 它是 ValueError 子類但既不是 OSError 也不是 json.JSONDecodeError,
        # 舊 (OSError, ValueError) 接口接住了它,新分支需顯式補充避免迴歸)。
        print(f"⚠️ 事件載荷非 UTF-8 ({type(exc).__name__}): {event_path}，降级為空對象")
        return {}
    except OSError as exc:
        print(f"⚠️ 事件載荷讀取失敗 ({type(exc).__name__}): {event_path}，降级為空對象")
        return {}
    except json.JSONDecodeError as exc:
        print(f"⚠️ 事件載荷 JSON 解析失敗 ({type(exc).__name__}): {event_path}，降级為空對象")
        return {}


def _pull_request_number(payload=None):
    configured = os.environ.get('PR_NUMBER', '').strip()
    if configured:
        return int(configured)

    payload = payload if payload is not None else _event_payload()
    pull_request = payload.get('pull_request') or {}
    number = pull_request.get('number') or payload.get('number')
    if not number:
        raise RuntimeError('PR number is unavailable for GitHub API review')
    return int(number)


def _github_api_json(path):
    api_url = os.environ.get('GITHUB_API_URL', 'https://api.github.com').rstrip('/')
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'daily-stock-analysis-pr-review',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'

    request = urllib.request.Request(f'{api_url}{path}', headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as exc:
        raise RuntimeError(f'GitHub API request failed for {path}: {exc}') from exc


def _github_repository():
    repository = os.environ.get('GITHUB_REPOSITORY', '').strip()
    if repository.count('/') != 1:
        raise RuntimeError('GITHUB_REPOSITORY must use owner/name format')
    return repository


def _fetch_pull_files():
    repository = _github_repository()
    pull_number = _pull_request_number()
    files = []

    for page in range(1, GITHUB_API_MAX_PAGES + 1):
        batch = _github_api_json(
            f'/repos/{repository}/pulls/{pull_number}/files'
            f'?per_page={GITHUB_API_PAGE_SIZE}&page={page}'
        )
        if not isinstance(batch, list):
            raise RuntimeError('GitHub pull files response is not a list')
        files.extend(batch)
        if len(batch) < GITHUB_API_PAGE_SIZE:
            return files

    raise RuntimeError('GitHub pull files response exceeded the 3000-file API limit')


def _is_review_path(filename):
    return any(fnmatch.fnmatchcase(filename, pattern) for pattern in REVIEW_PATHS)


def _build_api_diff(files):
    chunks = []
    for file_info in files:
        filename = file_info.get('filename', '')
        if not filename or not _is_review_path(filename):
            continue

        status = file_info.get('status')
        previous = file_info.get('previous_filename') or filename
        old_path = '/dev/null' if status == 'added' else f'a/{previous}'
        new_path = '/dev/null' if status == 'removed' else f'b/{filename}'
        patch = file_info.get('patch')
        if not patch:
            patch = '@@ Patch unavailable from GitHub API (binary or truncated file) @@'
        chunks.append(
            f'diff --git a/{previous} b/{filename}\n'
            f'--- {old_path}\n'
            f'+++ {new_path}\n'
            f'{patch}'
        )
    return '\n'.join(chunks)


def get_review_data():
    """Return review diff, changed paths, and truncation without executing PR code."""
    if os.environ.get('AI_REVIEW_SOURCE') == 'github_api':
        pull_files = _fetch_pull_files()
        files = [
            item.get('filename', '')
            for item in pull_files
            if item.get('filename') and _is_review_path(item['filename'])
        ]
        diff = _build_api_diff(pull_files)
    else:
        base_ref = os.environ.get('GITHUB_BASE_REF', 'main')
        diff = run_git(['git', 'diff', f'origin/{base_ref}...HEAD', '--', *REVIEW_PATHS])
        output = run_git(['git', 'diff', '--name-only', f'origin/{base_ref}...HEAD', '--', *REVIEW_PATHS])
        files = output.split('\n') if output else []

    truncated = len(diff) > MAX_DIFF_LENGTH
    return diff[:MAX_DIFF_LENGTH], files, truncated


def get_diff():
    """Get PR diff content for review-relevant files."""
    diff, _, truncated = get_review_data()
    return diff, truncated


def get_changed_files():
    """Get changed file list for review-relevant files."""
    _, files, _ = get_review_data()
    return files


def get_pr_context():
    """Read PR title/body from GitHub event payload when available."""
    payload = _event_payload()
    pr = payload.get('pull_request') or {}
    if not pr and os.environ.get('AI_REVIEW_SOURCE') == 'github_api':
        try:
            repository = _github_repository()
            number = _pull_request_number(payload)
            pr = _github_api_json(f'/repos/{repository}/pulls/{number}')
        except (RuntimeError, ValueError):
            pr = {}
    return (pr.get('title') or '').strip(), (pr.get('body') or '').strip()


def classify_files(files):
    py_files = [f for f in files if f.endswith('.py')]
    doc_files = [f for f in files if f.endswith('.md') or f.startswith('docs/') or f in ('README.md', 'AGENTS.md')]
    frontend_files = [f for f in files if f.startswith('apps/dsa-web/') or f.endswith(('.tsx', '.ts'))]
    ci_files = [f for f in files if f.startswith('.github/workflows/')]
    config_files = [
        f for f in files if f in ('requirements.txt', '.github/requirements-ci.txt', 'pyproject.toml', 'setup.cfg', '.github/PULL_REQUEST_TEMPLATE.md')
    ]
    return py_files, doc_files, frontend_files, ci_files, config_files


def _build_ci_context():
    """Build CI context section from environment variables set by the workflow."""
    auto_check_result = os.environ.get('CI_AUTO_CHECK_RESULT', '')
    syntax_ok = os.environ.get('CI_SYNTAX_OK', '')
    has_py = os.environ.get('CI_HAS_PY_CHANGES', 'false')

    if os.environ.get('CI_DELEGATED_TO_PULL_REQUEST', '').lower() == 'true':
        return """
## CI 檢查狀態
> Python 語法、Flake8、確定性檢查和離線測試由獨立的 `pull_request` CI / `backend-gate` 執行。本審查工作流不在帶 secrets 的 `pull_request_target` 上執行 PR 代碼，也不假设並行 CI 已通過；合入判斷必須核對当前 Head 的實際 CI 結果。
"""

    if not auto_check_result:
        return """
## CI 檢查狀態
> ⚠️ 未獲取到 CI 檢查結果。審查時不得假设 CI 已通過，驗證相關判斷應標註為"無法確認"。
"""

    lines = ["\n## CI 检查状态（来自本次 PR 的自动化流水线）"]
    lines.append(f"- 靜態檢查總體結果: **{'✅ 通過' if auto_check_result == 'success' else '❌ 失敗'}**")
    if has_py == 'true':
        lines.append(f"- Python 語法檢查 (py_compile): **{'✅ 通過' if syntax_ok == 'true' else '❌ 失敗' if syntax_ok == 'false' else '⏭️ 未執行'}**")
        lines.append("- Flake8 嚴重錯誤檢查 (E9/F63/F7/F82): **✅ 通過**（若未通過則靜態檢查總體會失敗）")
    else:
        lines.append("- Python 文件: 無變更，語法檢查已跳過")
    lines.append("")
    lines.append("> 以上 CI 僅覆蓋語法正確性（py_compile）和致命 lint 錯誤（flake8 E9/F63/F7/F82）。`./scripts/ci_gate.sh` **未包含在 CI 中**：對 Python 後端改動，若 PR 描述未說明該 gate 是否執行（或給出跳過原因），應在建议項中註明，但不構成阻斷。語法/flake8 已通過則无需重複貼對應本地輸出。")
    lines.append("")
    return '\n'.join(lines)


def build_prompt(diff_content, files, truncated, pr_title, pr_body):
    """Build AI review prompt aligned with AGENTS.md requirements."""
    truncate_notice = ''
    if truncated:
        truncate_notice = "\n\n> ⚠️ 注意：diff 過長已截斷，請基於可見內容審查並標註不確定點。\n"

    py_files, doc_files, frontend_files, ci_files, config_files = classify_files(files)
    ci_context = _build_ci_context()
    return f"""你是本倉庫的 PR 審查助手。請根據變更內容和 PR 描述，執行“代碼 + 文檔 + CI”聯合審查。

## PR 信息
- 標題: {pr_title or '(empty)'}
- 描述:
{pr_body or '(empty)'}

## 修改文件統計
- Python: {len(py_files)}
- Docs/Markdown: {len(doc_files)}
- Frontend (apps/dsa-web): {len(frontend_files)}
- CI Workflow: {len(ci_files)}
- Config/Template: {len(config_files)}

修改文件列表:
{', '.join(files)}{truncate_notice}

## 代碼變更 (diff)
```diff
{diff_content}
```
{ci_context}
## 必須對齊的審查規則（來自倉庫 AGENTS.md）
1. 必要性（Necessity）：是否有明確問題/業務價值，避免無效重構。
2. 關聯性（Traceability）：是否有關聯 Issue（Fixes/Refs）；自然語言關聯（如"關聯 issue 為 #xxx"）也可接受，不因格式問題判定不通過。無 Issue 時是否給出動機與驗收標準。
3. 類型判定（Type）：fix/feat/refactor/docs/chore/test 是否匹配。
4. 描述完整性（Description Completeness）：是否包含背景、範圍、驗證命令與結果、兼容性风险、回滾方案。判斷驗證是否充分時，必須參考上方"CI 檢查狀態"段落：（a）若 py_compile 和 flake8 已通過，PR 描述中可引用 CI 結果而不必貼對應本地輸出；（b）`./scripts/ci_gate.sh` 不在 CI 覆蓋範圍，對 Python 後端改動需檢查 PR 描述是否說明了該 gate 的執行情況，若未說明應列為建议項；（c）若未提供 CI 結果，則不得假设 CI 已通過，驗證充分性應標註為"無法確認"。
5. 合入判定（Merge Readiness）：給出 Ready / Not Ready，並列出阻斷項。
6. 若涉及用户可見能力，檢查 README.md 與 docs/CHANGELOG.md 是否同步。

## 阻斷 vs 建议的判定標準
僅以下問題可判定為 Not Ready（阻斷項/必改項）：
- 代碼存在正確性或安全性問題（邏輯錯誤、異常吞沒、安全漏洞等）
- CI 檢查未通過
- PR 描述與實際改動內容存在實質性矛盾
- 缺少回滾方案

以下問題僅放入建议項，不影響合入判定：
- issue 關聯格式不規範
- 語法/flake8 驗證證據缺失但上方"CI 檢查狀態"顯示 py_compile 和 flake8 均通過
- Python 後端改動的 PR 描述未說明 `./scripts/ci_gate.sh` 是否執行或給出跳過原因
- 描述中非關鍵性措辭或格式問題
- 註釋語言風格、無關鎖文件變更等

## 審查輸出要求
- 使用中文。
- 先給"结论"：`Ready to Merge` 或 `Not Ready`。
- 再給結構化結果：
  - 必要性：通過/不通過 + 理由
  - 關聯性：通過/不通過 + 證據
  - 類型：建议類型
  - 描述完整性：完整/不完整（缺失項）
  - 风险級別：低/中/高 + 關鍵风险
  - 必改項（最多 5 條，僅限阻斷條件，按優先級）
  - 建议項（最多 5 條）
- 必改項僅包含上述阻斷條件中的問題；格式、關聯、驗證證據等非阻斷問題放入建议項。
- 對發現的問題，儘量定位到文件路徑並說明影響。
- 如果信息不足，明確寫“基於当前 diff/PR 描述無法確認”。
"""


def review_with_gemini(prompt):
    """Run review with Gemini API."""
    api_key = os.environ.get('GEMINI_API_KEY')
    model = os.environ.get('GEMINI_MODEL') or os.environ.get('GEMINI_MODEL_FALLBACK') or 'gemini-3.6-flash'

    if not api_key:
        print("❌ Gemini API Key 未配置（檢查 GitHub Secrets: GEMINI_API_KEY）")
        return None

    print(f"🤖 使用模型: {model}")

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        print(f"✅ Gemini ({model}) 審查成功")
        return response.text
    except ImportError as e:
        print(f"❌ Gemini 依賴未安装: {e}")
        print("   請確保安装了 google-genai: pip install google-genai")
        return None
    except Exception as e:
        print(f"❌ Gemini 審查失敗: {e}")
        traceback.print_exc()
        return None


def review_with_openai(prompt):
    """Run review with OpenAI-compatible API as fallback."""
    api_key = os.environ.get('OPENAI_API_KEY')
    base_url = os.environ.get('OPENAI_BASE_URL', 'https://api.openai.com/v1')
    model = os.environ.get('OPENAI_MODEL', 'gpt-6.1-sol')

    if not api_key:
        print("❌ OpenAI API Key 未配置（檢查 GitHub Secrets: OPENAI_API_KEY）")
        return None

    print(f"🌐 Base URL: {base_url}")
    print(f"🤖 使用模型: {model}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.3
        )
        print(f"✅ OpenAI 兼容接口 ({model}) 審查成功")
        return response.choices[0].message.content
    except ImportError as e:
        print(f"❌ OpenAI 依賴未安装: {e}")
        print("   請確保安装了 openai: pip install openai")
        return None
    except Exception as e:
        print(f"❌ OpenAI 兼容接口審查失敗: {e}")
        traceback.print_exc()
        return None


def ai_review(diff_content, files, truncated):
    """Run AI review: Gemini first, then OpenAI fallback."""
    pr_title, pr_body = get_pr_context()
    prompt = build_prompt(diff_content, files, truncated, pr_title, pr_body)

    result = review_with_gemini(prompt)
    if result:
        return result

    print("嘗試使用 OpenAI 兼容接口...")
    result = review_with_openai(prompt)
    if result:
        return result

    return None


def main():
    diff, files, truncated = get_review_data()

    if not diff or not files:
        print("沒有可審查的代碼/文檔/配置變更，跳過 AI 審查")
        summary_file = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write("## 🤖 AI 代碼審查\n\n✅ 沒有可審查變更\n")
        return

    print(f"審查文件: {files}")
    if truncated:
        print(f"⚠️ Diff 內容已截斷至 {MAX_DIFF_LENGTH} 字符")

    review = ai_review(diff, files, truncated)

    summary_file = os.environ.get('GITHUB_STEP_SUMMARY')

    strict_mode = os.environ.get('AI_REVIEW_STRICT', 'false').lower() == 'true'

    if review:
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write(f"## 🤖 AI 代碼審查\n\n{review}\n")

        with open('ai_review_result.txt', 'w', encoding='utf-8') as f:
            f.write(review)

        print("AI 審查完成")
    else:
        print("⚠️ 所有 AI 接口都不可用")
        if summary_file:
            with open(summary_file, 'a', encoding='utf-8') as f:
                f.write("## 🤖 AI 代碼審查\n\n⚠️ AI 接口不可用，請檢查配置\n")
        if strict_mode:
            raise SystemExit("AI_REVIEW_STRICT=true and no AI review result is available")


if __name__ == '__main__':
    main()
