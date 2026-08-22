#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

args = sys.argv[1:]
if args[:1] == ["cli"]:
    args = args[1:]
log = os.environ.get("FAKE_WEZTERM_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(args) + "\n")

if args[:1] == ["list"]:
    if os.environ.get("FAKE_WEZTERM_PANES") == "coexist":
        print(json.dumps([{"pane_id": 1, "tab_id": 1, "window_id": 1, "title": "π - operator - repo", "cwd": "file:///tmp", "is_active": True},
                          {"pane_id": 2, "tab_id": 1, "window_id": 1, "title": "π - hax-worker - repo", "cwd": "file:///tmp", "is_active": False},
                          {"pane_id": 3, "tab_id": 1, "window_id": 1, "title": "π - pi-worker - repo", "cwd": "file:///tmp", "is_active": False}]))
    else:
        print(json.dumps([{"pane_id": 1, "tab_id": 1, "window_id": 1, "title": "π - operator - repo", "cwd": "file:///tmp", "is_active": True}]))
elif args[:1] in (["split-pane"], ["spawn"]):
    print("2")
elif args[:1] == ["get-text"]:
    print("READY >")
