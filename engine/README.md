# engine/

Single source of truth for what the data means and what to do about it.
The only layer `web/` is allowed to import from.

## CRA build constraint
CRA (create-react-app) blocks imports from outside `web/src/`. Engine files must
also exist at `web/src/engine/` for the build to work. Never edit `web/src/engine/`
directly — it is overwritten on every build.

Engine files are automatically synced to `web/src/engine/` before every
build and dev server start via the `prebuild`/`prestart` scripts in
`web/package.json`. Do not manually copy — edit at `engine/` and let the
build process handle the rest.

## Purpose
- Threshold definitions (numeric cutoffs per biomarker)
- Scoring logic (readiness tier, suppression level)
- Command string generation (what METHUSELAH tells the user to do)
- Cross-vector relationship logic (how HRV + glucose + sleep interact)
- Canonical biomarker key schema (used by all parsers as their output contract)

## The scope-change rule
Adding a new data vector, removing one, or reweighting cross-vector logic should only
require touching `engine/`. If a scope change requires editing `web/` AND `engine/`
AND `pipeline/`, a boundary has been violated somewhere. `web/` should need only to
read a new key that `engine/` exposes — not know anything about where the data came from.

## Import rules
- `engine/` imports from `parsers/` to get biomarker values. Nothing else.
- `web/` imports from `engine/` only.
- `engine/` never imports from `pipeline/`, `web/`, or `firmware/`.

## Removability
This directory cannot be silently removed — `web/` depends on it. However, individual
files within `engine/` are independently removable: removing `engine/scoring.js` removes
the scoring feature from `web/` cleanly, without touching any other layer.

If `engine/` itself needs to be replaced (e.g. server-side logic instead of client-side),
`web/` only needs to update its import target. `pipeline/`, `parsers/`, and `firmware/`
are unaffected.

## Files (updated 2026-09-14 — this table said "Not built" for all of these
## as late as 2026-07-24's Fable master audit, nearly two months after the
## extraction below was actually completed; see known_issues.md 2026-09-14)
| File | Purpose | Status |
|---|---|---|
| `thresholds.js` | Numeric cutoffs per biomarker. | **Built.** |
| `index.js` | `evaluate()` command logic + `calculateBRI()` — scoring lives here, there is no separate `scoring.js`. | **Built.** |
| `commands.js` | Command string generation from scored state. | **Built.** |
| `sources.js` | Gen4/Gen3 source resolution per vector (`evaluateSources()`). | **Built.** |
| `schema.py` | Canonical biomarker key list. Parsers import this. | Not built — the one real remaining gap, blocks the Calibration Layer (`parsers/`). |

`src/App.js` now imports all scoring/threshold/command logic from this
directory (`web/src/App.js:2`) — the "Current violations" table that used
to live here described an extraction that has since been completed and was
removed rather than left stale a third time.
