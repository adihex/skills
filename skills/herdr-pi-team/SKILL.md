---
name: herdr-pi-team
description: Use when launching, steering, monitoring, resuming, or safely cleaning up named pi agents in Herdr panes.
license: MIT
compatibility: [herdr, pi]
risk: destructive-operations-gated
category: orchestration
tags: [herdr, pi, multi-agent, panes, workmux, integration]
---
# herdr-pi-team

Use `pi-team-herdr` for the supported wrapper, and native `herdr` commands when the wrapper does not expose the operation. Keep one Herdr session, one repository/worktree, and one configuration story per worker.

## When to use
- Start named pi workers in Herdr panes.
- Verify native working/idle/blocked state, model, reasoning level, and context after launch or restart.
- Submit steering prompts without mistaking a wait timeout for worker failure.
- Resume a preserved Pi session safely after configuration, integration, or extension changes.
- Diagnose worktree setup, integration, and skill-copy collisions before dispatch.
- Dry-run cleanup and close only explicitly matched worker panes.

## Preflight: inspect the live installation
Do not trust this document over the installed CLI. Run these before a dispatch or after an upgrade:

```bash
herdr --version
pi-team-herdr --version
herdr integration status
herdr integration doctor  # if supported by this Herdr version
pi-team-herdr --help
pi-team-herdr launch --help
pi-team-herdr status --help
herdr agent start --help
herdr agent prompt --help
```

The current verified interface is Herdr `0.8.2`, `pi-team-herdr 0.2.0`, Pi integration v8, and `status --manifest MANIFEST`; a bare `pi-team-herdr status` is not portable. If integration is stale, run `herdr integration install pi`, then restart existing agents: integration changes are loaded at process start. Do not install `omp` merely to fix this: OMP and Pi share the agent extension directory, so Herdr may refuse `herdr integration install omp` as a collision. Record the collision and keep the existing canonical/symlinked extension arrangement unless migration is explicitly requested.

Check for duplicated skill copies before launching. A work-profile copy alongside canonical `~/.agents/skills` can produce skill-collision warnings; use the canonical skill via symlink and do not edit installed/generated copies. Confirm the source with `realpath` and repository status.

## Backend and completion boundaries
Pi is the default native backend. If the installed wrapper exposes `--backend hax`, opt into it explicitly and run its backend-specific doctor; never silently fall back between backends. Keep the wrapper's manifest, reconciliation, review, checks, and cleanup gates when using backend modes. Native Herdr state `idle` means available, not complete; completion still requires the applicable artifact, Git, review, and check evidence.

## One-session and one-worktree rules
- Use the same session everywhere: bare `herdr` + bare `pi-team-herdr`, or `herdr --session NAME` + `pi-team-herdr --session NAME`.
- Treat a worktree as the worker's durable identity. Never reuse a worktree concurrently for another writer.
- For an existing workspace ID, verify the wrapper version and help first. If `pi-team-herdr launch --workspace ID` returns `workspace setup failed`, stop retrying blindly; use native `herdr agent start` in an existing interactive pane, or launch without `--workspace` and inspect the resulting workspace. This observed failure is a wrapper/setup-path mismatch until proven otherwise, not evidence that the worker failed.
- Workmux setup is not readiness. If `pnpm install`/`post_create` fails (for example canvas/pangocairo), retain the worktree, record the exact error, and repair dependencies deliberately. `--no-hooks` may avoid the hook but leaves node_modules absent or partial; run the chosen dependency setup afterward and record a concrete readiness check (`test -d node_modules`, lockfile/package-manager command, and the focused command that passes). Do not dispatch on “dependencies appeared later” without evidence.

## Launch and verify
```bash
# Default session
herdr
pi-team-herdr --brief
pi-team-herdr list
pi-team-herdr launch --name worker-1 --brief-file docs/brief.md

# Explicit model/reasoning; verify the live result, never infer it from flags
pi-team-herdr launch --name reviewer --brief-file docs/brief.md \
  --model cvf/luna --thinking medium
herdr agent list
herdr agent read reviewer --lines 20
```

The live Pi footer is authoritative. Verify the displayed provider/model, thinking level, and context; an auto-loaded preset extension can override requested `--model`/`--thinking` (observed request `cvf/luna • medium` became `openai-codex/gpt-5.6-luna • high`). If the footer is wrong, do not proceed: fix the preset/configuration, restart the agent, and verify again.

