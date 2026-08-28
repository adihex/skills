# Hax Backend for Terminal Worker Skills — Implementation Plan

## Purpose

After the current skill-hardening implementation finishes, extend the terminal worker skills so they can run either:

- the existing Pi backend; or
- Hax as an opt-in backend using the user's ChatGPT/Codex subscription.

This is not a Herdr-only change. Herdr does not currently provide first-class native Hax support: its `agent start --kind` list does not include Hax. The implementation must add a backend adapter while also updating the more generic `tmux-pi-team` and `wezterm-pi-team` skills so Hax workers can run through those pane runtimes directly.

Pi must remain the default in every runtime and must not regress.

This plan is intentionally written for a separate continuation of the same implementation agent. Do not start this phase until the skill-hardening plan has reached its final validation, commit, and push gates.

## Target repository

Repository: `https://github.com/adihex/skills`

Primary files are expected under:

```text
skills/herdr-pi-team/
skills/tmux-pi-team/
skills/wezterm-pi-team/
skills/pi-dogfood-os/
tests/
```

Before editing, inspect the actual post-hardening tree. Do not assume the paths in this plan still match if the preceding phase changed the architecture; preserve the same responsibilities and update the plan's file references in the final report.

## Current environment evidence

Observed during setup:

- `hax` is installed at `/opt/homebrew/bin/hax`, version `0.3.0`.
- `codex` is installed and can authenticate with the ChatGPT account.
- `hax`'s Codex provider reads the official Codex credentials from `~/.codex/auth.json`.
- The official `codex login` flow completed successfully.
- Hax's saved selection is currently provider `codex`, model `gpt-5.6-sol`, effort `high`.
- A real Hax request reached the Codex backend but returned HTTP 429 because the subscription usage limit was exhausted. This is evidence that authentication and backend routing worked; it is not evidence of a code-integration failure.
- Hax `v0.3.0` did not expose `/login`; authentication was performed with `codex login`.
- Hax requires an explicit model when the Codex provider has no configured model.
- Hax supports interactive REPL mode and one-shot mode via `hax -p`.
- Herdr's native `agent start --kind` list does not currently include `hax`; use an explicit shell-backed adapter rather than pretending Herdr has native Hax support.
- The tmux and WezTerm skills already model generic pane control, but their documented send/status capabilities differ and must be tested independently.

Never copy, print, commit, or place the contents of either authentication file into a manifest, test fixture, log, prompt, or worktree.

---

# Required outcome

A user must be able to launch a worker with either backend through each supported pane runtime. The exact option names may follow each post-hardening CLI, but the semantic form must be equivalent to these examples:

```bash
# Herdr: Pi remains the default
pi-team-herdr launch \
  --name review-worker \
  --backend pi \
  --brief-file /tmp/review.md

# Herdr: Hax is explicit opt-in through a shell-backed adapter
pi-team-herdr launch \
  --name review-worker \
  --backend hax \
  --provider codex \
  --model gpt-5.6-sol \
  --effort high \
  --brief-file /tmp/review.md

# tmux: the same backend contract through tmux panes
pi-team-tmux launch \
  --name review-worker \
  --backend hax \
  --provider codex \
  --model gpt-5.6-sol \
  --effort high \
  --brief-file /tmp/review.md

# WezTerm: the same backend contract through pi-team-pane
pi-team-pane launch \
  --name review-worker \
  --backend hax \
  --provider codex \
  --model gpt-5.6-sol \
  --effort high \
  --brief-file /tmp/review.md
```

These are three runtime adapters over one backend/lifecycle contract, not three independent Hax implementations.

The following semantic guarantees are mandatory:

- `pi` remains the default in Herdr, tmux, and WezTerm.
- Hax is explicit opt-in; it must never be selected accidentally through auto-detection.
- Backend, runtime, provider, model, effort, mode, auth source, and worker identity are recorded in the manifest.
- The same setup, send, status, completion, Git, review, check, and cleanup gates apply to every runtime.
- Backend-specific capabilities and limitations are visible in machine-readable status output.
- A missing model, missing authentication, quota exhaustion, unsupported Hax version, or failed Hax process produces a specific blocker code.
- No API key is required for the ChatGPT subscription path.
- Herdr must not claim native Hax support; it must expose Hax through an explicit backend adapter.
- tmux and WezTerm must preserve their existing pane safety rules while adding Hax support.


