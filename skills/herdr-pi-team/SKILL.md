---
name: herdr-pi-team
description: Run and steer named pi agents in herdr panes. Use when users ask to launch, monitor native agent state, send worker instructions, or safely clean up pi workers in herdr.
license: MIT
compatibility: [herdr, pi]
risk: destructive-operations-gated
category: orchestration
tags: [herdr, pi, multi-agent, panes]
---
# herdr-pi-team

Use `pi-team-herdr` to manage named pi agents in herdr's session → workspace → tab → pane hierarchy. JSON is default; `--human` is available for `list`.

## When to use
- Start pi workers in a herdr workspace.
- Monitor herdr's native idle/working/blocked agent state.
- Send steering messages or clean up stale worker panes safely.

## Prerequisites
- Running Herdr server/session (`herdr pane list`).
- Pi integration installed once: `herdr integration install pi`.
- **One session scope:** the visible client and every wrapper command must use the same session. Use bare `herdr` plus bare `pi-team-herdr` for the default session, or use `herdr --session <name>` plus `pi-team-herdr --session <name>` consistently.
- `pi` and the team extension available.

## Quick start
```bash
# Default Herdr session
herdr
pi-team-herdr --brief
pi-team-herdr list
pi-team-herdr status
pi-team-herdr launch --name worker-1 --brief-file docs/brief.md

# Named session (apply the same name everywhere)
herdr --session review
pi-team-herdr --session review launch --name worker-1 --brief-file docs/brief.md
```

## CLI reference
| Command | Purpose |
|---|---|
| `--brief` / bare | JSON identity and command list |
| `--session NAME` | Scope every operation to a named Herdr session; must match the visible client |
| `list [--human]` | List panes and native agent metadata |
| `launch --name N --brief-file P [--cwd P] [--workspace ID] [--model M] [--thinking LEVEL]` | `herdr agent start` for a named pi worker; target a dedicated space and set Pi reasoning effort explicitly |
| `send --pane-id ID --text TEXT [--require-idle] [--submit] [--force]` | Send a literal message; `--submit` safely follows it with Herdr's `enter` key |
| `status` | Native state for pi panes |
| `cleanup --pattern RX [--confirm] [--force]` | Dry-run by default; closes matched panes |

## Recipes
- Launch: `pi-team-herdr launch --name tests --brief-file /tmp/brief.md`.
- Target a dedicated space: `pi-team-herdr launch --name plan-review --brief-file /tmp/brief.md --cwd /repo --workspace <workspace-id>`.
- Use a reasoning model deliberately: `pi-team-herdr launch --name architecture-review --brief-file /tmp/brief.md --model openai-codex/gpt-5.6-luna --thinking high`.
- Named session: `pi-team-herdr --session review launch --name tests --brief-file /tmp/brief.md`.
- Send and submit to a ready worker: `pi-team-herdr send --pane-id ID --require-idle --submit --text '@tests: run focused tests'`.
- Move a paused worker to a dedicated workspace: create it with `herdr workspace create --cwd <repo> --label <name>`, verify the old worker is idle, close its old pane, then resume Pi from the same repository with `herdr agent start <name> --cwd <repo> --workspace <workspace-id> -- pi --continue --name <name>`. Verify the new `workspace_id` using `herdr agent list` before resuming work.
- Inspect output directly: `herdr agent read tests --lines 50`.
- Cleanup safely: `pi-team-herdr cleanup --pattern 'π - tests' --dry-run`, inspect, then add `--confirm`.

## Safety contract
- Default stdout is JSON; structured errors go to stderr. Exit `0` ok, `1` usage, `2` runtime, `3` safety refusal.
- Cleanup requires a regex and `--confirm`; it is dry-run by default.
- Sending to a non-pi pane, or a non-idle worker with `--require-idle`, is refused unless `--force`.
- Message text and brief contents are not returned in output.

## Known gotchas
- **Invisible workers usually mean a session mismatch.** `herdr --session review` displays only `review`, while a bare `herdr agent start` creates in the default session. Either use the default session everywhere or pass `--session review` to both the client and `pi-team-herdr`.
- `herdr agent send` writes literal text; it does not press Enter. Prefer wrapper `send --submit`; its native key is lowercase `enter` (uppercase `ENTER` is rejected). Use `herdr pane run` only when deliberate command execution is wanted.
- Herdr has no in-place pane/workspace move in this CLI surface. Move only an **idle** agent: preserve its worktree, close the old pane, restart `pi --continue` in the destination workspace, then verify the resulting `workspace_id`. Do not pass a long Pi session-file path through `herdr agent start`; resume by project with `pi --continue` instead.
- Native integration supports `idle`, `working`, `blocked`, and `unknown`; `herdr wait agent-status` additionally recognizes `done`.
- Pane IDs can be terminal IDs; use `list` before automation.

## Limitations
This lightweight wrapper does not expose every herdr focus/wait/read command; call native herdr commands for those advanced workflows.
