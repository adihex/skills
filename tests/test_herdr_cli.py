import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CLI = ROOT / "skills" / "herdr-pi-team" / "scripts" / "pi-team-herdr"
FAKE_GIT = ROOT / "tests" / "fixtures" / "fake_git.py"
FAKE_GH = ROOT / "tests" / "fixtures" / "fake_gh.py"
FAKE_HERDR = ROOT / "tests" / "fixtures" / "fake_herdr.py"


class HerdrCliTests(unittest.TestCase):
    def test_complete_command_invokes_git_review_checks_and_state_machine(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            worktree = root / "worktree"
            worktree.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "run_id": "run-cli", "label": "worker", "workspace_id": "ws-1", "tab_id": "tab-1",
                "pane_id": "pane-1", "cwd": str(worktree), "worktree": str(worktree),
                "branch": "feature/test", "upstream": "origin/feature/test", "state": "review_pending",
                "head_sha": "abc123", "pushed_sha": "abc123", "pr_number": None,
                "review_status": "pending", "checks_status": "pending", "last_heartbeat": "2099-01-01T00:00:00Z", "blocker": None,
            }), encoding="utf-8")
            report = root / "report.txt"
            report.write_text("\n".join([
                "RESULT: complete", f"WORKTREE: {worktree}", "BRANCH: feature/test", "COMMIT: abc123",
                "PUSHED: abc123", "PR: 7", "CODERABBIT: approved", "CHECKS: passed", "CLEANUP: verified",
                "BLOCKER: none", "EVIDENCE: cli-test",
            ]) + "\n", encoding="utf-8")
            command = [sys.executable, str(CLI), "--git-command", str(FAKE_GIT), "--gh-command", str(FAKE_GH),
                       "complete", "--manifest", str(manifest), "--report", str(report), "--repository", "org/repo", "--pr", "7"]
            result = subprocess.run(command, capture_output=True, text=True, shell=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "complete")
            self.assertEqual(json.loads(manifest.read_text())["state"], "complete")

    def test_reconcile_accepts_run_id_and_reports_missing_final_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            worktree = root / "worktree"
            worktree.mkdir()
            manifest_dir = root / "manifests"
            manifest_dir.mkdir()
            manifest = manifest_dir / "run.json"
            manifest.write_text(json.dumps({
                "run_id": "run-reconcile", "label": "worker", "workspace_id": "ws-1", "tab_id": "tab-1",
                "pane_id": "pane-1", "cwd": str(worktree), "worktree": str(worktree), "branch": "feature/test",
                "state": "review_pending", "last_heartbeat": "2099-01-01T00:00:00Z", "review_status": "pending", "checks_status": "pending",
            }), encoding="utf-8")
            extension = root / "team.ts"
            extension.write_text("export {};\n", encoding="utf-8")
            command = [sys.executable, str(CLI), "--session", "review", "--herdr-command", str(FAKE_HERDR),
                       "--git-command", str(FAKE_GIT), "--pi-command", sys.executable, "--extension", str(extension),
                       "reconcile", "--run", "run-reconcile", "--manifest-dir", str(manifest_dir)]
            result = subprocess.run(command, capture_output=True, text=True, shell=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("REPORT_MISSING", payload["issues"])
            self.assertIn("state_machine", payload)


if __name__ == "__main__":
    unittest.main()
