# pi-dogfood-os — Golden Scenarios (G1–G10)

> The minimal set of scenarios to rerun **after every team.ts change** (and before shipping any change). Each has: intent, steps, pass criteria, evidence to collect.
> Usage: run in order (or via `scripts/run-golden`); record PASS/FAIL/evidence in the dogfood log. **Any FAIL blocks the change** (ship gate, `operating-model.md`).
> Coverage: G1 simple run · G2 carousel auto-route · G3 checklist auto-route · G4 chain/theater · G5 named-agent steering · G6 view override · G7 canvas writer · G8 failure/turn-cap semantics · G9 pane launch · G10 scroll-jump (repro, conditional).
> Paths below are relative; substitute your session's status/log dirs (e.g., `$DOGFOOD_STATUS_DIR`).

---

## G1 — Simple `/team run`
- **Intent:** basic single-context team run works end-to-end (activate → run → result).
- **Steps:**
  1. `/team run <short task>` with a single worker (e.g., "write a 5-line markdown summary of X").
  2. Watch UI: status footer appears, worker starts, completion renders, scrubber appears after completion.
  3. Check the produced output file exists and is non-empty.
- **Pass criteria:** exit clean; output produced; `/team status` reflects the completed run; no stuck widget remains after cleanup.
- **Evidence:** terminal capture of widget lifecycle; status `_dispatch.json`; output file path + size.

## G2 — Parallel ≤4 with auto UI
- **Intent:** `team_dispatch` parallel with ≤4 workers resolves to the **carousel** view automatically and renders it.
- **Steps:**
  1. `team_dispatch` parallel, 3–4 workers (`max_turns` sized to task).
  2. Within the ticker: expect `renderDispatchCarousel` widget (`team-dispatch-carousel`).
  3. Confirm the view announcement (`team view: carousel (n workers · parallel)`).
  4. Let it complete; confirm carousel cleared and scrubber shown.
- **Pass criteria:** carousel widget rendered, updated ≥2× while running, cleared after; `renderDispatchCarousel` is *called*, not just defined.
- **Evidence:** pane capture; grep of the `renderDispatchCarousel` call site in team.ts; status json.

## G3 — Parallel >4 with auto UI
- **Intent:** >4 parallel workers resolve to the **pipeline checklist** view.
- **Steps:**
  1. Dispatch 5 parallel workers.
  2. Expect `renderDispatchChecklist` widget (`team-checklist`), not carousel.
  3. Let all finish; confirm checklist cleared and status footer restored.
- **Pass criteria:** pipeline view shown for >4; per-worker done states tick; cleanup on completion.
- **Evidence:** pane capture; grep of the `renderDispatchChecklist` call site; status json with 5 workers.

