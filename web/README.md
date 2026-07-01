# web/

React PWA — methuselah.ca. Capacitor wrapper for iOS lives at `../ios/`.

## What belongs here
- React components, pages, hooks, styles
- `public/` assets and `src/` application code
- Build tooling config (`package.json`, `.eslintrc.json`, `capacitor.config.ts`)
- `api/oura.js` — Vercel serverless function (deployment constraint, not a logic layer)

## Import rules
**Imports from `engine/` only.** Never import from `pipeline/`, `parsers/`, or `firmware/`.
Business logic (thresholds, scoring, status labels, command strings) must live in `engine/`.

## Removability
This directory can be removed without affecting `pipeline/`, `parsers/`, `engine/`, or
`firmware/`. The other layers have no dependency on `web/` existing. If the frontend is
replaced (e.g. native SwiftUI), delete this directory and build against `engine/` directly.

## Current violations (flagged, not yet fixed)
These exist because `engine/` hasn't been built yet. Fix by extracting to `engine/` — do not
add more logic to `src/App.js` in the meantime.

| File | Lines | Violation | Correct home |
|---|---|---|---|
| `src/App.js` | 275–291 | HRV/RHR/deep-sleep thresholds + OPTIMAL/NOMINAL/SUPPRESSION scoring hardcoded in React component | `engine/thresholds.js` + `engine/scoring.js` |
| `src/App.js` | 481–522 | Command string generation and warn-level logic inside component | `engine/commands.js` |
| `src/App.js` | 637–655 | Status label ternaries (`< 22 ? "SUPPRESSED" : "OPTIMAL"`) inline in JSX | `engine/thresholds.js` |
