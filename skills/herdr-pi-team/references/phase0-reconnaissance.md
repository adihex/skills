# Phase 0 reconnaissance

Baseline: `9efc14b1faea53e7111c9e9de1edc2d4f31ce5e4` on `agent/skills-hardening`.
The worktree was clean at baseline. The only pre-existing untracked path observed after goal setup is `.pi/`, which is pi goal bookkeeping and is not part of this feature.

## Dependency inventory

| Reference | Type | Existence at baseline | Notes |
|---|---|---:|---|
| `pi-team-herdr` | bundled script | yes | `skills/herdr-pi-team/scripts/pi-team-herdr`; executable |
| `pi-team-fut` | bundled script | no | No Fut package exists in this checkout; documentation must not advertise it. |
| `pi-team-tmux` | bundled script | yes | `skills/tmux-pi-team/scripts/pi-team-tmux`; executable |
| `pi-team-pane` | bundled script | yes | `skills/wezterm-pi-team/scripts/pi-team-pane`; executable |
| `dogfood-score` | bundled script | yes | `skills/pi-dogfood-os/scripts/dogfood-score`; executable |
| `run-golden` | bundled script | yes | `skills/pi-dogfood-os/scripts/run-golden`; executable |
| `audit-dev-logs.sh` | bundled script | yes | `skills/yash-logger/scripts/audit-dev-logs.sh`; executable |
| `references/*.md`, `templates/*.md` | bundled resources | yes | all paths referenced by the five skill packages exist |
| `herdr` | external command | yes on this host | `<host-bin>/herdr`; no live session used during reconnaissance |
| `fut` | external command | no on this host | no binary in `PATH`; Fut fixtures are required for offline tests |
| `tmux` | external command | yes on this host | `<host-bin>/tmux`; no server was started |
| `wezterm` | external command | yes on this host | `<host-bin>/wezterm`; no mux was contacted |
| `pi` | external command | yes on this host | `<host-bin>/pi` |
| `gh` | external command | yes on this host | `<host-bin>/gh`; no network/API call was made |
| `shellcheck` | optional external command | yes on this host | `<host-bin>/shellcheck` |
| `pi extension` | external file | yes on this host | `<pi-home>/agent/extensions/team.ts`; read-only prerequisite |
| Fut Pi integration | external file | no on this host | `<pi-home>/agent/git/github.com/mikker/fut/integrations/pi/fut.ts` is absent |
| archived dogfood evidence | external evidence | no on this host | repository copy under `references/operating-model.md` is present |

Referenced environment variables: `DOGFOOD_STATUS_DIR`, `DOGFOOD_LOG`, `WEZTERM_CLASS`, `WEZTERM_PANE`, and `PI_TEAM_PANE_WZ_TIMEOUT`. No secret values were read or logged.

## Baseline failure fixtures

`tests/fixtures/phase0/known-failures.json` records eight deterministic synthetic traces for the known failures: missing Enter submission, unstable name lookup, setup/launch race, idle-versus-done confusion, dirty completion, CodeRabbit rate limiting, stale worker processes, and interrupted worktree removal. Real Herdr, Fut, GitHub, and user worktrees were not touched. The later phase tests must turn each trace into a passing regression scenario.

## Reproduction boundary

The baseline wrappers are documentation-sized command adapters. They do not contain a durable manifest, setup barrier, state machine, Git completion gate, CodeRabbit response tracker, or worktree cleanup transaction. Therefore the eight traces are recorded as synthetic fixtures rather than reproduced against live infrastructure. `fut` is not installed, and no Herdr session or GitHub network operation is safe or required for the offline baseline gate.
