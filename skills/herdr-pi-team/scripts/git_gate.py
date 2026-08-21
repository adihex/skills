#!/usr/bin/env python3
"""Git, pull-request, review, and commit-check evidence gates."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


REPORT_FIELDS = ("RESULT", "WORKTREE", "BRANCH", "COMMIT", "PUSHED", "PR", "CODERABBIT", "CHECKS", "CLEANUP", "BLOCKER", "EVIDENCE")
REPORT_VALUES = {
    "RESULT": {"complete", "blocked_external", "blocked", "failed"},
    "CODERABBIT": {"approved", "changes_requested", "rate_limited", "not_run", "blocked"},
    "CHECKS": {"passed", "failed_touched_scope", "failed_unrelated", "skipped_expected", "pending", "external_blocked"},
    "CLEANUP": {"verified", "pending", "refused", "failed", "not_applicable"},
}


def parse_worker_report(path: str, *, expected_worktree: str | None = None, expected_branch: str | None = None) -> dict:
    """Parse and validate the exact worker report contract without executing its contents."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise GateError("REPORT_UNREADABLE", "worker report is not readable", details={"path": path}) from exc
    values = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if key in REPORT_FIELDS:
            if key in values:
                raise GateError("REPORT_DUPLICATE_FIELD", f"worker report repeats {key}")
            values[key] = value
    missing = [key for key in REPORT_FIELDS if not values.get(key)]
    if missing:
        raise GateError("REPORT_FIELDS_MISSING", "worker report is missing fields", details={"fields": missing})
    for key, allowed in REPORT_VALUES.items():
        if values[key] not in allowed:
            raise GateError("REPORT_VALUE_INVALID", f"invalid {key} value", details={"value": values[key]})
    if expected_worktree and Path(values["WORKTREE"]).resolve() != Path(expected_worktree).resolve():
        raise GateError("REPORT_WORKTREE_MISMATCH", "report worktree does not match manifest")
    if expected_branch and values["BRANCH"] != expected_branch:
        raise GateError("REPORT_BRANCH_MISMATCH", "report branch does not match manifest")
    if values["RESULT"] == "complete":
        required = {
            "COMMIT": values["COMMIT"] != "none", "PUSHED": values["PUSHED"] != "none",
            "PR": values["PR"] != "none", "CODERABBIT": values["CODERABBIT"] == "approved",
            "CHECKS": values["CHECKS"] in {"passed", "skipped_expected"}, "CLEANUP": values["CLEANUP"] == "verified",
        }
        failed = [key for key, valid in required.items() if not valid]
        if failed:
            raise GateError("REPORT_COMPLETION_EVIDENCE_MISSING", "complete report lacks evidence", details={"fields": failed})
    return values


def verify_push_invocation(argv: list[str]) -> None:
    bad = [arg for arg in argv if arg in {"--force", "-f", "--no-verify"} or arg.startswith("--force=")]
    if bad:
        raise GateError("UNSAFE_PUSH", "force push and hook bypass are forbidden", details={"arguments": bad})


def classify_push_result(returncode: int, stderr: str, command: list[str]) -> dict:
    if returncode == 0:
        return {"status": "pushed", "command": command}
    if re.search(r"pre-push|hook", stderr, re.I):
        raise GateError("PUSH_HOOK_FAILED", "pre-push hook failed", details={"command": command, "stderr": stderr[:500]})
    raise GateError("PUSH_FAILED", "git push failed", details={"command": command, "stderr": stderr[:500]})


