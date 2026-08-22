#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
scenario = os.environ.get("FAKE_GH_SCENARIO", "ok")
if args[:2] == ["pr", "list"]:
    if scenario == "missing-pr":
        print("[]")
    elif scenario == "multiple-prs":
        print(json.dumps([{"number": 1}, {"number": 2}]))
    else:
        print(json.dumps([{"number": 7, "url": "https://example.invalid/pr/7", "state": "OPEN", "headRefName": "feature/test"}]))
elif args[:2] == ["pr", "view"]:
    if "reviews,reviewDecision" in " ".join(args):
        body = "rate limit exceeded" if scenario == "rate-limit" else "looks good"
        print(json.dumps({"reviewDecision": "APPROVED" if scenario != "rate-limit" else None, "reviews": [{"id": 9, "body": body, "state": "COMMENTED"}]}))
    else:
        print(json.dumps({"number": 7, "url": "https://example.invalid/pr/7", "state": "OPEN", "headRefName": "feature/test"}))
elif args[:1] == ["api"]:
    if len(args) > 1 and args[1] == "graphql":
        print(json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [{"id": "thread-1", "isResolved": False, "comments": {"nodes": [{"id": "comment-1", "body": "thread comment"}]}}]}}}}}))
    elif "issues" in args[1]:
        print(json.dumps([{"id": 11, "body": "duplicate"}, {"id": 11, "body": "duplicate"}]))
    else:
        print(json.dumps([{"id": 12, "body": "inline"}]))
elif args[:2] == ["pr", "checks"]:
    sha = "wrong-sha" if scenario == "wrong-commit" else "abc123"
    if scenario == "unrelated-failure":
        print(json.dumps([{"name": "docs", "state": "failure", "headSha": sha, "paths": ["docs/readme.md"]}]))
    else:
        print(json.dumps([{"name": "tests", "state": "success", "headSha": sha}]))
else:
    print(json.dumps({"error": "unknown fake gh command"}), file=sys.stderr)
    raise SystemExit(1)
