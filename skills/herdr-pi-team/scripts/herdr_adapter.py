#!/usr/bin/env python3
"""Reliable Herdr adapter with stable IDs and evidence-producing operations."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import importlib.util
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SHARED_BACKEND_PATH = Path(__file__).resolve().parents[3] / "scripts" / "hax_backend.py"
SHARED_SPEC = importlib.util.spec_from_file_location("shared_hax_backend", SHARED_BACKEND_PATH)
if SHARED_SPEC is None or SHARED_SPEC.loader is None:
    raise ImportError(f"shared Hax backend is unavailable: {SHARED_BACKEND_PATH}")
hax_backend = importlib.util.module_from_spec(SHARED_SPEC)
sys.modules[SHARED_SPEC.name] = hax_backend
SHARED_SPEC.loader.exec_module(hax_backend)

STATES = {
    "created", "setup_pending", "setup_failed", "ready", "working", "verifying",
    "pushed", "review_pending", "blocked_external", "blocked", "complete",
    "cleanup_pending", "cleaned", "failed", "aborted",
}


class AdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


class HerdrAdapter:
    def __init__(self, *, session: str | None = None, herdr_command: str = "herdr",
                 pi_command: str = "pi", extension: str | None = None,
                 timeout: float = 20.0, poll_interval: float = 0.2,
                 backend_config: Mapping[str, Any] | None = None,
                 hax_command: str = "hax", codex_command: str = "codex",
                 auth_path: str | None = None):
        self.session = session
        self.herdr_command = herdr_command
        self.pi_command = pi_command
        self.extension = os.path.expanduser(extension or "~/.pi/agent/extensions/team.ts")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.config = hax_backend.BackendConfig.from_mapping(backend_config)
        self.hax = hax_backend.HaxBackend(hax_command=hax_command, codex_command=codex_command, auth_path=auth_path)
        self._resolved_session: str | None = None
    def _command(self) -> str:
        command = self.herdr_command
        if os.path.isabs(command):
            if not os.access(command, os.X_OK):
                raise AdapterError("MUX_UNAVAILABLE", "herdr command is not executable", details={"command": command})
            return command
        found = shutil.which(command)
        if not found:
            raise AdapterError("MUX_UNAVAILABLE", "herdr command not found", details={"command": command})
        return found

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        command = [self._command()]
        if self.session:
            command += ["--session", self.session]
        command += args
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=self.timeout, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise AdapterError("MUX_TIMEOUT", "herdr command timed out", details={"args": args}) from exc
        except OSError as exc:
            raise AdapterError("MUX_UNAVAILABLE", "herdr command could not start", details={"error": str(exc)}) from exc

    @staticmethod
    def _json(process: subprocess.CompletedProcess[str], operation: str) -> dict:
        if process.returncode:
            raise AdapterError("HERDR_COMMAND_FAILED", f"{operation} failed", details={
                "operation": operation,
                "stderr": process.stderr.strip()[:500],
                "exit_code": process.returncode,
            })
        try:
            value = json.loads(process.stdout)
        except (TypeError, ValueError) as exc:
            raise AdapterError("INVALID_RESPONSE", f"{operation} returned invalid JSON") from exc
        if isinstance(value, dict) and isinstance(value.get("result"), dict):
            return value["result"]
        if isinstance(value, dict):
            return value
        raise AdapterError("INVALID_RESPONSE", f"{operation} returned a non-object")

    def preflight(self) -> dict:
        self._command()
        if self.config.backend == "hax":
            try:
                hax_result = self.hax.preflight(self.config)
            except (hax_backend.HaxConfigError, hax_backend.HaxPreflightError) as exc:
                raise AdapterError(getattr(exc, "code", "HAX_PREFLIGHT_FAILED"), str(exc), details=getattr(exc, "details", {})) from exc
            return {"backend": "hax", "hax": hax_result, **self.resolve_session()}
        if not shutil.which(self.pi_command) and not os.path.isabs(self.pi_command):
            raise AdapterError("PI_UNAVAILABLE", "pi command not found", details={"command": self.pi_command})
        if os.path.isabs(self.pi_command) and not os.access(self.pi_command, os.X_OK):
            raise AdapterError("PI_UNAVAILABLE", "pi command is not executable", details={"command": self.pi_command})
        if not os.path.isfile(self.extension):
            raise AdapterError("PI_INTEGRATION_UNAVAILABLE", "Pi integration extension is missing", details={"extension": self.extension})
        return self.resolve_session()

    def resolve_session(self) -> dict:
        result = self._json(self._run(["pane", "list"]), "pane list")
        actual = result.get("session") or result.get("session_id")
        if self.session and actual and actual != self.session:
            raise AdapterError("SESSION_MISMATCH", "Herdr returned a different session", details={"expected": self.session, "actual": actual})
        self._resolved_session = actual or self.session
        if self.session and self._resolved_session != self.session:
            raise AdapterError("SESSION_UNAVAILABLE", "selected Herdr session was not confirmed", details={"session": self.session})
        return result

    def _ensure_preflight(self) -> dict:
        return self.preflight()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _pane_rows(result: dict) -> list[dict]:
        panes = result.get("panes", [])
        return panes if isinstance(panes, list) else []
    def _wait_hax_ready(self, pane_id: str) -> dict:
        deadline = time.monotonic() + self.timeout
        last_text = ""
        while time.monotonic() < deadline:
            readback = self._json(self._run(["pane", "read", pane_id, "--lines", "20"]), "pane read")
            last_text = str(readback.get("text") or readback.get("output") or "")
            lowered = last_text.lower()
            if any(marker in lowered for marker in ("ready", "ack", "❯", ">")):
                return {"ready": True, "marker": "ready" if "ready" in lowered else "prompt"}
            time.sleep(self.poll_interval)
        raise AdapterError("HAX_READINESS_TIMEOUT", "Hax did not expose a readiness marker", details={"pane_id": pane_id, "last_text_sha256": hashlib.sha256(last_text.encode()).hexdigest(), "last_text_chars": len(last_text)})

    def launch(self, *, run_id: str, label: str, cwd: str, worktree: str, branch: str,
               brief_file: str, workspace_id: str | None = None, model: str = "opencode/deepseek-v4-flash-free",
               thinking: str | None = None, setup_timeout: float = 30.0) -> dict:
        self._ensure_preflight()
        if not os.path.isfile(brief_file):
            raise AdapterError("BRIEF_NOT_READABLE", "worker brief is not readable")
        brief_text = Path(brief_file).read_text(encoding="utf-8")
        started = time.monotonic()
        if self.config.backend == "hax" and self.config.mode == "oneshot":
            result = self.hax.run_oneshot(self.config, prompt=brief_text, cwd=cwd, timeout=self.timeout)
            fields = self.config.manifest_fields(runtime="herdr")
            return {
                "run_id": run_id, "label": label, "workspace_id": "direct-oneshot", "tab_id": "direct-oneshot",
                "pane_id": "direct-oneshot", "cwd": os.path.abspath(cwd), "worktree": os.path.abspath(worktree),
                "branch": branch, "upstream": None, "state": result["state"], "head_sha": None, "pushed_sha": None,
                "pr_number": None, "review_status": "pending", "checks_status": "pending", "last_heartbeat": self._now(),
                "blocker": result.get("code") if result["state"] != "verifying" else None,
                "setup_duration_seconds": round(time.monotonic() - started, 3), "setup_status": "direct",
                **fields,
                "_backend_output": {"stdout": result.get("stdout", ""), "stderr": result.get("stderr", ""), "command": result.get("command", [])},
                "backend_exit_code": result.get("exit_code"), "backend_error_code": result.get("code"),
            }
        if workspace_id:
            workspace = {"workspace_id": workspace_id}
        else:
            workspace = self._json(self._run(["workspace", "create", "--cwd", os.path.abspath(cwd), "--label", label]), "workspace create")
        workspace_id = str(workspace.get("workspace_id") or workspace.get("id") or "")
        if not workspace_id:
            raise AdapterError("INVALID_RESPONSE", "workspace create returned no workspace ID")
        setup = self._json(self._run(["workspace", "setup", workspace_id]), "workspace setup")
        deadline = time.monotonic() + setup_timeout
        while setup.get("status") in {"queued", "pending", "working", "running"}:
            if time.monotonic() >= deadline:
                raise AdapterError("SETUP_TIMEOUT", "workspace setup did not become ready", details={"workspace_id": workspace_id, "setup": setup, "setup_duration_seconds": round(time.monotonic() - started, 3)})
            time.sleep(self.poll_interval)
            setup = self._json(self._run(["workspace", "status", workspace_id]), "workspace status")
        if setup.get("status") not in {"ready", "complete", "completed", "ok"}:
            raise AdapterError("SETUP_FAILED", "workspace setup failed", details={"workspace_id": workspace_id, "setup": setup, "setup_duration_seconds": round(time.monotonic() - started, 3)})
        if self.config.backend == "hax":
            worker_command = self.hax.build_command(self.config)
        else:
            worker_command = [self.pi_command, "-e", self.extension, "--model", model]
            if thinking:
                worker_command += ["--thinking", thinking]
            worker_command += ["--name", label, "@" + os.path.abspath(brief_file)]
        command = ["agent", "start", label, "--cwd", os.path.abspath(cwd), "--workspace", workspace_id, "--", *worker_command]
        worker = self._json(self._run(command), "agent start")
        manifest = {
            "run_id": run_id, "label": label, "workspace_id": workspace_id,
            "tab_id": str(worker.get("tab_id") or ""), "pane_id": str(worker.get("pane_id") or worker.get("id") or ""),
            "cwd": os.path.abspath(cwd), "worktree": os.path.abspath(worktree), "branch": branch,
            "upstream": None, "state": "ready", "head_sha": None, "pushed_sha": None,
            "pr_number": None, "review_status": "pending", "checks_status": "pending",
            "last_heartbeat": self._now(), "blocker": None,
            "setup_duration_seconds": round(time.monotonic() - started, 3), "setup_status": setup.get("status"),
            **self.config.manifest_fields(runtime="herdr"),
        }
        if not manifest["pane_id"]:
            raise AdapterError("INVALID_RESPONSE", "agent start returned no pane ID")
        if self.config.backend == "hax":
            readiness = self._wait_hax_ready(manifest["pane_id"])
            submission = self.send(manifest, brief_text, acknowledge="ACKNOWLEDGED")
            manifest.update({"state": "working", "hax_readiness": readiness, "hax_submission": submission})
        return manifest

    def send(self, manifest: dict, text: str, *, acknowledge: str | None = None) -> dict:
        self._ensure_preflight()
        pane_id = str(manifest.get("pane_id") or "")
        if not pane_id:
            raise AdapterError("TARGET_INVALID", "manifest has no pane_id")
        panes = self._pane_rows(self.resolve_session())
        if not any(str(p.get("pane_id") or p.get("id")) == pane_id for p in panes):
            raise AdapterError("TARGET_NOT_FOUND", "manifest pane_id is not present in the selected session", details={"pane_id": pane_id})
        sent = self._run(["agent", "send", pane_id, text])
        if sent.returncode:
            raise AdapterError("SEND_FAILED", "Herdr rejected the message", details={"pane_id": pane_id})
        submitted = self._run(["pane", "send-keys", pane_id, "enter"])
        if submitted.returncode:
            raise AdapterError("SUBMIT_FAILED", "message was sent but Enter submission failed", details={"pane_id": pane_id})
        readback = self._json(self._run(["pane", "read", pane_id, "--lines", "20"]), "pane read")
        visible = str(readback.get("text") or readback.get("output") or "")
        expected = acknowledge or "ACK"
        ack = expected in visible or bool(readback.get("acknowledged"))
        if not ack:
            raise AdapterError("ACK_NOT_CONFIRMED", "message submission was not acknowledged by pane readback", details={"pane_id": pane_id})
        return {"pane_id": pane_id, "sent": True, "submitted": True, "acknowledged": True,
                "chars": len(text), "readback_sha256": hashlib.sha256(visible.encode()).hexdigest()}

    def status(self, manifest: dict) -> dict:
        native = self._ensure_preflight()
        pane_id = str(manifest.get("pane_id") or "")
        pane = next((p for p in self._pane_rows(native) if str(p.get("pane_id") or p.get("id")) == pane_id), None)
        worktree = Path(str(manifest.get("worktree") or ""))
        git = {"exists": worktree.is_dir(), "dirty": None, "head_sha": None, "upstream_sha": None, "synchronized": None}
        if git["exists"]:
            git["dirty"] = bool(self._git(["status", "--porcelain"], worktree).stdout.strip())
            head = self._git(["rev-parse", "HEAD"], worktree)
            git["head_sha"] = head.stdout.strip() if head.returncode == 0 else None
            upstream = self._git(["rev-parse", "@{u}"], worktree)
            git["upstream_sha"] = upstream.stdout.strip() if upstream.returncode == 0 else None
            git["synchronized"] = bool(git["upstream_sha"] and git["head_sha"] == git["upstream_sha"])
        state = pane.get("agent_state") or pane.get("agent_status") or pane.get("state") if pane else "missing"
        return {"backend": manifest.get("backend", self.config.backend), "runtime": manifest.get("runtime", "herdr"),
                "backend_capabilities": manifest.get("backend_capabilities", self.hax.capabilities(self.config, runtime="herdr") if self.config.backend == "hax" else hax_backend.capabilities_for("pi", "herdr")),
                "native_state": state, "pane": pane, "manifest_state": manifest.get("state"),
                "state_mismatch": pane is not None and state != manifest.get("state"),
                "last_heartbeat": manifest.get("last_heartbeat"), "git": git,
                "review_status": manifest.get("review_status"), "checks_status": manifest.get("checks_status")}

    @staticmethod
    def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", "-C", str(cwd)] + args, capture_output=True, text=True, timeout=20, shell=False)

    def reconcile(self, manifest: dict, *, heartbeat_timeout: float = 300.0, report_path: str | None = None) -> dict:
        snapshot = self.status(manifest)
        issues = []
        if snapshot["pane"] is None:
            issues.append("missing_pane")
        if not snapshot["git"]["exists"]:
            issues.append("missing_worktree")
        heartbeat = manifest.get("last_heartbeat")
        if heartbeat:
            try:
                stamp = datetime.fromisoformat(str(heartbeat).replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - stamp).total_seconds() > heartbeat_timeout:
                    issues.append("stale_heartbeat")
            except ValueError:
                issues.append("invalid_heartbeat")
        if snapshot["state_mismatch"]:
            issues.append("native_manifest_state_mismatch")
        if snapshot["git"].get("dirty"):
            issues.append("dirty_worktree")
        if snapshot["git"].get("synchronized") is False:
            issues.append("unpushed_commits")
        if report_path and not os.path.isfile(report_path):
            issues.append("missing_final_report")
        return {"run_id": manifest.get("run_id"), "pane_id": manifest.get("pane_id"), "issues": issues,
                "ok": not issues, "snapshot": snapshot}
