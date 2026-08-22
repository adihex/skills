# Hax backend for tmux

## Prerequisites

- Install tmux, Hax 0.3.0 or newer, and the official Codex CLI.
- Run `codex login` yourself when subscription authentication is missing.
- Use an explicit `codex` provider and model; no API key is required.

Credential-file contents must never enter a manifest, pane command, prompt, report, or log.

## Launch and send

Pi remains the default. Hax is explicit:

```text
pi-team-tmux launch --name worker --backend hax --provider codex --model MODEL --effort high --brief-file FILE
```

The shared Hax backend constructs argv safely. The tmux adapter starts that command in the named worker pane, waits for readiness, sends literal text, and sends a separate `Enter`. Pane IDs and backend fields are written to a manifest. tmux has no native agent state; pane text plus the manifest are used for reconciliation.

Use `--mode oneshot` explicitly when steering is unnecessary. It runs the child directly, captures stdout and stderr, records the exit classification, and reports `steerable: false`.

## Diagnostics and lifecycle

```text
pi-team-tmux doctor --backend hax --provider codex --model MODEL
pi-team-tmux status --manifest FILE
pi-team-tmux complete --manifest FILE --report FILE --repository OWNER/REPO
```

The completion command delegates to the common Git, push, review, checks, report, and state gate. An idle pane or final response is never completion. Cleanup is dry-run first and must target only owned worker panes; it must not cross-kill a sibling Pi or Hax worker.

## Diagnostics and blockers

Machine-readable status includes `backend`, `runtime`, provider, model, effort, mode, capabilities, and safe backend error fields. `hax_missing`, `codex_auth_missing`, `model_missing`, unsupported version, `HTTP_401_403`, `HTTP_429`, and `network_timeout` are distinct. HTTP 429 is `blocked_external`; it is not success and is not retried indefinitely. Hax never silently falls back to Pi.

## Known limitations

Pane text and manifests replace native agent state. One-shot workers cannot receive later pane messages. Resume is not claimed unless the installed Hax version proves it. Quota is unknown until a request.
