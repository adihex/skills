#!/usr/bin/env python3
"""Dry-run-first, ownership-checked worker worktree cleanup."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


class CleanupError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


TARGET_PROCESS_KINDS = {"nx", "git-fsmonitor", "worker-child"}


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


class CleanupManager:
    def __init__(self, *, worktree_root: str, main_checkout: str, current_cwd: str | None = None,
                 git_command: str = "git", process_inspector: Callable[[], list[dict] | None] | None = None,
                 process_stopper: Callable[[dict], None] | None = None,
                 process_verifier: Callable[[dict], bool] | None = None,
                 workspace_closer: Callable[[dict], None] | None = None,
                 manifest_writer: Callable[[dict], None] | None = None):
        self.worktree_root = Path(worktree_root).resolve()
        self.main_checkout = Path(main_checkout).resolve()
        self.current_cwd = Path(current_cwd or os.getcwd()).resolve()
        self.git_command = git_command
        self.process_inspector = process_inspector or self._inspect_processes
        self.process_stopper = process_stopper or self._stop_process
        self.process_verifier = process_verifier or self._verify_process_stopped
        self.workspace_closer = workspace_closer or self._close_workspace
        self.manifest_writer = manifest_writer or (lambda _: None)

    def _git(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([self.git_command, "-C", str(cwd)] + args, capture_output=True, text=True, timeout=20, shell=False)

    def _git_state(self, path: Path, repo_root: Path) -> tuple[bool | None, bool | None, str | None]:
        status = self._git(["status", "--porcelain"], path)
        if status.returncode:
            return None, None, status.stderr.strip()[:500]
        head = self._git(["rev-parse", "HEAD"], path)
        upstream = self._git(["rev-parse", "@{u}"], path)
        if head.returncode or upstream.returncode:
            return bool(status.stdout.strip()), False, "upstream missing"
        return bool(status.stdout.strip()), head.stdout.strip() == upstream.stdout.strip(), None

    def _inspect_processes(self) -> list[dict] | None:
        try:
            result = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=10, shell=False)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode:
            return None
        processes = []
        for line in result.stdout.splitlines():
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                continue
            try:
                pid = int(parts[0])
            except ValueError:
                continue
            command = parts[1]
            kind = next((candidate for candidate in TARGET_PROCESS_KINDS if candidate in command.lower()), None)
            if not kind:
                continue
            try:
                cwd_result = subprocess.run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], capture_output=True, text=True, timeout=10, shell=False)
            except (OSError, subprocess.TimeoutExpired):
                return None
            if cwd_result.returncode:
                return None
            cwd = next((row[1:] for row in cwd_result.stdout.splitlines() if row.startswith("n")), None)
            if not cwd:
                return None
            processes.append({"pid": pid, "kind": kind, "cwd": cwd, "command": command, "owned": True})
        return processes

    @staticmethod
    def _stop_process(process: dict) -> None:
        pid = int(process["pid"])
        os.kill(pid, signal.SIGTERM)

    @staticmethod
    def _verify_process_stopped(process: dict) -> bool:
        pid = int(process["pid"])
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            except PermissionError:
                return False
            time.sleep(0.05)
        return False

    @staticmethod
    def _close_workspace(manifest: dict) -> None:
        command = manifest.get("herdr_command", "herdr")
        session = manifest.get("session")
        args = ([command] + (["--session", session] if session else []) + ["workspace", "close", str(manifest["workspace_id"])])
        result = subprocess.run(args, capture_output=True, text=True, timeout=20, shell=False)
        if result.returncode:
            raise CleanupError("WORKSPACE_CLOSE_FAILED", "Herdr workspace close failed", details={"stderr": result.stderr[:500]})

    def _ownership_issues(self, manifest: dict) -> list[str]:
        issues = []
        state = manifest.get("state")
        if state == "cleaned":
            return issues
        if state != "complete":
            issues.append("state_not_complete")
        worktree = Path(str(manifest.get("worktree") or "")).resolve()
        if not worktree.is_absolute() or not _within(worktree, self.worktree_root):
            issues.append("outside_worktree_root")
        if worktree == self.main_checkout:
            issues.append("main_checkout")
        if worktree == self.current_cwd:
            issues.append("current_process_cwd")
        if not manifest.get("workspace_id"):
            issues.append("missing_workspace")
        if manifest.get("owner_run_id") and manifest.get("owner_run_id") != manifest.get("run_id"):
            issues.append("manifest_ownership_mismatch")
        if manifest.get("active_owner_run_id") and manifest.get("active_owner_run_id") != manifest.get("run_id"):
            issues.append("duplicate_worktree_ownership")
        return issues

    def _target_processes(self, worktree: Path, inventory: list[dict] | None) -> tuple[list[dict], list[str]]:
        if inventory is None:
            return [], ["process_inspection_inconclusive"]
        target, issues = [], []
        for process in inventory:
            cwd = process.get("cwd")
            if cwd is None:
                issues.append("process_cwd_unknown")
                continue
            if Path(str(cwd)).resolve() == worktree and process.get("kind") in TARGET_PROCESS_KINDS:
                if process.get("owned") is not True:
                    issues.append("process_ownership_inconclusive")
                else:
                    target.append(process)
        return target, issues

    def plan(self, manifest: dict, *, require_pushed: bool = True) -> dict:
        if manifest.get("state") == "cleaned":
            return {"workspace": manifest.get("workspace_id"), "worktree": manifest.get("worktree"), "state": "cleaned", "dirty": False, "synchronized": True, "processes": [], "action": "noop", "issues": []}
        worktree = Path(str(manifest.get("worktree") or "")).resolve()
        issues = self._ownership_issues(manifest)
        dirty, synchronized, git_error = self._git_state(worktree, Path(str(manifest.get("repo_root") or self.main_checkout))) if worktree.is_dir() else (None, None, "worktree missing")
        if dirty is None:
            issues.append("worktree_unavailable")
        elif dirty:
            issues.append("dirty_worktree")
        if require_pushed and synchronized is not True:
            issues.append("unsynchronized_worktree")
        inventory = self.process_inspector()
        processes, process_issues = self._target_processes(worktree, inventory)
        issues.extend(process_issues)
        if git_error and "upstream missing" not in git_error and "worktree missing" not in git_error:
            issues.append("git_inspection_failed")
        return {"workspace": manifest.get("workspace_id"), "worktree": str(worktree), "state": manifest.get("state"),
                "dirty": dirty, "synchronized": synchronized, "processes": processes,
                "action": "remove" if not issues else "refuse", "issues": sorted(set(issues))}

    def cleanup(self, manifest: dict, *, confirm: bool = False, require_pushed: bool = True,
                remove_worktree: Callable[[dict], None] | None = None,
                prune_worktrees: Callable[[dict], None] | None = None) -> dict:
        planned = self.plan(manifest, require_pushed=require_pushed)
        if planned["action"] == "noop" or not confirm:
            planned["dry_run"] = not confirm
            return planned
        if planned["action"] != "remove":
            raise CleanupError("CLEANUP_REFUSED", "cleanup safety gate refused removal", details=planned)
        manifest["state"] = "cleanup_pending"
        self.manifest_writer(manifest)
        remover = remove_worktree or self._remove_worktree
        pruner = prune_worktrees or self._prune_worktrees
        try:
            for process in planned["processes"]:
                self.process_stopper(process)
            remaining = [process for process in planned["processes"] if not self.process_verifier(process)]
            if remaining:
                raise CleanupError("PROCESS_REMAINS", "owned process remains after scoped stop",
                                   details={"pids": [process["pid"] for process in remaining]})
            self.workspace_closer(manifest)
            remover(manifest)
            pruner(manifest)
            path = Path(manifest["worktree"])
            if path.exists():
                raise CleanupError("WORKTREE_REMAINS", "worktree path still exists after removal")
            manifest.update({"state": "cleaned", "cleanup_verified": True, "processes_stopped": True, "path_gone": True})
            self.manifest_writer(manifest)
            planned.update({"action": "cleaned", "dry_run": False})
            return planned
        except Exception as exc:
            manifest["state"] = "cleanup_pending"
            self.manifest_writer(manifest)
            planned.update({"action": "failed", "dry_run": False, "error": str(exc)})
            return planned

    def _remove_worktree(self, manifest: dict) -> None:
        repo_root = Path(str(manifest.get("repo_root") or self.main_checkout))
        result = self._git(["worktree", "remove", str(Path(manifest["worktree"]).resolve())], repo_root)
        if result.returncode:
            raise CleanupError("WORKTREE_REMOVE_FAILED", "git worktree remove failed", details={"stderr": result.stderr[:500]})

    def _prune_worktrees(self, manifest: dict) -> None:
        repo_root = Path(str(manifest.get("repo_root") or self.main_checkout))
        result = self._git(["worktree", "prune"], repo_root)
        if result.returncode:
            raise CleanupError("WORKTREE_PRUNE_FAILED", "git worktree prune failed", details={"stderr": result.stderr[:500]})


def load_manifest(path: str) -> dict | None:
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


@contextmanager
def cleanup_lock(path: str):
    lock_path = Path(path).with_suffix(Path(path).suffix + ".cleanup.lock")
    with lock_path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
        try:
            yield True
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def watch_once(manifest_paths: list[str], *, run_id: str, manager_factory: Callable[[dict], CleanupManager],
               cleanup_enabled: bool = False, require_pushed: bool = True) -> dict:
    """Process only this run's manifests once; callers provide the polling loop."""
    results, tracked = [], 0
    for path in sorted(manifest_paths):
        manifest = load_manifest(path)
        if not manifest or manifest.get("run_id") != run_id:
            continue
        tracked += 1
        with cleanup_lock(path) as acquired:
            if not acquired:
                results.append({"manifest": path, "action": "locked"})
                continue
            manifest["_manifest_path"] = path
            manager = manager_factory(manifest)
            if cleanup_enabled and manifest.get("state") == "complete":
                result = manager.cleanup(manifest, confirm=True, require_pushed=require_pushed)
            else:
                result = manager.plan(manifest, require_pushed=require_pushed)
            results.append({"manifest": path, "result": result})
    return {"tracked": tracked, "remaining": sum(1 for row in results if row.get("result", {}).get("action") not in {"cleaned", "noop"}), "results": results}
