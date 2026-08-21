#!/usr/bin/env python3
"""Shared, opt-in Hax backend primitives for terminal worker runtimes.

This module owns Hax configuration, safe command construction, preflight, capability
reporting, and process-outcome classification. Pane runtimes provide transport; this
module never reads or logs credential contents.
"""
from __future__ import annotations

import os
import time
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

BACKENDS = ("pi", "hax")
EFFORTS = ("default", "none", "low", "medium", "high", "xhigh", "max")
MODES = ("interactive", "oneshot")
AUTH_SOURCES = ("codex_cli", "hax_managed")
HAX_MIN_VERSION = "0.3.0"
VERSION_RE = re.compile(r"(?:hax\s+)?v?(\d+)\.(\d+)\.(\d+)", re.IGNORECASE)


class HaxConfigError(ValueError):
    """Raised when a backend configuration cannot be used safely."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class HaxPreflightError(RuntimeError):
    """Raised when a Hax prerequisite is unavailable."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


class HaxLifecycleError(RuntimeError):
    """Raised when a shared Hax lifecycle operation cannot proceed safely."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = dict(details or {})


@dataclass(frozen=True)
class BackendConfig:
    """Backend-neutral configuration persisted in a worker manifest."""

    backend: str = "pi"
    provider: str | None = None
    model: str | None = None
    effort: str = "default"
    mode: str = "interactive"
    auth_source: str | None = None
    hax_min_version: str = HAX_MIN_VERSION

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "BackendConfig":
        raw = dict(value or {})
        backend = raw.get("backend", "pi")
        if backend == "hax" and "provider" not in raw:
            # The subscription path has a documented codex default, while an
            # explicitly empty provider remains an actionable configuration error.
            raw["provider"] = "codex"
        if backend == "hax" and "auth_source" not in raw:
            raw["auth_source"] = "codex_cli"
        config = cls(
            backend=backend,
            provider=raw.get("provider"),
            model=raw.get("model"),
            effort=raw.get("effort", "default"),
            mode=raw.get("mode", "interactive"),
            auth_source=raw.get("auth_source"),
            hax_min_version=raw.get("hax_min_version", HAX_MIN_VERSION),
        )
        return config.validate()

    def validate(self) -> "BackendConfig":
        if self.backend not in BACKENDS:
            raise HaxConfigError("BACKEND_UNSUPPORTED", f"unsupported backend: {self.backend}")
        if self.effort not in EFFORTS:
            raise HaxConfigError("EFFORT_UNSUPPORTED", f"unsupported effort: {self.effort}")
        if self.mode not in MODES:
            raise HaxConfigError("MODE_UNSUPPORTED", f"unsupported mode: {self.mode}")
        if self.backend == "pi":
            return self
        if not self.provider:
            raise HaxConfigError("PROVIDER_MISSING", "Hax requires an explicit provider")
        if not self.model:
            raise HaxConfigError("MODEL_MISSING", "Hax requires an explicit model")
        if self.auth_source not in AUTH_SOURCES:
            raise HaxConfigError("AUTH_SOURCE_UNSUPPORTED", "Hax auth_source must be codex_cli or hax_managed")
        if not self.hax_min_version:
            raise HaxConfigError("HAX_VERSION_MISSING", "Hax minimum version is required")
        return self

    @property
    def steerable(self) -> bool:
        return self.backend == "pi" or self.mode == "interactive"

    def manifest_fields(self, *, runtime: str, capabilities: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return only safe backend fields for a manifest."""
        capability_fields = dict(capabilities or capabilities_for(self.backend, runtime))
        capability_fields["steerable"] = self.steerable
        return {
            "backend": self.backend,
            "runtime": runtime,
            "backend_config": {
                "provider": self.provider,
                "model": self.model,
                "effort": self.effort,
                "mode": self.mode,
                "auth_source": self.auth_source,
                "hax_min_version": self.hax_min_version,
            },
            "backend_capabilities": capability_fields,
            "backend_session_id": None,
            "backend_exit_code": None,
            "backend_error_code": None,
        }


