---
name: wezterm-pi-team
description: Run and steer named pi agents (team.ts) in visible WezTerm panes and clean up safely. Use when the user asks to split panes and launch pi agents; when dispatching reliable interactive teams from a brief; when monitoring or steering named workers through WezTerm; when polling team status and report dirs; when cleaning stale prototype/team panes safely. Backed by the `pi-team-pane` CLI (JSON by default, --human for humans, dry-run cleanup).
license: MIT
compatibility: [wezterm, pi]
risk: destructive-operations-gated
category: orchestration
tags: [wezterm, pi, multi-agent, panes]
date_added: 2026-08-01
---

# wezterm-pi-team

## Overview

Heavy headless chains can silently fail. This skill runs named pi agents (`pi -e ~/.pi/agent/extensions/team.ts --model opencode/deepseek-v4-flash-free --name <label> @<brief-file>`) in visible WezTerm panes, steers them with `@worker` messages, monitors them by polling status dirs and pane text, and cleans up stale team panes safely. All operations go through the bundled `pi-team-pane` CLI.

## When to use

Use when:
- the user asks to split panes and launch pi agents
- dispatching reliable interactive teams from a brief
- monitoring or steering named workers through WezTerm
- polling team status and report dirs
- cleaning stale prototype/team panes safely

## Prerequisites

- A running WezTerm GUI (`wezterm cli list` must succeed; otherwise the CLI exits 2 with a clear message).
- `~/.local/bin` on PATH (contains the `pi-team-pane` symlink).
- Extension `~/.pi/agent/extensions/team.ts` present — it is read-only, never edited by this skill.
- If WezTerm was started with `--class SOMETHING`, set `WEZTERM_CLASS=SOMETHING` so CLI calls find the instance.

## Quick start

```bash
pi-team-pane --brief        # CLI identity + command list
pi-team-pane list           # live panes (JSON; add --human for a table)
pi-team-pane status         # newest dispatch dir -> workers, deduped by label
pi-team-pane status --human # per-worker one-liners
```

Defaults: model `opencode/deepseek-v4-flash-free` · extension `~/.pi/agent/extensions/team.ts` · cwd `$PWD` · status root `/tmp/team-task/status` · split `bottom`. `--percent 10..90` sizes a split pane when `--split` is a direction (right/bottom/left/top), never for `spawn`.

## CLI reference

| Subcommand | Flags | Exit | Output summary |
|---|---|---|---|
| `--brief` / bare | — | 0 | identity + commands |
| `--version` | — | 0 | `{"name","version"}` |
| `list` | `--human` | 0 / 2 | `{panes[], currentPaneId, count}` |
| `launch` | `--name` `--brief-file` `--split right\|bottom\|left\|top\|spawn` `--percent N` `--cwd` `--model` `--extension` | 0 / 1 / 2 | `{paneId, split, cwd, title, piCommand}`; Pi receives the brief as `@<brief-file>` |
| `send` | `--pane-id` `--text` `--require-idle` `--force` | 0 / 1 / 2 / 3 | `{paneId, sent, chars, cliState, fenced}` |
| `status` | `--dispatch` `--status-root` `--human` | 0 / 1 / 2 | `{root, dir, dispatch, workers[], panes[]}` |
| `status --tail` | `--tail PANE` `--lines N` `--human` | 0 / 1 / 2 | `{paneId, lines, text, cliState}` (human: plain text) |
| `focus` | `--pane-id` `--force` | 0 / 1 / 2 / 3 | `{paneId, focused}` |
| `cleanup` | `--pattern` `--dry-run` `--confirm` `--force` `--human` | 0 / 1 / 2 / 3 | `{dryRun, pattern, matches[], skipped[], killed[]}` |
| `launch-and-dispatch` | `--name` `--brief-file` `--dispatch-instruction` + launch flags (`--split`, `--percent`, …) | 0 / 1 / 2 | `{paneId, split, title, dispatched, chars}` |

Exit codes: `0` ok · `1` usage · `2` runtime/wezterm · `3` safety refusal. JSON on stdout by default; errors as `{"error":true,"code","message","suggestion"}` on stderr. No interactive prompts.

## Recipes

- **Split current pane + launch pi**: `pi-team-pane launch --name worker-1 --brief-file docs/brief.md --split right --percent 40` (directions: right/bottom/left/top; `spawn` opens a new window; the brief path is passed to Pi as `@docs/brief.md`)
- **Dispatch from a brief**: `pi-team-pane launch-and-dispatch --name worker-1 --brief-file docs/brief.md --dispatch-instruction 'Run team_dispatch chain mode with workers A,B; write results to reports/'`
- **Poll reports & status**: `pi-team-pane status --human`; then tail a worker's pane: `pi-team-pane status --tail <id> --lines 50` (JSON with `cliState`; `--human` prints the text plainly; line count caps at 200).
- **Send `@worker` steering**: `pi-team-pane send --pane-id <id> --text '@worker-1: adjust — focus on tests'` (payload is pasted, a `get-text` round-trip fences PTY ordering, then Enter is sent automatically). Add `--require-idle` when you only want to steer a ready prompt.
- **Bring a worker pane forward**: `pi-team-pane focus --pane-id <id>` — activates the pane (refuses pane 0/current unless `--force`).
- **Clean stale panes safely**: `pi-team-pane cleanup --pattern 'proto-|team-' --dry-run` → review → `pi-team-pane cleanup --pattern 'proto-|team-' --confirm`

## Safety contract

- `cleanup` is **dry-run by default**; real kills require `--confirm`. No prompt fallbacks.
- `--pattern` is **required**; no blanket/wildcard killing. Matches pane title/label regex only.
- **Never kill pane 0, the current pane (`WEZTERM_PANE`), or the last pane in a window** — hard invariant, `--confirm` does not override (manual `wezterm cli kill-pane --pane-id <id>` is the documented escape hatch).
- `send` refuses pane 0/current and non-`π - ` pi panes (exit 3) unless `--force`; payload and Enter are separated by a `get-text` fence to avoid WezTerm PTY write ordering races. Enter is platform-aware (`\r` on Unix, `\n` on Windows).
- `focus` refuses pane 0 / the current pane (`WEZTERM_PANE`) unless `--force` — focusing your own cursor pane yanks focus and is almost always a mistake.
- `send --require-idle` refuses unless recent pane text looks idle/ready; omit it for normal steering, or use `--force` for a deliberate manual override.
- **No secrets echoed**: never print env values, brief-file contents, or sent text; `send` reports only a char count.

## Known gotchas

- `send-text` does **not** press Enter — `pi-team-pane send` sends the payload, performs a read fence, then sends Enter. Raw `wezterm cli send-text` can silently fill a prompt and never run it.
- `get-text` is **screen-only** by default (start-line 0 = first screen line); use negative `--start-line` to read scrollback.
- `WEZTERM_PANE` is unset outside a WezTerm pane (headless cron/ssh) — run launch/send from inside a pane.
- `kill-pane` has **no undo**; that is why cleanup is dry-run-first, pane 0/current are hard-protected, and non-pi panes are skipped unless `--force`.