---

# Non-negotiable safety rules

- Do not modify the existing Pi launch path except to route it through a backward-compatible adapter interface.
- Do not use `--no-verify`, force-push, `git reset --hard`, `git clean`, or broad process killing.
- Do not automate browser login or handle the user's ChatGPT credentials.
- Do not expose credential-file contents.
- Do not place credentials in `HAX_*` configuration, JSON manifests, shell command logs, or transcripts.
- Do not treat HTTP 429 as success.
- Do not retry quota exhaustion indefinitely.
- Do not claim Hax support merely because `hax` is installed; prove command construction and lifecycle behavior with tests.
- Do not use a live subscription in unit or golden tests.
- Do not make Hax the default backend until the user explicitly asks for that behavior.
- Do not silently fall back from Hax to Pi. Backend fallback would make results non-reproducible and could consume the wrong subscription or provider.
- Do not mark a worker complete from Hax's final text alone. Use the same Git, review, check, and cleanup gates as Pi.

---

# Backend and runtime contract

Extend the post-hardening backend abstraction, or create one if it does not exist. Do not duplicate lifecycle logic inside the Hax adapter or inside a runtime-specific skill.

Every backend must expose these operations or their semantic equivalents:

```text
capabilities()
preflight(config)
start(worker, config)
send(worker, text)
read_state(worker)
interrupt(worker)
resume(worker)
stop(worker)
diagnostics(worker)
```

The backend adapter owns process-specific behavior. The common orchestrator owns:

- worker identity;
- setup readiness;
- manifest writes;
- state transitions;
- Git gates;
- PR and CodeRabbit gates;
- check polling;
- cleanup;
- metrics;
- final reports.

Runtime adapters own only pane/process transport:

```text
herdr_runtime
  - stable workspace/tab/pane identity
  - explicit shell-backed Hax startup because native Hax kind is absent
  - Herdr pane send/read/close operations

tmux_runtime
  - stable tmux pane identity
  - literal send followed by Enter
  - manifest-backed state because tmux has no native Pi state
  - scoped pane/process cleanup

wezterm_runtime
  - stable WezTerm pane identity
  - send/read fence followed by Enter
  - status directory and pane text reconciliation
  - pane safety rules: never kill pane 0, current pane, or last pane
```

Do not create three Hax command builders. Create one Hax backend and three thin runtime adapters.

## Required capability shape

```json
{
  "backend": "hax",
  "runtime": "herdr|tmux|wezterm",
  "interactive": true,
  "one_shot": true,
  "native_state": false,
  "subscription_auth": true,
  "steerable": true,
  "resume_supported": true,
  "requires_explicit_model": true
}
```

Do not claim a capability unless it is verified by a test or by Hax documentation and a live smoke check where appropriate.

---

# Phase 0 — Dependency gate and post-hardening inspection

## 0.1 Wait for the prior implementation to finish

The orchestrator must not send this plan to the agent while the skill-hardening work is still running.

Verify using Herdr:

```bash
herdr workspace list
herdr agent list
```

Then verify the skill-hardening worktree:

```bash
git -C /Users/adityabalakrishnan/Documents/skills-worktrees/skills-hardening status --short --branch
git -C /Users/adityabalakrishnan/Documents/skills-worktrees/skills-hardening log -3 --oneline --decorate
```

Entry conditions:

- The prior agent has produced its final report.
- The prior branch is committed.
- The prior branch is pushed or its push blocker is explicitly recorded.
- No uncommitted changes from the prior phase are mistaken for Hax work.

If the prior branch is dirty, stop and ask the user whether to finalize it before continuing.

## 0.2 Inspect the actual backend implementation

Read the post-hardening versions of:

- `skills/herdr-pi-team/SKILL.md`.
- The CLI entrypoint.
- The Herdr adapter.
- The manifest schema and store.
- The state machine.
- The fake Herdr fixture.
- The golden scenario runner.
- The current tests.

