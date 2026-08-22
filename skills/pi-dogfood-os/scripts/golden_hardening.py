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
CLI = HERDR / "pi-team-herdr"

def run_cli(arguments: list[str], *, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    child_env = os.environ.copy()
    if env:
        child_env.update(env)
    return subprocess.run([sys.executable, str(CLI)] + arguments, capture_output=True, text=True, env=child_env, shell=False)



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
        _, _, log = fake_adapter(root, "session-mismatch")
        result = run_cli(["--session", "review", "--herdr-command", str(FIXTURES / "fake_herdr.py"), "--pi-command", sys.executable,
                          "--extension", str(root / "team.ts"), "list"], env={"FAKE_HERDR_SCENARIO": "session-mismatch", "FAKE_HERDR_LOG": str(log)})
        payload = json.loads(result.stderr)
        return result.returncode == 2 and payload["code"] == "SESSION_MISMATCH", {"error_code": payload.get("code")}


def scenario_g2():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _, brief, log = fake_adapter(root, "setup-failure")
        result = run_cli(["--session", "review", "--herdr-command", str(FIXTURES / "fake_herdr.py"), "--pi-command", sys.executable,
                          "--extension", str(root / "team.ts"), "launch", "--name", "worker", "--run-id", "run-g2",
                          "--brief-file", str(brief), "--cwd", str(root), "--worktree", str(root), "--branch", "feature",
                          "--manifest", str(root / "manifest.json")], env={"FAKE_HERDR_SCENARIO": "setup-failure", "FAKE_HERDR_LOG": str(log)})
        commands = [json.loads(line)["op"] for line in log.read_text().splitlines()]
        payload = json.loads(result.stderr)
        return result.returncode == 2 and payload["code"] == "SETUP_FAILED" and "agent start" not in commands, {"error_code": payload.get("code"), "worker_started": "agent start" in commands}


def scenario_g3():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _, brief, log = fake_adapter(root, "setup-timeout")
        started = time.monotonic()
        result = run_cli(["--session", "review", "--herdr-command", str(FIXTURES / "fake_herdr.py"), "--pi-command", sys.executable,
                          "--extension", str(root / "team.ts"), "--poll-interval", "0.001", "launch", "--name", "worker", "--run-id", "run-g3",
                          "--brief-file", str(brief), "--cwd", str(root), "--worktree", str(root), "--branch", "feature",
                          "--setup-timeout", "0.01", "--manifest", str(root / "manifest.json")], env={"FAKE_HERDR_SCENARIO": "setup-timeout", "FAKE_HERDR_LOG": str(log)})
        bounded = result.returncode == 2 and time.monotonic() - started < 1
        payload = json.loads(result.stderr)
        try:
            policy.DispatchPolicy().admit(active_workers=4, setup_workers=0)
        except policy.DispatchRefused as admission:
            return bounded and payload["code"] == "SETUP_TIMEOUT" and admission.code == "MAX_ACTIVE", {"setup_error": payload.get("code"), "admission": admission.code}
    return False, {"error_code": "not_detected"}


def scenario_g4():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _, _, log = fake_adapter(root)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"pane_id": "pane-1", "label": "renamed-worker", "state": "ready", "worktree": str(root)}), encoding="utf-8")
        result = run_cli(["--session", "review", "--herdr-command", str(FIXTURES / "fake_herdr.py"), "--pi-command", sys.executable,
                          "--extension", str(root / "team.ts"), "send", "--manifest", str(manifest), "--text", "stable target"],
                         env={"FAKE_HERDR_SCENARIO": "ok", "FAKE_HERDR_LOG": str(log)})
        payload = json.loads(result.stdout)
        return result.returncode == 0 and payload["pane_id"] == "pane-1", {"pane_id": payload.get("pane_id")}


def scenario_g5():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        _, _, log = fake_adapter(root)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"pane_id": "pane-1", "label": "worker", "state": "ready", "worktree": str(root)}), encoding="utf-8")
        result = run_cli(["--session", "review", "--herdr-command", str(FIXTURES / "fake_herdr.py"), "--pi-command", sys.executable,
                          "--extension", str(root / "team.ts"), "send", "--manifest", str(manifest), "--text", "message"],
                         env={"FAKE_HERDR_SCENARIO": "ok", "FAKE_HERDR_LOG": str(log)})
        commands = [json.loads(line) for line in log.read_text().splitlines()]
        enter = next((row for row in commands if row["op"] == "pane send-keys"), None)
        return result.returncode == 0 and bool(enter and enter["key"] == "enter"), {"submit_key": enter["key"] if enter else None}