## G4 — Chain / theater
- **Intent:** chain mode renders **theater** (each worker gets the previous worker's output).
- **Steps:**
  1. `team_dispatch` chain, 3–5 workers.
  2. Expect `renderTheater` widget in the ticker for the duration.
  3. Verify each worker's brief includes prior outputs (worker files / status json).
  4. Confirm theater cleared on completion.
- **Pass criteria:** theater rendered; ordering respected (worker N+1 sees worker N output); clean teardown.
- **Evidence:** pane capture; status json; worker artifacts showing chained content.

## G5 — Named-agent steering
- **Intent:** `@name` and `team_message` redirect a running worker mid-flight.
- **Steps:**
  1. Start a 3-worker dispatch.
  2. While running, send `@<worker-name> skip step X, focus on Y`.
  3. Also exercise parent-driven `team_message { agent, message }` once.
  4. Verify the worker's next output reflects the steer and `{ type: "agent_message" }` events land in the team events log.
- **Pass criteria:** steer delivered to the named agent only; unknown name → warning, no crash.
- **Evidence:** events log lines; worker output diff; notify messages.

## G6 — `/team view` override
- **Intent:** `runtimeViewOverride` overrides deterministic routing; `auto` restores it.
- **Steps:**
  1. `/team view carousel` → notify confirms override; next dispatch uses carousel even for 1 worker.
  2. `/team view status` → status view.
  3. `/team view invalid-name` → usage string, no crash.
  4. `/team view auto` → override cleared; deterministic routing restored.
  5. Env path: run with `PI_TEAM_VIEW=pipeline` → overridden to pipeline.
- **Pass criteria:** every sub-command returns the documented notification/usage; no crash on invalid input; auto restores default.
- **Evidence:** notify outputs; resolver order verified (override > env > router); harness re-run — and **re-diff the harness against team.ts first** (known drift risk: harness must import live code, not be a copy).

## G7 — `/team canvas`
- **Intent:** static HTML canvas writer works, no server.
- **Steps:**
  1. `/team canvas <out.html>`.
  2. Open the file — must be standalone HTML (no `Bun.serve`, no `localhost`).
  3. Confirm a second invocation overwrites cleanly.
- **Pass criteria:** file written; valid HTML; `grep -nE 'Bun\.serve|localhost' team.ts` → 0 matches (regression gate).
- **Evidence:** file size/head; grep output.

## G8 — Failure / turn-cap behavior
- **Intent:** aborts and turn caps fail *gracefully* and are *correctly reported*.
- **Steps:**
  1. Dispatch with `max_turns` deliberately low (e.g., 6) on a task that needs ~12.
  2. Observe: soft steer at max_turns, hard abort at max_turns+2, partial work preserved on disk.
  3. Record the exact status/activity in the dispatch and worker JSONs (`aborted` vs `failed`).
  4. Confirm: partial deliverable files exist; no orphan panes; parent can distinguish cutoff from error.
- **Pass criteria:** abort is graceful (no crash, no orphan state); partial work present; status classification is **accurate** (cutoff ≠ failed — tracked limitation; escalate if still mislabeled); steers don't get stuck.
- **Evidence:** status json; PROGRESS files; whether `aborted → "failed"` mislabeling is still present.

## G9 — Pane launch workflow
- **Intent:** `pi-team-pane` launches, lists, reads, sends, and cleans up panes safely.
- **Preconditions:** WezTerm running; `pi-team-pane` on PATH.
- **Steps:**
  1. `pi-team-pane list --human` → panes with correct `current` marker.
  2. `pi-team-pane launch --name <t> --brief-file <valid>` → pane spawned, marker written; validate *before* spawn (orphan regression: `launch --name t --brief-file /missing` must fail pre-spawn, pane count unchanged).
  3. `pi-team-pane read --pane-id <id>` and `send` against the pane.
  4. `pi-team-pane cleanup --pattern 't-' --dry-run` → matches, kills nothing; `cleanup` without `--confirm` must never kill.
  5. Protected panes: pane 0 and current pane never killable even with `--confirm`.
- **Pass criteria:** all exits match the documented contract; no orphan panes; zero writes under `~/.pi`.
- **Evidence:** command outputs; `wezterm cli list` before/after; exit codes.

## G10 — Scroll-jump (RCA landed; repro conditional)
- **Intent:** reproduce/falsify the pi TUI jump-to-top on new agent messages; guard the eventual fix.
- **Status:** RCA landed (pi-tui main-screen renderer emits `\x1b[2J\x1b[H\x1b[3J` — clear + erase scrollback — whenever a line above the logical viewport changes; team.ts widget churn is the trigger amplifier; upstream fix unreleased in the pinned npm build).
- **Trigger recipe:**
  1. Long session (transcript > terminal height), user scrolled up.
  2. Run with `PI_DEBUG_REDRAW=1`; trigger a dispatch (widget churn) or stream markdown reflow.
  3. Confirm the debug log records `fullRender: firstChanged < viewportTop` at the moment of the jump and scrollback is wiped.
- **Until repro lands:** capture any observed scroll jump with timestamp + pane capture and attach it here.
- **Pass criteria (future):** deterministic repro command; jump stops when ESC[3J removal or widget-churn reduction lands, while the screen still repaints correctly.
- **Evidence:** RCA artifact; upstream issue/PR links; debug log excerpts.

---

## Rerun protocol (after every team.ts change)

1. `bunx tsc -p <team tsconfig>` → exit 0.
2. Re-run the router harness — **after re-diffing it against team.ts** (drift risk if it's a copy).
3. G1 → G9 in order via `scripts/run-golden`; G10 only if a repro exists. Use `scripts/run-golden --subset G1-G4,G8` for the critical time-boxed subset.
4. Record per-scenario PASS/FAIL + evidence paths in the dogfood log; any FAIL blocks ship.
5. Timing budget: ~30–45 min for the full set; **G1–G4 + G8 are the critical subset (~15 min)** when time-boxed.
