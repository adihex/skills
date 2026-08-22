# Hax backend for Herdr

## Prerequisites

- Install Hax version 0.3.0 or newer.
- Install the official Codex CLI.
- Run `codex login` yourself when subscription authentication is missing.
- Use an explicit provider and model. The subscription path uses `codex`; no API key is required.

Never copy credential files into a manifest, prompt, report, fixture, or log.

## Launch

Pi remains the default:

```text
pi-team-herdr launch --name worker --backend pi --brief-file FILE
```

Opt into Hax explicitly:

```text
pi-team-herdr launch --name worker --backend hax --provider codex --model MODEL --effort high --brief-file FILE
```

Herdr does not expose a native Hax agent kind. The adapter starts Hax as an explicit command in the recorded pane, waits for a readiness marker, then submits the brief with literal send, a separate Enter, and pane readback. `--mode oneshot` runs directly, captures stdout/stderr separately, reports the exit classification, and is not steerable.

## Diagnostics and status

```text
pi-team-herdr doctor --backend hax --provider codex --model MODEL
pi-team-herdr status --manifest FILE
```

Machine-readable output records `backend`, `runtime`, `backend_config`, capabilities, and safe error/session fields. It reports auth presence only. `HTTP_429` and network timeouts are `blocked_external`; missing binary, auth, model, provider, or unsupported version are actionable blockers. Hax never falls back silently to Pi.

## Completion and cleanup

Use the same final report, clean/pushed Git, PR/review, checks, and dry-run-first cleanup gates as Pi. A final Hax response or an idle pane is not completion. Cleanup targets the manifest-owned workspace and process identity only.

## Known limitations

Hax native state and resume are not assumed. The manifest and pane reconciliation are authoritative, and one-shot requests cannot be steered after launch. Live quota is unknown until a request; quota exhaustion must not be retried indefinitely.
