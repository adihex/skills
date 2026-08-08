# Weekly Friction Triage — Template

> Cadence: weekly, 30 min, triager (human + parent agent). Input: dogfood log + `scripts/dogfood-score` output. Output: prioritized issue queue below + next-cycle plan.
> Rules: 3rd occurrence in 7 days → +1 severity; golden failure blocks ship; no evidence → stays "open/investigate".

## 1. Metrics review (5 min)
- Run `scripts/dogfood-score <status-dir>` and compare vs last week: completion rate, abort rate, cutoff-vs-failed ratio, median latency.
- ⬆/⬇/→ trend for each. Any metric regressing ≥20% → find cause this week.

## 2. Friction queue (15 min) — dedupe & prioritize

| ID | Friction (from log) | Sev | Occurrences (7d) | Evidence | Owner | Decision (Fix-now / Schedule / Backlog / Won't-fix) | Next action |
|---|---|---|---|---|---|---|---|
| F-<n> | | | | | | | |

Decision rules:
- Fix-now: S1, S2-small (<50 lines), any 3rd occurrence.
- Schedule: S2-medium, S3 with a clear owner; attach to the relevant team.ts session.
- Backlog: S4; revisit at bug bash.

## 3. Verification & gates (5 min)
- Golden rerun status after the last change: <PASS/FAIL, which scenarios> (run via `scripts/run-golden`).
- Harness drift check: is the router harness a copy or a live import? Drift? (Y/N).
- Outstanding S1s from last week: <all closed? Y/N>.

## 4. Next-cycle plan (5 min)
- One sentence: what feature/tooling change is this week's focus (e.g., "turn-cap graceful abort + cutoff status").
- Dispatch plan: workers, `max_turns` right-sized per task volume, write-early clause present? (Y/N).
- Goldens to rerun after the change: <G-list>.

## 5. Escalations
- Anything needing pi upstream (e.g., scroll-jump, soft-limit binding, `cutoff` status classification): list with artifact paths.
