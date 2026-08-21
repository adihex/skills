# Agentic orchestration skills

A small set of Pi-compatible skills for visible workers, lifecycle evidence, and offline orchestration tests.

## Requirements

- Python 3.10+ (standard library only for bundled scripts).
- Git 2.30+ for worktree and push evidence.
- Pi and its team extension, installed from their official distributions.
- Optional backends: Herdr, Fut, tmux, and WezTerm. Each skill checks its backend before side effects.
- Cleanup process identity checks use `ps` and `lsof`.

The repository does not bundle Herdr, Fut, Pi, GitHub CLI, or a network service. Install those from their official project instructions and verify with `<command> --version`. Use fake executables in `tests/fixtures/` for offline development.

## Install scripts

Run from the repository root:

```bash
export PATH="$PWD/skills/herdr-pi-team/scripts:$PWD/skills/fut-pi-team/scripts:$PWD/skills/tmux-pi-team/scripts:$PWD/skills/wezterm-pi-team/scripts:$PWD/skills/pi-dogfood-os/scripts:$PATH"
python3 scripts/validate_skills.py
```

Do not add generated status directories or manifests to the repository. Keep manifests under an operator-owned run directory. Set `DOGFOOD_STATUS_DIR` and `DOGFOOD_LOG` explicitly when their defaults are not appropriate.

## Offline validation

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/herdr-pi-team/tests -v
python3 -m compileall -q skills scripts tests
python3 skills/pi-dogfood-os/scripts/run-golden --all --json
python3 -m compileall -q skills scripts tests
git diff --check
```

The golden gate runs G1–G10 against fake Herdr/Git/GitHub commands and disposable temporary Git repositories. It never requires GitHub authentication or deletes a real checkout. A failed scenario blocks release.

## Optional integration checks

Run only when the relevant external service is intentionally available:

```bash
herdr pane list
fut list --json
tmux list-panes -a
wezterm cli list --format json
gh auth status
shellcheck skills/**/scripts/*
```

Do not run destructive cleanup against a real worktree while validating. Preview first:

```bash
pi-team-herdr cleanup --manifest RUN/manifest.json --worktree-root WORKTREES --main-checkout CHECKOUT
```

Apply cleanup only after inspecting the JSON and confirming ownership:

```bash
pi-team-herdr cleanup --manifest RUN/manifest.json --worktree-root WORKTREES --main-checkout CHECKOUT --confirm
```

Automatic cleanup is disabled by default. To enable the bounded watcher, supply one run ID, an owned manifest directory, and an explicit polling interval:

```bash
pi-team-herdr watch --manifest-dir RUN --run-id RUN_ID --worktree-root WORKTREES --main-checkout CHECKOUT --cleanup --require-pushed --poll 15
```

Stop the watcher with Ctrl-C. It uses a per-manifest lock and never watches other run IDs. To disable automatic cleanup, omit `--cleanup`; the watcher then emits plans only.

## Skill map

- `herdr-pi-team`: durable manifest, state machine, review/check gates, and safe worktree lifecycle.
- `fut-pi-team`: visible Fut operations with honest terminal-input and native-state limitations.
- `tmux-pi-team`: visible tmux operations with explicit pane identity and no native Pi state claim.
- `wezterm-pi-team`: visible WezTerm operations with fenced submission and protected panes.
- `pi-dogfood-os`: offline G1–G10 gate, F15–F24 taxonomy, and metrics.
- `yash-logger`: structured logging guidance for other projects.