Map:

- How Pi is started.
- How prompts are delivered.
- How pane IDs are recorded.
- How completion is detected.
- How processes are stopped.
- How backend configuration is represented.

Do not implement Hax until this map is written in the final phase notes.

## 0.3 Confirm local Hax prerequisites without revealing secrets

Run only safe checks:

```bash
command -v hax
hax --version
command -v codex
codex --version
```

Check authentication only by presence and permissions:

```bash
test -r "$HOME/.codex/auth.json"
test "$(stat -f '%Lp' "$HOME/.codex/auth.json" 2>/dev/null)" = 600 || true
```

Do not `cat` the auth file.

### Phase 0 gate

Do not continue until:

- The prior hardening phase is complete enough to extend.
- The actual adapter and manifest paths are known.
- Pi behavior is covered by an existing test or a baseline test is added.
- Hax availability and authentication status are classified without exposing credentials.

---

# Phase 1 — Backend configuration and manifest extension

## 1.1 Define backend configuration

Add a backward-compatible configuration shape. Use the post-hardening naming conventions, but it must represent at least:

```json
{
  "backend": "pi|hax",
  "provider": "codex",
  "model": "gpt-5.6-sol",
  "effort": "default|none|low|medium|high|xhigh|max",
  "mode": "interactive|oneshot",
  "auth_source": "codex_cli|hax_managed",
  "hax_min_version": "0.3.0"
}
```

Rules:

- `backend` defaults to `pi`.
- `provider` defaults to `codex` only when `backend=hax`.
- `model` is required for Hax unless the Hax provider can prove a configured default.
- `mode=interactive` is the default for pane workers because it permits steering.
- `mode=oneshot` must be explicit and must report that live steering is unavailable during the request.
- Unsupported values fail before a pane is created.

## 1.2 Extend the manifest schema

Add fields without breaking existing Pi manifests:

```json
{
  "backend": "pi|hax",
  "backend_config": {
    "provider": "string or null",
    "model": "string or null",
    "effort": "string or null",
    "mode": "interactive|oneshot",
    "auth_source": "string or null"
  },
  "backend_capabilities": {},
  "backend_session_id": "string or null",
  "backend_exit_code": "integer or null",
  "backend_error_code": "string or null"
}
```

Never store tokens, auth payloads, or full command lines containing secrets.

## 1.3 Add configuration validation tests

Test:

- Omitted backend selects Pi.
- Explicit Pi remains unchanged.
- Hax requires a model.
- Hax rejects unsupported effort values.
- Hax rejects missing provider.
- One-shot mode reports non-steerability.
- Unknown backend fails clearly.
- Credentials are represented only as an auth source and presence status.

### Phase 1 gate

Run the existing offline suite plus the new configuration tests. Confirm that every existing Pi test remains green.

---

# Phase 2 — Backend-neutral Hax adapter implementation

## 2.1 Implement command construction

Create or extend the backend adapter with argv-based command construction.

Interactive Hax command shape:

```text
hax
  --provider=codex
  --model=<model>
  --effort=<effort>
```

One-shot Hax command shape:

```text
hax
  --provider=codex
  --model=<model>
  --effort=<effort>
  -p <prompt>
```

Requirements:

- Use argv arrays, not shell interpolation.
- Preserve the current working directory.
- Do not include auth-file contents.
- Do not add `--raw` or `--bare` unless the user explicitly selected that mode.
- Do not pass a prompt through an environment variable when it can be sent through the pane or argv safely.
- Emit a redacted command representation for diagnostics.

## 2.2 Implement preflight

Preflight must distinguish:

```text
hax_missing
hax_version_unsupported
codex_missing
codex_auth_missing
model_missing
provider_unavailable
quota_unknown
ready
```

For the ChatGPT subscription path:

- Check that Codex auth exists without reading its value.
- Do not require `OPENAI_API_KEY`.
- Do not require the official Codex CLI to be running.
- Do not attempt browser login automatically.
- Tell the user to run `codex login` when authentication is missing.

## 2.3 Implement Hax startup

For interactive mode:

