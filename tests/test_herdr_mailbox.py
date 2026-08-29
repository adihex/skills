import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CLI = ROOT / "skills" / "herdr-pi-team" / "scripts" / "pi-team-herdr"
MAILBOX_MODULE = ROOT / "skills" / "herdr-pi-team" / "scripts" / "mailbox.py"
spec = importlib.util.spec_from_file_location("herdr_mailbox", MAILBOX_MODULE)
mailbox_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mailbox_module)


FAKE_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ["--session", "named"]: args = args[2:]
state_path = Path(os.environ["HERDR_STATE"])
state = json.loads(state_path.read_text())
def save(): state_path.write_text(json.dumps(state))
def out(value): print(json.dumps({"result": value}))
def view(worker):
    calls = state.get("list_calls", 0)
    states = worker.get("states", ["working"])
    status = states[min(max(calls - 1, 0), len(states) - 1)]
    return {"name": worker["name"], "agent": "pi", "workspace_id": worker["workspace"],
            "pane_id": worker["pane"], "tab_id": "tab", "agent_status": status,
            "state_change_seq": calls, "agent_session": {"kind": "path", "value": worker["session"]} if worker.get("session") else None}
if args == ["--version"]: print("herdr mailbox fake")
elif args[:2] == ["workspace", "create"]: out({"workspace_id": "w-new"})
elif args[:2] == ["pane", "list"]: out({"panes": [{"pane_id": "w-new:p1", "workspace_id": "w-new", "tab_id": "tab"}]})
elif args[:2] == ["agent", "start"]: out({"name": args[2], "pane_id": "w-new:p1", "workspace_id": "w-new", "tab_id": "tab", "agent_status": "idle"})
elif args[:2] == ["agent", "prompt"]: out({"name": args[2], "pane_id": "w-new:p1", "workspace_id": "w-new", "agent_status": "working"})
elif args[:2] == ["agent", "list"]:
    state["list_calls"] = state.get("list_calls", 0) + 1; save()
    out({"agents": [view(worker) for worker in state.get("workers", [])]})
elif args[:2] == ["agent", "get"]:
    worker = next(worker for worker in state.get("workers", []) if worker["name"] == args[2]); out(view(worker))
