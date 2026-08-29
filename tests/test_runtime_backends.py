from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMUX = ROOT / "skills" / "tmux-pi-team" / "scripts" / "pi-team-tmux"
WEZTERM = ROOT / "skills" / "wezterm-pi-team" / "scripts" / "pi-team-pane"
FAKE_HAX = ROOT / "tests" / "fixtures" / "fake_hax.py"
FAKE_TMUX = ROOT / "tests" / "fixtures" / "fake_tmux.py"
FAKE_WEZTERM = ROOT / "tests" / "fixtures" / "fake_wezterm.py"


class RuntimeBackendTests(unittest.TestCase):
    def env(self, **extra):
        value = os.environ.copy()
        value.update(extra)
        return value

    def run_cli(self, script, args, env):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=env, shell=False)

    def hax_args(self):
        return ["--backend", "hax", "--provider", "codex", "--model", "gpt-5.6-sol", "--effort", "high",
                "--auth-source", "hax_managed", "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)]

    def test_tmux_hax_launch_records_backend_and_enter_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brief = root / "brief.md"
            brief.write_text("tmux task\n", encoding="utf-8")
            log = root / "tmux.log"
            result = self.run_cli(TMUX, ["launch", "--name", "worker", "--brief-file", str(brief), "--cwd", str(root),
                                         "--manifest", str(root / "manifest.json"), *self.hax_args()],
                                  self.env(PI_TEAM_TMUX_COMMAND=str(FAKE_TMUX), FAKE_TMUX_LOG=str(log)))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["backend"], "hax")
            entries = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertLess(next(i for i, row in enumerate(entries) if row[0] == "capture-pane"),
                            next(i for i, row in enumerate(entries) if row[0] == "send-keys" and "-l" in row))
            self.assertEqual([row[-1] for row in entries if row[0] == "send-keys"][-1], "Enter")

    def test_wezterm_hax_launch_records_fenced_send(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brief = root / "brief.md"
            brief.write_text("wez task\n", encoding="utf-8")
            log = root / "wez.log"
            result = self.run_cli(WEZTERM, ["launch", "--name", "worker", "--brief-file", str(brief), "--cwd", str(root),
                                            "--manifest", str(root / "manifest.json"), *self.hax_args()],
                                  self.env(PI_TEAM_WEZTERM_COMMAND=str(FAKE_WEZTERM), WEZTERM_PANE="1", FAKE_WEZTERM_LOG=str(log)))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["backend"], "hax")
            self.assertTrue(payload["hax_submission"]["fenced"])
            commands = [json.loads(line) for line in log.read_text().splitlines()]
            names = [row[0] for row in commands]
            self.assertLess(names.index("get-text"), names.index("send-text", names.index("get-text") + 1))
            self.assertIn("--no-paste", commands[-1])

    def test_missing_hax_fails_before_tmux_pane_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brief = root / "brief.md"
            brief.write_text("task\n", encoding="utf-8")
            log = root / "tmux.log"
            args = ["launch", "--name", "worker", "--brief-file", str(brief), "--cwd", str(root),
                    "--hax-command", str(root / "missing-hax"), "--codex-command", str(FAKE_HAX), "--auth-source", "hax_managed",
                    "--model", "gpt-5.6-sol", "--backend", "hax"]
            result = self.run_cli(TMUX, args, self.env(PI_TEAM_TMUX_COMMAND=str(FAKE_TMUX), FAKE_TMUX_LOG=str(log)))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('"code": "hax_missing"', result.stderr)
            self.assertFalse(log.exists())

    def test_pi_remains_default_in_both_runtimes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brief = root / "brief.md"
            brief.write_text("pi task\n", encoding="utf-8")
            tmux = self.run_cli(TMUX, ["launch", "--name", "pi-worker", "--brief-file", str(brief), "--cwd", str(root)],
                                self.env(PI_TEAM_TMUX_COMMAND=str(FAKE_TMUX)))
            wez = self.run_cli(WEZTERM, ["launch", "--name", "pi-worker", "--brief-file", str(brief), "--cwd", str(root)],
                               self.env(PI_TEAM_WEZTERM_COMMAND=str(FAKE_WEZTERM), WEZTERM_PANE="1"))
            self.assertEqual(tmux.returncode, 0, tmux.stderr)
            self.assertEqual(wez.returncode, 0, wez.stderr)
            self.assertEqual(json.loads(tmux.stdout)["backend"], "pi")
            self.assertEqual(json.loads(wez.stdout)["backend"], "pi")

    def test_tmux_oneshot_is_direct_and_non_steerable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            brief = root / "brief.md"
            brief.write_text("one shot\n", encoding="utf-8")
            log = root / "tmux.log"
            result = self.run_cli(TMUX, ["launch", "--name", "worker", "--brief-file", str(brief), "--cwd", str(root),
                                         "--mode", "oneshot", "--model", "gpt-5.6-sol", "--auth-source", "hax_managed", "--hax-command", str(FAKE_HAX),
                                         "--codex-command", str(FAKE_HAX), "--backend", "hax"],
                                  self.env(PI_TEAM_TMUX_COMMAND=str(FAKE_TMUX), FAKE_TMUX_LOG=str(log)))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "verifying")
            self.assertFalse(log.exists())
            self.assertEqual(payload["backend_capabilities"]["steerable"], False)

    def test_backend_owned_cleanup_requires_common_worktree_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workers = root / "workers"
            worktree = workers / "worker"
            main = root / "main"
            worktree.mkdir(parents=True)
            main.mkdir()
            manifest = root / "manifest.json"
            common = {"run_id": "run-1", "owner_run_id": "run-1", "state": "working", "workspace_id": "tmux",
                      "worktree": str(worktree), "repo_root": str(main), "backend": "hax",
                      "backend_config": {"provider": "codex", "model": "gpt-5.6-sol", "effort": "high", "mode": "interactive", "auth_source": "hax_managed"}}
            manifest.write_text(json.dumps({**common, "runtime": "tmux", "pane_id": "%1"}), encoding="utf-8")
            tmux_log = root / "tmux-stop.log"
            scope = ["--worktree-root", str(workers), "--main-checkout", str(main)]
            tmux = self.run_cli(TMUX, ["cleanup", "--manifest", str(manifest), "--confirm", *scope, "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)],
                                self.env(PI_TEAM_TMUX_COMMAND=str(FAKE_TMUX), FAKE_TMUX_LOG=str(tmux_log)))
            self.assertEqual(tmux.returncode, 3, tmux.stderr)
            self.assertIn("CLEANUP_REFUSED", tmux.stderr)
            self.assertFalse(tmux_log.exists())

            manifest.write_text(json.dumps({**common, "runtime": "wezterm", "pane_id": 2}), encoding="utf-8")
            wez_log = root / "wez-stop.log"
            wez = self.run_cli(WEZTERM, ["cleanup", "--manifest", str(manifest), "--confirm", *scope, "--hax-command", str(FAKE_HAX), "--codex-command", str(FAKE_HAX)],
                               self.env(PI_TEAM_WEZTERM_COMMAND=str(FAKE_WEZTERM), FAKE_WEZTERM_PANES="coexist", WEZTERM_PANE="1", FAKE_WEZTERM_LOG=str(wez_log)))
            self.assertEqual(wez.returncode, 3, wez.stderr)
            self.assertIn("CLEANUP_REFUSED", wez.stderr)
            self.assertFalse(wez_log.exists())



if __name__ == "__main__":
    unittest.main()
