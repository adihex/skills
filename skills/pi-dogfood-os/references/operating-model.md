# pi-dogfood-os — Operating Model

> Distilled from the 2026-08-01 seed session (evidence: 22+ dispatches, 48 workers, 14 frictions). Full seed: `$DOGFOOD_ARCHIVE/operating-model.md`.

## The loop

```
[PLAN] → [DISPATCH team run] → [OBSERVE] → [TRIAGE] → [FIX] → [VERIFY] → [GOLDEN RERUN] → [SHIP GATE]
```

One cycle = one focused feature change (router wiring, canvas fix, turn-cap semantics). Cadence: **continuous dogfood** (every real session) + **weekly triage** + **golden rerun after every team.ts change**.

## Roles

| Role | Who | Responsibilities | Anti-pattern to avoid |
|---|---|---|---|
| **User / operator** | human driving pi | Sets intent, launches panes/dispatches, steers via `@name`, records observations | Deferring the log entry — capture at the moment of friction or it is lost |
| **Parent agent** | orchestrating pi session | Reads the brief, provisions `max_turns` to task volume, dispatches workers, owns acceptance, writes a post-mortem if a worker dies | Blindly reusing default turn caps; trusting `status:"completed"` without checking worker statuses |
| **Worker teams** | subagents | Deliver a named file deliverable **early**, then refine; inspect static state only | Polling other workers; breadth-first reading with no write |
| **Verifier** | dedicated verifier worker or parent | Runs gates (tsc, harness, greps) against *final* state; writes the report first, refines later; labels executed vs inspected | Copying logic into the harness; declaring PASS on inspection alone |
| **Triager** | human + parent (weekly) | Converts friction log → prioritized issues, assigns owner + next action, closes the loop | Letting the backlog grow without a decision rule |

## Severity and decision rules

| Severity | Definition | Decision |
|---|---|---|
| S1 | Data loss / lost deliverable / run unusable | Fix immediately, block further dispatch until patched; add a golden scenario |
| S2 | Feature path broken (router gap, widget never renders) | Fix this cycle if small (<50 lines); else next cycle; add a golden scenario |
| S3 | Friction / slow / confusing but recoverable (turn-abort mislabeling, polling waste) | Triage queue; fix when touching that code; note in prompts now (no-code) |
| S4 | Cosmetic / nice-to-have | Backlog; revisit at bug bash |

**Decision rules**
1. 3rd occurrence of the same friction in 7 days → promote one severity level, fix this cycle.
2. Golden scenario fails after a team.ts change → the change does not ship until it passes (ship gate).
3. A worker aborts before writing its deliverable → treat as S1 pattern, even if the dispatch "completed".
4. No objective evidence (test run, log, file diff) → the item stays "open/investigate", not "fixed".
5. Manual workaround adopted → flag as S3 friction, not an acceptable end state.

## Cadence

| Ritual | Frequency | Owner | Input → Output |
|---|---|---|---|
| Dogfood diary entry | after each session | user/parent | session notes → `dogfood-log.md` |
| Golden scenario rerun | after every team.ts change | verifier worker | change → PASS/FAIL per scenario (`run-golden`) |
| Friction triage | weekly (30 min) | triager | friction log + scorecard → prioritized issue queue |
| Build-measure-learn review | weekly | triager | scorecard deltas + fixed/backlog → next-cycle plan |
| Bug bash | monthly or pre-release | whole team | exploratory session → 10–20 friction entries, no fixes during bash |
| Release gate | per merged change | verifier | golden scenarios + tsc + harness → ship/block |

## AI-agent-specific rules

1. **Turn budgets are the #1 failure mode.** Provision `max_turns` to task volume: read-only research 16–20; inspect+implement+verify 24–30. Budget *includes* verify.
2. **Write-early-then-improve.** Every worker brief: "Write your deliverable file by turn N, then refine."
3. **No cross-worker polling.** Verifiers inspect static state, never poll other workers; re-check final mtime before reporting.
4. **Verify agent claims, always.** Every claim maps to a gate (tsc exit code, harness output, file diff, grep assertion). Mark "inspected, not executed" honestly.
5. **Self-referential risk.** Every team.ts change goes through the golden rerun *before* being used to dispatch the next task.
6. **Human-in-the-loop steering.** `@name` / `team_message` are the escape hatches; a running worker must never run away past its budget.
7. **Runaway-automation guard.** Never auto-dispatch recursively from within a worker; only the parent dispatches. Pane cleanup is dry-run by default and never kills pane 0 / the current pane.
