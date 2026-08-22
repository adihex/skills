# Dispatch policy

The default policy is bounded and applies before launching a worker:
- Maximum active Pi workers: **4**.
- Maximum active Hax workers: **2**.
- Maximum active Codex-subscription workers: **2**.
- Setup concurrency: **2**.
- Launch stagger: **1 second** between planned launches.
- Default worker turn budget: **30 turns**.
- Default per-run wall-clock budget: **30 minutes**.
- Backpressure begins at 85% configured memory pressure.

`dispatch_policy.py` is the executable contract. Admission returns a deterministic refusal code instead of silently launching more work: `MAX_ACTIVE`, `SETUP_BACKPRESSURE`, or `MEMORY_BACKPRESSURE`. The limit is configurable, but increasing it is an explicit operator choice. Workers must write an initial deliverable before refining it, and parent orchestration owns retries and cleanup.
