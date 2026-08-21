#!/usr/bin/env python3
"""Atomic, locked, redacting worker manifest storage."""
from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

SECRET_RE = re.compile(r"(?:sk|rk)-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}")
REDACT_KEYS = re.compile(r"(?:token|secret|password|cookie|authorization|credential|prompt|brief|contents?|text)", re.I)


def redact(value, key: str | None = None):
    if key and REDACT_KEYS.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_RE.sub("<redacted>", value)
    return value


class ManifestStore:
    def __init__(self, directory: str | os.PathLike[str]):
        self.directory = Path(directory)
        self.manifest_path = self.directory / "manifest.json"
        self.lock_path = self.directory / ".manifest.lock"
        self.events_path = self.directory / "events.jsonl"
        self.directory.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _lock(self) -> Iterator[None]:
        with self.lock_path.open("a+", encoding="utf-8") as lock:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def read(self) -> dict | None:
        try:
            with self.manifest_path.open(encoding="utf-8") as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    def write(self, manifest: dict) -> dict:
        if not isinstance(manifest, dict):
            raise TypeError("manifest must be an object")
        safe = redact(manifest)
        with self._lock():
            fd, temporary = tempfile.mkstemp(prefix="manifest.", suffix=".tmp", dir=self.directory)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(safe, handle, indent=2, sort_keys=True)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.manifest_path)
                return safe
            except Exception:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
                raise

    def append_event(self, event: dict) -> None:
        if not isinstance(event, dict):
            raise TypeError("event must be an object")
        safe = redact(event)
        with self._lock():
            with self.events_path.open("a", encoding="utf-8") as handle:
                json.dump(safe, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

    def events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        output = []
        with self.events_path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except ValueError:
                    continue
                if isinstance(value, dict):
                    output.append(value)
        return output
