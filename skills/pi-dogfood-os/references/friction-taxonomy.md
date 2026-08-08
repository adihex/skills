# pi-dogfood-os — Friction Taxonomy (seed session F1–F14 → preventive rules)

> Condensed from the 2026-08-01 seed friction log. Use this table to (a) classify a new friction, and (b) pre-empt known failure classes when authoring worker briefs. Each row ends in a **preventive rule** you can copy into a prompt or checklist.

## Classification table

| ID | Friction | Sev | Class | Preventive rule |
|---|---|---|---|---|
| F1 | Turn-cap aborts dominate; soft steer is not binding (17/48 workers aborted; 0% wrapped up after steer) | P1 | turn-budget | "Right-size `max_turns` to task volume (research 16–20; inspect+implement+verify 24–30). Assume the soft steer is advisory." |
| F2 | Aborted-but-useful workers mislabeled `status: "failed"` (2/3 failed yet 9/9 deliverables) | P1 | status-semantics | "Read `activity` and the worker files before trusting `status`. A cutoff with partial delivery is recoverable; an error is not." |
| F3 | Deliverables lost when a worker aborts before writing (no write-early) | P1 | turn-budget | "Write your deliverable file by turn N, then refine. A half-written report beats a lost one." |
| F4 | Verifiers burn turns polling implementers instead of auditing | P2 | verification | "Inspect static state only; never poll other workers; re-check the final mtime before reporting." |
| F5 | No live E2E verification; harness is a copy and can silently drift | P2 | verification | "Harnesses must import live code or fail loudly on drift; add at least one live smoke step to the gate." |
| F6 | Scroll-jump: pi-tui clears scrollback on above-viewport changes; team.ts widget churn is the trigger | P1 | ui | "Don't repaint widgets on a fixed timer — repaint only on real status transitions (extension-side mitigation)." |
| F7 | Orphan-pane bug in `pi-team-pane` launch (validate after spawn) | P1 | safety | "Validate all inputs before any side effect; prove 'bad input ⇒ no side effect' with a negative test." |
| F8 | CLI contract deviations (cleanup exit codes, missing-name charset) | P2 | contract | "Document the contract; loud refusal beats silent success for destructive ops." |
| F9 | Concurrent-edit races on team.ts while workers are mid-flight | P2 | concurrency | "One writer to team.ts at a time; verify against final mtime; don't start a second team.ts-mutating dispatch until the first lands." |
| F10 | Research workers go breadth-first and never finish writing | P2 | turn-budget | "Cap fetches ('≤6 fetches, then write findings'); record sources incrementally." |
| F11 | Stragglers dominate wall-clock (34 min vs 3.3 min median) | P2 | turn-budget | "Fail-fast dependent workers when a peer aborts; consider per-worker wall-clock caps." |
| F12 | Dead code / partial wiring shipped (defined-but-never-called views) | P2 | gate | "Green = executed, not just defined; add a golden scenario per new code path." |
| F13 | Status-dir clutter / stale panes accumulate | P3 | hygiene | "Clean stale markers with dry-run first; rotate the status dir on a schedule." |
| F14 | Overlapping duplicate dispatch chains on the same artifact set | P2 | concurrency | "Before dispatching, check for a completed run of the same brief; name re-runs explicitly (-round2)." |

## The four failure classes to pre-empt in every brief

1. **Turn-budget aborts (F1, F3, F10, F11 — 100% of seed failures).** The single biggest lever. Every brief carries: right-sized `max_turns`, a write-early deadline, a fetch cap, fail-fast on peer abort.
2. **Verification drift (F4, F5).** Verifiers audit static state, never poll; harnesses import live code; gates are executed, not inspected.
3. **Concurrency & duplication (F9, F14).** One writer per shared file; check for a completed run before dispatching the same brief.
4. **Safety & contract (F7, F8, F13).** Validate before side effects; dry-run destructive ops; loud refusal over silent success.

## Scoring a new friction

- Severity: S1 (data loss) / S2 (feature broken) / S3 (friction, recoverable) / S4 (cosmetic).
- Evidence-first: never mark "fixed" without a gate (tsc exit code, harness output, file diff, grep assertion, pane capture). Otherwise: **open/investigate**.
- Promotion rule: 3rd occurrence in 7 days → +1 severity, fix this cycle.
