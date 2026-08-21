---
name: pi-dogfood-os
description: Run offline dogfood evaluation for pi team orchestration, including deterministic G1–G10 gates, F15–F24 failure taxonomy, bounded dispatch metrics, and evidence logs. Use when users ask to dogfood a team change, run golden scenarios, classify a worker failure, or review orchestration metrics.
license: MIT
compatibility: [pi, python3]
risk: safe
category: workflow
tags: [dogfood, golden-scenarios, metrics, orchestration, evaluation]
date_added: 2026-08-01
---
# pi-dogfood-os

## When to use

Use after an orchestration adapter, lifecycle, cleanup, or dispatch-policy change; when a worker aborts or loses a deliverable; or when the user asks for golden scenarios or a scorecard. The gate is offline and does not require Herdr, Fut, GitHub, or network credentials.

## Ship gate

Run the deterministic live-code scenarios after every orchestration change:

```bash
python3 skills/pi-dogfood-os/scripts/run-golden --all --json
```

G1 detects session mismatch. G2 blocks launch after setup failure. G3 bounds setup and active-worker queues. G4 proves stable IDs survive label changes. G5 proves Enter submission and readback. G6 blocks dirty/unpushed completion. G7 classifies CodeRabbit rate limiting as `blocked_external`. G8 accepts a clean pushed reviewed worker. G9 stops only owned processes and removes a disposable worktree. G10 proves repeated cleanup is safe and protects the main checkout.

Run the independent Hax runtime gate after Hax/backend changes:

```bash
python3 skills/pi-dogfood-os/scripts/run-hax-golden --json
```

H1–H13 cover Pi defaults, explicit Hax manifests, missing binary/auth/model blockers, readiness and Enter transport, one-shot output, HTTP 429, coexistence cleanup, shared completion, tmux send ordering, WezTerm fencing/safety, and Herdr's shell-backed Hax adapter. The harness uses only fake commands and temporary repositories; it never calls a live subscription.

A scenario must import live code and emit reproducible evidence. Any FAIL blocks release. Use `--subset G1-G4,G8` only for a time-boxed diagnostic, never as the final gate.

## Bounded dispatch

Use [Herdr dispatch policy](../herdr-pi-team/references/dispatch-policy.md) and `../herdr-pi-team/scripts/dispatch_policy.py`: default maximum four active workers, setup concurrency two, staggered launch, turn and wall-clock budgets, and memory backpressure. Do not launch fourteen full-repository workers by default.

## Capture and metrics

- Capture friction immediately using [templates/dogfood-log-entry.md](templates/dogfood-log-entry.md).
- Run `scripts/dogfood-score STATUS_DIR --json` for dispatch status metrics.
- `run-golden --all --json` records setup wait, launch time, worker duration, turns, retries, memory/concurrency events, review latency, cleanup latency/failures, aborted workers, dirty completion attempts, and external blockers.
- Use [templates/triage.md](templates/triage.md) for weekly review.

## Failure taxonomy

F1–F14 are the seed-session classes. F15–F24 cover stable targeting, Enter submission, setup races, state confusion, dirty completion, review rate limits, process leaks, duplicate ownership, partial deletion, and memory-pressure collapse. Each entry has trigger, evidence, prevention, detection, recovery, and a regression scenario in [references/friction-taxonomy.md](references/friction-taxonomy.md).

## Rules

- Never claim a worker finished from a status summary alone.
- `idle` is an observation, not completion.
- Never execute worker output or log prompts, tokens, cookies, or secrets.
- Never poll peer workers from a verifier; inspect static artifacts and live code gates.
- Keep cleanup dry-run by default and never delete a dirty or unsynchronized worktree.
