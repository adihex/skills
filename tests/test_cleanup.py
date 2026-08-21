import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "skills" / "herdr-pi-team" / "scripts" / "cleanup.py"
spec = importlib.util.spec_from_file_location("cleanup", MODULE_PATH)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def git(cwd, *args, check=True):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=check, shell=False)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.main = self.root / "main"
        self.remote = self.root / "remote.git"
        self.worktree = self.root / "workers" / "worker-1"
        self.main.mkdir()
        self.worktree.parent.mkdir()
        subprocess.run(["git", "init", "--bare", str(self.remote)], check=True, capture_output=True, shell=False)
        git(self.main, "init")
        git(self.main, "config", "user.email", "test@example.invalid")
        git(self.main, "config", "user.name", "Test User")
        (self.main / "README.md").write_text("base\n", encoding="utf-8")
        git(self.main, "add", "README.md")
        git(self.main, "commit", "-m", "initial")
        git(self.main, "branch", "-M", "main")
        git(self.main, "remote", "add", "origin", str(self.remote))
        git(self.main, "push", "-u", "origin", "main")
        git(self.main, "worktree", "add", "-b", "feature/worker", str(self.worktree), "origin/main")
        git(self.worktree, "branch", "--set-upstream-to=origin/main")
        self.addCleanup(self.temp.cleanup)

    def manifest(self, **changes):
        value = {
            "run_id": "run-1", "owner_run_id": "run-1", "workspace_id": "ws-1",
            "worktree": str(self.worktree), "repo_root": str(self.main), "state": "complete",
        }
        value.update(changes)
        return value

    def manager(self, inventory=None, **kwargs):
        return cleanup.CleanupManager(
            worktree_root=str(self.root / "workers"), main_checkout=str(self.main),
            current_cwd=str(self.root / "operator"), process_inspector=lambda: inventory if inventory is not None else [],
            workspace_closer=lambda _: None, **kwargs,
        )

    def test_clean_synchronized_worktree_is_dry_run_by_default(self):
        manager = self.manager()
        result = manager.cleanup(self.manifest())
        self.assertEqual(result["action"], "remove")
        self.assertTrue(result["dry_run"])
        self.assertTrue(self.worktree.exists())

    def test_dirty_worktree_is_refused(self):
        (self.worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result = self.manager().plan(self.manifest())
        self.assertEqual(result["action"], "refuse")
        self.assertIn("dirty_worktree", result["issues"])

    def test_unpushed_commit_is_refused(self):
        (self.worktree / "new.txt").write_text("new\n", encoding="utf-8")
        git(self.worktree, "add", "new.txt")
        git(self.worktree, "commit", "-m", "local")
        result = self.manager().plan(self.manifest())
        self.assertIn("unsynchronized_worktree", result["issues"])

    def test_missing_upstream_is_refused(self):
        git(self.worktree, "branch", "--unset-upstream")
        result = self.manager().plan(self.manifest())
        self.assertIn("unsynchronized_worktree", result["issues"])

    def test_missing_workspace_is_refused(self):
        result = self.manager().plan(self.manifest(workspace_id=None))
        self.assertIn("missing_workspace", result["issues"])

    def test_stale_nx_process_is_owned_and_only_owned_process_is_stopped(self):
        inventory = [
            {"pid": 101, "kind": "nx", "cwd": str(self.worktree), "owned": True},
            {"pid": 102, "kind": "watchman", "cwd": str(self.worktree), "owned": True},
        ]
        stopped = []
        manager = self.manager(inventory, process_stopper=lambda process: stopped.append(process["pid"]))
        planned = manager.plan(self.manifest())
        self.assertEqual([p["pid"] for p in planned["processes"]], [101])
        result = manager.cleanup(self.manifest(), confirm=True)
        self.assertEqual(result["action"], "cleaned")
        self.assertEqual(stopped, [101])
        self.assertFalse(self.worktree.exists())

    def test_current_checkout_is_never_removed(self):
        manifest = self.manifest(worktree=str(self.main))
        result = cleanup.CleanupManager(
            worktree_root=str(self.root), main_checkout=str(self.main), current_cwd=str(self.root / "operator"),
            process_inspector=lambda: [], workspace_closer=lambda _: None,
        ).plan(manifest)
        self.assertIn("main_checkout", result["issues"])
        self.assertEqual(result["action"], "refuse")
        self.assertTrue(self.main.exists())

    def test_repeated_cleanup_is_idempotent(self):
        manifest = self.manifest()
        manager = self.manager()
        first = manager.cleanup(manifest, confirm=True)
        self.assertEqual(first["action"], "cleaned")
        second = manager.cleanup(manifest, confirm=True)
        self.assertEqual(second["action"], "noop")

    def test_interrupted_cleanup_preserves_cleanup_pending_manifest(self):
        manifest = self.manifest()
        writes = []
        manager = self.manager(manifest_writer=lambda value: writes.append(value["state"]))
        result = manager.cleanup(manifest, confirm=True, remove_worktree=lambda _: (_ for _ in ()).throw(RuntimeError("interrupted")))
        self.assertEqual(result["action"], "failed")
        self.assertEqual(manifest["state"], "cleanup_pending")
        self.assertEqual(writes, ["cleanup_pending", "cleanup_pending"])
        self.assertTrue(self.worktree.exists())

    def test_inconclusive_process_inspection_refuses_cleanup(self):
        manager = cleanup.CleanupManager(
            worktree_root=str(self.root / "workers"), main_checkout=str(self.main), current_cwd=str(self.root / "operator"),
            process_inspector=lambda: None, workspace_closer=lambda _: None,
        )
        result = manager.plan(self.manifest())
        self.assertIn("process_inspection_inconclusive", result["issues"])

    def test_watch_filters_to_owner_and_stops_after_cleanup(self):
        own_path = self.root / "run-1.json"
        other_path = self.root / "run-2.json"
        own_path.write_text(json.dumps({"run_id": "run-1", "state": "complete"}), encoding="utf-8")
        other_path.write_text(json.dumps({"run_id": "run-2", "state": "complete"}), encoding="utf-8")
        seen = []

        class FakeManager:
            def cleanup(self, manifest, **kwargs):
                seen.append(manifest["run_id"])
                return {"action": "cleaned"}

            def plan(self, manifest, **kwargs):
                return {"action": "remove"}

        result = cleanup.watch_once([str(own_path), str(other_path)], run_id="run-1", manager_factory=lambda _: FakeManager(), cleanup_enabled=True)
        self.assertEqual(result["tracked"], 1)
        self.assertEqual(result["remaining"], 0)
        self.assertEqual(seen, ["run-1"])
        self.assertTrue(Path(str(own_path) + ".cleanup.lock").exists())


if __name__ == "__main__":
    unittest.main()
