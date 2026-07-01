# web/

React PWA — the methuselah.ca frontend. Capacitor wrapper for iOS lives at `../ios/`.

## What belongs here
- React components, pages, hooks, styles
- `public/` assets
- `src/` application code
- Build tooling config (`package.json`, `.eslintrc.json`, `capacitor.config.ts`)

## Import rules
- **Imports from `engine/` only.** Never import directly from `pipeline/`, `parsers/`, or `firmware/`.
- Business logic (thresholds, scoring, status labels, command strings) must live in `engine/` — not in components.
- Data fetching for Oura Gen4 cloud API lives in `api/` at the repo root (Vercel serverless function); this is a deployment constraint, not a logic layer.

## Current violations (do not fix here — fix by moving logic to engine/)
- `src/App.js` lines 275–291: HRV/RHR/deep-sleep thresholds and OPTIMAL/NOMINAL/SUPPRESSION scoring hardcoded in a React component. Correct home: `engine/scoring.js`.
- `src/App.js` lines 481–522: Command string generation and warn-level logic inside the component. Correct home: `engine/commands.js`.
- `src/App.js` lines 637–655: Status label ternaries (`< 22 ? "SUPPRESSED" : "OPTIMAL"`) inline in JSX. Correct home: `engine/thresholds.js`.
