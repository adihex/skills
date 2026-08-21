#!/usr/bin/env python3
import json
import os
import sys


def emit(value):
    print(json.dumps({"result": value}))


def main():
    args = list(sys.argv[1:])
    session = None
    if len(args) >= 2 and args[0] == "--session":
        session, args = args[1], args[2:]
    scenario = os.environ.get("FAKE_HERDR_SCENARIO", "ok")
    log_path = os.environ.get("FAKE_HERDR_LOG")
    op = " ".join(args[:2])
    if log_path:
        safe = {"op": op}
        if args[:2] == ["agent", "start"]:
            safe["args"] = args[2:]
        if args[:2] == ["pane", "send-keys"]:
            safe.update({"pane": args[2], "key": args[3]})
        elif args[:2] == ["agent", "send"]:
            safe.update({"pane": args[2]})
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe) + "\n")
    if args[:2] == ["pane", "list"]:
        actual = "other" if scenario == "session-mismatch" else (session or "default")
        panes = [] if scenario == "missing-pane" else [{
            "pane_id": "pane-1", "tab_id": "tab-1", "workspace_id": "ws-1",
            "agent": "worker-1", "agent_state": "working" if scenario == "native-mismatch" else "ready",
        }]
        emit({"session": actual, "panes": panes})
    elif args[:2] == ["workspace", "create"]:
        emit({"workspace_id": "ws-1"})
    elif args[:2] == ["workspace", "setup"]:
        emit({"status": "queued" if scenario == "setup-timeout" else ("failed" if scenario == "setup-failure" else "ready"), "error": "install failed" if scenario == "setup-failure" else None})
    elif args[:2] == ["workspace", "status"]:
        emit({"status": "queued" if scenario == "setup-timeout" else "ready"})
    elif args[:2] == ["workspace", "close"]:
        emit({"ok": True})
    elif args[:2] == ["agent", "start"]:
        emit({"tab_id": "tab-1", "pane_id": "pane-1"})
    elif args[:2] == ["agent", "send"]:
        emit({"ok": True})
    elif args[:2] == ["pane", "send-keys"]:
        emit({"ok": True})
    elif args[:2] == ["pane", "read"]:
        emit({"text": "ACKNOWLEDGED"})
    else:
        print(json.dumps({"error": True, "message": "unknown fake command"}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
