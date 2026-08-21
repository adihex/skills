# Offline hardening golden scenarios

Run all ten with `scripts/run-golden --all --json`. The runner imports the live adapters and uses disposable temporary repositories and fake commands. No live Herdr, Fut, GitHub, or network credentials are required.

| ID | Scenario | Pass evidence |
|---|---|---|
| G1 | Session mismatch is detected | `SESSION_MISMATCH` and no operation proceeds |
| G2 | Setup failure prevents worker launch | `SETUP_FAILED`; no `agent start` command |
| G3 | Setup queue is visible and bounded | bounded timeout plus `MAX_ACTIVE` admission refusal |
| G4 | Stable IDs survive name changes | renamed label still targets manifest `pane_id` |
| G5 | Message delivery requires Enter and readback | separate `pane send-keys enter` and acknowledgement |
| G6 | Dirty or unpushed worktree cannot become complete | completion gate returns `blocked` |
| G7 | CodeRabbit rate limiting becomes `blocked_external` | provider rate-limit response is not review approval |
| G8 | Clean pushed worker passes the completion gate | clean, synchronized, approved, passed evidence returns `complete` |
| G9 | Cleanup stops only owned processes and removes the worktree | owned Nx PID stopped; Watchman untouched; disposable path gone |
| G10 | Repeated cleanup is safe and protects the main checkout | second cleanup is `noop`; main checkout is refused |

A FAIL blocks release. The JSON output includes per-scenario evidence and traceable setup, launch, review, cleanup, retry, blocker, and concurrency metrics.
