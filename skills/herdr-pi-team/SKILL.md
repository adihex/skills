---
name: herdr-pi-team
description: Safely launch, inspect, steer, resume, retrieve results from, and clean up named Pi workers through Herdr. Use for Herdr Pi worker lifecycle or compatibility diagnosis.
license: MIT
compatibility: [herdr, pi]
risk: destructive-operations-gated
category: orchestration
tags: [herdr, pi, workers, lifecycle, compatibility]
---

# herdr-pi-team

Use `pi-team-herdr` for the common worker lifecycle. JSON is default. Use the same `--session NAME` as the visible Herdr client; mixing default and named sessions hides workers.

## Safe lifecycle

1. Inspect scope, branch/worktree conflict risk, and existing workers.
2. Write the brief to a file. **`--file` is mandatory for multiline or shell-sensitive text.** Never shell-interpolate a prompt.
3. Create a dedicated workspace and launch with explicit provider/model/thinking.
4. Verify `working`; native `idle` alone is never completion.
5. Inspect before resuming. Retrieve the structured final result, then independently verify edits and checks.
6. Use exact-name cleanup dry-run first.

```bash
cat > /tmp/runtime-brief.md <<'EOF'
Investigate `refs`, `$(literal)`, and Unicode: 日本語.
EOF
pi-team-herdr launch --name runtime-research --cwd /repo --new-workspace \
  --provider cvf --model muse --thinking high \
  --brief-file /tmp/runtime-brief.md --verify-working
pi-team-herdr inspect --name runtime-research
pi-team-herdr result --name runtime-research
```

`--provider`, `--model`, and `--thinking` pass directly to Pi. Do not hardcode a provider or rely on the parent Pi model.

## Everyday commands

| Command | Purpose |
|---|---|
| `launch --name N --cwd P --new-workspace --brief-file P --verify-working` | Atomic workspace → Pi start → safe brief delivery → working verification. A dispatch failure reports that startup succeeded but dispatch failed. |
| `inspect --name N` | Compact native state plus session evidence, workspace and pane traceability. |
| `prompt --name N --file P` | Submit one complete Pi user turn safely. `--text` is only for short literal input. |
| `resume --name N --file P` | Inspect then continue an existing live worker. |
| `result --name N` | Read the complete last Pi assistant message from its session artifact, not terminal viewport text. |
| `doctor` | Check installed versions, session reachability, and required capabilities. |
| `compatibility snapshot` / `compatibility check` | Capture/check sanitized native capability contract. |
| `docs check` | Ensure this skill only documents tested wrapper commands. |

Stable names are preferred. `--pane-id` and `send --manifest` remain advanced legacy controls; `send` intentionally requires `--manifest`. The earlier documented pane-id send example failed because this wrapper’s legacy `send` is manifest-bound. Name-based `prompt` and `resume` resolve the native registry without an ambiguous manifest.

## State interpretation and resume

| Native state/evidence | Interpretation | Resume behavior |
|---|---|---|
| `working` | Working | Refuse; use `--force` only for deliberate steering. |
| `blocked` | Blocked | Inspect and resolve the blocker first. |
| `done` or `idle` with readable final session result | Completed | Require `--confirm-completed`. |
| `idle` without conclusive session evidence | Unknown | Inspect output/session; then `resume` continues the live worker. |
| Missing pane/session | Unknown | Do not guess. Restart `pi --continue` from the same project in a new workspace and verify identity. |

`herdr agent prompt` submits a complete Pi user turn. `herdr agent send-keys` is low-level terminal steering. `herdr pane run` intentionally executes a shell command. The wrapper never silently downgrades a safe prompt to keystrokes or shell execution.

## Compatibility policy

The installed Herdr binary is runtime truth: `herdr --version`, `herdr api schema --json`, and operation probes. The wrapper records tested versions in [references/compatibility.json](references/compatibility.json) and uses the machine-readable API schema before help-text probes. Newer, capability-complete versions warn/continue; a missing required operation blocks only its dependent wrapper command. Full schema/fixture and upstream guidance: [references/compatibility.md](references/compatibility.md).

## Cleanup and recovery

Legacy manifest cleanup is intentionally explicit and dry-run first:

```bash
pi-team-herdr cleanup --manifest /tmp/runtime.json --worktree-root /worktrees \
  --main-checkout /repo
# inspect JSON, then repeat with --confirm
```

Never use broad patterns or terminate a pre-existing worker. If launch reports `DISPATCH_FAILED_AFTER_START`, inspect the reported workspace/pane, preserve it, and retry with `prompt --name ... --file ...` after resolving the native blocker.

Do not trust a worker’s completion claim: independently inspect the diff and run the relevant checks.
