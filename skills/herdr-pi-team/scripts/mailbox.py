#!/usr/bin/env python3
"""Durable, locked delivery mailbox for modern Herdr workers."""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


class MailboxError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code, self.details = code, details or {}


class MailboxStore:
    """One run mailbox with idempotent events and per-consumer delivery cursors."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.events_path = self.path.with_name(self.path.name + ".events.jsonl")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            os.chmod(self.lock_path, 0o600)
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read_state(self) -> dict:
        try:
            with self.path.open(encoding="utf-8") as handle:
                value = json.load(handle)
        except FileNotFoundError:
            return {"version": 1, "run_id": None, "workers": {}, "consumers": {}}
        except (OSError, ValueError) as exc:
            raise MailboxError("MAILBOX_UNREADABLE", "mailbox state is unreadable", details={"path": str(self.path)}) from exc
        if not isinstance(value, dict) or value.get("version") != 1:
            raise MailboxError("MAILBOX_INVALID", "mailbox state has an unsupported format", details={"path": str(self.path)})
        value.setdefault("workers", {})
        value.setdefault("consumers", {})
        return value

    def _write_state(self, value: dict) -> None:
        fd, temporary = tempfile.mkstemp(prefix="mailbox.", suffix=".tmp", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _read_events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        events = []
        try:
            with self.events_path.open(encoding="utf-8") as handle:
                for line in handle:
                    try:
                        value = json.loads(line)
                    except ValueError:
                        continue
                    if isinstance(value, dict) and isinstance(value.get("event_id"), str):
                        events.append(value)
        except OSError as exc:
            raise MailboxError("MAILBOX_UNREADABLE", "mailbox events are unreadable", details={"path": str(self.events_path)}) from exc
        return events

    def register(self, *, run_id: str, name: str, workspace_id: str, pane_id: str) -> dict:
        if not all((run_id, name, workspace_id, pane_id)):
            raise MailboxError("WORKER_IDENTITY_INCOMPLETE", "run, worker, workspace, and pane identity are required")
        with self._lock():
            state = self._read_state()
            if state["run_id"] not in (None, run_id):
                raise MailboxError("RUN_ID_CONFLICT", "mailbox belongs to a different run", details={"expected": state["run_id"], "actual": run_id})
            state["run_id"] = run_id
            current = state["workers"].get(name)
            identity = {"workspace_id": workspace_id, "pane_id": pane_id}
            if current:
                if any(current.get(key) != value for key, value in identity.items()):
                    raise MailboxError("WORKER_IDENTITY_CONFLICT", "worker name is already registered to another pane", details={"name": name})
                return current
            generations = [int(worker.get("generation", 0)) for worker in state["workers"].values()]
            worker = {"name": name, **identity, "generation": max(generations, default=0) + 1, "registered_at": self._now()}
            state["workers"][name] = worker
            self._write_state(state)
            return worker

    def workers(self, names: list[str] | None = None) -> list[dict]:
        with self._lock():
            state = self._read_state()
            selected = names or list(state["workers"])
            if not selected:
                raise MailboxError("MAILBOX_EMPTY", "mailbox has no registered workers")
            missing = [name for name in selected if name not in state["workers"]]
            if missing:
                raise MailboxError("WORKER_NOT_REGISTERED", "requested worker is not registered", details={"workers": missing})
            return [dict(state["workers"][name]) for name in selected]

    def append_event(self, worker: dict, *, kind: str, outcome: str, native_status: str,
                     state_change_seq=None, session_artifact: str | None = None) -> dict:
        with self._lock():
            state = self._read_state()
            current = state["workers"].get(worker.get("name"))
            if not current or any(current.get(key) != worker.get(key) for key in ("workspace_id", "pane_id", "generation")):
                raise MailboxError("WORKER_IDENTITY_CONFLICT", "event identity does not match the registered worker")
            event_id = f"{state['run_id']}:{worker['name']}:{worker['generation']}:{kind}"
            events = self._read_events()
            existing = next((event for event in events if event.get("event_id") == event_id), None)
            if existing:
                return existing
            event = {
                "event_id": event_id,
                "run_id": state["run_id"],
                "worker": worker["name"],
                "workspaceId": worker["workspace_id"],
                "paneId": worker["pane_id"],
                "kind": kind,
                "outcome": outcome,
                "untrusted": True,
                "nativeStatus": native_status,
                "stateChangeSeq": state_change_seq,
                "sessionArtifact": session_artifact,
                "createdAt": self._now(),
            }
            with self.events_path.open("a", encoding="utf-8") as handle:
                os.chmod(self.events_path, 0o600)
                json.dump(event, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            return event

    def deliver(self, *, consumer: str, names: list[str] | None = None, limit: int | None = None) -> list[dict]:
        if not consumer:
            raise MailboxError("CONSUMER_REQUIRED", "mailbox consumer identity is required")
        with self._lock():
            state = self._read_state()
            selected = set(names or state["workers"])
            acknowledged = set(state["consumers"].get(consumer, []))
            pending = [event for event in self._read_events()
                       if event.get("worker") in selected and event.get("event_id") not in acknowledged]
            if limit is not None:
                pending = pending[:limit]
            if pending:
                acknowledged.update(event["event_id"] for event in pending)
                state["consumers"][consumer] = sorted(acknowledged)
                self._write_state(state)
            return pending

    def terminal_workers(self, names: list[str] | None = None) -> set[str]:
        selected = set(names) if names else None
        with self._lock():
            return {event["worker"] for event in self._read_events()
                    if selected is None or event.get("worker") in selected}

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
