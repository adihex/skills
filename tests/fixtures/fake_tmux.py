#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

args = sys.argv[1:]
log = os.environ.get("FAKE_TMUX_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(args) + "\n")

if args[:1] == ["list-panes"]:
    if os.environ.get("FAKE_TMUX_PANES") == "coexist":
        print("%1\tmain\t@1\t0\tπ - hax-worker\thax")
        print("%2\tmain\t@1\t0\tπ - pi-worker\tpi")
    else:
        print("%1\tmain\t@1\t0\tπ - hax-worker\tbash")
elif args[:1] in (["split-window"], ["new-window"]):
    print("%1")
elif args[:1] == ["capture-pane"]:
    print("READY >")
