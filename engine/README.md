# engine/

Single source of truth for what the data means and what to do about it.
The only layer `web/` is allowed to import from.

## CRA build constraint
CRA (create-react-app) blocks imports from outside `web/src/`. Engine files must
also exist at `web/src/engine/` for the build to work. **Edit files here in `engine/`,
then copy to `web/src/engine/` before committing.** Never edit `web/src/engine/` directly.

```bash
cp engine/*.js web/src/engine/
```

This copy is not automated. It is a known architectural friction point — acceptable
until CRA is ejected or replaced with Vite.

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

## Planned files
| File | Purpose | Status |
|---|---|---|
| `thresholds.js` | Numeric cutoffs per biomarker. Single place to tune. | Not built — logic in `src/App.js` L637–655 |
| `scoring.js` | Readiness and suppression tier calculation. | Not built — logic in `src/App.js` L275–291 |
| `commands.js` | Command string generation from scored state. | Not built — logic in `src/App.js` L481–522 |
| `schema.py` | Canonical biomarker key list. Parsers import this. | Not built |

## Current violations (to fix by extracting from src/App.js)
| Source file | Lines | What to move | Destination |
|---|---|---|---|
| `src/App.js` | 275–291 | HRV/RHR/deep-sleep thresholds + scoring ladder | `engine/thresholds.js` + `engine/scoring.js` |
| `src/App.js` | 481–522 | Command strings and warn-level logic | `engine/commands.js` |
| `src/App.js` | 637–655 | Status label ternaries inline in JSX | `engine/thresholds.js` (exported functions) |
