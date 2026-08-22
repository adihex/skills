#!/usr/bin/env python3
"""Pure worker lifecycle state machine.

The module has no Herdr, GitHub, filesystem, or network dependency.
"""
from __future__ import annotations

from copy import deepcopy

STATES = (
    "created", "setup_pending", "setup_failed", "ready", "working", "verifying",
    "pushed", "review_pending", "blocked_external", "blocked", "complete",
    "cleanup_pending", "cleaned", "failed", "aborted",
)
TERMINAL_STATES = frozenset({"cleaned", "failed", "aborted"})
TRANSITIONS = {
    "created": {"setup_pending", "aborted", "failed"},
    "setup_pending": {"setup_failed", "ready", "aborted", "failed"},
    "setup_failed": {"setup_pending", "aborted", "failed"},
    "ready": {"working", "aborted", "failed"},
    "working": {"verifying", "blocked_external", "blocked", "aborted", "failed"},
    "verifying": {"pushed", "review_pending", "blocked_external", "blocked", "aborted", "failed"},
    "pushed": {"review_pending", "blocked_external", "blocked", "failed"},
    "review_pending": {"complete", "blocked_external", "blocked", "failed"},
    "blocked_external": {"setup_pending", "working", "verifying", "review_pending", "aborted", "failed"},
    "blocked": {"setup_pending", "working", "verifying", "review_pending", "aborted", "failed"},
    "complete": {"cleanup_pending"},
    "cleanup_pending": {"cleaned", "failed", "aborted"},
    "cleaned": set(),
    "failed": set(),
    "aborted": set(),
}


def _fail(code: str, message: str) -> ValueError:
    exc = ValueError(message)
    exc.code = code  # type: ignore[attr-defined]
    return exc


def _completion_evidence(manifest: dict) -> list[str]:
    missing = []
    required_nonempty = ("head_sha", "pushed_sha", "pr_number")
    for key in required_nonempty:
        if manifest.get(key) in (None, ""):
            missing.append(key)
    if manifest.get("review_status") != "approved":
        missing.append("review_status=approved")
    if manifest.get("checks_status") != "passed":
        missing.append("checks_status=passed")
    if manifest.get("worktree_clean") is not True:
        missing.append("worktree_clean=true")
    if manifest.get("synchronized") is not True:
        missing.append("synchronized=true")
    return missing


def transition(manifest: dict, target: str, evidence: dict | None = None) -> dict:
    """Return a new manifest after a validated transition."""
    current = manifest.get("state")
    if current not in STATES:
        raise _fail("INVALID_STATE", f"unknown current state: {current!r}")
    if target not in STATES:
        raise _fail("INVALID_STATE", f"unknown target state: {target!r}")
    if current in TERMINAL_STATES:
        raise _fail("TERMINAL_STATE", f"cannot transition terminal state {current!r}")
    if target not in TRANSITIONS[current]:
        raise _fail("INVALID_TRANSITION", f"cannot transition {current!r} -> {target!r}")

    updated = deepcopy(manifest)
    if evidence:
        updated.update(deepcopy(evidence))
    if target == "complete":
        missing = _completion_evidence(updated)
        if missing:
            raise _fail("COMPLETION_EVIDENCE_REQUIRED", "missing completion evidence: " + ", ".join(missing))
    if target == "cleaned":
        required = ("cleanup_verified", "processes_stopped", "path_gone")
        missing = [key for key in required if updated.get(key) is not True]
        if missing:
            raise _fail("CLEANUP_EVIDENCE_REQUIRED", "missing cleanup evidence: " + ", ".join(missing))
    updated["state"] = target
    return updated


def can_transition(current: str, target: str) -> bool:
    return current in TRANSITIONS and target in TRANSITIONS[current]
