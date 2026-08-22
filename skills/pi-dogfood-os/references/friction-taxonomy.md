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
## Hardening taxonomy F15–F24

Each hardening entry is a regression contract with trigger, evidence, prevention, detection, recovery, and scenario.

### F15 — name/ID targeting mismatch
- **Trigger:** a pane label changes or name lookup returns `agent_not_found`.
- **Evidence:** manifest `workspace_id`, `tab_id`, and `pane_id`; target lookup result.
- **Prevention:** use stable IDs from the manifest and resolve one explicit session.
- **Detection:** reconcile reports `missing_pane` or `target_not_found`.
- **Recovery:** stop the send, refresh the manifest from the selected session, and require operator review.
- **Regression:** G4.

### F16 — message typed but not submitted
- **Trigger:** text is visible in a pane but the worker did not receive it.
- **Evidence:** separate send and Enter operations plus pane readback hash/acknowledgement.
- **Prevention:** send literal text, submit Enter separately, then read back.
- **Detection:** missing acknowledgement is a hard error.
- **Recovery:** do not retry blindly; preserve the failed send event and retry once after operator review.
- **Regression:** G5.

### F17 — setup readiness race
- **Trigger:** a worker launches while setup is queued, failed, or timed out.
- **Evidence:** setup status, duration, failure output, and absence of `agent start`.
- **Prevention:** bounded setup barrier before worker launch.
- **Detection:** setup failure/timeout state and launch audit.
- **Recovery:** preserve `setup_failed` or `blocked`; repair setup before retry.
- **Regression:** G2 and G3.

### F18 — idle/done state mismatch
- **Trigger:** native `idle` is mistaken for completed work.
- **Evidence:** native state, manifest state, final report, Git/push/review/check evidence.
- **Prevention:** `idle` is observational only; completion is state-machine gated.
- **Detection:** native/manifest disagreement during reconcile.
- **Recovery:** return to `verifying` or `blocked`, never promote from pane text.
- **Regression:** G6 and G8.

### F19 — dirty worktree reported complete
- **Trigger:** a worker claims completion with local changes.
- **Evidence:** `git status --porcelain` and commit SHA.
- **Prevention:** clean-worktree gate before completion.
- **Detection:** Git gate returns `DIRTY_WORKTREE`.
- **Recovery:** keep the worktree; ask the worker to commit or explain changes.
- **Regression:** G6.

### F20 — CodeRabbit rate-limit misclassification
- **Trigger:** a rate-limit message is treated as an approved review.
- **Evidence:** provider response body, review decision, and reply IDs.
- **Prevention:** classify rate limits as `blocked_external` with bounded retry.
- **Detection:** rate-limit pattern in review retrieval.
- **Recovery:** preserve the worktree and wait for operator-authorized retry.
- **Regression:** G7.

### F21 — teardown process leak
- **Trigger:** Nx, Git fsmonitor, or worker children remain after cleanup.
- **Evidence:** PID, exact cwd, process kind, and post-stop inspection.
- **Prevention:** stop only owned PIDs whose cwd equals the target worktree.
- **Detection:** cleanup process verification.
- **Recovery:** leave `cleanup_pending` and report remaining PIDs.
- **Regression:** G9.

### F22 — duplicate worktree ownership
- **Trigger:** two active runs claim one worktree.
- **Evidence:** run IDs and ownership fields in manifests.
- **Prevention:** refuse cleanup and launch when ownership is ambiguous.
- **Detection:** reconcile ownership mismatch.
- **Recovery:** operator selects the owner; no automatic deletion.
- **Regression:** G4 and G10.

### F23 — cleanup partial deletion
- **Trigger:** workspace close or worktree removal stops halfway through.
- **Evidence:** `cleanup_pending` manifest and exact failed command.
- **Prevention:** transactional order, dry-run default, bounded retries.
- **Detection:** path/workspace verification after each step.
- **Recovery:** preserve the manifest and leave the workspace for manual cleanup.
- **Regression:** G10.

### F24 — memory-pressure dispatch collapse
- **Trigger:** too many full-repository workers start together.
- **Evidence:** active/setup counts, memory ratio, wait and retry metrics.
- **Prevention:** default max four workers, setup concurrency two, staggered launches, and backpressure.
- **Detection:** deterministic admission refusal codes.
- **Recovery:** queue work and launch only after capacity returns.
- **Regression:** G3.


## The four failure classes to pre-empt in every brief

1. **Turn-budget aborts (F1, F3, F10, F11 — 100% of seed failures).** The single biggest lever. Every brief carries: right-sized `max_turns`, a write-early deadline, a fetch cap, fail-fast on peer abort.
2. **Verification drift (F4, F5).** Verifiers audit static state, never poll; harnesses import live code; gates are executed, not inspected.
3. **Concurrency & duplication (F9, F14).** One writer per shared file; check for a completed run before dispatching the same brief.
4. **Safety & contract (F7, F8, F13).** Validate before side effects; dry-run destructive ops; loud refusal over silent success.

## Scoring a new friction

- Severity: S1 (data loss) / S2 (feature broken) / S3 (friction, recoverable) / S4 (cosmetic).
- Evidence-first: never mark "fixed" without a gate (tsc exit code, harness output, file diff, grep assertion, pane capture). Otherwise: **open/investigate**.
- Promotion rule: 3rd occurrence in 7 days → +1 severity, fix this cycle.
