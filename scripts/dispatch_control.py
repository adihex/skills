#!/usr/bin/env python3
"""Cross-runtime launch admission backed by durable manifests and reservations."""
from __future__ import annotations

import atexit
import importlib.util
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None

POLICY_PATH = Path(__file__).resolve().parents[1] / "skills" / "herdr-pi-team" / "scripts" / "dispatch_policy.py"
SPEC = importlib.util.spec_from_file_location("worker_dispatch_policy", POLICY_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"dispatch policy is unavailable: {POLICY_PATH}")
policy_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = policy_module
SPEC.loader.exec_module(policy_module)

ACTIVE_STATES = {"created", "setup_pending", "ready", "working", "verifying", "pushed", "review_pending", "cleanup_pending"}
SETUP_STATES = {"created", "setup_pending"}


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        value = int(raw) if raw is not None else default
    except ValueError as exc:
        raise policy_module.DispatchRefused("DISPATCH_CONFIG_INVALID", f"{name} must be an integer") from exc
    if value < 1:
        raise policy_module.DispatchRefused("DISPATCH_CONFIG_INVALID", f"{name} must be positive")
    return value


def configured_policy():
    return policy_module.DispatchPolicy(
        max_active=_positive_int("PI_TEAM_MAX_ACTIVE", 4),
        max_active_pi_workers=_positive_int("PI_TEAM_MAX_ACTIVE_PI", 4),
        max_active_hax_workers=_positive_int("PI_TEAM_MAX_ACTIVE_HAX", 2),
        max_active_codex_subscription_workers=_positive_int("PI_TEAM_MAX_ACTIVE_CODEX", 2),
        setup_concurrency=_positive_int("PI_TEAM_SETUP_CONCURRENCY", 2),
    )


def memory_ratio() -> float:
    override = os.environ.get("PI_TEAM_MEMORY_RATIO")
    if override is not None:
        try:
            return max(0.0, min(1.0, float(override)))
        except ValueError as exc:
            raise policy_module.DispatchRefused("DISPATCH_CONFIG_INVALID", "PI_TEAM_MEMORY_RATIO must be a number") from exc
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])
        return 1.0 - (values["MemAvailable"] / values["MemTotal"])
    except (OSError, KeyError, ValueError, ZeroDivisionError):
        return 0.0


def _alive(pid: Any) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def _records(directory: Path) -> list[dict[str, Any]]:
    records = []
    for path in directory.glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        if path.name.startswith(".launching-") and not _alive(value.get("pid")):
            path.unlink(missing_ok=True)
            continue
        records.append(value)
    return records


class LaunchReservation:
    def __init__(self, directory: str | os.PathLike[str], backend: str):
        self.directory = Path(directory).resolve()
        self.backend = backend
        self.path: Path | None = None
        self.admission: dict[str, Any] | None = None

    def acquire(self) -> dict[str, Any]:
        self.directory.mkdir(parents=True, exist_ok=True)
        lock_path = self.directory / ".dispatch.lock"
        with lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            records = _records(self.directory)
            active = [row for row in records if row.get("state") in ACTIVE_STATES or row.get("reservation") is True]
            backend_active = [row for row in active if row.get("backend", "pi") == self.backend]
            setup = [row for row in active if row.get("state") in SETUP_STATES or row.get("reservation") is True]
            codex = [row for row in active if row.get("backend") == "hax" and (row.get("backend_config") or {}).get("provider", "codex") == "codex"]
            quota_blocked = any(row.get("backend") == "hax" and row.get("state") == "blocked_external" and row.get("blocker") == "HTTP_429" for row in records)
            self.admission = configured_policy().admit_backend(
                backend=self.backend, active_workers=len(backend_active), total_active_workers=len(active),
                setup_workers=len(setup), active_codex_workers=len(codex), quota_blocked=quota_blocked,
                memory_ratio=memory_ratio(),
            )
            stagger_path = self.directory / ".last-launch"
            try:
                previous = float(stagger_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                previous = 0.0
            now = time.time()
            scheduled = max(now, previous + float(self.admission["stagger_seconds"]))
            self.admission["stagger_wait_seconds"] = round(max(0.0, scheduled - now), 3)
            stagger_path.write_text(str(scheduled), encoding="utf-8")
            self.path = self.directory / f".launching-{os.getpid()}-{uuid.uuid4().hex}.json"
            self.path.write_text(json.dumps({"reservation": True, "pid": os.getpid(), "backend": self.backend,
                                             "backend_config": {"provider": "codex" if self.backend == "hax" else None}}), encoding="utf-8")
        if self.admission["stagger_wait_seconds"]:
            time.sleep(self.admission["stagger_wait_seconds"])
        atexit.register(self.release)
        return self.admission

    def release(self) -> None:
        if self.path is not None:
            self.path.unlink(missing_ok=True)
            self.path = None


__all__ = ["LaunchReservation", "configured_policy", "memory_ratio", "policy_module"]
