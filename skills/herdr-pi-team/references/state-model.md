# Worker state model

Use these states exactly:

`created → setup_pending → ready → working → verifying → pushed → review_pending → complete → cleanup_pending → cleaned`

Failure and recovery states are `setup_failed`, `blocked_external`, `blocked`, `failed`, and `aborted`. `idle` is a native observation, not a manifest state and never means complete. `blocked_external` is not success. Only `cleaned`, `failed`, and `aborted` are terminal. State transitions are enforced by `scripts/run_state.py`; completion needs clean, pushed, reviewed, and passed-check evidence. Cleaning needs process-stop and path-gone evidence.