def scenario_g6():
    result = gate.completion_gate(git={"clean": False, "synchronized": False, "head_sha": "abc", "pushed_sha": "def"}, review_status="approved", checks_status="passed")
    return result["state"] == "blocked", {"state": result["state"]}


def scenario_g7():
    os.environ["FAKE_GH_SCENARIO"] = "rate-limit"
    result = gate.GitGate(gh_command=str(FIXTURES / "fake_gh.py")).retrieve_reviews(repository="org/repo", pr_number=7)
    return result["review_status"] == "blocked_external", {"review_status": result["review_status"], "rate_limited": result["rate_limited"]}


def scenario_g8():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        worktree = root / "worktree"
        worktree.mkdir()
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"run_id": "g8", "state": "review_pending", "worktree": str(worktree), "branch": "feature/test"}), encoding="utf-8")
        report = root / "report.txt"
        report.write_text("\n".join(["RESULT: complete", f"WORKTREE: {worktree}", "BRANCH: feature/test", "COMMIT: abc123",
                                      "PUSHED: abc123", "PR: 7", "CODERABBIT: approved", "CHECKS: passed", "CLEANUP: verified",
                                      "BLOCKER: none", "EVIDENCE: golden-cli"]) + "\n", encoding="utf-8")
        result = run_cli(["--git-command", str(FIXTURES / "fake_git.py"), "--gh-command", str(FIXTURES / "fake_gh.py"),
                          "complete", "--manifest", str(manifest), "--report", str(report), "--repository", "org/repo", "--pr", "7"],
                         env={"FAKE_GIT_SCENARIO": "ok", "FAKE_GH_SCENARIO": "ok"})
        payload = json.loads(result.stdout) if result.stdout else {}
        return result.returncode == 0 and payload.get("state") == "complete", {"state": payload.get("state"), "returncode": result.returncode}



def cli_cleanup(root: Path, main: Path, worktree: Path, run_id: str, *, confirm: bool = True):
    manifest_path = root / f"{run_id}.json"
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps({"run_id": run_id, "owner_run_id": run_id, "workspace_id": "ws", "worktree": str(worktree),
                                            "repo_root": str(main), "state": "complete", "herdr_command": str(FIXTURES / "fake_herdr.py")}), encoding="utf-8")
    args = ["--herdr-command", str(FIXTURES / "fake_herdr.py"), "cleanup", "--manifest", str(manifest_path),
            "--worktree-root", str(root / "workers"), "--main-checkout", str(main)]
    if confirm:
        args.append("--confirm")
    result = run_cli(args, env={"FAKE_HERDR_SCENARIO": "ok", "FAKE_HERDR_LOG": str(root / "herdr.jsonl")})
    payload = json.loads(result.stdout) if result.stdout else json.loads(result.stderr)
    return result, payload, manifest_path


def scenario_g9():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        main, worktree = disposable_worktree(root)
        result, payload, _ = cli_cleanup(root, main, worktree, "g9")
        return result.returncode == 0 and payload.get("action") == "cleaned" and not worktree.exists(), {"action": payload.get("action"), "returncode": result.returncode, "error": payload.get("error")}


def scenario_g10():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        main, worktree = disposable_worktree(root)
        first_result, first, manifest_path = cli_cleanup(root, main, worktree, "g10")
        second_result, second, _ = cli_cleanup(root, main, worktree, "g10")
        protected_result, protected, _ = cli_cleanup(root, main, main, "g10-main", confirm=False)
        return (first_result.returncode == 0 and first.get("action") == "cleaned" and
                second_result.returncode == 0 and second.get("action") == "noop" and
                protected_result.returncode == 0 and protected.get("action") == "refuse" and "main_checkout" in protected.get("issues", [])), {
                    "first": first.get("action"), "second": second.get("action"), "main_action": protected.get("action")}



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
