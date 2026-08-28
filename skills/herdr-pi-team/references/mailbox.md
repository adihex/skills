# Worker mailbox

The mailbox currently supports modern native Pi workers. It solves result delivery, not workflow completion. `worker.turn_finished` means Pi produced a durable final assistant message for the dispatched turn. `worker.blocked` means operator or parent intervention is needed. Neither event bypasses the clean Git, push, review, checks, or cleanup gates.

## Usage

Create one operator-owned, untracked mailbox per run and use a unique stable name for each worker:

```bash
pi-team-herdr launch --name api-review --cwd WORKTREE --new-workspace \
  --brief-file BRIEF --verify-working --run-id review-123 \
  --mailbox RUN/mailbox.json

# Return the first completed or blocked worker, including its result when done.
pi-team-herdr await --mailbox RUN/mailbox.json --any

# Or wait for all registered workers. Repeat --name to select a subset.
pi-team-herdr await --mailbox RUN/mailbox.json --all \
  --name api-review --name test-review

# Drain events once without waiting while doing other parent work.
pi-team-herdr inbox --mailbox RUN/mailbox.json
```

The parent should continue useful independent work after dispatch. At a safe turn boundary it drains `inbox` once. Before finalizing, it calls `await` once if required workers remain. It never loops over `inspect` or asks the user to prompt another status check.

## Delivery and conflict rules

- Registration records the exact worker name, workspace ID, and pane ID. A name that later resolves to a different identity is refused.
- The mailbox state is atomically replaced under an exclusive lock. Events are append-only, flushed with `fsync`, and mode `0600`.
- Event IDs contain the run, worker generation, and event kind. Repeated and concurrent observations produce one durable event.
- Consumer cursors are independent. The default `parent` consumer receives each event once; another explicit consumer can independently review the same events.
- Results are read from Pi's durable session artifact only after a terminal observation. Terminal viewport text is not parsed.
- `blocked` is delivered immediately as intervention, not success. `idle` without durable session evidence is not terminal.
- The waiter takes one Herdr registry snapshot per cycle for every active worker. When native event waiting is unavailable, polling backs off from 0.5 seconds to a 10-second ceiling. Parent agents never perform repetitive checks.
- Mailboxes belong outside tracked worktrees. Workers do not write them, so parallel Git changes cannot conflict with mailbox delivery.

On timeout, `await` returns `WAIT_TIMEOUT` with stable pending worker names. It does not interrupt workers or infer failure.