1. Start Hax in the recorded Herdr pane.
2. Wait for the Hax prompt or a known readiness marker.
3. Record the backend session ID if Hax exposes one.
4. Do not send the task prompt before readiness.
5. Send the prompt using the same verified text-plus-Enter path as Pi.
6. Read back the pane to confirm that Hax accepted the prompt.

For one-shot mode:

- Track the child process directly.
- Capture stdout and stderr separately.
- Enforce the configured timeout.
- Record the exit code.
- Do not pretend the process is steerable.

## 2.4 Implement state and exit classification

Map Hax outcomes to common states:

```text
startup_error       → failed
missing_auth        → blocked
missing_model       → blocked
HTTP_401/403        → blocked
HTTP_429            → blocked_external
network_timeout     → blocked_external
process_exit_0      → verifying
process_exit_nonzero→ failed
interactive_prompt  → working
```

The adapter must not classify a successful-looking final response as complete. The common completion gate still owns that decision.

## 2.5 Implement resume and stop behavior

Determine from the installed Hax version whether `hax --continue` or `hax --resume=<id>` can safely resume a worker session.

If resume is not safely supported:

- Report `resume_supported: false`.
- Preserve the manifest and transcript location.
- Do not silently start a fresh conversation while claiming continuity.

Stopping must target only the owned Hax process and its children.

## 2.6 Implement runtime-specific transport adapters

The Hax backend must be runtime-neutral. Add only thin transport implementations:

### Herdr

- Keep Pi on Herdr's native agent path.
- Start Hax through an explicitly documented shell-backed pane adapter because Herdr's native agent-kind registry does not include Hax.
- Record the Herdr workspace, tab, and pane IDs.
- Wait for Hax readiness before sending the task.
- Use Herdr's literal send operation followed by a separate Enter key and pane readback.

### tmux

- Start Hax in a named Pi-marked tmux pane through the existing `pi-team-tmux` transport.
- Use tmux literal send mode followed by a separate Enter key.
- Treat tmux pane text and the shared manifest as the source of state; do not claim tmux has native agent state.
- Keep pane IDs stable in the manifest and scope cleanup to the owned tmux pane/process.

### WezTerm

- Start Hax through the existing `pi-team-pane` transport.
- Preserve its send/read fence before Enter so PTY ordering cannot silently drop the prompt.
- Use pane text plus manifest state for reconciliation.
- Preserve WezTerm safety rules: never kill pane 0, the current pane, or the last pane in a window.

Every runtime adapter must have its own fake transport tests. Do not share a Herdr-specific send implementation with tmux or WezTerm.

### Phase 2 gate

Use a fake `hax` executable to test:

- Exact argv construction.
- Missing binary.
- Missing auth.
- Missing model.
- Readiness success.
- Readiness timeout.
- Interactive prompt submission.
- One-shot stdout/stderr handling.
- Exit code mapping.
- HTTP 429 classification.
- Process stop behavior.

No test may call the real Codex backend.

---

# Phase 3 — Common lifecycle integration

## 3.1 Route both backends through the same orchestrator

Refactor only as necessary so Pi and Hax share:

- Setup state.
- Manifest writes.
- Heartbeats.
- Git validation.
- PR discovery.
- CodeRabbit handling.
- Check polling.
- Completion evidence.
- Cleanup.

Do not duplicate these gates in `hax_adapter.py`.

## 3.2 Add CLI backend selection

Expose a documented opt-in form such as:

```bash
pi-team-herdr launch --backend hax ...
```

Keep existing forms working:

```bash
pi-team-herdr launch ...
pi-team-herdr launch --backend pi ...
```

Make status output explicit:

```json
{
  "name": "worker-1",
  "backend": "hax",
  "provider": "codex",
  "model": "gpt-5.6-sol",
  "effort": "high",
  "state": "working"
}
```

## 3.3 Integrate Herdr explicitly

- Preserve Herdr's native Pi integration.
- Add Hax as a shell-backed runtime adapter, not as an invented native Herdr `--kind`.
- Ensure Herdr status clearly reports `runtime=herdr` and `backend=hax`.
- Test the workspace/tab/pane mapping and verified text-plus-Enter submission.

