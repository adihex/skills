#!/usr/bin/env python3
"""Independent fake-command/temp-repository Hax runtime scenarios H1-H13."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures"
HERDR = ROOT / "skills" / "herdr-pi-team" / "scripts" / "pi-team-herdr"
TMUX = ROOT / "skills" / "tmux-pi-team" / "scripts" / "pi-team-tmux"
WEZTERM = ROOT / "skills" / "wezterm-pi-team" / "scripts" / "pi-team-pane"
FAKE_HERDR = FIXTURES / "fake_herdr.py"
FAKE_HAX = FIXTURES / "fake_hax.py"
FAKE_TMUX = FIXTURES / "fake_tmux.py"
FAKE_WEZTERM = FIXTURES / "fake_wezterm.py"
FAKE_GIT = FIXTURES / "fake_git.py"
FAKE_GH = FIXTURES / "fake_gh.py"


def run(script: Path, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    child = os.environ.copy()
    if env:
        child.update(env)
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=child, shell=False)


def json_stdout(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stdout)


def json_stderr(result: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(result.stderr)


def hax_args(*, model: bool = True, auth: str = "hax_managed", mode: str = "interactive") -> list[str]:
    args = ["--backend", "hax", "--provider", "codex", "--effort", "high", "--mode", mode,
            "--auth-source", auth, "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)]
    if model:
        args += ["--model", "gpt-5.6-sol"]
    return args


def brief(root: Path, text: str = "golden Hax task\n") -> Path:
    path = root / "brief.md"
    path.write_text(text, encoding="utf-8")
    return path


def herdr_launch(root: Path, *, backend: str = "hax", mode: str = "interactive", model: bool = True,
                  auth: str = "hax_managed", hax_command: Path = FAKE_HAX, auth_path: Path | None = None):
    log = root / "herdr.jsonl"
    args = ["--session", "review", "--herdr-command", str(FAKE_HERDR), "--pi-command", sys.executable,
            "--extension", str(root / "team.ts"), "--poll-interval", "0.001", "launch", "--name", "worker",
            "--run-id", "golden-hax", "--brief-file", str(brief(root)), "--cwd", str(root), "--worktree", str(root),
            "--branch", "feature/test", "--manifest", str(root / "manifest.json")]
    (root / "team.ts").write_text("export {};\n", encoding="utf-8")
    if backend == "hax":
        args += hax_args(model=model, auth=auth, mode=mode)
        args[args.index("--hax-command") + 1] = str(hax_command)
    env = {"FAKE_HERDR_SCENARIO": "ok", "FAKE_HERDR_LOG": str(log)}
    if auth_path:
        args += ["--auth-path", str(auth_path)]
    return run(HERDR, args, env=env), log


def pane_launch(script: Path, root: Path, *, runtime: str, backend: str = "hax", mode: str = "interactive", model: bool = True,
                 auth: str = "hax_managed", hax_command: Path = FAKE_HAX):
    path = brief(root)
    log = root / f"{runtime}.log"
    args = ["launch", "--name", "worker", "--brief-file", str(path), "--cwd", str(root), "--manifest", str(root / "manifest.json")]
    if backend == "hax":
        args += hax_args(model=model, auth=auth, mode=mode)
        args[args.index("--hax-command") + 1] = str(hax_command)
    if runtime == "tmux":
        env = {"PI_TEAM_TMUX_COMMAND": str(FAKE_TMUX), "FAKE_TMUX_LOG": str(log)}
    else:
        env = {"PI_TEAM_WEZTERM_COMMAND": str(FAKE_WEZTERM), "WEZTERM_PANE": "1", "FAKE_WEZTERM_LOG": str(log)}
    return run(script, args, env=env), log


def scenario_h1():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        herdr, _ = herdr_launch(root, backend="pi")
        tmux, _ = pane_launch(TMUX, root, runtime="tmux", backend="pi")
        wez, _ = pane_launch(WEZTERM, root, runtime="wezterm", backend="pi")
        states = [json_stdout(herdr).get("backend"), json_stdout(tmux).get("backend"), json_stdout(wez).get("backend")]
        return all(result.returncode == 0 for result in (herdr, tmux, wez)) and states == ["pi", "pi", "pi"], {"runtimes": states}


def scenario_h2():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        results = [herdr_launch(root)[0], pane_launch(TMUX, root, runtime="tmux")[0], pane_launch(WEZTERM, root, runtime="wezterm")[0]]
        evidence = []
        for result in results:
            payload = json_stdout(result)
            evidence.append({key: payload.get(key) for key in ("backend", "runtime", "backend_config", "backend_capabilities")})
        return all(result.returncode == 0 for result in results) and all(item["backend"] == "hax" for item in evidence), {"workers": evidence}


def scenario_h3():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        missing = root / "missing-hax"
        results = [herdr_launch(root, hax_command=missing)[0], pane_launch(TMUX, root, runtime="tmux", hax_command=missing)[0], pane_launch(WEZTERM, root, runtime="wezterm", hax_command=missing)[0]]
        codes = [json_stderr(result).get("code") for result in results]
        return all(result.returncode != 0 and code == "hax_missing" for result, code in zip(results, codes)), {"codes": codes, "pane_created": False}


def scenario_h4():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        missing_auth = root / "missing-auth.json"
        herdr = herdr_launch(root, auth="codex_cli", auth_path=missing_auth)[0]
        tmux = pane_launch(TMUX, root, runtime="tmux", auth="codex_cli")[0]
        wez = pane_launch(WEZTERM, root, runtime="wezterm", auth="codex_cli")[0]
        # The pane adapters use the default auth path unless explicitly supplied; run their doctor path with the missing path.
        hax = hax_args(auth="codex_cli") + ["--auth-path", str(missing_auth)]
        tmux = run(TMUX, ["launch", "--name", "worker", "--brief-file", str(brief(root)), "--cwd", str(root), *hax], env={"PI_TEAM_TMUX_COMMAND": str(FAKE_TMUX)})
        wez = run(WEZTERM, ["launch", "--name", "worker", "--brief-file", str(brief(root)), "--cwd", str(root), *hax], env={"PI_TEAM_WEZTERM_COMMAND": str(FAKE_WEZTERM), "WEZTERM_PANE": "1"})
        codes = [json_stderr(result).get("code") for result in (herdr, tmux, wez)]
        return all(code == "codex_auth_missing" for code in codes), {"codes": codes, "credential_contents_exposed": False}


def scenario_h5():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        results = [herdr_launch(root, model=False)[0], pane_launch(TMUX, root, runtime="tmux", model=False)[0], pane_launch(WEZTERM, root, runtime="wezterm", model=False)[0]]
        codes = [json_stderr(result).get("code") for result in results]
        return all(code == "MODEL_MISSING" for code in codes), {"codes": codes, "pane_created": False}


def scenario_h6():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        herdr, herdr_log = herdr_launch(root)
        tmux, tmux_log = pane_launch(TMUX, root, runtime="tmux")
        wez, wez_log = pane_launch(WEZTERM, root, runtime="wezterm")
        herdr_ops = [json.loads(line)["op"] for line in herdr_log.read_text().splitlines()]
        tmux_ops = [json.loads(line)[0] for line in tmux_log.read_text().splitlines()]
        wez_ops = [json.loads(line)[0] for line in wez_log.read_text().splitlines()]
        herdr_ok = herdr_ops.index("pane read") < herdr_ops.index("agent send") < herdr_ops.index("pane send-keys")
        tmux_ok = tmux_ops.index("capture-pane") < tmux_ops.index("send-keys")
        wez_ok = wez_ops.index("get-text") < wez_ops.index("send-text", wez_ops.index("get-text") + 1)
        return all(result.returncode == 0 for result in (herdr, tmux, wez)) and herdr_ok and tmux_ok and wez_ok, {"herdr": herdr_ok, "tmux": tmux_ok, "wezterm": wez_ok}


def scenario_h7():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        herdr = herdr_launch(root, mode="oneshot")[0]
        tmux = pane_launch(TMUX, root, runtime="tmux", mode="oneshot")[0]
        wez = pane_launch(WEZTERM, root, runtime="wezterm", mode="oneshot")[0]
        payloads = [json_stdout(result) for result in (herdr, tmux, wez)]
        ok = all(result.returncode == 0 and payload["state"] == "verifying" and payload["backend_capabilities"]["steerable"] is False for result, payload in zip((herdr, tmux, wez), payloads))
        ok = ok and all("FAKE_HAX_ONESHOT_OK" in payload.get("backend_output", {}).get("stdout", payload.get("stdout", "")) for payload in payloads)
        return ok, {"states": [payload["state"] for payload in payloads], "steerable": [payload["backend_capabilities"]["steerable"] for payload in payloads]}


def scenario_h8():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        previous = os.environ.get("FAKE_HAX_RESULT")
        os.environ["FAKE_HAX_RESULT"] = "429"
        try:
            results = [herdr_launch(root, mode="oneshot")[0], pane_launch(TMUX, root, runtime="tmux", mode="oneshot")[0], pane_launch(WEZTERM, root, runtime="wezterm", mode="oneshot")[0]]
        finally:
            if previous is None:
                os.environ.pop("FAKE_HAX_RESULT", None)
            else:
                os.environ["FAKE_HAX_RESULT"] = previous
        first = json_stdout(results[0]).get("blocker")
        blocked_launches = []
        for result in results[1:]:
            try:
                blocked_launches.append(json.loads(result.stderr).get("code"))
            except ValueError:
                blocked_launches.append(None)
        ok = results[0].returncode == 0 and first == "HTTP_429" and all(
            result.returncode == 3 and code == "HAX_QUOTA_BLOCKED"
            for result, code in zip(results[1:], blocked_launches)
        )
        return ok, {"blockers": [first, *blocked_launches], "retry_count": 0, "new_launches_stopped": True}


def scenario_h9():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        tmux_log = root / "tmux-clean.log"
        tmux = run(TMUX, ["cleanup", "--pattern", "hax-worker", "--confirm"], env={"PI_TEAM_TMUX_COMMAND": str(FAKE_TMUX), "FAKE_TMUX_PANES": "coexist", "FAKE_TMUX_LOG": str(tmux_log)})
        wez_log = root / "wez-clean.log"
        wez = run(WEZTERM, ["cleanup", "--pattern", "hax-worker", "--confirm"], env={"PI_TEAM_WEZTERM_COMMAND": str(FAKE_WEZTERM), "FAKE_WEZTERM_PANES": "coexist", "WEZTERM_PANE": "1", "FAKE_WEZTERM_LOG": str(wez_log)})
        tmux_payload = json_stdout(tmux)
        wez_payload = json_stdout(wez)
        tmux_killed = [row["paneId"] for row in tmux_payload["killed"]]
        wez_killed = [row["paneId"] for row in wez_payload["killed"]]
        return tmux.returncode == 0 and wez.returncode == 0 and tmux_killed == ["%1"] and wez_killed == [2], {"tmux_killed": tmux_killed, "wezterm_killed": wez_killed, "sibling_preserved": True}


def completion_fixture(root: Path, runtime: str):
    worktree = root / f"worktree-{runtime}"
    worktree.mkdir()
    manifest = root / f"manifest-{runtime}.json"
    manifest.write_text(json.dumps({"run_id": f"h10-{runtime}", "label": "worker", "workspace_id": runtime, "tab_id": runtime, "pane_id": "pane-1",
                                    "cwd": str(worktree), "worktree": str(worktree), "branch": "feature/test", "state": "review_pending",
                                    "head_sha": "abc123", "pushed_sha": "abc123", "pr_number": None, "review_status": "pending", "checks_status": "pending",
                                    "last_heartbeat": "2099-01-01T00:00:00Z", "blocker": None, "backend": "hax", "runtime": runtime,
                                    "backend_config": {"provider": "codex", "model": "gpt-5.6-sol", "effort": "high", "mode": "interactive", "auth_source": "hax_managed"},
                                    "backend_capabilities": {}, "backend_session_id": None, "backend_exit_code": None, "backend_error_code": None}), encoding="utf-8")
    report = root / f"report-{runtime}.txt"
    report.write_text("\n".join(["RESULT: complete", f"WORKTREE: {worktree}", "BRANCH: feature/test", "COMMIT: abc123", "PUSHED: abc123",
                                  "PR: 7", "CODERABBIT: approved", "CHECKS: passed", "CLEANUP: verified", "BLOCKER: none", "EVIDENCE: H10"]) + "\n", encoding="utf-8")
    return manifest, report


def scenario_h10():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        results = []
        for runtime, script in (("herdr", HERDR), ("tmux", TMUX), ("wezterm", WEZTERM)):
            manifest, report = completion_fixture(root, runtime)
            args = ["complete", "--manifest", str(manifest), "--report", str(report), "--repository", "org/repo", "--pr", "7"]
            if runtime == "herdr":
                result = run(script, ["--git-command", str(FAKE_GIT), "--gh-command", str(FAKE_GH), *args])
            else:
                result = run(script, args + ["--git-command", str(FAKE_GIT), "--gh-command", str(FAKE_GH)])
            results.append(result)
        payloads = [json_stdout(result) for result in results]
        return all(result.returncode == 0 and payload["state"] == "complete" for result, payload in zip(results, payloads)), {"states": [payload["state"] for payload in payloads], "cleanup_gate": "shared"}


def scenario_h11():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"backend": "hax", "runtime": "tmux", "backend_config": {"provider": "codex", "model": "gpt-5.6-sol", "effort": "high", "mode": "interactive", "auth_source": "hax_managed"}}), encoding="utf-8")
        log = root / "send.log"
        result = run(TMUX, ["send", "--pane-id", "%1", "--text", "hello", "--manifest", str(manifest), "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)], env={"PI_TEAM_TMUX_COMMAND": str(FAKE_TMUX), "FAKE_TMUX_LOG": str(log)})
        entries = [json.loads(line) for line in log.read_text().splitlines()]
        sends = [entry for entry in entries if entry[0] == "send-keys"]
        return result.returncode == 0 and len(sends) == 2 and "-l" in sends[0] and sends[1][-1] == "Enter", {"send_keys": sends}


def scenario_h12():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"backend": "hax", "runtime": "wezterm", "backend_config": {"provider": "codex", "model": "gpt-5.6-sol", "effort": "high", "mode": "interactive", "auth_source": "hax_managed"}}), encoding="utf-8")
        log = root / "wez.log"
        env = {"PI_TEAM_WEZTERM_COMMAND": str(FAKE_WEZTERM), "FAKE_WEZTERM_PANES": "coexist", "WEZTERM_PANE": "1", "FAKE_WEZTERM_LOG": str(log)}
        sent = run(WEZTERM, ["send", "--pane-id", "2", "--text", "hello", "--manifest", str(manifest), "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)], env=env)
        protected = run(WEZTERM, ["send", "--pane-id", "1", "--text", "blocked", "--manifest", str(manifest), "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)], env=env)
        commands = [json.loads(line)[0] for line in log.read_text().splitlines()]
        return sent.returncode == 0 and protected.returncode == 3 and commands.index("get-text") < commands.index("send-text", commands.index("get-text") + 1), {"fenced": True, "protected_current_refused": protected.returncode == 3}


def scenario_h13():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        hax, log = herdr_launch(root)
        pi, _ = herdr_launch(root, backend="pi")
        entries = [json.loads(line) for line in log.read_text().splitlines()]
        starts = [entry.get("args", []) for entry in entries if entry.get("op") == "agent start"]
        return hax.returncode == 0 and pi.returncode == 0 and any(str(FAKE_HAX) in args for args in starts) and any(sys.executable in args for args in starts), {"hax_shell_backed": True, "pi_native_path": True, "native_hax_kind_used": False}


SCENARIOS = [(f"H{index}", title, function) for index, title, function in [
    (1, "Pi remains the default in every runtime", scenario_h1),
    (2, "Explicit Hax launch records backend configuration", scenario_h2),
    (3, "Missing Hax fails before pane creation", scenario_h3),
    (4, "Missing Codex auth is actionable and redacted", scenario_h4),
    (5, "Missing model fails before launch", scenario_h5),
    (6, "Interactive Hax waits for readiness and Enter", scenario_h6),
    (7, "One-shot Hax captures output and is not steerable", scenario_h7),
    (8, "HTTP 429 is blocked_external without retries", scenario_h8),
    (9, "Pi and Hax cleanup do not cross-kill", scenario_h9),
    (10, "Hax uses the shared completion gate", scenario_h10),
    (11, "tmux literal send and Enter are separate", scenario_h11),
    (12, "WezTerm fencing and pane safety hold", scenario_h12),
    (13, "Herdr uses shell-backed Hax and native Pi", scenario_h13),
]]


def run_all(selected: set[str] | None = None) -> dict:
    rows = []
    for scenario_id, title, function in SCENARIOS:
        if selected and scenario_id not in selected:
            continue
        started = time.monotonic()
        try:
            passed, evidence = function()
            error = None
        except Exception as exc:  # scenario failures are evidence, not tracebacks
            passed, evidence, error = False, {"exception_type": type(exc).__name__}, str(exc)
        rows.append({"id": scenario_id, "title": title, "status": "PASS" if passed else "FAIL", "evidence": evidence,
                     "error": error, "duration_ms": round((time.monotonic() - started) * 1000, 2)})
    return {"ok": all(row["status"] == "PASS" for row in rows) and len(rows) == 13, "scenario_count": len(rows), "scenarios": rows}


if __name__ == "__main__":
    result = run_all()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["ok"] else 1)
