---
name: pi-dogfood-os
description: >-
  Run pi's dogfooding operating loop for the team feature (team.ts): capture
  friction at the moment it happens, triage weekly, rerun the G1–G10 golden
  scenarios as a ship gate after every team.ts change, and compute the scorecard
  from dispatch status JSONs. Use when dispatching real work through pi's team
  feature and you want a feedback record; when a team.ts change needs a ship-gate
  check before it is trusted; when a worker aborts or a deliverable is lost and
  the failure needs a taxonomy entry; when starting a weekly dogfood triage; when
  asked to "run the golden scenarios", "compute the scorecard", or "dogfood this
  change".
license: MIT
compatibility: [pi, claude-code]
risk: safe
category: workflow
tags: [dogfood, feedback-loop, multi-agent, metrics, golden-scenarios, ship-gate, turn-caps]
date_added: 2026-08-01
---

# pi-dogfood-os

## Overview

We are the first user and the builder of pi's team feature. This skill makes the dogfood loop repeatable and cheap: capture friction in 30 seconds, triage weekly, and block any `team.ts` change that fails the golden scenarios. It packages the 2026-08-01 dogfooding research (evidence: 22+ dispatches, 48 workers, 14 logged frictions) into a working kit — no new ceremony beyond what the evidence already demands.

The loop it encodes:

```
[PLAN] → [DISPATCH team run] → [OBSERVE] → [TRIAGE] → [FIX] → [VERIFY] → [GOLDEN RERUN] → [SHIP GATE]
   ▲                                                                                       │
   └──────────────────────────── < 24h backlog, next dogfood cycle ◄────────────────────────┘
```

## When to use

Use when:
- the user asks to dogfood a `team.ts` / extension change, or "run the golden scenarios"
- a `team.ts` change is about to be used for the next dispatch (ship gate: goldens green first)
- a worker aborts, a deliverable is lost, or a workaround was needed — log it now, not at triage
- a weekly triage or scorecard review is due
- a turn-cap abort or status mislabeling needs a taxonomy classification

## Quick start (the 3 rituals)

1. **Capture (end of every session, 30 s):** append one block from `templates/dogfood-log-entry.md` to your dogfood log (default `dogfood-log.md` in the project dir, or `DOGFOOD_LOG`). Include dispatch ids, one-line frictions with evidence paths, wins, and a metrics snapshot.
2. **Gate (after every team.ts change):** run `scripts/run-golden`. Any FAIL blocks ship. Critical subset when time-boxed: `scripts/run-golden --subset G1-G4,G8` (~15 min).
3. **Triage (weekly, 30 min):** use `templates/triage.md`; compute the scorecard with `scripts/dogfood-score <status-dir>` and compare against last week.

## Artifacts

| File | What it is | When to open |
|---|---|---|
| `references/operating-model.md` | The loop, roles, severity table, decision rules, cadence | Read once; consult on severity/decision calls |
| `references/golden-scenarios.md` | G1–G10 rerunnable scenarios + rerun protocol (single source of truth for `run-golden`) | Every team.ts change; do not edit lightly |
| `references/friction-taxonomy.md` | F1–F14 classes from the seed session, each with a preventive rule | When classifying a new friction or writing a worker brief |
| `templates/dogfood-log-entry.md` | One-block session entry (30 s) | End of each session |
| `templates/triage.md` | Weekly triage agenda + decision rules | Weekly ritual |
| `scripts/dogfood-score` | Scorecard metrics from dispatch JSONs (activation, completion, abort share, latency, turns-at-abort) | Weekly; after any dispatch cluster |
| `scripts/run-golden` | Interactive G1–G10 runner that writes PASS/FAIL rows to the dogfood log; exit non-zero on FAIL | After every team.ts change (ship gate) |

## Config

Scripts honor environment variables (all optional):

| Env | Default | Used by |
|---|---|---|
| `DOGFOOD_STATUS_DIR` | `/tmp/team-task/status` | `dogfood-score` (also first CLI arg) |
| `DOGFOOD_LOG` | `./dogfood-log.md` | `run-golden` output (also `--log`) |

## Core rules (from the evidence — non-negotiable)

1. **Turn budget is the #1 failure mode.** 100% of seed-session worker failures were turn-cap aborts, 0% code errors. Right-size `max_turns` to task volume: read-only research 16–20, inspect+implement+verify 24–30 (budget includes the verifier).
2. **Write-early-then-improve.** Every worker brief: "Write your deliverable file by turn N, then refine." A half-written report beats a lost one (deliverable survival on abort rose to ~50% solely from this).
3. **Never poll other workers.** Verifiers inspect static state only (files, status JSON, diffs); they never poll peers.
4. **Verify every claim.** Every claim maps to a gate: `tsc` exit code, harness output, file diff, grep assertion. Mark "inspected, not executed" honestly. Harnesses must import live code, not be copies.
5. **Workarounds are frictions, not fixes.** Manual workaround adopted → log as friction (S3), flag the root cause.
6. **Golden scenarios green = ship gate.** A `team.ts` change does not ship (and is not used for the next dispatch) until the full G1–G9 gate passes, plus G10 when a repro exists; when explicitly time-boxed, the minimum gate is G1–G4 + G8. Any FAIL blocks ship.
7. **Human-in-the-loop.** `@name` / `team_message` are the escape hatches; never auto-dispatch recursively from inside a worker; cleanup stays dry-run by default.

## Failure taxonomy cheat-sheet (details: `references/friction-taxonomy.md`)

- **Turn-budget abort** (`activity: "aborted"`, ~all failures): fix = right-size turns + write-early + binding soft limit.
- **Cutoff-vs-error mislabeling** (`aborted` reported as `"failed"`): a cutoff with partial delivery is *recoverable*; an error needs investigation. Note it in the log until the status model emits a distinct `cutoff`.
- **Lost deliverables** on abort: prompt failure, not model failure — write-early fixes it.
- **Verifier poll-waste**: verifier prompts must forbid polling and re-check final mtime.
- **Concurrent-edit races / duplicate chains**: one writer to `team.ts` at a time; check for a completed run of the same brief before dispatching.

## References

- Full seed evidence: friction log, scorecard, research, recommendations archived by `dogfood-packager` (see `/tmp/team-task/dogfood/` and this skill's `references/`).
- External grounding (verified sources): Wikipedia "Eating your own dog food", Paul Graham "Do Things that Don't Scale", GitLab "Dogfooding for R&D" handbook, DORA Four Keys, Anthropic agent best practices, Lean startup BML. Summarized in the archived `research.md`.
