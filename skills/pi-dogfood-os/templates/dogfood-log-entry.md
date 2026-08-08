# Dogfood Log Entry — Template

> Copy one block per session into your dogfood log (default `dogfood-log.md`, or `DOGFOOD_LOG`). Goal: 30 seconds. Capture at the moment of friction, not at weekly triage.

```markdown
## YYYY-MM-DD — <session label, e.g. "router wiring round 2">

**Ran:** <dispatch ids, e.g. dispatch-1785550175708> · mode: <parallel|chain|run> · workers: <n> · model: <model> · max_turns: <n>
**Panes:** <pane ids launched> · **Brief:** <path>

### Frictions (one line each)
| # | Friction | Sev | Evidence (path) | Owner | Next action |
|---|---|---|---|---|---|
| 1 | <what broke/slowed> | S1-S4 | <status json, log, file> | <who> | <concrete next step> |
| 2 | ... | | | | |

### Wins / surprises
- <something that worked better than expected>

### Metrics snapshot (from `scripts/dogfood-score`)
- Dispatches: <n> · Workers done/failed: <n/n> · Aborted: <n> · Green dispatches: <n/n> · Median latency: <s> · Golden rerun: <PASS|FAIL — G#>

### Follow-ups
- [ ] <item promoted to triage queue>
```

---

### Severity cheat-sheet (see `references/operating-model.md`)
- **S1** data loss / lost deliverable / run unusable → fix now, block dispatch
- **S2** feature path broken → fix this cycle if small
- **S3** friction, recoverable (turn-abort mislabeling, polling waste) → triage queue
- **S4** cosmetic / nice-to-have → backlog, bug bash

### Evidence-first rule
Never write "fixed" without a gate: tsc exit code, harness output, file diff, grep assertion, or pane capture. Otherwise mark **open/investigate**.
