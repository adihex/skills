# Changelog

## 0.3.0

- Add name-based `launch`, `inspect`, `prompt`, `resume`, and structured `result` operations for modern Herdr Pi agents.
- Deliver file prompts through direct argv only; prompt content is never evaluated by a shell or echoed.
- Preserve legacy manifest-bound `send` as an advanced compatibility command and make its manifest requirement explicit.
- Add schema-based capability probes, compatibility metadata/fixtures, docs validation, and weekly drift-monitor workflow.
