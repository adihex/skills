# Worker result contract

A worker must emit exactly one final report with these fields. Values are evidence references or explicit `none`; do not paste prompts, tokens, cookies, or secret values.

```text
RESULT: complete | blocked_external | blocked | failed
WORKTREE: absolute owned worktree path
BRANCH: branch name
COMMIT: commit SHA or none
PUSHED: pushed SHA or none
PR: PR number or none
CODERABBIT: approved | changes_requested | rate_limited | not_run | blocked
CHECKS: passed | failed_touched_scope | failed_unrelated | skipped_expected | pending | external_blocked
CLEANUP: verified | pending | refused | failed | not_applicable
BLOCKER: concise blocker or none
EVIDENCE: paths or command IDs proving each claim
```

The orchestrator validates this report against the worker manifest, Git state, remote state, review API evidence, checks by commit SHA, and cleanup evidence. A pane tail, native `idle` state, or worker assertion is never sufficient by itself.
