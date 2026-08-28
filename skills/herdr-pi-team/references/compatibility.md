# Compatibility contract

`herdr api schema --json` is the preferred machine-readable contract. The wrapper also probes required commands with `--help`; it does not parse terminal output. `references/compatibility.json` records the tested Herdr/Pi range and wrapper version. `references/herdr-*.schema.json` contains sanitized structural fixtures only.

## Commands

- `pi-team-herdr doctor`: versions, session/CLI reachability, Pi availability, required capabilities. It never prints prompt/session/user data, environment, or credentials.
- `pi-team-herdr compatibility snapshot`: emits a sanitized capability record suitable for review and fixture capture.
- `pi-team-herdr compatibility check`: compares required commands and state enum with the installed binary. Missing capabilities block affected operations; additive fields/commands do not.
- `pi-team-herdr docs check`: validates that the concise skill names the tested lifecycle commands. Unit tests also parse legacy examples so `send` cannot be documented without its required `--manifest`.

## Change policy

| Native change | Wrapper behavior |
|---|---|
| Additive field/optional flag | Continue and report it. |
| New required argument | Block the affected operation until adapter update. |
| Removed/renamed command | Block affected operations only. |
| State enum changed | Return `interpretation: unknown`; do not infer completion. |
| Invalid JSON/schema | Stop parsing the affected operation and expose a sanitized error. |
| Newer version with passing probes | Warn and continue; never impose a version ceiling. |

## Release procedure

1. Capture a sanitized fixture from a disposable install.
2. Review semantic command/schema changes and update only `scripts/modern_adapter.py`.
3. Add deterministic regression tests for each change, then run full tests and disposable live smoke.
4. Update compatibility metadata/changelog, then update `SKILL.md` from passing commands.
5. Human-review changes. Never auto-publish or auto-merge.

## Upstream request

Herdr already exposes `api schema --json`, which is preferable to formatted help. A small addition would remove the remaining probe: `herdr capabilities --json` returning `{version, protocol, commands, requiredArgs, stateEnums}`. It would let adapters detect `agent prompt` availability and any future required argument without invoking terminal help. The response must be versioned, path-free, and backward compatible.
