# Package Loggers (blinqV2)

Use the existing logger in the package being edited. Do **not** introduce a new logger.

## Universal rule (any TS package)

Before writing the first log, run:

```bash
rg -l "from ['\"]@blinq/observability['\"]" <package>/src
rg -n "logger\." <package>/src | head
```

If the package has an existing `obs.logger` or imported `Logger` instance, use that. If neither exists, search up one level (often a sibling `observability.ts` exports the singleton).

## blinqV2 inventory

| Package | Import | Bootstrap file | Notes |
| ------- | ------ | -------------- | ----- |
| `apps/ai-server` | `import { obs } from "./observability.js"` | `apps/ai-server/src/observability.ts` | Wraps `@blinq/observability`. Use `obs.logger.withContext({...})` for per-request loggers. AI-specific events also flow through `ai-observability.ts`. |
| `apps/server` | `import { obs } from "./observability.js"` (or local pattern) | `apps/server/src/observability.ts` | Same pattern as ai-server. Express middleware adds request context. |
| `apps/orchestrator-server` | `import { logger } from "./logging/logger.js"` | `apps/orchestrator-server/src/logging/logger.ts` | Pino-backed; bridges to `@blinq/observability`. Has request-scoped child loggers. |
| `apps/worker` | `import { obs } from "./logger.js"` | `apps/worker/src/logger.ts` | `@blinq/observability` + Console + Kafka transports. Use `obs.logger`. |
| `apps/client` (React SPA) | `import { clientLogger } from "@/observability/clientLogger"` | `apps/client/src/observability/clientLogger.ts` | Browser logger with batching + Mixpanel transport. **No raw `console.log`.** |
| `apps/desktop-app` (Electron) | Same client pattern in renderer; main process uses its own bootstrap | `apps/desktop-app/src/main/observability.ts` (verify path before use) | Renderer reuses `clientLogger`-style; main is Node, can use `@blinq/observability` directly. |
| `core/bvt-agent` | Library — accept logger via constructor / params | n/a | Do not instantiate; let the consumer (worker / desktop) inject. |
| `core/data-resolver` | Library — accept logger via params or use a no-op default | n/a | Same as bvt-agent. |
| `core/db` | Library — caller supplies logger | n/a | Wrap mongo operations in caller-side 🚀/✅ logs. |
| `core/schemas` | No logging (pure Zod) | n/a | Skip — types/validation only. |
| `shared/observability` | This **is** the logger package itself | `shared/observability/src/logger.ts` | Edit only when extending the framework, never to log application events. |
| `shared/external-clients` | Library — accept logger via constructor | n/a | When adding a new SDK wrapper, expose a `logger?` parameter. |
| `shared/config-utils` | Boot-time only; logs to `console` are OK pre-config | n/a | Config loaders run before observability is initialized. |

## Common shape

`@blinq/observability` exposes:

```ts
class Logger {
  debug(message: string, metadata?: Record<string, unknown>, context?: LogContext): void;
  info(message: string, metadata?: Record<string, unknown>, context?: LogContext): void;
  warn(message: string, metadata?: Record<string, unknown>, context?: LogContext): void;
  error(message: string, metadata?: Record<string, unknown>, context?: LogContext): void;
  withContext(context: LogContext): Logger;
}
```

- `message` — emoji-prefixed string. Keep it grep-friendly: `"👹 <module>:<event>"`.
- `metadata` — structured, JSON-serializable. IDs, counts, sizes. Never raw payloads.
- `context` — `{ system, userId, runId, sessionId, requestId, ... }`. Prefer `withContext` to bind once per request rather than passing per-call.

## Library packages (no logger)

For `core/*` and `shared/*` libraries: do not import a logger package. Instead, accept a `logger?: Logger` parameter and use a no-op default if absent. Application packages (`apps/*`) inject their bound logger when constructing the library object.

```ts
import type { Logger } from "@blinq/observability";

const noop: Pick<Logger, "info" | "warn" | "error" | "debug"> = {
  info() {}, warn() {}, error() {}, debug() {},
};

export class FooResolver {
  constructor(private readonly log: Pick<Logger, "info" | "warn" | "error" | "debug"> = noop) {}
  resolve(input: string) {
    this.log.info("👹 FooResolver:resolve", { inputLength: input.length }); // dev-log
    // ...
  }
}
```

## Quick tRPC / Express request-scoped context

In the `server` and `ai-server` request pipelines, prefer:

```ts
const log = obs.logger.withContext({
  system: false,
  requestId: ctx.requestId,
  userId: ctx.userId,
});
```

Then use `log.info(...)` throughout the handler — every line auto-carries the same context, keeping log lines individually small.
