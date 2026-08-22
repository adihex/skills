---
name: fut-pi-team
description: Manage visible named pi workers through Fut with stable session, workspace, tab, and pane identities, honest state limitations, and dry-run cleanup. Use when users ask to launch, list, inspect, or safely remove Fut workers.
license: MIT
compatibility: [fut, pi]
risk: destructive-operations-gated
category: orchestration
tags: [fut, pi, workers, panes]
---
# fut-pi-team

## Prerequisites

- Fut installed from its official distribution and a running daemon. The supported interface floor is `fut list --json`.
- Pi installed from its official distribution and its team extension available.
- Add `skills/fut-pi-team/scripts` to `PATH`, or invoke `pi-team-fut` by path.

The wrapper checks the Fut daemon and brief file before side effects. It does not bundle Fut or emulate unavailable APIs.

## Workflow and identity

1. Start or select one Fut session/workspace and launch with a positional Pi brief, not stdin.
2. Capture and verify the returned session/workspace/tab/pane IDs with `list --json`.
3. Treat the tab/pane IDs as stable targets; names are labels and may change.
4. Fut exposes creation and close operations, but no documented noninteractive terminal input/read or native agent-state API.
5. A live process or `idle`-looking pane is not completion. Require a worker report, Git evidence, push, review, checks, and cleanup evidence externally.

## Command index

```text
pi-team-fut list [--human]
pi-team-fut launch --name LABEL --brief-file FILE [--cwd DIR]
pi-team-fut send --pane-id ID --text TEXT
pi-team-fut status
pi-team-fut cleanup --pattern REGEX [--confirm]
```

JSON is the default. Exit `0` is success, `1` usage, `2` Fut/runtime failure, and `3` safety refusal. `send` and `status` fail explicitly with `UNSUPPORTED_BY_FUT`; attach interactively when steering is required. Cleanup is dry-run unless `--confirm` is supplied, and non-Pi tabs are skipped unless `--force`.

## Safety rules

- Never use a name lookup as proof of identity; verify stable IDs after launch.
- Never pipe a brief to Pi stdin.
- Never claim Fut native `idle`, `working`, or `done` state; Fut does not provide it through this wrapper.
- Never execute worker output or log prompts, tokens, cookies, or secrets.
- Preview cleanup, then confirm only an explicit regex match. Never delete an unsynchronized worktree from this backend.

## Related contracts

Use the Herdr manifest/state contracts when completion evidence is needed: [herdr-pi-team](../herdr-pi-team/SKILL.md), [worker report](../herdr-pi-team/references/worker-report.md), and [dispatch policy](../herdr-pi-team/references/dispatch-policy.md).