## 3.4 Integrate tmux

Update `skills/tmux-pi-team/SKILL.md` and its implementation so:

- `--backend hax` starts Hax in the existing named worker pane.
- Pi remains the default command.
- Hax prompts use literal tmux send followed by a separate Enter.
- Pane text and the shared manifest are used for reconciliation because tmux has no native agent state.
- Cleanup targets only the owned pane and Hax process.
- Missing Hax, missing auth, missing model, and 429 are reported using the common blocker codes.

## 3.5 Integrate WezTerm

Update `skills/wezterm-pi-team/SKILL.md` and its implementation so:

- `--backend hax` starts Hax in the existing `pi-team-pane` worker pane.
- Pi remains the default command.
- Hax prompts use the existing send/read fence followed by Enter.
- Status combines pane text, report files, and the shared manifest.
- Existing safety rules for pane 0, the current pane, and the last pane remain enforced.
- Cleanup targets only the owned pane and Hax process.
- Missing Hax, missing auth, missing model, and 429 are reported using the common blocker codes.

## 3.6 Add backend-aware cleanup

Ensure cleanup:

- Stops Pi and Hax processes through their respective adapters.
- Does not kill a sibling worker using the other backend.
- Uses the same dirty/synchronized worktree guards.
- Records backend shutdown diagnostics.

## 3.7 Add concurrency and quota controls

Add per-backend limits:

```text
max_active_pi_workers
max_active_hax_workers
max_active_codex_subscription_workers
```

Default Hax/Codex subscription concurrency conservatively, for example `2`, unless evidence supports a higher value.

When Hax returns 429:

- Stop launching new Hax workers.
- Mark affected workers `blocked_external`.
- Use bounded backoff.
- Do not retry all workers simultaneously.
- Do not fall back to Pi without explicit user authorization.

### Phase 3 gate

Run the full offline suite and verify:

- Existing Pi launch tests pass unchanged.
- Hax launch is opt-in.
- Backend and runtime appear in every relevant status and manifest.
- Herdr, tmux, and WezTerm transport adapters pass their focused tests.
- Cleanup handles both backends across all supported runtimes.
- Quota limits prevent retry storms.

---

# Phase 4 — Dogfood and golden scenarios

Add Hax-specific scenarios to the existing dogfood/golden framework.

## Required scenarios

- **H1:** Default launch still uses Pi in Herdr, tmux, and WezTerm.
- **H2:** Explicit Hax launch records backend, runtime, provider, model, and effort.
- **H3:** Missing Hax binary fails before workspace or pane creation in every runtime.
- **H4:** Missing Codex auth gives an actionable blocker without exposing credentials.
- **H5:** Missing model fails before worker launch.
- **H6:** Interactive Hax receives a task only after runtime-specific readiness and verified Enter submission.
- **H7:** One-shot Hax captures stdout/stderr and reports non-steerability.
- **H8:** HTTP 429 becomes `blocked_external` without an infinite retry loop.
- **H9:** Hax and Pi workers can coexist across Herdr, tmux, and WezTerm without cross-killing processes.
- **H10:** A completed Hax worker passes the same clean/pushed/reviewed/checks gate before cleanup.
- **H11:** tmux literal-send and Enter behavior is independently verified.
- **H12:** WezTerm send/read fencing and pane safety rules are independently verified.
- **H13:** Herdr uses a shell-backed Hax adapter while Pi continues using native Herdr support.

Every scenario must:

- Fail before the implementation.
- Pass after implementation.
- Use fake binaries and temporary repositories.
- Produce machine-readable evidence.

## Optional live smoke test

Only run when the user has available subscription quota:

```bash
hax --provider=codex --model=gpt-5.6-sol --effort=high \
  -p 'Reply with exactly HAX_SMOKE_OK'
```

Expected response: `HAX_SMOKE_OK`.

If it returns HTTP 429, classify the smoke test as `blocked_external`; do not change code or retry repeatedly.

### Phase 4 gate

Run all existing G1–G10 scenarios plus H1–H13. Produce a JSON scorecard showing each scenario, runtime, status, evidence path, and blocker.

