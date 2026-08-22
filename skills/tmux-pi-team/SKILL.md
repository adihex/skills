---
name: tmux-pi-team
description: Manage named pi workers in tmux with stable pane identities, explicit state limitations, verified Enter submission, and dry-run cleanup. Use when users ask to launch, list, steer, or safely remove tmux workers.
license: MIT
compatibility: [tmux, pi]
risk: destructive-operations-gated
category: orchestration
tags: [tmux, pi, workers, panes]
---
# tmux-pi-team

## Prerequisites

- tmux installed from its official distribution with `list-panes`, `send-keys`, and `kill-pane`; this is the minimum supported CLI surface.
- Pi installed from its official distribution and its team extension available.
- Hax 0.3.0+ and the official Codex CLI are optional. Hax uses `codex login`, requires an explicit provider/model, and is never selected automatically.
- Add `skills/tmux-pi-team/scripts` to `PATH`, or invoke `pi-team-tmux` by path.

## Workflow and identity

1. Launch from a known tmux server and capture the returned pane ID.
2. Verify `list` after launch; `%pane` IDs are the target identity and titles are labels.
3. `send` uses literal mode and submits Enter separately. A successful send call is not completion.
4. tmux has no built-in Pi agent state. `status` identifies panes only; it cannot classify `idle`, `working`, or `done` reliably.
5. Require the worker report and external Git/push/review/check gates before completion.

## Backend selection

Pi remains the default. Hax is explicit opt-in with `--backend hax`, `--provider codex`, `--model MODEL`, and optional `--effort`/`--mode`. Hax starts in the named tmux pane through the shared backend, waits for readiness, and uses literal send followed by a separate Enter. One-shot mode is direct and non-steerable. Missing Hax, auth, model, version, or quota are reported as blocker codes; HTTP 429 is `blocked_external`, never success, and never silently falls back to Pi.

Use [references/hax-backend.md](references/hax-backend.md) for setup, diagnostics, common completion, and cleanup details. Backend, runtime, provider, model, effort, mode, auth source, capabilities, and safe backend errors are recorded in manifests.

## Command index

```text
pi-team-tmux list [--human]
pi-team-tmux launch --name LABEL --brief-file FILE [--backend pi|hax --provider codex --model MODEL --effort high --mode interactive|oneshot] [--split right|bottom|spawn]
pi-team-tmux send --pane-id %ID --text TEXT
pi-team-tmux status [--manifest FILE]
pi-team-tmux doctor --backend hax --provider codex --model MODEL
pi-team-tmux complete --manifest FILE --report FILE --repository OWNER/REPO
pi-team-tmux cleanup --pattern REGEX [--confirm]
```

JSON is the default. Exit `0` is success, `1` usage, `2` tmux/runtime failure, and `3` safety refusal. Cleanup is dry-run unless `--confirm` is supplied. Non-Pi panes are rejected unless `--force`.

## Safety rules

- Never target by mutable name when a pane ID is available.
- Never execute worker output or log prompts, tokens, cookies, or secrets.
- Never treat pane presence or apparent idle text as completion.
- Preview cleanup and confirm only an explicit regex. Do not remove a dirty or unsynchronized worktree through automation.

Use [herdr-pi-team](../herdr-pi-team/SKILL.md) for the durable manifest, state machine, review, and worktree cleanup contracts.