class GitGate:
    def __init__(self, *, git_command: str = "git", gh_command: str = "gh", timeout: float = 20.0):
        self.git_command = git_command
        self.gh_command = gh_command
        self.timeout = timeout

    def _run(self, command: str, args: list[str], *, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
        executable = shutil.which(command) or command
        try:
            return subprocess.run([executable] + args, cwd=cwd, capture_output=True, text=True, timeout=self.timeout, shell=False)
        except FileNotFoundError as exc:
            raise GateError("COMMAND_UNAVAILABLE", f"{command} command not found", details={"command": command}) from exc
        except subprocess.TimeoutExpired as exc:
            raise GateError("COMMAND_TIMEOUT", f"{command} command timed out", details={"command": command}) from exc

    def verify_worktree(self, *, worktree: str, expected_worktree: str, expected_branch: str,
                       require_upstream: bool = True) -> dict:
        actual_path = Path(worktree).resolve()
        expected_path = Path(expected_worktree).resolve()
        if actual_path != expected_path:
            raise GateError("WORKTREE_MISMATCH", "worktree path is not the owned path", details={"expected": str(expected_path), "actual": str(actual_path)})
        if not actual_path.is_dir():
            raise GateError("WORKTREE_MISSING", "owned worktree does not exist", details={"worktree": str(actual_path)})
        status = self._run(self.git_command, ["-C", str(actual_path), "status", "--porcelain"])
        if status.returncode:
            raise GateError("GIT_STATUS_FAILED", "cannot inspect worktree", details={"stderr": status.stderr[:500]})
        if status.stdout.strip():
            raise GateError("DIRTY_WORKTREE", "worktree has uncommitted changes", details={"status": status.stdout[:500]})
        branch = self._run(self.git_command, ["-C", str(actual_path), "branch", "--show-current"])
        actual_branch = branch.stdout.strip()
        if branch.returncode or actual_branch != expected_branch:
            raise GateError("BRANCH_MISMATCH", "worktree branch is not the owned branch", details={"expected": expected_branch, "actual": actual_branch})
        head = self._run(self.git_command, ["-C", str(actual_path), "rev-parse", "HEAD"])
        if head.returncode or not head.stdout.strip():
            raise GateError("NO_COMMIT", "HEAD is not a commit", details={"stderr": head.stderr[:500]})
        upstream = self._run(self.git_command, ["-C", str(actual_path), "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
        if require_upstream and (upstream.returncode or not upstream.stdout.strip()):
            raise GateError("UPSTREAM_MISSING", "branch has no upstream", details={"stderr": upstream.stderr[:500]})
        upstream_sha = self._run(self.git_command, ["-C", str(actual_path), "rev-parse", "@{u}"]) if upstream.returncode == 0 else None
        head_sha = head.stdout.strip()
        pushed_sha = upstream_sha.stdout.strip() if upstream_sha and upstream_sha.returncode == 0 else None
        if require_upstream and head_sha != pushed_sha:
            raise GateError("UNPUSHED_COMMITS", "local HEAD differs from upstream", details={"head_sha": head_sha, "upstream_sha": pushed_sha})
        return {"worktree": str(actual_path), "branch": actual_branch, "clean": True,
                "head_sha": head_sha, "upstream": upstream.stdout.strip() if upstream.returncode == 0 else None,
                "pushed_sha": pushed_sha, "synchronized": head_sha == pushed_sha if require_upstream else None}

    def discover_pr(self, *, branch: str, explicit_pr: int | None = None) -> dict:
        if explicit_pr is not None:
            return self._gh_json(["pr", "view", str(explicit_pr), "--json", "number,url,state,headRefName"], "pr view")
        rows = self._gh_json(["pr", "list", "--head", branch, "--state", "open", "--json", "number,url,state,headRefName"], "pr list")
        if not isinstance(rows, list):
            raise GateError("INVALID_PR_RESPONSE", "gh pr list returned an object")
        if not rows:
            raise GateError("PR_NOT_FOUND", "no open pull request found for branch", details={"branch": branch})
        if len(rows) > 1:
            raise GateError("MULTIPLE_PRS", "multiple pull requests found; pass --pr explicitly", details={"count": len(rows)})
        return rows[0]

    def _gh_json(self, args: list[str], operation: str):
        process = self._run(self.gh_command, args)
        if process.returncode:
            raise GateError("GH_COMMAND_FAILED", f"{operation} failed", details={"stderr": process.stderr[:500], "operation": operation})
        try:
            return json.loads(process.stdout)
        except ValueError as exc:
            raise GateError("INVALID_GH_RESPONSE", f"{operation} returned invalid JSON") from exc

    def retrieve_reviews(self, *, repository: str, pr_number: int) -> dict:
        reviews = self._gh_json(["pr", "view", str(pr_number), "--repo", repository, "--json", "reviews,reviewDecision"], "review summary")
        issue_comments = self._gh_json(["api", f"repos/{repository}/issues/{pr_number}/comments"], "issue comments")
        inline_comments = self._gh_json(["api", f"repos/{repository}/pulls/{pr_number}/comments"], "inline comments")
        owner, name = repository.split("/", 1)
        query = "query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100){nodes{id,isResolved,comments(first:100){nodes{id,body}}}}}}}"
        thread_response = self._gh_json(["api", "graphql", "-f", f"query={query}", "-F", f"owner={owner}", "-F", f"name={name}", "-F", f"number={pr_number}"], "review threads")
        all_comments = []
        for row in (reviews.get("reviews", []) if isinstance(reviews, dict) else []):
            all_comments.append({"id": str(row.get("id")), "body": row.get("body", ""), "kind": "review", "state": row.get("state")})
        for kind, rows in (("issue", issue_comments), ("inline", inline_comments)):
            for row in rows if isinstance(rows, list) else []:
                all_comments.append({"id": str(row.get("id")), "body": row.get("body", ""), "kind": kind})
        thread_nodes = (((thread_response.get("data") or {}).get("repository") or {}).get("pullRequest") or {}).get("reviewThreads", {}).get("nodes", []) if isinstance(thread_response, dict) else []
        for node in thread_nodes if isinstance(thread_nodes, list) else []:
            comments = ((node.get("comments") or {}).get("nodes", [])) if isinstance(node, dict) else []
            body = comments[0].get("body", "") if comments and isinstance(comments[0], dict) else ""
            all_comments.append({"id": str(node.get("id")), "body": body, "kind": "thread", "resolved": node.get("isResolved")})
        unique = {}
        for row in all_comments:
            if row["id"] not in unique:
                unique[row["id"]] = row
        rate_limited = any(re.search(r"rate limit|secondary rate|too many requests|try again later", str(row.get("body", "")), re.I) for row in unique.values())
        decision = reviews.get("reviewDecision") if isinstance(reviews, dict) else None
        threads = [row for row in unique.values() if row.get("kind") == "thread"]
        return {"review_status": "blocked_external" if rate_limited else (str(decision or "pending").lower()),
                "rate_limited": rate_limited, "comments": list(unique.values()), "review_threads": threads}

    @staticmethod
    def record_response(*, thread_id: str, action: str, reply_id: str | None, commit_sha: str) -> dict:
        if not thread_id or action not in {"fixed", "explained", "blocked"} or not reply_id or not commit_sha:
            raise GateError("REPLY_EVIDENCE_REQUIRED", "actionable review response needs thread, action, reply ID, and commit SHA")
        return {"thread_id": thread_id, "action": action, "reply_id": reply_id, "commit_sha": commit_sha}

    def poll_checks(self, *, repository: str, commit_sha: str, pr_number: int | None = None) -> dict:
        args = ["pr", "checks", "--commit", commit_sha, "--repo", repository, "--json", "name,state,bucket,headSha"]
        rows = self._gh_json(args, "commit checks")
        if isinstance(rows, dict):
            rows = rows.get("checks", [])
        if not isinstance(rows, list):
            raise GateError("INVALID_CHECK_RESPONSE", "gh checks returned an unexpected shape")
        for row in rows:
            head_sha = row.get("headSha") or row.get("head_sha")
            if head_sha and head_sha != commit_sha:
                raise GateError("CHECKS_WRONG_COMMIT", "checks are not tied to the requested commit", details={"requested": commit_sha, "actual": head_sha})
        return {"status": classify_checks(rows), "commit_sha": commit_sha, "checks": rows}


def classify_checks(checks: list[dict], touched_scope: set[str] | None = None) -> str:
    if not checks:
        return "pending"
    states = [str(row.get("state") or row.get("bucket") or "").lower() for row in checks]
    if any(state in {"pending", "queued", "in_progress", "running"} for state in states):
        return "pending"
    failures = [row for row, state in zip(checks, states) if state in {"failure", "failed", "cancelled", "error"}]
    if failures:
        if touched_scope is not None and any(set(row.get("paths", [])) & touched_scope for row in failures):
            return "failed_touched_scope"
        return "failed_unrelated"
    if all(state in {"success", "passed", "skipped", "neutral"} for state in states):
        return "skipped_expected" if all(state in {"skipped", "neutral"} for state in states) else "passed"
    return "external_blocked"


def completion_gate(*, git: dict, review_status: str, checks_status: str) -> dict:
    if not git.get("clean") or not git.get("synchronized") or not git.get("head_sha") or not git.get("pushed_sha"):
        return {"ok": False, "state": "blocked", "reason": "git evidence incomplete"}
    if review_status == "blocked_external":
        return {"ok": False, "state": "blocked_external", "reason": "review provider rate-limited"}
    if review_status != "approved":
        return {"ok": False, "state": "blocked", "reason": "review not approved"}
    if checks_status not in {"passed", "skipped_expected"}:
        return {"ok": False, "state": "blocked", "reason": "checks not passing"}
    return {"ok": True, "state": "complete"}
