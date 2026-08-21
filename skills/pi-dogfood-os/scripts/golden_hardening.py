#!/usr/bin/env python3
"""Offline G1-G10 hardening scenarios. Imports the live orchestration modules."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures"
HERDR = ROOT / "skills" / "herdr-pi-team" / "scripts"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter = load("golden_adapter", HERDR / "herdr_adapter.py")
cleanup = load("golden_cleanup", HERDR / "cleanup.py")
gate = load("golden_git_gate", HERDR / "git_gate.py")
policy = load("golden_policy", HERDR / "dispatch_policy.py")
state = load("golden_state", HERDR / "run_state.py")


def fake_adapter(root: Path, scenario: str = "ok"):
    extension = root / "team.ts"
    extension.write_text("export {};\n", encoding="utf-8")
    brief = root / "brief.md"
    brief.write_text("fixture brief\n", encoding="utf-8")
    log = root / "herdr.jsonl"
    os.environ["FAKE_HERDR_SCENARIO"] = scenario
    os.environ["FAKE_HERDR_LOG"] = str(log)
    return adapter.HerdrAdapter(session="review", herdr_command=str(FIXTURES / "fake_herdr.py"),
                                pi_command=sys.executable, extension=str(extension), poll_interval=0.001), brief, log


def git(cwd: Path, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True, shell=False)


def disposable_worktree(root: Path):
    main = root / "main"
    remote = root / "remote.git"
    worktree = root / "workers" / "worker-1"
    main.mkdir()
    worktree.parent.mkdir()
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, shell=False)
    git(main, "init")
    git(main, "config", "user.email", "golden@example.invalid")
    git(main, "config", "user.name", "Golden")
    (main / "README.md").write_text("base\n", encoding="utf-8")
    git(main, "add", "README.md")
    git(main, "commit", "-m", "initial")
    git(main, "branch", "-M", "main")
    git(main, "remote", "add", "origin", str(remote))
    git(main, "push", "-u", "origin", "main")
    git(main, "worktree", "add", "-b", "feature/worker", str(worktree), "origin/main")
    git(worktree, "branch", "--set-upstream-to=origin/main")
    return main, worktree


def scenario_g1():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mux, _, _ = fake_adapter(root, "session-mismatch")
        try:
            mux.preflight()
        except adapter.AdapterError as exc:
            return exc.code == "SESSION_MISMATCH", {"error_code": exc.code}
    return False, {"error_code": "not_detected"}


def scenario_g2():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mux, brief, log = fake_adapter(root, "setup-failure")
        try:
            mux.launch(run_id="run-g2", label="worker", cwd=str(root), worktree=str(root), branch="feature", brief_file=str(brief))
        except adapter.AdapterError as exc:
            commands = [json.loads(line)["op"] for line in log.read_text().splitlines()]
            return exc.code == "SETUP_FAILED" and "agent start" not in commands, {"error_code": exc.code, "worker_started": "agent start" in commands}
    return False, {"error_code": "not_detected"}


def scenario_g3():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mux, brief, _ = fake_adapter(root, "setup-timeout")
        started = time.monotonic()
        try:
            mux.launch(run_id="run-g3", label="worker", cwd=str(root), worktree=str(root), branch="feature", brief_file=str(brief), setup_timeout=0.01)
        except adapter.AdapterError as exc:
            bounded = exc.code == "SETUP_TIMEOUT" and time.monotonic() - started < 1
            try:
                policy.DispatchPolicy().admit(active_workers=4, setup_workers=0)
            except policy.DispatchRefused as admission:
                return bounded and admission.code == "MAX_ACTIVE", {"setup_error": exc.code, "admission": admission.code}
    return False, {"error_code": "not_detected"}


def scenario_g4():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mux, _, _ = fake_adapter(root)
        manifest = {"pane_id": "pane-1", "label": "renamed-worker", "state": "ready", "worktree": str(root)}
        result = mux.send(manifest, "stable target", acknowledge="ACKNOWLEDGED")
        return result["acknowledged"] and result["pane_id"] == "pane-1", {"pane_id": result["pane_id"]}


def scenario_g5():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        mux, _, log = fake_adapter(root)
        mux.send({"pane_id": "pane-1", "label": "worker", "state": "ready", "worktree": str(root)}, "message", acknowledge="ACKNOWLEDGED")
        commands = [json.loads(line) for line in log.read_text().splitlines()]
        enter = next((row for row in commands if row["op"] == "pane send-keys"), None)
        return bool(enter and enter["key"] == "enter"), {"submit_key": enter["key"] if enter else None}


def scenario_g6():
    result = gate.completion_gate(git={"clean": False, "synchronized": False, "head_sha": "abc", "pushed_sha": "def"}, review_status="approved", checks_status="passed")
    return result["state"] == "blocked", {"state": result["state"]}


def scenario_g7():
    os.environ["FAKE_GH_SCENARIO"] = "rate-limit"
    result = gate.GitGate(gh_command=str(FIXTURES / "fake_gh.py")).retrieve_reviews(repository="org/repo", pr_number=7)
    return result["review_status"] == "blocked_external", {"review_status": result["review_status"], "rate_limited": result["rate_limited"]}


def scenario_g8():
    result = gate.completion_gate(git={"clean": True, "synchronized": True, "head_sha": "abc", "pushed_sha": "abc"}, review_status="approved", checks_status="passed")
    return result["state"] == "complete", {"state": result["state"]}


def cleanup_manager(main: Path, root: Path, stopped: list):
    return cleanup.CleanupManager(worktree_root=str(root / "workers"), main_checkout=str(main), current_cwd=str(root / "operator"),
                                  process_inspector=lambda: [{"pid": 1, "kind": "nx", "cwd": str(root / "workers" / "worker-1"), "owned": True}, {"pid": 2, "kind": "watchman", "cwd": str(root / "workers" / "worker-1"), "owned": True}],
                                  process_stopper=lambda process: stopped.append(process["pid"]), workspace_closer=lambda _: None)


def scenario_g9():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        main, worktree = disposable_worktree(root)
        stopped = []
        manager = cleanup_manager(main, root, stopped)
        manifest = {"run_id": "g9", "owner_run_id": "g9", "workspace_id": "ws", "worktree": str(worktree), "repo_root": str(main), "state": "complete"}
        result = manager.cleanup(manifest, confirm=True)
        return result["action"] == "cleaned" and stopped == [1] and not worktree.exists(), {"action": result["action"], "stopped": stopped}


def scenario_g10():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        main, worktree = disposable_worktree(root)
        manager = cleanup_manager(main, root, [])
        manifest = {"run_id": "g10", "owner_run_id": "g10", "workspace_id": "ws", "worktree": str(worktree), "repo_root": str(main), "state": "complete"}
        first = manager.cleanup(manifest, confirm=True)
        second = manager.cleanup(manifest, confirm=True)
        protected = manager.plan({**manifest, "state": "complete", "worktree": str(main)})
        return first["action"] == "cleaned" and second["action"] == "noop" and "main_checkout" in protected["issues"], {"first": first["action"], "second": second["action"], "main_action": protected["action"]}


SCENARIOS = [("G1", "Session mismatch is detected", scenario_g1), ("G2", "Setup failure prevents worker launch", scenario_g2),
             ("G3", "Setup queue is visible and bounded", scenario_g3), ("G4", "Stable IDs survive name changes", scenario_g4),
             ("G5", "Message delivery requires Enter and readback", scenario_g5), ("G6", "Dirty or unpushed worktree cannot become complete", scenario_g6),
             ("G7", "CodeRabbit rate limiting becomes blocked_external", scenario_g7), ("G8", "Clean pushed worker passes completion gate", scenario_g8),
             ("G9", "Cleanup stops only owned processes and removes worktree", scenario_g9), ("G10", "Repeated cleanup is safe and protects main checkout", scenario_g10)]


def run_all(selected=None):
    rows = []
    for sid, title, function in SCENARIOS:
        if selected and sid not in selected:
            continue
        started = time.monotonic()
        try:
            passed, evidence = function()
            error = None
        except Exception as exc:  # a golden failure must be visible, never a traceback-only result
            passed, evidence, error = False, {"exception_type": type(exc).__name__}, str(exc)
        rows.append({"id": sid, "title": title, "status": "PASS" if passed else "FAIL", "evidence": evidence,
                     "error": error, "metrics": {"duration_ms": round((time.monotonic() - started) * 1000, 2), "retries": 0}})
    passed = sum(row["status"] == "PASS" for row in rows)
    failed = sum(row["status"] == "FAIL" for row in rows)
    durations = {row["id"]: row["metrics"]["duration_ms"] for row in rows}
    return {"ok": all(row["status"] == "PASS" for row in rows), "scenarios": rows,
            "metrics": {
                "scenario_count": len(rows), "passed": passed, "failed": failed,
                "setup_wait_ms": sum(durations.get(sid, 0) for sid in ("G2", "G3")),
                "launch_time_ms": durations.get("G4", 0),
                "worker_duration_ms": durations.get("G8", 0),
                "turns": 0,
                "retry_count": sum(row["metrics"]["retries"] for row in rows),
                "memory_concurrency_limit_events": 1 if any(row["id"] == "G3" and row["status"] == "PASS" for row in rows) else 0,
                "review_latency_ms": durations.get("G7", 0),
                "cleanup_latency_ms": sum(durations.get(sid, 0) for sid in ("G9", "G10")),
                "cleanup_failures": sum(row["id"] in {"G9", "G10"} and row["status"] == "FAIL" for row in rows),
                "aborted_workers": 0,
                "dirty_completion_attempts": 1 if any(row["id"] == "G6" for row in rows) else 0,
                "external_blockers": sum(row["id"] == "G7" and row["status"] == "PASS" for row in rows),
            }}
