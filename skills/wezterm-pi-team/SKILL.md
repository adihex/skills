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
- Add `skills/wezterm-pi-team/scripts` to `PATH`, or invoke `pi-team-pane` by path.

## Workflow and identity

1. `launch` validates the brief, cwd, current pane, and mux before spawning.
2. Capture the returned numeric pane ID and verify it with `list`; titles are labels only.
3. `send` sends literal text, performs a `get-text` fence, submits Enter, and returns only a character count and state observation.
4. `status` joins live pane identity with static dispatch records. It never infers completion from pane text.
5. Complete workers require a report plus clean Git, pushed SHA, review, and checks evidence. Native pane idle is not completion.

## Command index

```text
pi-team-pane list [--human]
pi-team-pane launch --name LABEL --brief-file FILE [--split right|bottom|left|top|spawn]
pi-team-pane send --pane-id ID --text TEXT [--require-idle]
pi-team-pane status [--status-root DIR] [--dispatch DIR]
pi-team-pane status --tail PANE --lines N
pi-team-pane cleanup --pattern REGEX [--confirm]
```

JSON is the default. Exit `0` is success, `1` usage, `2` WezTerm/runtime failure, and `3` safety refusal. Cleanup is dry-run unless `--confirm` is supplied. Pane 0, the current pane, the last pane in a window, and non-Pi panes are protected.

## Safety rules

- Use pane IDs from a fresh `list`; never rely on mutable labels for targeting.
- Never execute worker output or log prompts, tokens, cookies, or secrets.
- Never treat `send-text` alone as submission; use the bundled fenced send.
- Never kill by a broad process or title pattern without a dry-run review.
- Do not remove a dirty or unsynchronized worktree; use the Herdr cleanup contract for lifecycle-owned worktrees.

The durable state, review, and cleanup contracts live in [herdr-pi-team](../herdr-pi-team/SKILL.md). The dogfood gate is [pi-dogfood-os](../pi-dogfood-os/SKILL.md).