---

# Phase 5 — Documentation and user setup

## 5.1 Update the runtime skills

Update all three runtime skills:

- `herdr-pi-team/SKILL.md`
- `tmux-pi-team/SKILL.md`
- `wezterm-pi-team/SKILL.md`

Document:

- Pi remains the default.
- Hax is explicit opt-in.
- Herdr uses a shell-backed Hax adapter because native Herdr agent kinds do not include Hax.
- tmux and WezTerm use their generic pane transports.
- Hax/Codex subscription prerequisites.
- `codex login` as the authentication path.
- No API key is needed for the subscription backend.
- Model and effort must be explicit when required.
- HTTP 429 means external quota exhaustion.
- Hax interactive versus one-shot behavior.
- Backend and runtime in status output.
- Backend-aware cleanup.

Do not document the user's auth path or any token value.

## 5.2 Add Hax reference files

Create a runtime-local reference file for each independently installable skill:

```text
skills/herdr-pi-team/references/hax-backend.md
skills/tmux-pi-team/references/hax-backend.md
skills/wezterm-pi-team/references/hax-backend.md
```

Keep their shared semantics aligned. Each file must include:

- Prerequisites.
- Safe setup commands.
- Configuration examples without secrets.
- The runtime-specific launch/send/status behavior.
- Diagnostics.
- Known limitations.
- Troubleshooting table.
- When to choose Hax versus Pi.


## 5.3 Update README examples

Add copyable examples:

```bash
codex login

# Herdr shell-backed adapter
pi-team-herdr launch --backend hax --provider codex \
  --model gpt-5.6-sol --effort high \
  --brief-file /tmp/task.md

# tmux pane adapter
pi-team-tmux launch --backend hax --provider codex \
  --model gpt-5.6-sol --effort high \
  --brief-file /tmp/task.md

# WezTerm pane adapter
pi-team-pane launch --backend hax --provider codex \
  --model gpt-5.6-sol --effort high \
  --brief-file /tmp/task.md
```

Also document that direct API providers are separate from the ChatGPT subscription path.

## 5.4 Add installation and capability diagnostics

Document and test capability diagnostics for each runtime:

```bash
pi-team-herdr doctor --backend hax
pi-team-tmux doctor --backend hax
pi-team-pane doctor --backend hax
```

The diagnostic must report only:

```text
hax: installed / missing
codex: installed / missing
codex auth: present / missing / unreadable
provider: codex
model: configured / missing
quota: unknown until request
```

Never print auth-file contents.

### Phase 5 gate

