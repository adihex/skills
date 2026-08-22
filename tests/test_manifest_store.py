import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).parents[1] / "skills" / "herdr-pi-team" / "scripts" / "manifest_store.py"
spec = importlib.util.spec_from_file_location("manifest_store", MODULE_PATH)
manifest_store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest_store)


class ManifestStoreTests(unittest.TestCase):
    def store(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return manifest_store.ManifestStore(temp.name)

    def test_atomic_write_and_read(self):
        store = self.store()
        value = {"run_id": "run-1", "state": "created"}
        self.assertEqual(store.write(value), value)
        self.assertEqual(store.read(), value)
        self.assertTrue(store.lock_path.exists())
        self.assertEqual(store.manifest_path.stat().st_mode & 0o777, 0o600)

    def test_interrupted_replace_preserves_previous_manifest(self):
        store = self.store()
        store.write({"run_id": "run-1", "state": "ready"})
        with mock.patch.object(manifest_store.os, "replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                store.write({"run_id": "run-1", "state": "working"})
        self.assertEqual(store.read()["state"], "ready")
        self.assertEqual(list(store.directory.glob("manifest.*.tmp")), [])

    def test_redacts_secrets_and_prompt_contents(self):
        store = self.store()
        value = {
            "run_id": "run-1",
            "token": "ghp_123456789012345678901234567890",
            "prompt": "do not persist this prompt",
            "nested": {"message": "sk-12345678901234567890"},
        }
        store.write(value)
        store.append_event({"event": "send", "text": "secret prompt text", "api_key": "AKIA1234567890ABCDEF"})
        manifest = store.read()
        self.assertEqual(manifest["token"], "<redacted>")
        self.assertEqual(manifest["prompt"], "<redacted>")
        self.assertEqual(manifest["nested"]["message"], "<redacted>")
        raw = store.manifest_path.read_text() + store.events_path.read_text()
        self.assertNotIn("ghp_", raw)
        self.assertNotIn("do not persist", raw)
        self.assertNotIn("AKIA", raw)
        self.assertEqual(store.events()[0]["text"], "<redacted>")

    def test_events_are_append_only_json_records(self):
        store = self.store()
        store.append_event({"event": "created", "state": "created"})
        store.append_event({"event": "ready", "state": "ready"})
        self.assertEqual([event["event"] for event in store.events()], ["created", "ready"])


if __name__ == "__main__":
    unittest.main()
