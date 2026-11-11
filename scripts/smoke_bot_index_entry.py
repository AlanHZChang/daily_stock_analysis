# -*- coding: utf-8 -*-
"""
=============================================
Bot 指數入口 transport-independent 在線 E2E smoke
=============================================

從真實 ``CommandDispatcher.dispatch_async -> AnalyzeCommand ->
TaskService -> StockAnalysisPipeline`` 在線貫穿單標的分析，覆蓋
SH_ALIAS / REGISTERED_NAME / CSI_ALIAS 三條矩陣場景，不經過任何 webhook
transport（不修 transport，不 mock 在線依賴，不 dry-run）。

運行方式（單 target 參數，--timeout 默認 900 秒）::

    .venv\\Scripts\\python.exe scripts/smoke_bot_index_entry.py "SH.000016"
    .venv\\Scripts\\python.exe scripts/smoke_bot_index_entry.py "上证50"
    .venv\\Scripts\\python.exe scripts/smoke_bot_index_entry.py "930955.CSI"
    .venv\\Scripts\\python.exe scripts/smoke_bot_index_entry.py "SH.000016" --timeout 1800

進程職責:
- 父進程: 只負責 deadline、進程樹清理和退出碼；worker 繼承控制檯。
- worker: 獨立子進程（由父進程以內部 ``--worker`` flag 顯式拉起，不依賴
  任何環境變量），經真實 dispatcher 提交併在同一進程內輪詢
  ``TaskService``，輸出單行 ``E2E_EVENT {json}`` 事件。

事件契約（單行 ``E2E_EVENT {json}``，phase=submitted|completed|failed|timeout，
含 target，按階段附加 task_id / stock_code / result / error）:
- submitted : 任務已提交，附帶 ``task_id`` / ``stock_code``。
- completed : 任務完成且結構斷言通過，附帶 ``result``。
- failed    : 任務失敗或 completed 但結果不完整，附帶 ``error``。
- timeout   : worker 超過 deadline 被清理（父進程輸出）。

退出碼: 0 = 成功；1 = 失敗（結構斷言或 failed 事件）；124 = 超時。

超時清理: Windows 使用 ``taskkill /T /F`` 結束整個進程樹；POSIX 向進程組
發送 SIGKILL。超時只清理進程樹，不回滾 DB / 報告 / 通知等既有副作用。

Ctrl-C 中止: 父進程在輪詢窗口收到 Ctrl-C 時同樣先清理進程樹——清理成功
透傳中斷，清理失敗輸出含清理錯誤的 ``failed`` 事件並退出 1，絕不靜默
吞掉清理失敗。
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_env import _reconfigure_output_stream  # noqa: E402

EVENT_PREFIX = "E2E_EVENT "

# 矩陣輸入 -> (canonical code, registered display name) 的權威映射。
# worker 的期望 code/name 只從這裡取值，絕不信任響應或任務結果自報的身份，
# 防止 dispatcher 路由錯誤時仍假通過。
EXPECTED_OUTCOMES = {
    "SH.000016": ("sh000016", "上证50"),
    "上证50": ("sh000016", "上证50"),
    "930955.CSI": ("csi930955", "红利低波100"),
}


def _resolve_expected(target: str):
    """Return ``(expected_code, expected_name)`` for a matrix target.

    Raises ``ValueError`` for targets outside the required matrix.
    """
    try:
        return EXPECTED_OUTCOMES[target]
    except KeyError:
        raise ValueError(
            f"unsupported smoke target: {target!r} (must be one of "
            f"{sorted(EXPECTED_OUTCOMES)!r})"
        )


def _emit_event(phase: str, target: str, **fields) -> None:
    """Print one single-line ``E2E_EVENT {json}`` event to stdout."""
    payload = {"phase": phase, "target": target}
    payload.update(fields)
    print(f"{EVENT_PREFIX}{json.dumps(payload, ensure_ascii=False)}", flush=True)


def _spawn_kwargs(platform_name: str) -> dict:
    """Worker spawn kwargs: inherit the console (never ``PIPE``) and detach
    the child into its own session / new process group so the parent can
    kill the whole tree on timeout."""
    if platform_name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return {"creationflags": creationflags} if creationflags else {}
    return {"start_new_session": True}


def _terminate_process_tree(proc, platform_name: str) -> Optional[str]:
    """Kill the whole worker process tree.

    Returns ``None`` only when tree cleanup is confirmed: a successful
    ``taskkill /T /F`` (Windows) or process-group kill (POSIX), or a
    ``ProcessLookupError`` for the tree/group (already gone). A failed tree
    cleanup returns an error string even when the direct ``proc.kill()``
    best-effort fallback succeeds — direct kill only proves the worker
    process itself was killed, not its descendants, so it never erases the
    original tree-cleanup error.
    """
    if platform_name == "nt":
        try:
            result = subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                timeout=30,
            )
            if result.returncode == 0:
                return None
            taskkill_error = f"taskkill exited {result.returncode}"
        except Exception as exc:
            taskkill_error = f"taskkill failed: {exc}"
        # Best-effort damage control: kill the worker process itself, but
        # never report a confirmed tree cleanup.
        try:
            proc.kill()
            return (
                f"{taskkill_error}; direct worker kill succeeded but "
                f"tree cleanup is unconfirmed"
            )
        except ProcessLookupError:
            return (
                f"{taskkill_error}; worker process already gone but "
                f"tree cleanup is unconfirmed"
            )
        except Exception as exc:
            return f"{taskkill_error}; direct worker kill also failed: {exc}"
    kill_signal = getattr(signal, "SIGKILL", signal.SIGTERM)
    killpg = getattr(os, "killpg", None)
    try:
        if killpg is not None:
            killpg(proc.pid, kill_signal)
        else:
            # 無進程組原語：直接 kill 只能證明 worker 本身被殺，不能證明
            # 後代已清理，不得返回 None 聲稱樹清理已確認。
            proc.kill()
            return (
                "process-group kill unavailable; direct worker kill "
                "succeeded but tree cleanup is unconfirmed"
            )
        return None
    except ProcessLookupError:
        # The process group is already gone — confirmed success.
        return None
    except OSError as exc:
        try:
            proc.kill()
            return (
                f"process-group kill failed: {exc}; "
                f"direct worker kill succeeded but tree cleanup is unconfirmed"
            )
        except ProcessLookupError:
            return (
                f"process-group kill failed: {exc}; "
                f"worker process already gone but tree cleanup is unconfirmed"
            )
        except Exception as kill_exc:
            return (
                f"process-group kill failed: {exc}; "
                f"direct worker kill also failed: {kill_exc}"
            )


def _cleanup_process_tree(proc, platform_name: str) -> Optional[str]:
    """Terminate the worker tree and wait for the worker to exit.

    Returns ``None`` only when tree cleanup is confirmed; any terminate /
    post-cleanup wait / kill failure is merged into the returned error
    string so callers never silently claim a confirmed cleanup.
    """
    cleanup_error = _terminate_process_tree(proc, platform_name)
    # Post-cleanup handling must never escape as an uncaught exception:
    # merge any failure into ``cleanup_error``.
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
        except Exception as exc:
            post_error = f"post-cleanup kill failed: {exc}"
            cleanup_error = (
                f"{cleanup_error}; {post_error}"
                if cleanup_error is not None
                else post_error
            )
    except Exception as exc:
        post_error = f"post-cleanup wait failed: {exc}"
        cleanup_error = (
            f"{cleanup_error}; {post_error}"
            if cleanup_error is not None
            else post_error
        )
    return cleanup_error


def _assert_complete_result(result: dict, expected_code: str, expected_name: str):
    """Validate a completed task result.

    Returns ``None`` on success, or a human-readable failure reason string.
    A completed task is only a success when the canonical code equals the
    authoritative expected code, the name equals the registered display
    name, and the three non-empty result fields (analysis_summary /
    operation_advice / trend_prediction) are present.
    """
    if not isinstance(result, dict):
        return "completed result is not a dict"
    if result.get("code") != expected_code:
        return (
            f"result code mismatch: expected {expected_code!r}, "
            f"got {result.get('code')!r}"
        )
    if result.get("name") != expected_name:
        return (
            f"result name mismatch: expected {expected_name!r}, "
            f"got {result.get('name')!r}"
        )
    missing = [
        key
        for key in ("analysis_summary", "operation_advice", "trend_prediction")
        if not (result.get(key) or "").strip()
    ]
    if missing:
        return f"completed result missing non-empty fields: {missing}"
    return None


def _poll_once(service, task_id: str, target: str, stock_code: str):
    """One poll of the in-process ``TaskService``.

    Empty initial state (``None`` / ``running``) returns ``None`` so the
    caller keeps waiting. Terminal states return exactly one event dict:
    ``completed`` (structure assertions passed against the authoritative
    matrix expectation) or ``failed`` (task failed or completed but
    incomplete).
    """
    expected_code, expected_name = _resolve_expected(target)
    status = service.get_task_status(task_id)
    if status is None or status.get("status") in ("running", "pending"):
        return None
    if status.get("status") == "completed":
        result = status.get("result")
        reason = _assert_complete_result(result, expected_code, expected_name)
        if reason is not None:
            return {
                "phase": "failed",
                "target": target,
                "task_id": task_id,
                "stock_code": stock_code,
                "error": reason,
            }
        return {
            "phase": "completed",
            "target": target,
            "task_id": task_id,
            "stock_code": stock_code,
            "result": result,
        }
    return {
        "phase": "failed",
        "target": target,
        "task_id": task_id,
        "stock_code": stock_code,
        "error": status.get("error") or f"task status is {status.get('status')!r}",
    }


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
def _run_worker(target: str) -> int:
    """Worker entrypoint: submit via the real dispatcher in this process and
    poll the same process's TaskService until a terminal state.

    Only exits 0 when a completed event with passing structure assertions
    was produced. Authoritative target validation runs BEFORE any dispatcher
    construction or submission, so an unsupported target can never submit.
    Unexpected exceptions from dispatch / poll / event serialization are
    converted into a ``failed`` E2E event with the exception evidence on
    stderr and exit 1 — never an uncaught traceback. ``KeyboardInterrupt``
    is not treated as an ordinary failure.
    """
    expected_code = _resolve_expected(target)[0]

    try:
        return _run_worker_inner(target, expected_code)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        _emit_event("failed", target, error=f"worker exception: {exc}")
        print(f"ERROR: worker exception: {exc}", file=sys.stderr)
        return 1


def _run_worker_inner(target: str, expected_code: str) -> int:
    """Dispatch + poll loop of the worker (see :func:`_run_worker`)."""
    from datetime import datetime

    from bot.commands.analyze import AnalyzeCommand
    from bot.dispatcher import CommandDispatcher
    from bot.models import BotMessage, ChatType
    from src.services.task_service import get_task_service

    dispatcher = CommandDispatcher()
    dispatcher.register(AnalyzeCommand())

    message = BotMessage(
        platform="smoke",
        message_id="smoke-e2e",
        user_id="smoke",
        user_name="smoke",
        chat_id="smoke",
        chat_type=ChatType.PRIVATE,
        content=f"/analyze {target}",
        raw_content=f"/analyze {target}",
        mentioned=False,
        timestamp=datetime.now(),
    )

    import asyncio

    response = asyncio.run(dispatcher.dispatch_async(message))

    # 權威期望只來自矩陣映射，絕不信任 ``extra.stock_code`` 或任務結果自報
    # 身份：dispatcher 路由錯誤（提交了錯誤 code/name）時仍會失敗。
    response_code = response.extra.get("stock_code")
    response_task_id = response.extra.get("task_id")
    if response_task_id and response_code == expected_code:
        task_id = response_task_id
        _emit_event(
            "submitted",
            target,
            task_id=task_id,
            stock_code=expected_code,
        )
    elif response_task_id:
        # 有任務 identity 但 code 與矩陣期望不符：提交了錯誤的標的，輸出
        # 明確的 mismatch 錯誤（含期望值與實際值）與結構化實際 code，
        # 而不是成功響應文本。
        _emit_event(
            "failed",
            target,
            task_id=response_task_id,
            stock_code=response_code,
            error=(
                f"submitted code mismatch: expected {expected_code!r}, "
                f"got {response_code!r}"
            ),
        )
        return 1
    else:
        _emit_event("failed", target, error=response.text)
        return 1

    service = get_task_service()
    while True:
        event = _poll_once(service, task_id, target, expected_code)
        if event is not None:
            _emit_event(event["phase"], target, **{
                k: v
                for k, v in event.items()
                if k not in ("phase", "target")
            })
            return 0 if event["phase"] == "completed" else 1
        time.sleep(5)


# ---------------------------------------------------------------------------
# Parent
# ---------------------------------------------------------------------------
def _run_parent(target: str, timeout: int) -> int:
    """Parent entrypoint: spawn the worker (inheriting the console), enforce
    the deadline, clean up the process tree on timeout and on Ctrl-C, and
    map to exit codes 0 / 1 / 124. Authoritative target validation runs
    before the subprocess spawn, so an unsupported target never reaches
    ``Popen``; a non-positive timeout is rejected the same way. On Ctrl-C
    the parent cleans up the worker tree first: a confirmed cleanup
    propagates the interrupt, a failed cleanup emits a structured ``failed``
    event and returns 1."""
    _resolve_expected(target)  # raises ValueError for unsupported targets
    if timeout <= 0:
        raise ValueError(f"timeout must be positive, got {timeout}")

    # ``proc.wait`` without ``timeout`` would block SIGINT handling on
    # Windows, so poll with the deadline instead.
    child_args = [sys.executable, str(Path(__file__).resolve()), "--worker", target]
    if os.name == "nt":
        proc = subprocess.Popen(
            child_args,
            cwd=str(REPO_ROOT),
            **_spawn_kwargs("nt"),
        )
    else:
        proc = subprocess.Popen(
            child_args,
            cwd=str(REPO_ROOT),
            **_spawn_kwargs("posix"),
        )
    deadline = time.monotonic() + timeout
    while True:
        try:
            exit_code = proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            exit_code = None
        except KeyboardInterrupt:
            # 用戶主動中止：清理 worker 進程樹。清理失敗不得靜默吞掉——
            # 與 timeout 分支一致，輸出結構化 failed 事件並返回 1，避免
            # 用戶誤以為進程樹已清理而 worker 後代仍在跑真實副作用。
            if proc.poll() is not None:
                # worker 已自行退出：無需清理，直接透傳中斷。
                raise
            cleanup_error = _cleanup_process_tree(
                proc, "nt" if os.name == "nt" else "posix"
            )
            if cleanup_error is not None:
                _emit_event(
                    "failed",
                    target,
                    error=f"interrupt cleanup failed: {cleanup_error}",
                )
                return 1
            raise
        if exit_code is not None:
            # 文檔化運行時契約只暴露 0 / 1 / 124：worker 的任意其他退出碼
            # 歸一化為 1，避免洩漏任意崩潰碼。
            if exit_code in (0, 1, 124):
                return exit_code
            return 1
        if time.monotonic() >= deadline:
            cleanup_error = _cleanup_process_tree(
                proc, "nt" if os.name == "nt" else "posix"
            )
            if cleanup_error is not None:
                # 清理失敗不得靜默聲稱成功：輸出結構化 failed 事件並返回 1。
                _emit_event(
                    "failed",
                    target,
                    error=f"timeout cleanup failed: {cleanup_error}",
                )
                return 1
            _emit_event("timeout", target)
            return 124


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bot 指数入口 transport-independent 在線 E2E smoke："
            "從真實 dispatcher 貫穿 Pipeline，單标的在線分析。"
        )
    )
    parser.add_argument("target", help="矩陣輸入：SH.000016 / 上證50 / 930955.CSI")
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="worker 超時秒數（默認 900 秒；超時清理進程樹，不回滾副作用）",
    )
    parser.add_argument(
        "--worker",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    target = (args.target or "").strip()
    if not target:
        print("ERROR: target 不能為空", file=sys.stderr)
        return 2

    # 權威 target 校驗必須先於任何角色分支：不支持的 target 不得構造
    # dispatcher、不得提交、不得 spawn 子進程（參數/輸入錯誤，非零返回）。
    try:
        _resolve_expected(target)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # ``--timeout`` 必須為正：非正超時在 spawn/提交之前即拒絕（輸入錯誤）。
    if args.timeout <= 0:
        print(f"ERROR: --timeout 必須為正整數，got {args.timeout}", file=sys.stderr)
        return 2

    _reconfigure_output_stream(sys.stdout)
    _reconfigure_output_stream(sys.stderr)

    # 角色選擇只由顯式 ``--worker`` flag 決定（父進程拉起子進程時顯式傳入），
    # 不依賴任何環境變量，避免外部預置環境變量繞過父進程的硬超時。
    if args.worker:
        return _run_worker(target)
    return _run_parent(target, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
