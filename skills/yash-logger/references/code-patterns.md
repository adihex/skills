# Code Patterns

Concrete templates for the six trigger points across the common blinqV2 surfaces.

## Table of contents

- [Service method (ai-server / server)](#service-method)
- [Mastra tool (ai-server)](#mastra-tool)
- [tRPC procedure](#trpc-procedure)
- [Express middleware / route handler](#express-handler)
- [Worker job step](#worker-step)
- [React mutation hook (client)](#react-mutation-hook)
- [Library function (core/*)](#library-function)

## Service method

```ts
import { obs } from "../observability.js";

export async function publishScenario(
  scenarioId: string,
  userId: string,
): Promise<PublishResult> {
  const log = obs.logger.withContext({ system: false, scenarioId, userId });

  log.info("👹 publishScenario:start", { scenarioId }); // dev-log

  const scenario = await scenarioRepo.findById(scenarioId);
  if (!scenario) {
    log.warn("⚠️ publishScenario:not-found", { scenarioId }); // dev-log
    throw new ScenarioNotFoundError(scenarioId);
  }

  if (scenario.status === "published") {
    log.debug("🔍 publishScenario:already-published-noop", { scenarioId }); // dev-log
    return { status: "noop" };
  }

  log.info("🚀 publishScenario:db-update:start", { scenarioId }); // dev-log
  try {
    const updated = await scenarioRepo.markPublished(scenarioId);
    log.info("✅ publishScenario:db-update:done", { version: updated.version }); // dev-log
    log.info("✅ publishScenario:done", { scenarioId, version: updated.version });
    return { status: "published", version: updated.version };
  } catch (err) {
    log.error("❌ publishScenario:db-update:failed", { scenarioId, error: serializeError(err) });
    throw err;
  }
}
```

The final two lines are kept post-cleanup (no `// dev-log` tag) — they are durable boundary signals.

## Mastra tool

```ts
import { createTool } from "@mastra/core";
import { obs } from "../../observability.js";

export const fetchRunSummaryTool = createTool({
  id: "fetch-run-summary",
  description: "Fetches a summarized view of a recorder run.",
  inputSchema: z.object({ runId: z.string() }),
  execute: async ({ context }) => {
    const { runId } = context;
    const log = obs.logger.withContext({ system: false, tool: "fetch-run-summary", runId });

    log.info("👹 fetchRunSummaryTool:start", { runId }); // dev-log

    log.info("🚀 fetchRunSummaryTool:repo-call:start"); // dev-log
    const run = await runRepo.findById(runId);
    log.info("✅ fetchRunSummaryTool:repo-call:done", { found: Boolean(run) }); // dev-log

    if (!run) {
      log.warn("⚠️ fetchRunSummaryTool:not-found", { runId }); // dev-log
      return { error: "not_found" };
    }

    log.info("✅ fetchRunSummaryTool:done", { runId, stepCount: run.steps.length });
    return { run };
  },
});
```

## tRPC procedure

```ts
publishScenario: protectedProcedure
  .input(z.object({ scenarioId: z.string() }))
  .mutation(async ({ input, ctx }) => {
    const log = obs.logger.withContext({
      system: false,
      requestId: ctx.requestId,
      userId: ctx.user.id,
      route: "scenario.publish",
    });

    log.info("👹 scenario.publish:invoked", { scenarioId: input.scenarioId }); // dev-log
    try {
      const result = await scenarioService.publish(input.scenarioId, ctx.user.id);
      log.info("✅ scenario.publish:done", { status: result.status });
      return result;
    } catch (err) {
      log.error("❌ scenario.publish:failed", { error: serializeError(err) });
      throw err;
    }
  });
```

## Express handler

```ts
router.post("/sessions", async (req, res, next) => {
  const log = req.log.withContext({ route: "POST /sessions" });
  const bodyFieldCount = req.body && typeof req.body === "object" ? Object.keys(req.body).length : 0;

  log.info("👹 createSession:start", { bodyFieldCount }); // dev-log

  try {
    const session = await sessionService.create(req.body, req.user);
    log.info("✅ createSession:done", { sessionId: session.id });
    res.status(201).json(session);
  } catch (err) {
    log.error("❌ createSession:failed", { error: serializeError(err) });
    next(err);
  }
});
```

## Worker step

```ts
import { createHash } from "node:crypto";
import { obs } from "../logger.js";

function summarizeUrlForLog(rawUrl: string): Record<string, unknown> {
  try {
    const url = new URL(rawUrl);
    return {
      origin: url.origin,
      pathHash: createHash("sha256").update(url.pathname).digest("hex").slice(0, 12),
      hasQuery: url.search.length > 0,
    };
  } catch {
    return { urlValid: false, urlLength: rawUrl.length };
  }
}

export async function executeNavigateStep(step: NavigateStep, ctx: StepContext): Promise<void> {
  const log = obs.logger.withContext({
    system: false,
    runId: ctx.runId,
    stepId: step.id,
    stepType: "navigate",
  });
  const target = summarizeUrlForLog(step.url);

  log.info("👹 navigateStep:start", { target }); // dev-log

  log.info("🚀 navigateStep:browser-goto:start", { target }); // dev-log
  try {
    await ctx.page.goto(step.url, { waitUntil: "domcontentloaded" });
    log.info("✅ navigateStep:browser-goto:done", { target }); // dev-log
  } catch (err) {
    log.error("❌ navigateStep:browser-goto:failed", { target, error: serializeError(err) });
    throw err;
  }

  log.info("✅ navigateStep:done", { target });
}
```

## React mutation hook

```ts
import { clientLogger } from "@/observability/clientLogger";

export function usePublishScenario() {
  return useMutation({
    mutationFn: async (scenarioId: string) => {
      clientLogger.info("👹 usePublishScenario:invoke", { scenarioId }); // dev-log
      try {
        const result = await trpc.scenario.publish.mutate({ scenarioId });
        clientLogger.info("✅ usePublishScenario:done", { status: result.status });
        return result;
      } catch (err) {
        clientLogger.error("❌ usePublishScenario:failed", { scenarioId, error: serializeError(err) });
        throw err;
      }
    },
  });
}
```

**Do not** put logs inside the render body of a component. Only inside event handlers, effects, callbacks, and the `mutationFn` / `queryFn` of TanStack Query.

## Library function

Inject the logger; do not import one.

```ts
import type { Logger } from "@blinq/observability";

const noop = { info() {}, warn() {}, error() {}, debug() {} } as Pick<
  Logger, "info" | "warn" | "error" | "debug"
>;

export async function resolveExpression(
  expr: string,
  data: Record<string, unknown>,
  log: Pick<Logger, "info" | "warn" | "error" | "debug"> = noop,
): Promise<unknown> {
  log.debug("👹 resolveExpression:start", { exprLen: expr.length }); // dev-log

  const ast = parse(expr);
  log.debug("🔍 resolveExpression:parsed", { nodeKind: ast.kind }); // dev-log

  try {
    const value = await evaluate(ast, data);
    log.debug("✅ resolveExpression:done", { resultType: typeof value }); // dev-log
    return value;
  } catch (err) {
    log.warn("⚠️ resolveExpression:failed", { error: serializeError(err) }); // dev-log
    throw err;
  }
}
```

Library logs default to `debug` — application code controls visibility through the injected logger's level.
