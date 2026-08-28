import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
CLI = ROOT / "skills" / "herdr-pi-team" / "scripts" / "pi-team-herdr"


FAKE_HERDR = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args[:2] == ["--session", "named"]: args = args[2:]
scenario = os.getenv("SCENARIO", "ok")
log = os.getenv("FAKE_LOG")
def out(value): print(json.dumps({"result": value}))
def record(op):
    if log:
        with open(log, "a", encoding="utf-8") as f: f.write(json.dumps({"args": args, "op": op}) + "\n")
def agent(name="worker", state="idle", pane="w1:p1", session_path=None):
    return {"name": name, "agent": "pi", "pane_id": pane, "workspace_id": "w1", "tab_id": "t1", "agent_status": state, "cwd": "/repo", "agent_session": {"kind": "path", "value": session_path} if session_path else None}
if args == ["--version"]: print("herdr 0.8.2")
elif args == ["api", "schema", "--json"]:
    out({"protocol": 20, "schema_version": 1, "schemas": {"success_response": {"$defs": {"AgentStatus": {"enum": ["idle", "working", "blocked", "done", "unknown"]}}}}})
elif args[:2] == ["agent", "list"]:
    if scenario == "duplicate": out({"agents": [agent(), agent(pane="w2:p1")]})
    elif scenario == "wrong-kind": out({"agents": [{**agent(), "agent": "claude"}]})
    else: out({"agents": [agent(state="working" if scenario == "working" else "idle", session_path=os.getenv("SESSION_FILE"))]})
elif args[:2] == ["agent", "get"]:
    name = args[2]
    if scenario == "missing": print(json.dumps({"error": {"code": "agent_not_found"}})); sys.exit(1)
    out(agent(name=name, state="working" if scenario == "working" else "idle", session_path=os.getenv("SESSION_FILE")))
elif args[:2] == ["workspace", "create"]: record("workspace.create"); out({"workspace_id": "w-new"})
elif args[:2] == ["pane", "list"]: out({"panes": [{"pane_id": "w-new:p1", "workspace_id": "w-new", "tab_id": "t-new", "cwd": "/repo"}]})
elif args[:2] == ["agent", "start"]: record("agent.start"); out({"name": args[2], "pane_id": "w-new:p1", "workspace_id": "w-new", "tab_id": "t-new", "agent_status": "idle"})
elif args[:2] == ["agent", "prompt"]:
    record("agent.prompt")
    if scenario == "dispatch-fails": print(json.dumps({"error": {"code": "agent_prompt_stalled"}})); sys.exit(1)
    out({"name": args[2], "agent_status": "working", "pane_id": "w-new:p1", "workspace_id": "w-new", "tab_id": "t-new"})
elif args[:2] == ["agent", "read"]: out({"text": "terminal tail only"})
elif args[:2] == ["workspace", "list"]: out({"workspaces": []})
else: print(json.dumps({"error": {"code": "unknown", "message": " ".join(args)}})); sys.exit(1)
'''


class ModernLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fake = self.root / "herdr"
        self.fake.write_text(FAKE_HERDR, encoding="utf-8")
        self.fake.chmod(0o755)
        self.extension = self.root / "team.ts"
        self.extension.write_text("export {};\n", encoding="utf-8")
        self.log = self.root / "calls.jsonl"

    def tearDown(self): self.temp.cleanup()

    def invoke(self, *args, scenario="ok", session_file=None):
        env = {**os.environ, "FAKE_LOG": str(self.log), "SCENARIO": scenario}
        if session_file: env["SESSION_FILE"] = str(session_file)
        return subprocess.run([sys.executable, str(CLI), "--herdr-command", str(self.fake), "--pi-command", sys.executable, "--extension", str(self.extension), *args], capture_output=True, text=True, env=env)

    def prompt_file(self, text="Line with `backticks`, $(not-a-command), 'quotes', 日本語\n"):
        path = self.root / "prompt.md"; path.write_text(text, encoding="utf-8"); return path, text

    def calls(self): return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def test_prompt_file_uses_direct_argv_and_never_echoes_content(self):
        prompt, text = self.prompt_file()
        result = self.invoke("prompt", "--name", "worker", "--file", str(prompt))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(text, result.stdout + result.stderr)
        call = next(c for c in self.calls() if c["op"] == "agent.prompt")
        self.assertEqual(call["args"][-1], text)

    def test_rejects_missing_empty_and_unreadable_prompt_files(self):
        missing = self.invoke("prompt", "--name", "worker", "--file", str(self.root / "missing.md"))
        self.assertEqual(missing.returncode, 2); self.assertIn("PROMPT_NOT_READABLE", missing.stderr)
        empty = self.root / "empty.md"; empty.write_bytes(b"")
        result = self.invoke("prompt", "--name", "worker", "--file", str(empty))
        self.assertEqual(result.returncode, 2); self.assertIn("PROMPT_EMPTY", result.stderr)

    def test_name_resolution_refuses_duplicate_and_wrong_kind(self):
        prompt, _ = self.prompt_file("continue")
        duplicate = self.invoke("prompt", "--name", "worker", "--file", str(prompt), scenario="duplicate")
        self.assertEqual(duplicate.returncode, 3); self.assertIn("WORKER_NAME_AMBIGUOUS", duplicate.stderr)
        wrong = self.invoke("inspect", "--name", "worker", scenario="wrong-kind")
        self.assertEqual(wrong.returncode, 3); self.assertIn("NOT_PI_AGENT", wrong.stderr)

    def test_launch_propagates_provider_model_thinking_and_reports_dispatch_failure(self):
        prompt, _ = self.prompt_file("launch text")
        result = self.invoke("launch", "--name", "runtime-research", "--cwd", "/repo", "--new-workspace", "--provider", "cvf", "--model", "muse", "--thinking", "high", "--brief-file", str(prompt), "--verify-working", scenario="dispatch-fails")
        self.assertEqual(result.returncode, 2); self.assertIn("DISPATCH_FAILED_AFTER_START", result.stderr)
        start = next(c for c in self.calls() if c["op"] == "agent.start")["args"]
        self.assertIn("--provider", start); self.assertIn("cvf", start); self.assertIn("--model", start); self.assertIn("muse", start); self.assertIn("--thinking", start); self.assertIn("high", start)

    def test_result_reads_complete_final_assistant_message_from_session_not_terminal(self):
        session = self.root / "worker.jsonl"
        session.write_text('\n'.join([json.dumps({"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "first"}]}}), json.dumps({"type": "message", "message": {"role": "assistant", "content": [{"type": "text", "text": "complete final answer"}]}})]) + '\n', encoding="utf-8")
        result = self.invoke("result", "--name", "worker", session_file=session)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["result"], "complete final answer")
        self.assertNotIn("terminal tail", result.stdout)

    def test_inspect_treats_idle_as_unknown_without_session_evidence(self):
        result = self.invoke("inspect", "--name", "worker")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["interpretation"], "unknown")

    def test_legacy_send_without_manifest_shows_migration_error(self):
        result = self.invoke("send", "--pane-id", "w1:p1", "--require-idle", "--submit", "--text", "Continue")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--manifest", result.stderr)

if __name__ == "__main__": unittest.main()
