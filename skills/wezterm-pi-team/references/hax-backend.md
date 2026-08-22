# Hax backend for WezTerm

## Prerequisites

- Install WezTerm with its CLI, Hax 0.3.0 or newer, and the official Codex CLI.
- Run `codex login` yourself when subscription authentication is missing.
- Select the `codex` provider and an explicit model; no API key is required.

Never expose credential-file contents in pane text, manifests, prompts, reports, or logs.

## Launch and transport

Pi remains the default. Opt into Hax explicitly:

```text
pi-team-pane launch --name worker --backend hax --provider codex --model MODEL --effort high --brief-file FILE
```

The shared Hax backend constructs argv. The WezTerm adapter starts Hax in the worker pane, waits for readiness, sends the task, performs a `get-text` fence, and submits Enter separately. The manifest records stable pane identity, runtime, backend configuration, and capabilities. Pane text plus manifest state are used for reconciliation.

`--mode oneshot` is explicit and runs directly with separate stdout/stderr capture. It reports `steerable: false`; do not send later pane messages to it.

## Diagnostics, completion, and cleanup

```text
pi-team-pane doctor --backend hax --provider codex --model MODEL
pi-team-pane status --manifest FILE
pi-team-pane complete --manifest FILE --report FILE --repository OWNER/REPO
```

Completion delegates to the common clean/pushed Git, PR/review, checks, report, and state gates. Cleanup remains dry-run first and absolutely protects pane 0, the current pane, the last pane in a window, and non-owned panes. Hax cleanup must not cross-kill Pi workers.

## Blockers and limitations

Status reports only safe prerequisite and capability information. Missing Hax, Codex auth, model, or supported version are actionable blockers. HTTP 401/403 is blocked; HTTP 429 and network timeouts are `blocked_external`. There is no silent Hax-to-Pi fallback and no indefinite quota retry. Native Hax state and resume are not claimed unless verified by the installed version.
