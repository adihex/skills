import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[3]
MODULE_PATH = ROOT / "skills" / "herdr-pi-team" / "scripts" / "herdr_adapter.py"
FAKE = ROOT / "tests" / "fixtures" / "fake_herdr.py"
FAKE_HAX = ROOT / "tests" / "fixtures" / "fake_hax.py"
spec = importlib.util.spec_from_file_location("herdr_adapter", MODULE_PATH)
adapter_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter_module)


class HerdrAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.extension = self.root / "team.ts"
        self.extension.write_text("export {};\n", encoding="utf-8")
        self.brief = self.root / "brief.md"
        self.brief.write_text("brief is fixture data\n", encoding="utf-8")
        self.log = self.root / "commands.jsonl"
        self.env = {"FAKE_HERDR_LOG": str(self.log), "FAKE_HERDR_SCENARIO": "ok"}
        self.old_env = os.environ.copy()
        os.environ.update(self.env)
        self.addCleanup(self.restore_env)
        self.addCleanup(self.temp.cleanup)

    def restore_env(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def adapter(self, scenario="ok", **kwargs):
        os.environ["FAKE_HERDR_SCENARIO"] = scenario
        return adapter_module.HerdrAdapter(
            session="review", herdr_command=str(FAKE), pi_command=sys.executable,
            extension=str(self.extension), poll_interval=0.001, **kwargs,
        )

    def manifest(self):
        return {
            "run_id": "run-1", "label": "worker-1", "workspace_id": "ws-1", "tab_id": "tab-1",
            "pane_id": "pane-1", "cwd": str(self.root), "worktree": str(self.root),
            "branch": "feature", "state": "ready", "last_heartbeat": "2099-01-01T00:00:00Z",
        }

    def codes(self, scenario, callback):
        with self.assertRaises(adapter_module.AdapterError) as context:
            callback(self.adapter(scenario))
        return context.exception.code

    def test_missing_command(self):
        adapter = adapter_module.HerdrAdapter(session="review", herdr_command=str(self.root / "missing"), pi_command=sys.executable, extension=str(self.extension))
        with self.assertRaises(adapter_module.AdapterError) as context:
            adapter.preflight()
        self.assertEqual(context.exception.code, "MUX_UNAVAILABLE")

    def test_session_mismatch(self):
        self.assertEqual(self.codes("session-mismatch", lambda adapter: adapter.preflight()), "SESSION_MISMATCH")

    def test_setup_failure_prevents_worker_launch(self):
        self.assertEqual(self.codes("setup-failure", lambda adapter: adapter.launch(
            run_id="run-1", label="worker-1", cwd=str(self.root), worktree=str(self.root),
            branch="feature", brief_file=str(self.brief),
        )), "SETUP_FAILED")
        commands = [json.loads(line)["op"] for line in self.log.read_text().splitlines()]
        self.assertNotIn("agent start", commands)

    def test_setup_timeout_prevents_worker_launch(self):
        self.assertEqual(self.codes("setup-timeout", lambda adapter: adapter.launch(
            run_id="run-1", label="worker-1", cwd=str(self.root), worktree=str(self.root),
            branch="feature", brief_file=str(self.brief), setup_timeout=0.01,
        )), "SETUP_TIMEOUT")
        commands = [json.loads(line)["op"] for line in self.log.read_text().splitlines()]
        self.assertNotIn("agent start", commands)

    def test_launch_waits_for_setup_and_records_stable_ids(self):
        result = self.adapter().launch(
            run_id="run-1", label="worker-1", cwd=str(self.root), worktree=str(self.root),
            branch="feature", brief_file=str(self.brief),
        )
        self.assertEqual(result["workspace_id"], "ws-1")
        self.assertEqual(result["tab_id"], "tab-1")
        self.assertEqual(result["pane_id"], "pane-1")
        self.assertEqual(result["state"], "ready")
        commands = [json.loads(line)["op"] for line in self.log.read_text().splitlines()]
        self.assertLess(commands.index("workspace setup"), commands.index("agent start"))

    def test_send_requires_enter_and_readback(self):
        result = self.adapter().send(self.manifest(), "literal message", acknowledge="ACKNOWLEDGED")
        self.assertTrue(result["submitted"])
        self.assertTrue(result["acknowledged"])
        commands = [json.loads(line) for line in self.log.read_text().splitlines()]
        ops = [entry["op"] for entry in commands]
        self.assertLess(ops.index("agent send"), ops.index("pane send-keys"))
        key = next(entry for entry in commands if entry["op"] == "pane send-keys")
        self.assertEqual(key["key"], "enter")
        self.assertIn("pane read", ops)

    def test_send_targets_manifest_pane_id(self):
        self.assertEqual(self.codes("missing-pane", lambda adapter: adapter.send(self.manifest(), "text")), "TARGET_NOT_FOUND")

    def test_status_reports_native_state_mismatch(self):
        snapshot = self.adapter("native-mismatch").status(self.manifest())
        self.assertEqual(snapshot["native_state"], "working")
        self.assertTrue(snapshot["state_mismatch"])

    def test_reconcile_detects_missing_pane(self):
        result = self.adapter("missing-pane").reconcile(self.manifest())
        self.assertIn("missing_pane", result["issues"])
        self.assertFalse(result["ok"])

    def test_hax_interactive_uses_shell_backed_command_and_readiness(self):
        adapter = self.adapter(backend_config={"backend": "hax", "provider": "codex", "model": "gpt-5.6-sol", "effort": "high", "auth_source": "hax_managed"},
                               hax_command=str(FAKE_HAX), codex_command=str(FAKE_HAX))
        result = adapter.launch(run_id="run-hax", label="hax-worker", cwd=str(self.root), worktree=str(self.root),
                                branch="feature", brief_file=str(self.brief))
        self.assertEqual(result["backend"], "hax")
        self.assertEqual(result["runtime"], "herdr")
        self.assertEqual(result["state"], "working")
        entries = [json.loads(line) for line in self.log.read_text().splitlines()]
        ops = [entry["op"] for entry in entries]
        self.assertLess(ops.index("pane read"), ops.index("agent send"))
        start = next(entry for entry in entries if entry["op"] == "agent start")
        self.assertIn(str(FAKE_HAX), start["args"])
        self.assertIn("--provider=codex", start["args"])
        self.assertNotIn("--kind", str(entries))

    def test_hax_missing_binary_fails_before_workspace_creation(self):
        adapter = self.adapter(backend_config={"backend": "hax", "provider": "codex", "model": "gpt-5.6-sol", "auth_source": "hax_managed"},
                               hax_command=str(self.root / "missing-hax"), codex_command=str(FAKE_HAX))
        with self.assertRaises(adapter_module.AdapterError) as context:
            adapter.launch(run_id="run-hax", label="hax-worker", cwd=str(self.root), worktree=str(self.root),
                           branch="feature", brief_file=str(self.brief))
        self.assertEqual(context.exception.code, "hax_missing")
        if self.log.exists():
            self.assertNotIn("workspace create", self.log.read_text())

    def test_hax_oneshot_is_direct_and_non_steerable(self):
        adapter = self.adapter(backend_config={"backend": "hax", "provider": "codex", "model": "gpt-5.6-sol", "mode": "oneshot", "auth_source": "hax_managed"},
                               hax_command=str(FAKE_HAX), codex_command=str(FAKE_HAX))
        result = adapter.launch(run_id="run-hax", label="hax-worker", cwd=str(self.root), worktree=str(self.root),
                                branch="feature", brief_file=str(self.brief))
        self.assertEqual(result["state"], "verifying")
        self.assertFalse(result["backend_capabilities"]["steerable"])
        if self.log.exists():
            self.assertNotIn("workspace create", self.log.read_text())

    def test_hax_stop_uses_owned_agent_target(self):
        adapter = self.adapter(backend_config={"backend": "hax", "provider": "codex", "model": "gpt-5.6-sol", "auth_source": "hax_managed"},
                               hax_command=str(FAKE_HAX), codex_command=str(FAKE_HAX))
        manifest = {"backend": "hax", "runtime": "herdr", "pane_id": "pane-1"}
        result = adapter.stop(manifest)
        self.assertTrue(result["stopped"])
        self.assertIn("agent stop", self.log.read_text())



if __name__ == "__main__":
    unittest.main()
