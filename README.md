# Agentic orchestration skills

A small set of Pi-compatible skills for visible workers, lifecycle evidence, and offline orchestration tests.

## Requirements

- Python 3.10+ (standard library only for bundled scripts).
- Git 2.30+ for worktree and push evidence.
- Pi and its team extension, installed from their official distributions.
- Optional backends: Herdr, Fut, tmux, WezTerm, and Hax. Each skill checks its selected backend before side effects.
- Hax subscription mode uses the official Codex CLI and `codex login`; no API key is required.
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
python3 -m unittest discover -s skills/tmux-pi-team/tests -v
python3 -m unittest discover -s skills/wezterm-pi-team/tests -v
python3 -m compileall -q skills scripts tests
python3 skills/pi-dogfood-os/scripts/run-golden --all --json
python3 skills/pi-dogfood-os/scripts/run-hax-golden --json
git diff --check
```
Python runtime scripts are checked with Ruff and compileall; ShellCheck is run only on files ending in `.sh`.

The golden gate runs G1–G10 against fake Herdr/Git/GitHub commands and disposable temporary Git repositories. It never requires GitHub authentication or deletes a real checkout. A failed scenario blocks release.

## Herdr worker mailbox

Register modern Pi workers in one untracked run mailbox, then make one blocking call instead of repeatedly checking worker status:

```bash
pi-team-herdr launch --name review-worker --cwd WORKTREE --new-workspace \
  --brief-file BRIEF --verify-working --run-id review-123 --mailbox RUN/mailbox.json
pi-team-herdr await --mailbox RUN/mailbox.json --all
```

`await --any` returns the next completed or blocked worker. `await --all` waits for all selected workers. `inbox` performs one non-blocking observation and delivers anything ready. Done events include the complete final Pi assistant result from its session artifact; blocked events remain intervention states. Mailbox delivery never marks the Git/review/check workflow complete. See `skills/herdr-pi-team/references/mailbox.md` for identity, deduplication, and concurrency guarantees.

## Hax backend

Pi remains the default in every runtime. Hax is explicit opt-in and uses one shared backend with thin runtime adapters:

```text
codex login
pi-team-herdr launch --name review-worker --backend hax --provider codex --model MODEL --effort high --brief-file FILE
pi-team-tmux launch --name review-worker --backend hax --provider codex --model MODEL --effort high --brief-file FILE
pi-team-pane launch --name review-worker --backend hax --provider codex --model MODEL --effort high --brief-file FILE
```

Use `--mode oneshot` only when steering is unnecessary. Hax readiness, literal send, Enter submission, manifest state, Git/review/check gates, and cleanup remain runtime-specific but evidence-gated. HTTP 429 is external quota exhaustion and never triggers a silent fallback to Pi. Run `doctor --backend hax` for safe capability diagnostics; credential contents are never printed or persisted.

`run-hax-golden` runs H1–H13 with fake Hax, Herdr, tmux, WezTerm, Git, and GitHub commands. It never calls a live subscription.

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
