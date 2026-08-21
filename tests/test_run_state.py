import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "skills" / "herdr-pi-team" / "scripts" / "run_state.py"
spec = importlib.util.spec_from_file_location("run_state", MODULE_PATH)
run_state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_state)


class RunStateTests(unittest.TestCase):
    def manifest(self, state="created"):
        return {
            "run_id": "run-1",
            "state": state,
            "head_sha": None,
            "pushed_sha": None,
            "pr_number": None,
            "review_status": "pending",
            "checks_status": "pending",
        }

    def transition(self, manifest, target, evidence=None):
        try:
            return run_state.transition(manifest, target, evidence)
        except ValueError as exc:
            self.fail(f"unexpected {getattr(exc, 'code', None)}: {exc}")

    def test_happy_path_requires_evidence(self):
        value = self.manifest()
        for target in ("setup_pending", "ready", "working", "verifying", "pushed", "review_pending"):
            value = self.transition(value, target)
        evidence = {
            "head_sha": "abc123",
            "pushed_sha": "abc123",
            "pr_number": 42,
            "review_status": "approved",
            "checks_status": "passed",
            "worktree_clean": True,
            "synchronized": True,
        }
        value = self.transition(value, "complete", evidence)
        self.assertEqual(value["state"], "complete")
        value = self.transition(value, "cleanup_pending")
        value = self.transition(value, "cleaned", {
            "cleanup_verified": True,
            "processes_stopped": True,
            "path_gone": True,
        })
        self.assertEqual(value["state"], "cleaned")

    def assert_code(self, code, callback):
        with self.assertRaises(ValueError) as context:
            callback()
        self.assertEqual(getattr(context.exception, "code", None), code)

    def test_invalid_transition_is_rejected(self):
        self.assert_code("INVALID_TRANSITION", lambda: run_state.transition(self.manifest(), "working"))
        self.assert_code("INVALID_STATE", lambda: run_state.transition(self.manifest("idle"), "ready"))

    def test_complete_requires_all_evidence(self):
        value = self.manifest("review_pending")
        self.assert_code("COMPLETION_EVIDENCE_REQUIRED", lambda: run_state.transition(value, "complete"))
        value["head_sha"] = "abc"
        value["pushed_sha"] = "abc"
        value["pr_number"] = 1
        value["review_status"] = "approved"
        value["checks_status"] = "passed"
        self.assert_code("COMPLETION_EVIDENCE_REQUIRED", lambda: run_state.transition(value, "complete"))

    def test_cleaned_requires_cleanup_evidence(self):
        value = self.manifest("cleanup_pending")
        self.assert_code("CLEANUP_EVIDENCE_REQUIRED", lambda: run_state.transition(value, "cleaned"))

    def test_terminal_state_is_preserved(self):
        value = self.manifest("failed")
        self.assert_code("TERMINAL_STATE", lambda: run_state.transition(value, "working"))
        self.assertFalse(run_state.can_transition("failed", "working"))


if __name__ == "__main__":
    unittest.main()
