from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hax_backend", ROOT / "scripts" / "hax_backend.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class HaxBackendTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ROOT / "tests" / "fixtures" / "fake_hax.py"
        self.backend = MODULE.HaxBackend(hax_command=str(self.fixture), codex_command=str(self.fixture))

    def config(self, **overrides):
        value = {"backend": "hax", "provider": "codex", "model": "gpt-5.6-sol", "effort": "high",
                 "auth_source": "hax_managed", **overrides}
        return MODULE.BackendConfig.from_mapping(value)

    def test_omitted_backend_selects_pi(self):
        config = MODULE.BackendConfig.from_mapping({})
        self.assertEqual(config.backend, "pi")
        self.assertTrue(config.steerable)

    def test_hax_defaults_provider_and_codex_auth_source(self):
        config = MODULE.BackendConfig.from_mapping({"backend": "hax", "model": "gpt-5.6-sol"})
        self.assertEqual(config.provider, "codex")
        self.assertEqual(config.auth_source, "codex_cli")

    def test_explicit_empty_provider_is_rejected(self):
        with self.assertRaisesRegex(MODULE.HaxConfigError, "provider") as context:
            MODULE.BackendConfig.from_mapping({"backend": "hax", "provider": None, "model": "m", "auth_source": "hax_managed"})
        self.assertEqual(context.exception.code, "PROVIDER_MISSING")

    def test_hax_requires_model(self):
        with self.assertRaisesRegex(MODULE.HaxConfigError, "model") as context:
            MODULE.BackendConfig.from_mapping({"backend": "hax", "provider": "codex", "auth_source": "hax_managed"})
        self.assertEqual(context.exception.code, "MODEL_MISSING")

    def test_unsupported_effort_and_backend_fail(self):
        for value, code in [({"backend": "hax", "provider": "codex", "model": "m", "effort": "turbo", "auth_source": "hax_managed"}, "EFFORT_UNSUPPORTED"),
                            ({"backend": "warp", "model": "m"}, "BACKEND_UNSUPPORTED")]:
            with self.subTest(code=code), self.assertRaises(MODULE.HaxConfigError) as context:
                MODULE.BackendConfig.from_mapping(value)
            self.assertEqual(context.exception.code, code)

    def test_exact_interactive_and_oneshot_argv(self):
        interactive = self.backend.build_command(self.config())
        self.assertEqual(interactive, [str(self.fixture), "--provider=codex", "--model=gpt-5.6-sol", "--effort=high"])
        oneshot = self.backend.build_command(self.config(mode="oneshot"), prompt="keep this prompt local")
        self.assertEqual(oneshot[-2:], ["-p", "keep this prompt local"])
        self.assertNotIn("keep this prompt local", self.backend.redacted_command(oneshot))
        self.assertEqual(self.backend.redacted_command(oneshot)[-1], "<prompt>")

    def test_oneshot_requires_prompt_and_is_not_steerable(self):
        config = self.config(mode="oneshot")
        self.assertFalse(config.steerable)
        with self.assertRaises(MODULE.HaxConfigError) as context:
            self.backend.build_command(config)
        self.assertEqual(context.exception.code, "PROMPT_MISSING")

    def test_preflight_ready_without_reading_auth_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "auth.json"
            auth.write_text('{"token":"must-not-be-read-by-test"}', encoding="utf-8")
            backend = MODULE.HaxBackend(hax_command=str(self.fixture), codex_command=str(self.fixture), auth_path=auth)
            result = backend.preflight(self.config(auth_source="codex_cli"))
        self.assertEqual(result["code"], "ready")
        self.assertEqual(result["hax_version"], "hax v0.3.0")
        self.assertNotIn("token", str(result))

    def test_missing_binary_and_auth_are_specific(self):
        with self.assertRaises(MODULE.HaxPreflightError) as missing:
            MODULE.HaxBackend(hax_command="/definitely/missing/hax", codex_command=str(self.fixture)).preflight(self.config())
        self.assertEqual(missing.exception.code, "hax_missing")
        with tempfile.TemporaryDirectory() as temp:
            backend = MODULE.HaxBackend(hax_command=str(self.fixture), codex_command=str(self.fixture), auth_path=Path(temp) / "missing")
            with self.assertRaises(MODULE.HaxPreflightError) as auth:
                backend.preflight(self.config(auth_source="codex_cli"))
        self.assertEqual(auth.exception.code, "codex_auth_missing")

    def test_version_and_outcome_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            auth = Path(temp) / "auth"
            auth.write_text("placeholder", encoding="utf-8")
            old = dict(os.environ)
            try:
                os.environ["FAKE_HAX_VERSION"] = "hax v0.2.0"
                with self.assertRaises(MODULE.HaxPreflightError) as version:
                    MODULE.HaxBackend(hax_command=str(self.fixture), codex_command=str(self.fixture), auth_path=auth).preflight(self.config(auth_source="codex_cli"))
            finally:
                os.environ.clear()
                os.environ.update(old)
        self.assertEqual(version.exception.code, "hax_version_unsupported")
        self.assertEqual(self.backend.classify(stderr="HTTP 429 quota exhausted", returncode=1), {"state": "blocked_external", "code": "HTTP_429"})
        self.assertEqual(self.backend.classify(stderr="HTTP 403 forbidden", returncode=1)["state"], "blocked")
        self.assertEqual(self.backend.classify(returncode=0)["code"], "process_exit_0")
        self.assertEqual(self.backend.classify(returncode=1)["code"], "process_exit_nonzero")

    def test_oneshot_captures_streams_and_classifies_exit(self):
        result = self.backend.run_oneshot(self.config(mode="oneshot"), prompt="hello", cwd=str(ROOT))
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["state"], "verifying")
        self.assertIn("FAKE_HAX_ONESHOT_OK", result["stdout"])
        self.assertNotIn("hello", str(result["command"]))

    def test_capabilities_and_manifest_fields_are_safe(self):
        config = self.config()
        capabilities = self.backend.capabilities(config, runtime="tmux")
        fields = config.manifest_fields(runtime="tmux", capabilities=capabilities)
        self.assertEqual(fields["backend"], "hax")
        self.assertEqual(fields["runtime"], "tmux")
        self.assertFalse(fields["backend_capabilities"]["native_state"])
        self.assertIsNone(fields["backend_session_id"])
        self.assertNotIn("auth.json", str(fields))


if __name__ == "__main__":
    unittest.main()
