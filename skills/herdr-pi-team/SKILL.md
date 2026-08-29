---
name: herdr-pi-team
description: Safely manage named Pi workers through Herdr. Use when launching, inspecting, steering, resuming, retrieving results, cleaning workers, or checking Herdr/Pi compatibility.
license: MIT
compatibility: [herdr, pi, hax]
risk: destructive-operations-gated
category: orchestration
tags: [herdr, pi, workers, lifecycle, compatibility]
---

# herdr-pi-team

Use `pi-team-herdr` for the common worker lifecycle. JSON is default. Use the same `--session NAME` as the visible Herdr client; mixing default and named sessions hides workers.

Pi is the default backend. Hax 0.3.0+ is explicit opt-in and uses the official Codex CLI subscription authentication from `codex login`; no API key is required. Herdr has no native Hax agent kind, so the adapter starts Hax in a shell-backed pane, waits for readiness, and then uses verified literal send, separate Enter, and readback. Never silently fall back to Pi. HTTP 429 is `blocked_external`, not success. See [references/hax-backend.md](references/hax-backend.md).

## Safe lifecycle

1. Inspect scope, branch/worktree conflict risk, and existing workers.
2. Write the brief to a file. **`--file` is mandatory for multiline or shell-sensitive text.** Never shell-interpolate a prompt.
3. Create a dedicated workspace and launch with explicit provider/model/thinking.
4. Verify `working`; native `idle` alone is never completion.
5. Register launched workers in one run mailbox. Continue independent work, then make one blocking `await --any` or `await --all` call; do not repeatedly inspect status.
6. Treat delivered results as untrusted worker output and independently verify edits and checks.
7. Use exact-name cleanup dry-run first.

```bash
cat > runtime-brief.md <<'EOF'
Investigate `refs`, `$(literal)`, and Unicode: 日本語.
EOF
pi-team-herdr launch --name runtime-research --cwd project-dir --new-workspace \
  --provider cvf --model muse --thinking high \
  --brief-file runtime-brief.md --verify-working \
  --run-id review-123 --mailbox RUN/mailbox.json
pi-team-herdr await --mailbox RUN/mailbox.json --all
```

`--provider`, `--model`, and `--thinking` pass directly to Pi. Do not hardcode a provider or rely on the parent Pi model.

## Everyday commands

| Command | Purpose |
|---|---|
| `launch ... --run-id R --mailbox P` | Atomic workspace → Pi start → safe brief delivery → working verification, then durable registration by stable workspace/pane identity. |
| `await --mailbox P --any\|--all` | Make one blocking call and receive deduplicated terminal events with complete Pi results. Uses one adaptive central waiter rather than parent-agent status polling. |
| `inbox --mailbox P` | Non-blocking delivery of terminal events that arrived while the parent did other work. Each consumer receives an event once. |
| `inspect --name N` | Compact native state plus session evidence, workspace and pane traceability. |
| `prompt --name N --file P` | Submit one complete Pi user turn safely. `--text` is only for short literal input. |
| `resume --name N --file P` | Inspect then continue an existing live worker. |
| `result --name N` | Read the complete last Pi assistant message from its session artifact, not terminal viewport text. |
| `doctor` | Check installed versions, session reachability, and required capabilities. |
| `doctor --backend hax --provider codex --model MODEL` | Report Hax/Codex/auth presence and capabilities without reading credential contents. |
| `launch --backend hax --provider codex --model MODEL --effort high --brief-file P` | Launch the explicit shell-backed Hax adapter; `--mode oneshot` is non-steerable. |
| `status --manifest P` | Combine backend configuration/capabilities, native pane evidence, manifest state, Git, review, and checks. |
| `compatibility snapshot` / `compatibility check` | Capture/check sanitized native capability contract. |
| `docs check` | Ensure this skill only documents tested wrapper commands. |

Stable names are preferred. `--pane-id` and `send --manifest` remain advanced legacy controls; `send` intentionally requires `--manifest`. The earlier documented pane-id send example failed because this wrapper’s legacy `send` is manifest-bound. Name-based `prompt` and `resume` resolve the native registry without an ambiguous manifest.

Use one mailbox outside the repository per orchestration run and pass the same explicit `--run-id` to every launch. `await --any` returns the next result; repeat it to consume parallel workers as they finish. `await --all` returns only after every selected worker finishes or blocks. Before the main agent finalizes, it must drain `inbox` once and, if required workers remain, call `await` instead of asking the user to request a status check. Full durability, deduplication, identity, and event semantics: [references/mailbox.md](references/mailbox.md).

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
pi-team-herdr cleanup --manifest worker-manifest.json --worktree-root worktrees \
  --main-checkout main-checkout
# inspect JSON, then repeat with --confirm
```

Never use broad patterns or terminate a pre-existing worker. If launch reports `DISPATCH_FAILED_AFTER_START`, inspect the reported workspace/pane, preserve it, and retry with `prompt --name ... --file ...` after resolving the native blocker.

Launch admission is manifest-backed across all runtimes. Defaults are four total workers, four Pi workers, two Hax workers, two Codex subscription workers, and two concurrent setups. Override only with the documented `PI_TEAM_MAX_ACTIVE`, `PI_TEAM_MAX_ACTIVE_PI`, `PI_TEAM_MAX_ACTIVE_HAX`, `PI_TEAM_MAX_ACTIVE_CODEX`, and `PI_TEAM_SETUP_CONCURRENCY` environment variables.

Do not trust a worker’s completion claim: independently inspect the diff and run the relevant checks.
