---
name: yash-logger
description: Generates production code with built-in observability logs from the first draft, eliminating a second debugging-instrumentation pass. Apply during initial feature development whenever writing or scaffolding new TypeScript code (functions, services, routes, handlers, agents, workflows) — especially in the blinqV2 monorepo. Reuses each package's existing logger and prefixes log messages with grep-friendly emojis (👹 entry, ✅ success, ⚠️ warning, ❌ error, 🔍 debug, 🚀 boundary). Pairs with test-driven-development, typescript-best-practices, react-best-practices, blinq-swarm-plan, and superpowers planning skills. Triggers on requests like "implement <feature>", "add <handler/service/agent/tool>", "scaffold <module>", or any first-cut code generation. Skill also covers the cleanup workflow before commit so dev-only logs do not leak into shipped code.
---

# Yash Logger

## Overview

Code without logs forces a wasted cycle: ship → break → re-open → instrument → re-test. This skill collapses that into one cycle: **logs are written together with the code**, using the package's existing logger and an emoji-prefixed message convention so future debugging starts with a single `grep`.

The skill is opinionated: every important operation gets a log, and every dev-only log is tagged with `// dev-log` so the cleanup pass before commit is mechanical.

## When to apply

Use during **initial feature development** — first-cut implementations of:

- New service methods, route handlers, tRPC procedures, Express middleware
- Mastra agents, tools, workflows (ai-server)
- Worker job handlers, browser-automation steps
- React hooks, mutations, query handlers (client/desktop)
- Cross-service boundary calls (DB, LLM, external HTTP, Kafka, S3, Stripe)

Skip / scale back for:

- Pure type definitions, Zod schemas, constants
- Trivial getters/setters or one-line wrappers
- Stable code being refactored (logs are already curated)
- Hot paths where log volume would dominate cost — log at `debug` then

## Workflow

1. **Discover the logger** for the package being edited. See [references/package-loggers.md](references/package-loggers.md) for the blinqV2 inventory and the universal "search-then-import" rule.
2. **Add logs alongside the code** at the six trigger points (see below). Use the emoji map. Tag every dev-only line with `// dev-log` so the audit script finds it.
3. **Stabilize** — run tests, fix bugs, iterate. Logs help here.
4. **Audit before commit** — run `scripts/audit-dev-logs.sh` and prune. Keep only logs that earn their place in production.
5. **Commit** with the curated subset.

## Emoji map

Always place the emoji at the **start of the message string** so a single `rg "👹"` returns every entry log across the repo.

| Emoji | Meaning | Level | Use when |
| ----- | ------- | ----- | -------- |
| 👹 | Entry / start | `debug` or `info` | Function or operation begins; include input identifiers |
| ✅ | Success | `info` | Operation completed successfully; include outcome |
| ⚠️ | Warning / recoverable | `warn` | Fallback taken, retry triggered, unexpected-but-handled state |
| ❌ | Error / failure | `error` | Caught exception, failed call, validation rejected |
| 🔍 | Debug / inspect | `debug` | Branch decision, computed value, intermediate state |
| 🚀 | Boundary cross | `info` | Outbound HTTP/DB/LLM/queue call; pair with ✅ or ❌ on return |

Treat the table as canonical. Do not invent extra emojis — consistency is the whole point.

## Six trigger points (what to log)

For every important operation, emit logs at these points:

1. **Function entry (👹)** — name + key inputs (IDs, not PII).
2. **Branch decisions (🔍)** — which path was taken and why (the discriminator value).
3. **External boundary out (🚀)** — destination + payload summary (sizes, IDs).
4. **External boundary back (✅ or ❌)** — outcome, latency if cheap, error.
5. **State mutation (✅)** — what changed, scoped identifiers.
6. **Function exit (✅ or ❌)** — return summary or thrown error.

For deep examples (TS service method, Mastra tool, React hook, worker step), see [references/code-patterns.md](references/code-patterns.md).

## Logging rules