Run:

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/herdr-pi-team/tests -v
python3 -m unittest discover -s skills/tmux-pi-team/tests -v
python3 -m unittest discover -s skills/wezterm-pi-team/tests -v
python3 -m compileall -q skills scripts tests
git diff --check
```

Verify all Hax references resolve and every example is syntactically valid.

---

# Phase 6 — Final review, commit, and handoff

## 6.1 Review the diff

Inspect:

```bash
git diff --stat
git diff -- skills/herdr-pi-team skills/tmux-pi-team skills/wezterm-pi-team skills/pi-dogfood-os tests scripts
git status --short --branch
```

Reject:

- Changes to Pi behavior without a regression test.
- Credentials or auth payloads in any file.
- Hidden fallback from Hax to Pi.
- Unbounded retry loops.
- Cleanup code without disposable-repository tests.
- Live-provider tests in the default suite.
- Claims unsupported by test evidence.

## 6.2 Run the final evidence suite

Run all offline tests and golden scenarios. Run the optional live smoke test only if quota is available.

Record:

- Commit SHA.
- Branch.
- Push result.
- Tests and exit statuses.
- Golden scorecard.
- Live smoke result or exact external blocker.
- Files changed.
- Known limitations.

## 6.3 Commit and push

Use a conventional commit, for example:

```text
feat(workers): add hax backend across pane runtimes
```

Do not bypass hooks. Push only the feature branch. Do not push directly to `main` or `uat`.

If the branch cannot be pushed, leave the worktree intact and report the exact blocker.

## 6.4 Final report format

```text
RESULT: complete | blocked_external | blocked | failed
RUNTIMES: herdr, tmux, wezterm
BACKENDS: pi, hax
HAX_VERSION:
HAX_PROVIDER:
HAX_MODEL:
HAX_EFFORT:
AUTH_CHECK: present | missing | unreadable | not_run
COMMIT:
PUSHED:
PR:
OFFLINE_TESTS:
GOLDEN_TESTS: G1–G10, H1–H13
LIVE_SMOKE: passed | quota_blocked | not_run
CLEANUP_TESTS:
BLOCKER:
EVIDENCE:
```

Do not call this complete unless all required offline gates pass and the Hax backend has deterministic fake-provider coverage.

---

# Orchestration instruction for the parent agent

When the existing `skills-hardening-impl` worker finishes:

1. Verify its Herdr state and final pane report.
2. Verify its branch is committed and the preceding plan's gates are complete.
3. Keep using the current Herdr session.
4. Prefer sending this plan to the same worker in the same workspace/worktree.
5. If that workspace was closed, create a new workspace in the same Herdr session using the existing skill-hardening worktree; do not create a new Herdr session unless the current Herdr server is unavailable.
6. Send the continuation with Herdr's verified prompt mechanism and Enter submission.
7. Tell the agent explicitly that this is a second phase after skill hardening and that it must not restart or undo the completed Pi implementation.
8. Monitor the Hax phase separately from the remaining 10x Hub workers.
9. Remove the Hax phase's Herdr space and worktree only after the final report, clean/synchronized branch, push evidence, and review gates are verified.

Suggested continuation message:

```text
The skill-hardening phase is complete. Continue in this same Herdr workspace and worktree by executing /Users/adityabalakrishnan/Documents/skills/hax-backend-for-herdr-workers-plan.md.

Add Hax as an explicit, opt-in backend across Herdr, tmux, and WezTerm while preserving Pi as the default in all three runtimes. Use one shared Hax backend and thin runtime adapters; reuse the existing hardened manifest, state, cleanup, and golden-test infrastructure. Do not duplicate lifecycle gates. Do not expose credentials, do not add silent fallback, do not use --no-verify or force-push, and do not treat HTTP 429 as success. Complete every phase, run the offline and H1–H13 gates, review the diff, commit, push the feature branch if possible, and report exact evidence and blockers.
```

---

# Definition of done

```text
[ ] Existing skill-hardening gates are complete
[ ] Pi remains the default backend in Herdr, tmux, and WezTerm
[ ] Hax is explicit opt-in in all three runtimes
[ ] One shared Hax backend and thin runtime adapters are used
[ ] Backend, runtime, and manifest fields are validated
[ ] Hax command construction is tested without a live provider
[ ] Missing binary/auth/model errors are actionable in every runtime
[ ] Interactive Hax readiness and Enter submission are verified for Herdr, tmux, and WezTerm
[ ] One-shot Hax behavior is explicit and tested
[ ] HTTP 429 is classified as blocked_external
[ ] No silent Hax-to-Pi fallback exists
[ ] Pi and Hax workers can coexist safely across all runtimes
[ ] Backend-specific process cleanup is safe and scoped
[ ] H1–H13 scenarios pass
[ ] Existing G1–G10 scenarios still pass
[ ] Documentation and examples match reality in all three runtime skills
[ ] No credentials or auth payloads are committed or logged
[ ] Final tests and diff checks pass
[ ] Feature branch is committed and pushed, or the exact external blocker is documented

If any item cannot be verified, report `blocked` or `blocked_external`; do not claim partial work is complete.

## Standards basis

- Agent Skills specification: <https://agentskills.io/specification>
- Hax provider documentation: <https://github.com/OleksandrChekhovskyi/hax/blob/master/docs/providers.md>
- Hax usage documentation: <https://github.com/OleksandrChekhovskyi/hax/blob/master/docs/usage.md>
- OpenAI agent evaluation guidance: <https://developers.openai.com/api/docs/guides/agent-evals>
- Applied principles: explicit backend selection, least privilege, bounded retries, durable state, independent fake-provider tests, human-controlled authentication, no silent fallback, and evidence-gated completion.
