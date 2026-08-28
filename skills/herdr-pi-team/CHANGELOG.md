# Changelog

## 0.4.0

- Add a durable per-run worker mailbox with locked, atomic state and append-only idempotent events.
- Add blocking `await --any|--all` delivery and non-blocking `inbox` draining with per-consumer deduplication.
- Return complete Pi session results with terminal events while refusing workspace/pane identity changes.
- Centralize bounded adaptive worker observation so parent agents no longer repeatedly poll status.

## 0.3.0

- Add name-based `launch`, `inspect`, `prompt`, `resume`, and structured `result` operations for modern Herdr Pi agents.
- Deliver file prompts through direct argv only; prompt content is never evaluated by a shell or echoed.
- Preserve legacy manifest-bound `send` as an advanced compatibility command and make its manifest requirement explicit.
- Add schema-based capability probes, compatibility metadata/fixtures, docs validation, and weekly drift-monitor workflow.
