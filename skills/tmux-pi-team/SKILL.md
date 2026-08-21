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
- Add `skills/tmux-pi-team/scripts` to `PATH`, or invoke `pi-team-tmux` by path.

## Workflow and identity

1. Launch from a known tmux server and capture the returned pane ID.
2. Verify `list` after launch; `%pane` IDs are the target identity and titles are labels.
3. `send` uses literal mode and submits Enter separately. A successful send call is not completion.
4. tmux has no built-in Pi agent state. `status` identifies panes only; it cannot classify `idle`, `working`, or `done` reliably.
5. Require the worker report and external Git/push/review/check gates before completion.

## Command index

```text
pi-team-tmux list [--human]
pi-team-tmux launch --name LABEL --brief-file FILE [--split right|bottom|spawn]
pi-team-tmux send --pane-id %ID --text TEXT
pi-team-tmux status
pi-team-tmux cleanup --pattern REGEX [--confirm]
```

JSON is the default. Exit `0` is success, `1` usage, `2` tmux/runtime failure, and `3` safety refusal. Cleanup is dry-run unless `--confirm` is supplied. Non-Pi panes are rejected unless `--force`.

## Safety rules

- Never target by mutable name when a pane ID is available.
- Never execute worker output or log prompts, tokens, cookies, or secrets.
- Never treat pane presence or apparent idle text as completion.
- Preview cleanup and confirm only an explicit regex. Do not remove a dirty or unsynchronized worktree through automation.

Use [herdr-pi-team](../herdr-pi-team/SKILL.md) for the durable manifest, state machine, review, and worktree cleanup contracts.