else: print(json.dumps({"error": {"code": "unknown", "args": args}})); sys.exit(1)
'''


class HerdrMailboxTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake = self.root / "herdr"
        self.fake.write_text(FAKE_HERDR, encoding="utf-8")
        self.fake.chmod(0o755)
        self.state = self.root / "state.json"
        self.mailbox_path = self.root / "run" / "mailbox.json"
        self.extension = self.root / "team.ts"
        self.extension.write_text("export {};\n", encoding="utf-8")
        self.brief = self.root / "brief.md"
        self.brief.write_text("Review only your owned scope.\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def session(self, name, result):
        path = self.root / f"{name}.jsonl"
        path.write_text(json.dumps({"message": {"role": "assistant", "content": [{"type": "text", "text": result}]}}) + "\n", encoding="utf-8")
        return str(path)

    def configure(self, workers):
        self.state.write_text(json.dumps({"list_calls": 0, "workers": workers}), encoding="utf-8")

    def store(self):
        return mailbox_module.MailboxStore(self.mailbox_path)

    def register(self, workers):
        store = self.store()
        for worker in workers:
            store.register(run_id="run-1", name=worker["name"], workspace_id=worker["workspace"], pane_id=worker["pane"])

    def invoke(self, *args):
        env = {**os.environ, "HERDR_STATE": str(self.state)}
        return subprocess.run([sys.executable, str(CLI), "--session", "named", "--herdr-command", str(self.fake),
                               "--pi-command", sys.executable, "--extension", str(self.extension), *args],
                              capture_output=True, text=True, env=env, timeout=5)

    def worker(self, name, states, result=None, workspace=None, pane=None):
        return {"name": name, "workspace": workspace or f"w-{name}", "pane": pane or f"p-{name}",
                "states": states, "session": self.session(name, result) if result is not None else None}

    def test_launch_registers_stable_identity_in_durable_mailbox(self):
        self.configure([])
        result = self.invoke("launch", "--name", "worker", "--cwd", str(self.root), "--new-workspace",
                             "--run-id", "run-1", "--mailbox", str(self.mailbox_path),
                             "--brief-file", str(self.brief), "--verify-working")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["registration"]["workspace_id"], "w-new")
        self.assertEqual(payload["registration"]["pane_id"], "w-new:p1")
        manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
        self.assertEqual(manifest["state"], "working")
        self.assertTrue(manifest["dispatch_admission"]["admitted"])
        self.assertEqual(self.store().workers()[0]["name"], "worker")

    def test_await_any_returns_each_result_once_without_parent_polling(self):
        workers = [self.worker("alpha", ["done"], "alpha found the race"),
                   self.worker("beta", ["working", "working", "done"], "beta fixed the test")]
        self.configure(workers); self.register(workers)

        first = self.invoke("await", "--mailbox", str(self.mailbox_path), "--any", "--timeout", "1",
                            "--poll-min", "0.01", "--poll-max", "0.02")
        self.assertEqual(first.returncode, 0, first.stderr)
        first_payload = json.loads(first.stdout)
        self.assertEqual([event["worker"] for event in first_payload["events"]], ["alpha"])
        self.assertEqual(first_payload["events"][0]["result"], "alpha found the race")

        second = self.invoke("await", "--mailbox", str(self.mailbox_path), "--any", "--timeout", "1",
                             "--poll-min", "0.01", "--poll-max", "0.02")
        self.assertEqual(second.returncode, 0, second.stderr)
        second_payload = json.loads(second.stdout)
        self.assertEqual([event["worker"] for event in second_payload["events"]], ["beta"])
        self.assertEqual(second_payload["events"][0]["result"], "beta fixed the test")

        empty = self.invoke("inbox", "--mailbox", str(self.mailbox_path))
        self.assertEqual(json.loads(empty.stdout), {"events": [], "count": 0})
        self.assertEqual(len(self.mailbox_path.with_name("mailbox.json.events.jsonl").read_text().splitlines()), 2)

    def test_await_all_returns_results_together_after_every_worker_finishes(self):
        workers = [self.worker("alpha", ["done"], "alpha result"),
                   self.worker("beta", ["working", "done"], "beta result")]
        self.configure(workers); self.register(workers)
        result = self.invoke("await", "--mailbox", str(self.mailbox_path), "--all", "--timeout", "1",
                             "--poll-min", "0.01", "--poll-max", "0.02")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["waitSatisfied"])
        self.assertNotIn("completed", payload)
        self.assertEqual({event["worker"]: event["result"] for event in payload["events"]},
                         {"alpha": "alpha result", "beta": "beta result"})

    def test_inbox_observes_once_and_delivers_without_a_prior_await(self):
        workers = [self.worker("alpha", ["done"], "arrived while parent worked")]
        self.configure(workers); self.register(workers)
        result = self.invoke("inbox", "--mailbox", str(self.mailbox_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["events"][0]["result"], "arrived while parent worked")
        self.assertEqual(json.loads(self.state.read_text())["list_calls"], 1)

    def test_inbox_delivers_durable_pending_event_when_herdr_is_unavailable(self):
        workers = [self.worker("alpha", ["done"], "durable result")]
        self.configure(workers); self.register(workers)
        store = self.store()
        store.append_event(store.workers()[0], kind="worker.turn_finished", outcome="done",
                           native_status="done", session_artifact=workers[0]["session"])
        self.fake.unlink()
        result = self.invoke("inbox", "--mailbox", str(self.mailbox_path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["events"][0]["result"], "durable result")

    def test_blocked_worker_is_delivered_as_intervention_not_completion(self):
        workers = [self.worker("alpha", ["blocked"])]
        self.configure(workers); self.register(workers)
        result = self.invoke("await", "--mailbox", str(self.mailbox_path), "--timeout", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        event = json.loads(result.stdout)["events"][0]
        self.assertEqual((event["kind"], event["outcome"]), ("worker.blocked", "blocked"))
        self.assertNotIn("result", event)

    def test_stable_identity_conflict_is_refused(self):
        registered = self.worker("alpha", ["done"], "do not deliver", workspace="expected", pane="expected-pane")
        observed = {**registered, "workspace": "other", "pane": "other-pane"}
        self.configure([observed]); self.register([registered])
        result = self.invoke("await", "--mailbox", str(self.mailbox_path), "--timeout", "0")
        self.assertEqual(result.returncode, 3)
        self.assertIn("WORKER_IDENTITY_CONFLICT", result.stderr)
        self.assertFalse(self.mailbox_path.with_name("mailbox.json.events.jsonl").exists())

    def test_adaptive_wait_is_bounded_and_times_out_with_pending_identity(self):
        workers = [self.worker("alpha", ["working"])]
        self.configure(workers); self.register(workers)
        started = time.monotonic()
        # Warm the fake Herdr binary once to avoid cold-start (0.4s+) counting against the tight deadline.
        # Then await with a slightly larger window so at least 2 polls occur even on slower macOS.
        try:
            import subprocess as _sp
            _sp.run([str(self.fake), "--version"], capture_output=True, timeout=2)
        except Exception:
            pass
        result = self.invoke("await", "--mailbox", str(self.mailbox_path), "--timeout", "0.45",
                             "--poll-min", "0.02", "--poll-max", "0.05")
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 2)
        self.assertIn("WAIT_TIMEOUT", result.stderr)
        self.assertIn("alpha", result.stderr)
        calls = json.loads(self.state.read_text())["list_calls"]
        self.assertGreaterEqual(calls, 2)
        self.assertLessEqual(calls, 12)
        self.assertLess(elapsed, 2)

    def test_concurrent_duplicate_observations_create_one_event(self):
        workers = [self.worker("alpha", ["done"], "one result")]
        self.configure(workers); self.register(workers)
        script = (
            "import importlib.util,sys;"
            "s=importlib.util.spec_from_file_location('m',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
            "x=m.MailboxStore(sys.argv[2]);w=x.workers()[0];"
            "x.append_event(w,kind='worker.turn_finished',outcome='done',native_status='done',session_artifact=sys.argv[3])"
        )
        processes = [subprocess.Popen([sys.executable, "-c", script, str(MAILBOX_MODULE), str(self.mailbox_path), workers[0]["session"]]) for _ in range(8)]
        self.assertEqual([process.wait(timeout=5) for process in processes], [0] * 8)
        lines = self.mailbox_path.with_name("mailbox.json.events.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 1)
        first = self.store().deliver(consumer="parent")
        second = self.store().deliver(consumer="parent")
        reviewer = self.store().deliver(consumer="reviewer")
        self.assertEqual((len(first), len(second), len(reviewer)), (1, 0, 1))


if __name__ == "__main__":
    unittest.main()
