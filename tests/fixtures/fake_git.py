#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
scenario = os.environ.get("FAKE_GIT_SCENARIO", "ok")
if "status" in args:
    print(" M changed.txt" if scenario == "dirty" else "", end="")
elif "branch" in args:
    print(os.environ.get("FAKE_GIT_BRANCH", "feature/test"))
elif "rev-parse" in args and "HEAD" in args:
    print("abc123")
elif "rev-parse" in args and "--abbrev-ref" in args:
    if scenario == "missing-upstream":
        print("no upstream", file=sys.stderr)
        raise SystemExit(1)
    print("origin/feature/test")
elif "rev-parse" in args and "@{u}" in args:
    print("def456" if scenario == "unpushed" else "abc123")
else:
    print("")
