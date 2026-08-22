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

## Hax runtime scenarios

Run all thirteen with `scripts/run-hax-golden --json`. This is an independent fake-command/temp-repository harness; it never calls Hax, Codex, Herdr, tmux, WezTerm, or GitHub live services.

| ID | Scenario | Pass evidence |
|---|---|---|
| H1 | Pi remains the default in Herdr, tmux, and WezTerm | all three manifests report `backend: pi` |
| H2 | Explicit Hax launch records configuration | backend, runtime, provider, model, effort, and capabilities are present |
| H3 | Missing Hax fails before pane creation | `hax_missing`; no split/workspace side effect |
| H4 | Missing Codex auth is actionable | `codex_auth_missing`; credential contents absent |
| H5 | Missing model fails before launch | `MODEL_MISSING` in every runtime |
| H6 | Interactive readiness and Enter submission | readiness precedes runtime-specific send and Enter |
| H7 | One-shot output is captured and non-steerable | stdout/stderr and `steerable: false` are reported |
| H8 | HTTP 429 is external blocking | `HTTP_429`/`blocked_external`; retry count remains bounded |
| H9 | Pi and Hax coexist safely | only the owned Hax pane is killed |
| H10 | Shared completion gate applies to Hax | clean/pushed/reviewed/checks evidence reaches `complete` |
| H11 | tmux send ordering is independent | literal payload and Enter are separate calls |
| H12 | WezTerm fencing and pane safety hold | read fence precedes Enter; current pane is refused |
| H13 | Herdr uses shell-backed Hax while Pi stays native | Hax argv is explicit and no native Hax kind is claimed |