def capabilities_for(backend: str = "hax", runtime: str = "unknown") -> dict[str, Any]:
    if backend == "pi":
        return {
            "backend": "pi", "runtime": runtime, "interactive": True, "one_shot": True,
            "native_state": True, "subscription_auth": False, "steerable": True,
            "resume_supported": True, "requires_explicit_model": False,
        }
    if backend != "hax":
        raise HaxConfigError("BACKEND_UNSUPPORTED", f"unsupported backend: {backend}")
    return {
        "backend": "hax", "runtime": runtime, "interactive": True, "one_shot": True,
        "native_state": False, "subscription_auth": True, "steerable": True,
        "resume_supported": False, "requires_explicit_model": True,
    }


def _version_tuple(value: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.search(value or "")
    return tuple(int(part) for part in match.groups()) if match else None


def _version_at_least(actual: str, minimum: str) -> bool:
    parsed_actual = _version_tuple(actual)
    parsed_minimum = _version_tuple(minimum)
    return bool(parsed_actual and parsed_minimum and parsed_actual >= parsed_minimum)


class HaxBackend:
    """Shared backend implementation used by all pane transports."""

    def __init__(self, *, hax_command: str = "hax", codex_command: str = "codex",
                 auth_path: str | os.PathLike[str] | None = None,
                 runner=subprocess.run):
        self.hax_command = hax_command
        self.codex_command = codex_command
        self.auth_path = Path(auth_path or "~/.codex/auth.json").expanduser()
        self.runner = runner

    def capabilities(self, config: BackendConfig, *, runtime: str = "unknown") -> dict[str, Any]:
        config.validate()
        result = capabilities_for(config.backend, runtime)
        result["steerable"] = config.steerable
        return result

    def build_command(self, config: BackendConfig, *, prompt: str | None = None) -> list[str]:
        config.validate()
        if config.backend != "hax":
            raise HaxConfigError("BACKEND_NOT_HAX", "HaxBackend can only build Hax commands")
        command = [self.hax_command, f"--provider={config.provider}", f"--model={config.model}", f"--effort={config.effort}"]
        if config.mode == "oneshot":
            if prompt is None:
                raise HaxConfigError("PROMPT_MISSING", "one-shot Hax mode requires a prompt")
            command += ["-p", prompt]
        return command

    def redacted_command(self, command: Sequence[str]) -> list[str]:
        """Return argv diagnostics without exposing credential material."""
        return ["<prompt>" if index and command[index - 1] == "-p" else str(value) for index, value in enumerate(command)]

    def preflight(self, config: BackendConfig) -> dict[str, Any]:
        config.validate()
        if config.backend == "pi":
            return {"code": "ready", "backend": "pi", "auth_source": None}
        hax = self._resolve_command(self.hax_command, "hax_missing")
        codex = self._resolve_command(self.codex_command, "codex_missing")
        if config.auth_source == "codex_cli":
            if not self.auth_path.is_file() or not os.access(self.auth_path, os.R_OK):
                raise HaxPreflightError("codex_auth_missing", "Codex authentication is missing or unreadable; run codex login")
        version = self._version(hax)
        if not _version_at_least(version, config.hax_min_version):
            raise HaxPreflightError("hax_version_unsupported", "installed Hax is below the required version",
                                    details={"hax_version": version, "required": config.hax_min_version})
        return {
            "code": "ready", "backend": "hax", "hax": hax, "codex": codex,
            "hax_version": version, "auth_source": config.auth_source,
            "auth_present": "present",
            "quota": "unknown until request",
        }

    def classify(self, *, returncode: int | None = None, stdout: str = "", stderr: str = "",
                 timed_out: bool = False) -> dict[str, Any]:
        text = f"{stdout}\n{stderr}".lower()
        if timed_out or "timed out" in text or "timeout" in text:
            return {"state": "blocked_external", "code": "network_timeout"}
        if "429" in text or "rate limit" in text or "quota" in text:
            return {"state": "blocked_external", "code": "HTTP_429"}
        if "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text:
            return {"state": "blocked", "code": "HTTP_401_403"}
        if returncode == 0:
            return {"state": "verifying", "code": "process_exit_0"}
        return {"state": "failed", "code": "process_exit_nonzero"}

    def diagnostics(self, config: BackendConfig, *, runtime: str = "unknown") -> dict[str, Any]:
        config.validate()
        result = {
            "hax": "missing", "codex": "missing", "codex_auth": "missing",
            "provider": config.provider, "model": "configured" if config.model and config.model != "__doctor_missing__" else "missing",
            "quota": "unknown until request", "backend": config.backend,
            "runtime": runtime,
        }
        if config.backend == "pi":
            return result | {"hax": "not_required", "codex": "not_required", "codex_auth": "not_required"}
        hax = self._find(self.hax_command)
        codex = self._find(self.codex_command)
        result["hax"] = "installed" if hax else "missing"
        result["codex"] = "installed" if codex else "missing"
        if config.auth_source == "codex_cli":
            result["codex_auth"] = "present" if self.auth_path.is_file() and os.access(self.auth_path, os.R_OK) else "missing"
        else:
            result["codex_auth"] = "not_required"
        return result

    def start(self, worker: Mapping[str, Any], config: BackendConfig, transport: Any) -> dict[str, Any]:
        """Start an interactive worker through a runtime transport."""
        config.validate()
        if config.backend != "hax" or config.mode != "interactive":
            raise HaxConfigError("INTERACTIVE_REQUIRED", "shared Hax start requires interactive Hax configuration")
        self.preflight(config)
        command = self.build_command(config)
        result = transport.start(dict(worker), command)
        if not isinstance(result, Mapping):
            raise HaxLifecycleError("START_INVALID", "runtime transport returned an invalid start result")
        started = dict(result)
        ready_worker = {**dict(worker), **started}
        started["ready"] = self.wait_ready(ready_worker, transport)
        return {"command": self.redacted_command(command), **started}

    def read_state(self, worker: Mapping[str, Any], transport: Any) -> dict[str, Any]:
        """Read and conservatively classify runtime state without claiming completion."""
        result = transport.read_state(dict(worker))
        if not isinstance(result, Mapping):
            raise HaxLifecycleError("READ_STATE_INVALID", "runtime transport returned an invalid state result")
        text = str(result.get("text") or result.get("output") or "")
        lowered = text.lower()
        if "429" in lowered or "quota" in lowered or "rate limit" in lowered:
            return {"state": "blocked_external", "code": "HTTP_429", "ready": False, "text_chars": len(text)}
        ready = any(marker in lowered for marker in ("ready", "ack", "❯", ">"))
        return {"state": "working" if ready else "unknown", "code": "interactive_prompt" if ready else "readiness_unknown",
                "ready": ready, "text_chars": len(text), "transport": dict(result)}

    def wait_ready(self, worker: Mapping[str, Any], transport: Any, *, timeout: float = 30.0, poll: float = 0.2) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last = None
        while time.monotonic() < deadline:
            last = self.read_state(worker, transport)
            if last.get("ready"):
                return last
            if last.get("state") == "blocked_external":
                raise HaxLifecycleError(last["code"], "Hax became externally blocked while starting", details=last)
            time.sleep(poll)
        raise HaxLifecycleError("HAX_READINESS_TIMEOUT", "Hax did not expose a readiness marker", details={"last_state": last or {}})

    def send(self, worker: Mapping[str, Any], text: str, transport: Any) -> dict[str, Any]:
        state = self.read_state(worker, transport)
        if not state["ready"]:
            raise HaxLifecycleError("HAX_READINESS_TIMEOUT", "Hax is not ready for a task submission", details={"state": state["state"], "code": state["code"]})
        result = transport.send(dict(worker), text)
        if not isinstance(result, Mapping):
            raise HaxLifecycleError("SEND_INVALID", "runtime transport returned an invalid send result")
        return {"state": "working", "submitted": True, **dict(result)}

    def interrupt(self, worker: Mapping[str, Any], transport: Any) -> dict[str, Any]:
        result = transport.interrupt(dict(worker))
        return {"interrupted": True, **dict(result or {})}

    def resume(self, worker: Mapping[str, Any], transport: Any) -> dict[str, Any]:
        if not self.capabilities_for_worker(worker).get("resume_supported", False):
            raise HaxLifecycleError("HAX_RESUME_UNSUPPORTED", "installed Hax runtime cannot prove safe resume")
        result = transport.resume(dict(worker))
        return {"resumed": True, **dict(result or {})}

    def stop(self, worker: Mapping[str, Any], transport: Any) -> dict[str, Any]:
        result = transport.stop(dict(worker))
        if isinstance(result, Mapping) and result.get("exit_code") not in (None, 0):
            raise HaxLifecycleError("STOP_FAILED", "runtime transport failed to stop the Hax worker", details=result)
        return {"stopped": True, "shutdown_diagnostics": dict(result or {})}

    def capabilities_for_worker(self, worker: Mapping[str, Any]) -> dict[str, Any]:
        capabilities = worker.get("backend_capabilities")
        return dict(capabilities) if isinstance(capabilities, Mapping) else capabilities_for("hax", str(worker.get("runtime", "unknown")))

    def run_oneshot(self, config: BackendConfig, *, prompt: str, cwd: str | os.PathLike[str], timeout: float = 900.0) -> dict[str, Any]:
        """Run an explicit Hax one-shot request with separate stdout/stderr capture."""
        if config.backend != "hax" or config.mode != "oneshot":
            raise HaxConfigError("ONESHOT_REQUIRED", "run_oneshot requires Hax oneshot configuration")
        self.preflight(config)
        command = self.build_command(config, prompt=prompt)
        try:
            process = self.runner(command, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, shell=False)
            classification = self.classify(returncode=process.returncode, stdout=process.stdout, stderr=process.stderr)
            return {"command": self.redacted_command(command), "stdout": process.stdout, "stderr": process.stderr,
                    "exit_code": process.returncode, **classification}
        except subprocess.TimeoutExpired as exc:
            return {"command": self.redacted_command(command), "stdout": exc.stdout or "", "stderr": exc.stderr or "",
                    "exit_code": None, **self.classify(timed_out=True)}

    def _find(self, command: str) -> str | None:
        if os.path.isabs(command):
            return command if os.access(command, os.X_OK) else None
        return shutil.which(command)

    def _resolve_command(self, command: str, code: str) -> str:
        resolved = self._find(command)
        if not resolved:
            raise HaxPreflightError(code, f"required command is not installed: {command}")
        return resolved

    def _version(self, command: str) -> str:
        try:
            process = self.runner([command, "--version"], capture_output=True, text=True, timeout=10, shell=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise HaxPreflightError("hax_version_unavailable", "could not determine Hax version") from exc
        if process.returncode != 0:
            raise HaxPreflightError("hax_version_unavailable", "Hax version command failed")
        return (process.stdout or process.stderr).strip().splitlines()[0] if (process.stdout or process.stderr).strip() else "unknown"


def config_from_mapping(value: Mapping[str, Any] | None) -> BackendConfig:
    return BackendConfig.from_mapping(value)


__all__ = [
    "AUTH_SOURCES", "BACKENDS", "EFFORTS", "HAX_MIN_VERSION", "MODES", "BackendConfig",
    "HaxBackend", "HaxConfigError", "HaxLifecycleError", "HaxPreflightError", "capabilities_for", "config_from_mapping",
]