- **Reuse the package's logger.** Never introduce a new logger or fall back to bare `console.log` unless the package has no other option (rare — even `client` has `clientLogger`). See [references/package-loggers.md](references/package-loggers.md).
- **Pass structured metadata as the second argument**, not interpolated into the message. The shared logger signature is `logger.info(message, metadata?, context?)` — keep messages searchable, put variables in metadata.
- **Never log secrets, tokens, full request bodies, raw user PII, or full LLM prompts/completions.** Log IDs, sizes, hashes. The codebase already runs through Logz/Kafka — leaks are durable.
- **Tag dev-only lines with `// dev-log`** at end-of-line. The cleanup script keys on this comment. Logs that should survive the cleanup pass do **not** carry the tag.
- **Match the existing message style** in the file you are editing. If the file already follows a different convention (e.g. namespaced prefixes), keep that; the emoji is added on top, not as a replacement.

### Canonical example (ai-server service)

```ts
import { obs } from "../observability.js";

export async function summarizeRun(runId: string, userId: string): Promise<Summary> {
  const log = obs.logger.withContext({ system: false, runId, userId });

  log.info("👹 summarizeRun:start", { runId }); // dev-log

  const run = await runRepo.findById(runId);
  if (!run) {
    log.warn("⚠️ summarizeRun:run-not-found", { runId }); // dev-log
    throw new RunNotFoundError(runId);
  }

  log.debug("🔍 summarizeRun:run-loaded", { stepCount: run.steps.length }); // dev-log

  log.info("🚀 summarizeRun:llm-call:start", { model: "Codex-opus-4-7", stepCount: run.steps.length }); // dev-log
  try {
    const summary = await llmClient.summarize(run);
    log.info("✅ summarizeRun:llm-call:done", { tokens: summary.usage.totalTokens }); // dev-log
    log.info("✅ summarizeRun:done", { runId, summaryLength: summary.text.length });
    return summary;
  } catch (err) {
    log.error("❌ summarizeRun:llm-call:failed", { runId, error: serializeError(err) });
    throw err;
  }
}
```

After stabilization, the cleanup pass deletes most `// dev-log` lines and keeps the boundary-cross + final ✅/❌ pair so production retains the high-signal events.

## Cleanup before commit

Logs marked `// dev-log` are **dev scaffolding**. Before committing:

```bash
bash ~/.agents/skills/yash-logger/scripts/audit-dev-logs.sh apps/ai-server/src
```

The script lists every `// dev-log` line in the given path, returns 0 when there are matches or no matches, and returns nonzero on `rg`/`grep` errors such as unreadable paths. For each line, decide:

- **Keep & untag** — the log is genuinely useful in production. Remove the `// dev-log` comment.
- **Delete** — temporary scaffolding. Remove the line.
- **Downgrade** — keep but change `info` → `debug` so it's quiet in production.

Run the script again until it returns nothing in the staged hunks. Then commit.

If `rg` (ripgrep) is unavailable, the script falls back to `grep`. Manual fallback:

```bash
grep -rn "// dev-log" <path> --include="*.ts" --include="*.tsx"
```

## Integration with other skills

| Skill | Interaction |
| ----- | ----------- |
| `test-driven-development` / `superpowers:test-driven-development` | Tests come first; once the test fails for the right reason, write impl **with logs** in the same draft. Failing logs help diagnose if the test still fails. |
| `typescript-best-practices` | Logs do not replace types — keep illegal states unrepresentable. Metadata objects should be typed, not stringly. |
| `react-best-practices` | Inside React: log inside event handlers and effects, never inside the render body. Use a stable logger reference (module-level) so re-renders don't churn. |
| `blinq-swarm-plan` / `superpowers:writing-plans` | Plan steps that introduce new code should treat "instrument with yash-logger" as an implicit acceptance criterion — do not add it as a separate step. |
| `commit-work` / `caveman:caveman-commit` | Run the cleanup audit before staging. Commit messages do not need to mention logging. |
| `logging-best-practices` | This skill **sits on top** of it. Use `logging-best-practices` for log-level taxonomy, structured-logging rationale, and PII handling. yash-logger adds the emoji convention, the dev-phase trigger discipline, and the `// dev-log` cleanup workflow. |

## Anti-patterns

- ❌ Adding logs in a "second pass" after the feature is done — the whole point is to write them together.
- ❌ `console.log("starting")` — no emoji, no logger, no context. Useless.
- ❌ `logger.info("👹 result is " + JSON.stringify(huge))` — interpolation + dump. Use metadata + IDs.
- ❌ Emoji on every line, including trivial branches — noise. Reserve for the six trigger points.
- ❌ Forgetting the `// dev-log` tag — the cleanup audit will miss the line and it will ship.
- ❌ Logging a secret because it was "easier" — never. Hash or omit.
