# web/

React PWA — methuselah.ca.

**iOS wrapper status, corrected 2026-08-12:** `../ios/` does not exist — checked directly,
not assumed. Capacitor is only partially set up: `capacitor.config.ts` is real and configured
(appId `com.methuselah.app`, iOS-specific webview settings), and `@capacitor/ios` is a real
dependency, but `@capacitor/core` and `@capacitor/cli` are not installed, so `npx cap add ios`
wouldn't run as-is. This was started, not finished, and not currently in progress — treat the
iOS wrapper as not built yet, not as "lives elsewhere."

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

## Current violations

None known. The three violations previously listed here (hardcoded thresholds/scoring at
old `src/App.js` lines 275–291, command-string generation at 481–522, status-label
ternaries at 637–655) no longer exist — checked directly against the current file
2026-08-11: all three call sites now use `THRESHOLDS`/`COMMANDS`/`calculateBRI()` from
`engine/`, and a repo-wide grep for the old hardcoded patterns (`< 22`, `"SUPPRESSED"`,
`"OPTIMAL"` as bare string literals) returns nothing. This section was stale — the
extraction it was tracking already happened, likely when `engine/` was first built
(`engine/` has shown "Done" in `SESSION_HANDOFF.md`'s status table since at least
2026-07-08), and nobody had come back to update this file to match. If a real violation
resurfaces, list it here the same way, with exact line numbers, so it can be verified the
same way this one was closed.
