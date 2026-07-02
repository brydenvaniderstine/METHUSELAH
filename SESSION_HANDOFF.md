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

**Session 1 — North Star document filed:**
- `pipeline/data/findings/why_not_conventional_trackers.md` created — founding rationale, 10 failure modes, design test checklist. Version-controlled.
- `ARCHITECTURE.md`: Founding rationale section added above layers breakdown.
- `SESSION_HANDOFF.md`: North Star pointer added to file header.
- Design test run against tap-to-expand briefing: 3 flags (#6 burnout — no adherence acknowledgment; #7 reliability — no confidence caveat on cited values; #8 override — no escape valve in briefing template). None block shipping. #8 is highest-priority to revisit.

**Prior session (infrastructure):**
- methuselah.ca confirmed live on Vercel. `vercel.json` picked up correctly.
- `engine/index.js` created with correct structure (stubs for THRESHOLDS/COMMANDS).
- `known_issues.md` and `open_ring_roadmap.md` updated. Track B definition drafted in ARCHITECTURE.md.

---

## Next session priority

1. **Session 2 — Extract business logic from `web/src/App.js` into `engine/`** — `engine/index.js` stub is ready. Extract THRESHOLDS from App.js L278-294, COMMANDS from L484-525. Create `engine/thresholds.js` and `engine/commands.js`. Update App.js to import from `engine/` only. App must behave identically before and after — same commands, same thresholds, no visual changes.

2. **Walk experiment (retry)** — Kill Oura app *before* walking. BT off on phone during walk. 20+ min walk. Pull immediately on return before relaunching app. This is the single remaining physical-action blocker for 0x7E/0x7F step decoder validation.

3. **Fresh Gen4 export** — Export Gen4 data from 2026-06-08 onward. Unlocks same-night cross-validation for all June 2026 pulls (current export ends 2026-06-07).

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