The wrapper's `--wait`/setup waits are bounded. Native prompt submission is accepted work, not completion:

```bash
herdr agent prompt reviewer '@reviewer: inspect the diff'  # nonblocking submission
herdr agent list                                               # observe state separately
herdr agent prompt reviewer '@reviewer: inspect the diff' --wait --timeout 30000
```

A 30-second prompt timeout can occur while the prompt was accepted and the worker continues. Classify it as a control-plane wait timeout, then inspect native state/output and worktree artifacts; do not relaunch or report worker failure solely because `--wait` timed out. Use nonblocking submission when the task is expected to run longer than the wait budget.

## Resume after changes or worker death
Configuration and extension changes require a restart. Preserve the same worktree and Pi session; do not create a replacement task merely because a pane died.

```bash
# Confirm the old pane/session and worktree are preserved, then restart in the same cwd.
herdr agent list
herdr pane list
herdr agent start NAME --kind pi --pane PANE_ID --timeout 30000 -- \
  pi --continue --name NAME
herdr agent list
herdr agent read NAME --lines 30
```

Use `--continue` only after confirming the session belongs to the same project/worktree. Verify the new native `workspace_id`, working/idle state, footer provider/model/thinking/context, and the latest artifact/diff before sending more work. Three observed workers required this same-worktree `--continue` recovery after extension/config changes; their deaths were not proof of lost work.

To move an idle worker, preserve its worktree, close the old pane, start `pi --continue` in the destination workspace, then verify `workspace_id`. Do not pass a long Pi session-file path to `herdr agent start`; resume by project with `pi --continue`.

## CLI reference
| Command | Purpose |
|---|---|
| `--brief` / bare | JSON identity and command list |
| `--session NAME` | Scope every operation to a named Herdr session |
| `list [--human]` | List panes and native agent metadata |
| `launch --name N --brief-file P [--cwd P] [--workspace ID] [--thinking LEVEL]` | Wrapper launch; inspect help for current model/setup options |
| `send --manifest MANIFEST --text TEXT` | Wrapper submission; inspect help because manifest is required in current version |
| `status --manifest MANIFEST` | Manifest-backed status in current wrapper; use `herdr agent list` for native live status |
| `cleanup --pattern RX [--confirm] [--force]` | Dry-run by default; closes matched panes |

## Safe recipes
- Launch: `pi-team-herdr launch --name tests --brief-file /tmp/brief.md`.
- Dedicated space: first verify the wrapper supports the workspace path; otherwise use native Herdr start in an existing pane.
- Send: prefer nonblocking `herdr agent prompt NAME TEXT`; use `--wait` only when the timeout and expected completion state are appropriate.
- Inspect: `herdr agent list` and `herdr agent read NAME --lines 50`.
- Cleanup: `pi-team-herdr cleanup --pattern 'π - tests' --dry-run`; inspect JSON, then add `--confirm`.

## Safety contract
- Default stdout is JSON where supported; structured errors go to stderr. Check the live CLI for exit-code details.
- Cleanup requires an explicit regex and confirmation; dry-run first.
- Sending to a non-pi pane or a non-idle worker with an idle requirement must be refused unless deliberate force is requested.
- Never delete a worktree or close a pane until its session, uncommitted files, and final artifact are checked.
- Log workarounds as dogfood frictions; do not call them fixes without root-cause evidence.

## Dogfood evidence and ship gate
This documentation update incorporates the real HUB-246, HUB-247, and HUB-248 dispatch evidence: wrapper workspace setup failure; model/preset override; restart requirement; accepted prompts timing out at 30 seconds; manifest-required status; Pi v2 versus Herdr v8 integration skew; OMP/Pi extension-directory collision; workmux canvas/pangocairo setup failure and `--no-hooks` readiness gap; same-worktree `--continue` recovery for three dead agents; and duplicated-skill collision warnings.

This change edits only `SKILL.md`, not `team.ts` or its runtime. Pi-dogfood-os G1–G10 golden scenarios therefore do not apply; they are the ship gate for `team.ts` changes, not documentation-only updates. Validate the skill with metadata/structure checks, current CLI help, integration status, and command snippets. If the wrapper or team runtime changes later, run the full golden gate and retain the JSON record.

## Limitations
This lightweight wrapper does not expose every Herdr focus/wait/read command. Use native Herdr commands for advanced workflows, and always re-check the installed help before copying a command into an automation script.
