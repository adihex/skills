---
name: wezterm-pi-team
description: Run and steer named pi workers in visible WezTerm panes with stable pane IDs, fenced Enter submission, status evidence, and protected dry-run cleanup. Use when users ask to launch, message, inspect, or clean up WezTerm workers.
license: MIT
compatibility: [wezterm, pi]
risk: destructive-operations-gated
category: orchestration
tags: [wezterm, pi, workers, panes, cleanup]
date_added: 2026-08-01
---
# wezterm-pi-team

## Prerequisites

- WezTerm with the `wezterm cli` surface for `list`, `split-pane`/`spawn`, `send-text`, `get-text`, and `kill-pane`; this is the minimum supported CLI surface.
- Pi and the team extension installed from their official distributions.
- Run inside a WezTerm pane with `WEZTERM_PANE` set. Set `WEZTERM_CLASS` when using a non-default mux class.
- Hax 0.3.0+ and the official Codex CLI are optional. Hax uses `codex login`, requires an explicit provider/model, and is never selected automatically.
- Add `skills/wezterm-pi-team/scripts` to `PATH`, or invoke `pi-team-pane` by path.

## Workflow and identity

1. `launch` validates the brief, cwd, current pane, and mux before spawning.
2. Capture the returned numeric pane ID and verify it with `list`; titles are labels only.
3. `send` sends literal text, performs a `get-text` fence, submits Enter, and returns only a character count and state observation.
4. `status` joins live pane identity with static dispatch records. It never infers completion from pane text.
5. Complete workers require a report plus clean Git, pushed SHA, review, and checks evidence. Native pane idle is not completion.

## Backend selection

Pi remains the default. Hax is explicit opt-in with `--backend hax`, `--provider codex`, `--model MODEL`, and optional `--effort`/`--mode`. The shared backend starts Hax in the worker pane, waits for readiness, and uses the existing `get-text` fence before a separate Enter. One-shot mode is direct and non-steerable. Missing Hax, auth, model, version, and quota have specific blocker codes; HTTP 429 is `blocked_external`, never success, and never silently falls back to Pi.

Use [references/hax-backend.md](references/hax-backend.md) for setup, diagnostics, common completion, and cleanup details. Backend, runtime, provider, model, effort, mode, auth source, capabilities, and safe backend errors are recorded in manifests.

## Command index

```text
pi-team-pane list [--human]
pi-team-pane launch --name LABEL --brief-file FILE [--backend pi|hax --provider codex --model MODEL --effort high --mode interactive|oneshot] [--split right|bottom|left|top|spawn]
pi-team-pane send --pane-id ID --text TEXT [--require-idle]
pi-team-pane status [--status-root DIR] [--dispatch DIR]
pi-team-pane status --tail PANE --lines N
pi-team-pane cleanup --pattern REGEX [--confirm]
pi-team-pane cleanup --manifest FILE --worktree-root ROOT --main-checkout CHECKOUT [--confirm]
pi-team-pane doctor --backend hax --provider codex --model MODEL
pi-team-pane complete --manifest FILE --report FILE --repository OWNER/REPO
```

JSON is the default. Exit `0` is success, `1` usage, `2` WezTerm/runtime failure, and `3` safety refusal. Cleanup is dry-run unless `--confirm` is supplied. Pane 0, the current pane, the last pane in a window, and non-Pi panes are protected.

## Safety rules

- Use pane IDs from a fresh `list`; never rely on mutable labels for targeting.
- Never execute worker output or log prompts, tokens, cookies, or secrets.
- Never treat `send-text` alone as submission; use the bundled fenced send.
- Never kill by a broad process or title pattern without a dry-run review.
- Do not remove a dirty or unsynchronized worktree; use the Herdr cleanup contract for lifecycle-owned worktrees.
- Pattern cleanup is manual pane cleanup only and never marks a worker complete. Manifest cleanup applies the shared state, Git, ownership, scoped-process, and worktree-removal transaction.

The durable state, review, and cleanup contracts live in [herdr-pi-team](../herdr-pi-team/SKILL.md). The dogfood gate is [pi-dogfood-os](../pi-dogfood-os/SKILL.md).
