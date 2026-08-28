"""Stable, safe adapter for Herdr's current Pi-agent lifecycle API.

All native calls live here.  Calls always use argv vectors (`shell=False`) and
this module never logs prompt content.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


class ModernAdapterError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None, safety: bool = False):
        super().__init__(message)
        self.code, self.details, self.safety = code, details or {}, safety


class ModernHerdrAdapter:
    """Adapter boundary for Herdr 0.8's agent prompt/start API."""
    REQUIRED = ("agent list", "agent get", "agent start", "agent prompt", "agent read", "workspace create", "pane list")

    def __init__(self, command: str, session: str | None, timeout: float = 30.0):
        self.command, self.session, self.timeout = command, session, timeout

    def _argv(self, args: list[str]) -> list[str]:
        binary = self.command if os.path.isabs(self.command) else shutil.which(self.command)
        if not binary:
            raise ModernAdapterError("MUX_UNAVAILABLE", "herdr command not found")
        return [binary, *( ["--session", self.session] if self.session else []), *args]

    def _run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(self._argv(args), capture_output=True, text=True, encoding="utf-8", timeout=self.timeout, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise ModernAdapterError("MUX_TIMEOUT", "Herdr command timed out", details={"operation": " ".join(args[:2])}) from exc

    def _json(self, args: list[str], operation: str) -> dict[str, Any]:
        result = self._run(args)
        if result.returncode:
            raise ModernAdapterError("HERDR_COMMAND_FAILED", f"{operation} failed", details={"operation": operation, "exitCode": result.returncode, "nativeError": result.stderr.strip()[:500]})
        try:
            payload = json.loads(result.stdout)
        except ValueError as exc:
            raise ModernAdapterError("INVALID_RESPONSE", f"{operation} returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ModernAdapterError("INVALID_RESPONSE", f"{operation} returned a non-object")
        if "error" in payload:
            raise ModernAdapterError("HERDR_COMMAND_FAILED", f"{operation} failed", details={"operation": operation, "nativeError": payload.get("error", {}).get("code", "unknown")})
        value = payload.get("result", payload)
        if not isinstance(value, dict):
            raise ModernAdapterError("INVALID_RESPONSE", f"{operation} returned a non-object")
        return value

    @staticmethod
    def _agents(value: dict) -> list[dict]:
        rows = value.get("agents", value.get("panes", []))
        return rows if isinstance(rows, list) else []

    def version(self, program: str = "herdr") -> str | None:
        result = self._run(["--version"])
        return result.stdout.strip() if result.returncode == 0 else None

    def schema(self) -> dict:
        return self._json(["api", "schema", "--json"], "api schema")

    def capabilities(self) -> dict:
        schema = self.schema()
        statuses: list[str] = []
        try:
            statuses = schema["schemas"]["success_response"]["$defs"]["AgentStatus"]["enum"]
        except (KeyError, TypeError):
            pass
        # api schema is the machine-readable contract; command help verifies CLI surface.
        commands = {}
        for operation in self.REQUIRED:
            args = operation.split() + ["--help"]
            commands[operation] = self._run(args).returncode == 0
        return {"schemaVersion": schema.get("schema_version"), "protocol": schema.get("protocol"), "commands": commands, "states": statuses}

    def list_workers(self) -> list[dict]:
        return self._agents(self._json(["agent", "list"], "agent list"))

    @staticmethod
    def _validate_pi_worker(worker: dict, name: str) -> dict:
        if str(worker.get("agent") or worker.get("kind") or "").lower() != "pi":
            raise ModernAdapterError("NOT_PI_AGENT", "target is not a Pi agent", details={"name": name}, safety=True)
        return worker

    def get_worker(self, name: str) -> dict:
        current = self._json(["agent", "get", name], "agent get")
        current = current["agent"] if isinstance(current.get("agent"), dict) else current
        return self._validate_pi_worker(current, name)

    def resolve_worker(self, name: str) -> dict:
        rows = [row for row in self.list_workers() if str(row.get("name") or row.get("agent") or "") == name]
        if len(rows) != 1:
            raise ModernAdapterError("WORKER_NAME_AMBIGUOUS", "worker name must resolve to exactly one agent", details={"name": name, "matches": len(rows)}, safety=True)
        self._validate_pi_worker(rows[0], name)
        # Get refreshes the registry result and proves target addressing works.
        return self.get_worker(name)

    def observe_registered_workers(self, registrations: list[dict]) -> list[tuple[dict, dict]]:
        """Resolve one registry snapshot against mailbox-owned stable identities."""
        rows = self.list_workers()
        observed = []
        for registration in registrations:
            name = str(registration.get("name") or "")
            matches = [row for row in rows if str(row.get("name") or "") == name]
            if len(matches) != 1:
                raise ModernAdapterError("WORKER_NAME_AMBIGUOUS", "registered worker must resolve to exactly one agent", details={"name": name, "matches": len(matches)}, safety=True)
            worker = self._validate_pi_worker(matches[0], name)
            actual_workspace = str(worker.get("workspace_id") or "")
            actual_pane = str(worker.get("pane_id") or "")
            if actual_workspace != str(registration.get("workspace_id")) or actual_pane != str(registration.get("pane_id")):
                raise ModernAdapterError("WORKER_IDENTITY_CONFLICT", "registered worker identity changed", details={"name": name, "expectedWorkspaceId": registration.get("workspace_id"), "actualWorkspaceId": actual_workspace, "expectedPaneId": registration.get("pane_id"), "actualPaneId": actual_pane}, safety=True)
            observed.append((registration, worker))
        return observed

    @staticmethod
    def read_prompt(path: str) -> str:
        file = Path(path)
        try:
            value = file.read_text(encoding="utf-8")
        except OSError as exc:
            raise ModernAdapterError("PROMPT_NOT_READABLE", "prompt file is missing or unreadable", details={"path": str(file), "reason": str(exc)}) from exc
        if not value:
            raise ModernAdapterError("PROMPT_EMPTY", "prompt file is empty", details={"path": str(file)})
        return value

    def prompt_worker(self, worker: dict, text: str, *, wait_for_working: bool = False) -> dict:
        target = str(worker.get("name") or worker.get("agent") or "")
        if not target:
            raise ModernAdapterError("TARGET_INVALID", "worker has no stable name")
        # Herdr currently has no prompt-file/stdin option. Passing argv directly preserves
        # shell-sensitive bytes and cannot invoke a shell.
        args = ["agent", "prompt", target, text]
        if wait_for_working:
            args += ["--wait", "--until", "working", "--timeout", "5000"]
        result = self._json(args, "agent prompt")
        return result["agent"] if isinstance(result.get("agent"), dict) else result

    def create_workspace(self, cwd: str, label: str) -> dict:
        result = self._json(["workspace", "create", "--cwd", os.path.abspath(cwd), "--label", label, "--no-focus"], "workspace create")
        workspace = result.get("workspace") if isinstance(result.get("workspace"), dict) else result
        if not (workspace.get("workspace_id") or workspace.get("id")):
            raise ModernAdapterError("INVALID_RESPONSE", "workspace create returned no workspace ID")
        return workspace

    def _workspace_pane(self, workspace_id: str) -> dict:
        result = self._json(["pane", "list", "--workspace", workspace_id], "pane list")
        panes = result.get("panes", [])
        if not isinstance(panes, list) or len(panes) != 1:
            raise ModernAdapterError("WORKSPACE_PANE_AMBIGUOUS", "new workspace must contain exactly one launch pane", details={"workspaceId": workspace_id, "panes": len(panes) if isinstance(panes, list) else 0})
        return panes[0]

    def start_worker(self, *, name: str, cwd: str, workspace_id: str, provider: str | None, model: str | None, thinking: str | None, extension: str) -> dict:
        pane = self._workspace_pane(workspace_id)
        pane_id = str(pane.get("pane_id") or pane.get("id") or "")
        if not pane_id:
            raise ModernAdapterError("INVALID_RESPONSE", "workspace pane has no pane ID")
        pi = ["pi", "-e", os.path.expanduser(extension)]
        if provider: pi += ["--provider", provider]
        if model: pi += ["--model", model]
        if thinking: pi += ["--thinking", thinking]
        pi += ["--name", name]
        deadline = time.monotonic() + min(self.timeout, 30.0)
        while True:
            try:
                started = self._json(["agent", "start", name, "--kind", "pi", "--pane", pane_id, "--timeout", "30000", "--", *pi], "agent start")
                break
            except ModernAdapterError as exc:
                native = str(exc.details.get("nativeError", ""))
                if "agent_pane_busy" not in native or time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)
        return {**started, "pane_id": started.get("pane_id") or pane_id, "workspace_id": started.get("workspace_id") or workspace_id, "tab_id": started.get("tab_id") or pane.get("tab_id")}

    def inspect_worker(self, worker: dict) -> dict:
        native = str(worker.get("agent_status") or "unknown")
        session = worker.get("agent_session") if isinstance(worker.get("agent_session"), dict) else {}
        artifact = session.get("value") if session.get("kind") == "path" else None
        interpretation = "unknown"
        if native == "working": interpretation = "working"
        elif native == "blocked": interpretation = "blocked"
        elif native == "done": interpretation = "completed"
        # idle is intentionally unknown: only a durable session may classify it.
        if native == "idle" and artifact and Path(str(artifact)).is_file():
            final = self.read_final_result(str(artifact))
            if final is not None: interpretation = "completed"
        return {"name": worker.get("name"), "nativeStatus": native, "interpretation": interpretation, "workspaceId": worker.get("workspace_id"), "paneId": worker.get("pane_id"), "cwd": worker.get("cwd"), "sessionArtifact": artifact, "lastActivity": worker.get("state_change_seq")}

    @staticmethod
    def read_final_result(path: str) -> str | None:
        try:
            records = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        last = None
        for line in records:
            try: entry = json.loads(line)
            except ValueError: continue
            message = entry.get("message") if isinstance(entry, dict) else None
            if not isinstance(message, dict) or message.get("role") != "assistant": continue
            content = message.get("content")
            if isinstance(content, str): last = content
            elif isinstance(content, list):
                parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
                if parts: last = "".join(parts)
        return last

    def result(self, worker: dict) -> dict:
        info = self.inspect_worker(worker)
        artifact = info.get("sessionArtifact")
        value = self.read_final_result(str(artifact)) if artifact else None
        if value is None:
            raise ModernAdapterError("RESULT_UNAVAILABLE", "Pi session artifact has no readable final assistant message", details={"sessionArtifact": artifact})
        return {"name": info["name"], "workspaceId": info["workspaceId"], "paneId": info["paneId"], "sessionArtifact": artifact, "result": value}
