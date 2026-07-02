<!--
UPDATE RULE: Claude Code must update the "Last session summary" and "Next session priority"
sections at the end of any session that produces a finding, structural change, or decoder
update. Do not skip this step.
-->

> North Star: pipeline/data/findings/why_not_conventional_trackers.md
> Read this before making any product decision this session.

# METHUSELAH — Session Handoff

This file is the single source of truth for picking up where the last session left off.
Updated by Claude Code at the end of any session that produces a finding, structural
change, or decoder update. If this file and a manually uploaded SESSION_HANDOFF_vN.md
conflict, this file takes precedence — it is version-controlled.

---

## Current build status

| Layer | Status | Notes |
|---|---|---|
| `web/` | Done | React PWA live. Business logic not yet extracted to `engine/` — violations documented in `web/README.md`. |
| `pipeline/` Track B | Active | 34 Gen3 pulls. 9 decoders validated, 14 partial. Decoders extracted to `pipeline/decoders/`. Walk experiment inconclusive (Oura app BLE contention). |
| `parsers/` | Not started | Skeleton exists. No parsers built. |
| `engine/` | Skeleton only | `engine/index.js` created with correct structure (priority comment, all-clear fallback). THRESHOLDS/COMMANDS are stubs — fill from `web/src/App.js` during engine build session. |
| `firmware/` | Done | XIAO ESP32S3 PlatformIO project functional. |

---

## Last session summary

**Date:** 2026-07-01

**Session 3 — Tap-to-expand briefing live. V1 architecture complete.**
- `web/src/App.js`: `briefingOpen` state added. Tapping `cmd-text` toggles briefing. Briefing is visually subordinate (11px, text-dim, left border). Resets on protocol change. Build verified passing.
- Design test (as built): 3 flags (#6 burnout, #7 reliability, #8 override). #8 partially mitigated — briefing is opt-in, hidden by default. None block shipping. All three flags remain open for a future session.

**Session 2 — Engine extraction complete:**
- `engine/thresholds.js`, `engine/commands.js`, `engine/index.js` — thresholds and commands canonical.
- `web/src/App.js`: zero hardcoded thresholds, zero hardcoded command strings. Imports from engine/ only.
- CRA constraint: `web/src/engine/` is a required physical copy. Edit `engine/` at root, then `cp engine/*.js web/src/engine/`.

**Session 1 — North Star document filed:**
- `pipeline/data/findings/why_not_conventional_trackers.md` created.

---

## Next session priority

1. **Walk experiment (retry)** — Kill Oura app BEFORE walking. BT off on phone. 20+ min walk. Pull immediately on return. This is the single remaining physical-action blocker for 0x7E/0x7F step decoder validation.

2. **Fresh Gen4 export** — Export Gen4 data from 2026-06-08 onward. Unlocks same-night cross-validation for June 2026 pulls (current export ends 2026-06-07).

3. **Track B decoder work** — Next unworked decoder in open_ring_roadmap.md. Check the roadmap before starting.

2. **Walk experiment (retry)** — Kill Oura app *before* walking. BT off on phone during walk. 20+ min walk. Pull immediately on return before relaunching app. This is the single remaining physical-action blocker for 0x7E/0x7F step decoder validation.

3. **Fresh Gen4 export** — Export Gen4 data from 2026-06-08 onward. Unlocks same-night cross-validation for all June 2026 pulls (current export ends 2026-06-07).

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
