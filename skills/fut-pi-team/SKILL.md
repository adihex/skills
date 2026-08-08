---
name: fut-pi-team
description: Run and steer named pi agents in fut tabs and panes. Use when users ask to launch, monitor, list, or safely clean up pi workers in fut's session/workspace/tab/pane hierarchy.
license: MIT
compatibility: [fut, pi]
risk: destructive-operations-gated
category: orchestration
tags: [fut, pi, multi-agent, panes]
---
# fut-pi-team

Manage visible named pi agents through `pi-team-fut`. It is JSON-first, stdlib-only, and wraps fut's JSON API.

## When to use
- Launch or list pi workers in fut.
- Inspect fut's session → workspace → tab → pane hierarchy.
- Safely preview or remove stale pi worker panes.

## Prerequisites
- A running fut daemon (`fut list --json`).
- `pi` and `~/.pi/agent/extensions/team.ts` available.
- Run the script directly or add its `scripts/` directory to PATH.

## Quick start
```bash
pi-team-fut --brief
pi-team-fut list
pi-team-fut launch --name worker-1 --brief-file docs/brief.md
pi-team-fut cleanup --pattern 'worker-|team-' --dry-run
```

## Reliable visible-worker launch

Use a Pi positional message for a worker brief; **do not pipe the brief to Pi stdin**. Piped stdin can leave Pi at an empty interactive prompt rather than starting the task.

1. Check the daemon. If it is absent and creating one is appropriate, start it in the background, then wait for `fut daemon ping --json` to succeed.
2. For a normal named worker tab, use `pi-team-fut launch`. Its wrapper chooses Fut's first available workspace; verify `pi-team-fut list` afterward. When the intended workspace is not that workspace, use the direct Fut recipe below.
3. To create adjacent worker panes in a specific workspace/tab, create an anchor worker with `fut open`, then create siblings with `fut pane new`. Pass each brief as a quoted final argument to `pi`.
4. Confirm the resulting pane layout with `fut list --json`. A live `pi` process only confirms launch, not that the task completed; Fut has no noninteractive terminal-read/status API. Attach to inspect progress.

```bash
# Starts a worker in a new Fut workspace; capture tab_id from its JSON output.
fut open --json --name my-project /abs/project -- \
  pi -e ~/.pi/agent/extensions/team.ts --name worker-1 "$(< /tmp/worker-1-brief.md)"

# Adds an adjacent worker pane to that exact tab.
fut pane new --json --cwd /abs/project <tab-id> -- \
  pi -e ~/.pi/agent/extensions/team.ts --name worker-2 "$(< /tmp/worker-2-brief.md)"
```

## CLI reference
| Command | Purpose |
|---|---|
| `--brief` / bare | JSON identity and command list |
| `list [--human]` | Flatten live fut panes with session/workspace/tab IDs |
| `launch --name N --brief-file P [--cwd P]` | Creates a named fut tab running pi |
| `send --pane-id ID --text TEXT` | Reports that fut lacks a scripted terminal-input API |
| `status` | Reports that fut lacks agent-state/read APIs |
| `cleanup --pattern RX [--confirm] [--force]` | Dry-run by default; closes matching pi panes with confirmation |

## Recipes
- Create a worker tab: `pi-team-fut launch --name research --brief-file /tmp/brief.md`.
- See stable UUIDs: `pi-team-fut list --human`.
- Attach manually for interactive steering: `fut terminal attach <terminal-id>`.
- Review before cleanup: `pi-team-fut cleanup --pattern 'π - worker-' --dry-run`, then repeat with `--confirm`.

## Safety contract
- JSON goes to stdout; structured errors go to stderr. Exit codes: `0` ok, `1` usage, `2` runtime, `3` safety refusal.
- Cleanup is dry-run by default and requires both a regex and `--confirm` to close panes.
- Non-pi tabs are skipped unless `--force`; sent text is never echoed.
- Fut currently exposes creation and close operations in its public noninteractive CLI, not arbitrary terminal input/read. `send` and `status` fail explicitly rather than pretending they worked.

## Known gotchas
- Fut worker identity is the tab name; a tab may contain more than one pane.
- `pi-team-fut launch` creates a tab and currently selects the first live Fut workspace. It is unsuitable when a worker must be placed in a particular existing workspace; use `fut pane new <tab-id>` instead.
- `fut pane new` can add a pane, but does not expose a documented layout direction.
- Closing the final pane closes its tab and can remove the workspace/session. When removing an empty anchor pane, keep at least one worker pane alive; otherwise recreate the workspace before launching replacements.
- Use fut's installed Pi integration at `~/.pi/agent/git/github.com/mikker/fut/integrations/pi/fut.ts` for native state reporting.

## Limitations
This wrapper does not emulate unavailable fut terminal-input APIs. Attach interactively when steering is needed.
