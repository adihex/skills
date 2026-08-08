---
name: tmux-pi-team
description: Run and steer named pi agents in tmux panes. Use when users ask to split panes, launch, list, send instructions to, monitor, or safely clean up pi workers in tmux.
license: MIT
compatibility: [tmux, pi]
risk: destructive-operations-gated
category: orchestration
tags: [tmux, pi, multi-agent, panes]
---
# tmux-pi-team

Use `pi-team-tmux` for JSON-first management of named pi agents in tmux's session → window → pane hierarchy.

## When to use
- Split a tmux pane and launch a named pi worker.
- List worker pane IDs, steer a known worker, or preview cleanup.
- Operate a visible tmux-based multi-agent team safely.

## Prerequisites
- A running tmux server (`tmux list-panes -a`).
- `pi` and `~/.pi/agent/extensions/team.ts` available.
- Run the script directly or expose `scripts/` on PATH.

## Quick start
```bash
pi-team-tmux --brief
pi-team-tmux list
pi-team-tmux launch --name worker-1 --brief-file docs/brief.md --split right
pi-team-tmux send --pane-id %3 --text '@worker-1: focus on tests'
```

## CLI reference
| Command | Purpose |
|---|---|
| `--brief` / bare | JSON identity and command list |
| `list [--human]` | Live panes with tmux session/window identifiers |
| `launch --name N --brief-file P [--split right\|bottom\|spawn]` | Split or create a window running pi |
| `send --pane-id ID --text TEXT [--force]` | `send-keys` literal text followed by Enter |
| `status` | List known pi panes |
| `cleanup --pattern RX [--confirm] [--force]` | Dry-run by default; kill matching pi panes |

## Recipes
- Split right: `pi-team-tmux launch --name review --brief-file /tmp/brief.md --split right`.
- Open a new window: use `--split spawn`.
- Send a worker instruction: `pi-team-tmux send --pane-id %4 --text '@review: inspect the diff'`.
- Preview then apply cleanup: `pi-team-tmux cleanup --pattern 'π - review' --dry-run` then `--confirm`.

## Safety contract
- JSON stdout, structured stderr errors; exits `0` ok, `1` usage, `2` runtime, `3` safety refusal.
- Cleanup requires a regex and `--confirm`; dry-run is the default.
- Non-pi panes are rejected for send/cleanup unless `--force`.
- Sends use tmux literal mode and submit Enter separately; returned JSON only includes character count.

## Known gotchas
- A tmux pane title is set after launch to `π - <name>` and is the pi-worker marker.
- Run `list` before sending: pane IDs include a leading `%` and are server-local.
- tmux has no built-in pi agent state, so `status` identifies workers but cannot reliably classify idle/blocked state.

## Limitations
`--require-idle` is accepted for interface compatibility but tmux cannot reliably detect state; use visible pane output before high-risk steering.
