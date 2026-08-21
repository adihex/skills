import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "skills" / "herdr-pi-team" / "scripts" / "dispatch_policy.py"
spec = importlib.util.spec_from_file_location("dispatch_policy", MODULE_PATH)
policy_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = policy_module
spec.loader.exec_module(policy_module)


class DispatchPolicyTests(unittest.TestCase):
    def test_defaults_bound_active_workers_and_setup(self):
        policy = policy_module.DispatchPolicy()
        self.assertEqual(policy.max_active, 4)
        self.assertEqual(policy.setup_concurrency, 2)
        self.assertEqual(len(policy.launch_plan(4)), 4)
        self.assertEqual(policy.launch_plan(4)[1]["delay_seconds"], 1.0)

    def test_backpressure_reasons_are_deterministic(self):
        policy = policy_module.DispatchPolicy()
        for kwargs, code in [
            ({"active_workers": 4, "setup_workers": 0}, "MAX_ACTIVE"),
            ({"active_workers": 1, "setup_workers": 2}, "SETUP_BACKPRESSURE"),
            ({"active_workers": 1, "setup_workers": 0, "memory_ratio": 0.9}, "MEMORY_BACKPRESSURE"),
        ]:
            with self.assertRaises(policy_module.DispatchRefused) as context:
                policy.admit(**kwargs)
            self.assertEqual(context.exception.code, code)

    def test_admission_returns_budgets(self):
        result = policy_module.DispatchPolicy().admit(active_workers=0, setup_workers=0)
        self.assertTrue(result["admitted"])
        self.assertEqual(result["turn_budget"], 30)

    def test_backend_specific_limits_and_quota_block(self):
        policy = policy_module.DispatchPolicy()
        self.assertEqual(policy.admit_backend(backend="hax", active_workers=0, setup_workers=0)["backend_limit"], 2)
        with self.assertRaises(policy_module.DispatchRefused) as limit:
            policy.admit_backend(backend="hax", active_workers=2, setup_workers=0)
        self.assertEqual(limit.exception.code, "MAX_ACTIVE_HAX")
        with self.assertRaises(policy_module.DispatchRefused) as quota:
            policy.admit_backend(backend="hax", active_workers=0, setup_workers=0, quota_blocked=True)
        self.assertEqual(quota.exception.code, "HAX_QUOTA_BLOCKED")



if __name__ == "__main__":
    unittest.main()
