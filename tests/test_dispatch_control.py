import json
import os
import tempfile
import unittest
from pathlib import Path

from scripts.dispatch_control import LaunchReservation, policy_module


class DispatchControlTests(unittest.TestCase):
    def test_active_manifests_enforce_backend_limit_before_reserving(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for index in range(2):
                (root / f"hax-{index}.json").write_text(json.dumps({"backend": "hax", "state": "working", "backend_config": {"provider": "codex"}}), encoding="utf-8")
            with self.assertRaises(policy_module.DispatchRefused) as raised:
                LaunchReservation(root, "hax").acquire()
            self.assertEqual(raised.exception.code, "MAX_ACTIVE_HAX")

    def test_reservation_is_visible_and_released(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reservation = LaunchReservation(root, "pi")
            self.assertTrue(reservation.acquire()["admitted"])
            self.assertEqual(len(list(root.glob(".launching-*.json"))), 1)
            reservation.release()
            self.assertEqual(list(root.glob(".launching-*.json")), [])

    def test_memory_pressure_refuses_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            previous = os.environ.get("PI_TEAM_MEMORY_RATIO")
            os.environ["PI_TEAM_MEMORY_RATIO"] = "0.9"
            try:
                with self.assertRaises(policy_module.DispatchRefused) as raised:
                    LaunchReservation(temp, "pi").acquire()
                self.assertEqual(raised.exception.code, "MEMORY_BACKPRESSURE")
            finally:
                if previous is None:
                    os.environ.pop("PI_TEAM_MEMORY_RATIO", None)
                else:
                    os.environ["PI_TEAM_MEMORY_RATIO"] = previous


if __name__ == "__main__":
    unittest.main()
