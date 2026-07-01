# engine/

Single source of truth for what the data means and what to do about it.
This is the only layer `web/` is allowed to import from.

## Purpose
- Threshold definitions (what HRV value is "suppressed" vs "optimal")
- Scoring logic (readiness score, suppression tier calculation)
- Command string generation (what METHUSELAH tells the user to do)
- Cross-vector relationship logic (how HRV + glucose + sleep together change a recommendation)
- Canonical biomarker schema (key names used by all parsers)

## Planned files
- `thresholds.js` / `thresholds.py` — numeric cutoffs per biomarker. Single place to tune.
- `scoring.js` — readiness and suppression tier calculation. No UI logic here.
- `commands.js` — command string generation given a scored state.
- `schema.py` — canonical biomarker key list. Parsers import this, not the reverse.

## Import rules
- `engine/` imports from `parsers/` (to get biomarker values) and nowhere else.
- `web/` imports from `engine/` only.
- `engine/` never imports from `pipeline/`, `web/`, or `firmware/`.

## Current violations (do not fix yet — fix by extracting from src/App.js)
- HRV/RHR/deep-sleep thresholds hardcoded in `src/App.js` lines 275–291. Move to `engine/thresholds.js`.
- Scoring function (`score += 25` / `score += 15` tiers) in `src/App.js` lines 275–291. Move to `engine/scoring.js`.
- Command string generation in `src/App.js` lines 481–522. Move to `engine/commands.js`.
- Status label ternaries in `src/App.js` lines 637–655. Move to `engine/thresholds.js` as exported functions.
