import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "skills" / "herdr-pi-team" / "scripts" / "git_gate.py"
FAKE_GIT = ROOT / "tests" / "fixtures" / "fake_git.py"
FAKE_GH = ROOT / "tests" / "fixtures" / "fake_gh.py"
spec = importlib.util.spec_from_file_location("git_gate", MODULE_PATH)
git_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_gate)


class GitGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.worktree = Path(self.temp.name) / "worktree"
        self.worktree.mkdir()
        self.old_env = os.environ.copy()
        os.environ["FAKE_GIT_SCENARIO"] = "ok"
        os.environ["FAKE_GH_SCENARIO"] = "ok"
        self.addCleanup(self.restore)

    def restore(self):
        os.environ.clear()
        os.environ.update(self.old_env)
        self.temp.cleanup()

    def gate(self):
        return git_gate.GitGate(git_command=str(FAKE_GIT), gh_command=str(FAKE_GH))

    def error_code(self, callback):
        with self.assertRaises(git_gate.GateError) as context:
            callback()
        return context.exception.code

    def test_clean_worktree_is_synchronized(self):
        result = self.gate().verify_worktree(worktree=str(self.worktree), expected_worktree=str(self.worktree), expected_branch="feature/test")
        self.assertTrue(result["clean"])
        self.assertTrue(result["synchronized"])
        self.assertEqual(result["head_sha"], result["pushed_sha"])

    def test_dirty_worktree_rejected(self):
        os.environ["FAKE_GIT_SCENARIO"] = "dirty"
        self.assertEqual(self.error_code(lambda: self.gate().verify_worktree(worktree=str(self.worktree), expected_worktree=str(self.worktree), expected_branch="feature/test")), "DIRTY_WORKTREE")

    def test_unpushed_commit_rejected(self):
        os.environ["FAKE_GIT_SCENARIO"] = "unpushed"
        self.assertEqual(self.error_code(lambda: self.gate().verify_worktree(worktree=str(self.worktree), expected_worktree=str(self.worktree), expected_branch="feature/test")), "UNPUSHED_COMMITS")

    def test_missing_upstream_rejected(self):
        os.environ["FAKE_GIT_SCENARIO"] = "missing-upstream"
        self.assertEqual(self.error_code(lambda: self.gate().verify_worktree(worktree=str(self.worktree), expected_worktree=str(self.worktree), expected_branch="feature/test")), "UPSTREAM_MISSING")

    def test_hook_failure_and_force_push_are_blocked(self):
        self.assertEqual(self.error_code(lambda: git_gate.verify_push_invocation(["git", "push", "--no-verify"])), "UNSAFE_PUSH")
        self.assertEqual(self.error_code(lambda: git_gate.classify_push_result(1, "pre-push hook failed", ["git", "push"])), "PUSH_HOOK_FAILED")

    def test_pr_discovery_requires_unambiguous_result(self):
        self.assertEqual(self.gate().discover_pr(branch="feature/test")["number"], 7)
        os.environ["FAKE_GH_SCENARIO"] = "missing-pr"
        self.assertEqual(self.error_code(lambda: self.gate().discover_pr(branch="feature/test")), "PR_NOT_FOUND")
        os.environ["FAKE_GH_SCENARIO"] = "multiple-prs"
        self.assertEqual(self.error_code(lambda: self.gate().discover_pr(branch="feature/test")), "MULTIPLE_PRS")

    def test_duplicate_comments_are_deduplicated_and_rate_limit_is_external(self):
        result = self.gate().retrieve_reviews(repository="org/repo", pr_number=7)
        self.assertEqual(len(result["comments"]), 4)
        self.assertEqual(len(result["review_threads"]), 1)
        os.environ["FAKE_GH_SCENARIO"] = "rate-limit"
        limited = self.gate().retrieve_reviews(repository="org/repo", pr_number=7)
        self.assertTrue(limited["rate_limited"])
        self.assertEqual(limited["review_status"], "blocked_external")

    def test_reply_requires_actual_evidence(self):
        self.assertEqual(self.error_code(lambda: git_gate.GitGate.record_response(thread_id="t1", action="fixed", reply_id=None, commit_sha="abc")), "REPLY_EVIDENCE_REQUIRED")
        result = git_gate.GitGate.record_response(thread_id="t1", action="fixed", reply_id="r1", commit_sha="abc")
        self.assertEqual(result["reply_id"], "r1")

    def test_checks_are_tied_to_commit_and_unrelated_failures_are_classified(self):
        self.assertEqual(self.gate().poll_checks(repository="org/repo", commit_sha="abc123")["status"], "passed")
        os.environ["FAKE_GH_SCENARIO"] = "wrong-commit"
        self.assertEqual(self.error_code(lambda: self.gate().poll_checks(repository="org/repo", commit_sha="abc123")), "CHECKS_WRONG_COMMIT")
        os.environ["FAKE_GH_SCENARIO"] = "unrelated-failure"
        self.assertEqual(self.gate().poll_checks(repository="org/repo", commit_sha="abc123")["status"], "failed_unrelated")

    def test_completion_gate_never_promotes_external_blocker(self):
        git = {"clean": True, "synchronized": True, "head_sha": "abc", "pushed_sha": "abc"}
        self.assertEqual(git_gate.completion_gate(git=git, review_status="blocked_external", checks_status="passed")["state"], "blocked_external")
        self.assertTrue(git_gate.completion_gate(git=git, review_status="approved", checks_status="passed")["ok"])


if __name__ == "__main__":
    unittest.main()
