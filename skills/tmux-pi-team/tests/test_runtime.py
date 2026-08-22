from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "skills" / "tmux-pi-team" / "scripts" / "pi-team-tmux"
FAKE = ROOT / "tests" / "fixtures" / "fake_tmux.py"


class TmuxRuntimeTests(unittest.TestCase):
    def test_status_exposes_hax_capabilities_and_limitations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"backend": "hax", "runtime": "tmux", "backend_config": {"mode": "interactive"},
                                            "backend_capabilities": {"native_state": False, "steerable": True},
                                            "backend_limitations": ["native_state_unavailable"]}), encoding="utf-8")
            env = os.environ.copy()
            env["PI_TEAM_TMUX_COMMAND"] = str(FAKE)
            result = subprocess.run([sys.executable, str(CLI), "status", "--manifest", str(manifest)], capture_output=True, text=True, env=env, shell=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["backend"], "hax")
            self.assertFalse(payload["backend_capabilities"]["native_state"])
            self.assertIn("native_state_unavailable", payload["backend_limitations"])


if __name__ == "__main__":
    unittest.main()
