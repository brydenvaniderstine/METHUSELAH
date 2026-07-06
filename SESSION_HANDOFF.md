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

**Date:** 2026-07-05

- **Oura API connection restored** — token expired (created 2026-06-20), new token valid until 2026-07-13. Date parameter bug fixed in commit a5681db — `toISOString()` replaces `toLocaleDateString`, `res.ok` check added. OURA LIVE confirmed on methuselah.ca.
- **⚠️ Hard deadline: 2026-07-13** — Oura Personal Access Token expires. After that date the Gen4 API connection drops permanently unless subscription renewed. Track B sovereign BLE pipeline must be primary data source by then or the live site loses three of four vectors.
- **EXECUTE 45-MIN ZONE 2 OUTPUT firing correctly** — HRV 18ms triggered command with briefing on live site.
- **Track B condition #3 night 1 of 3 passed** — Gen3 SpO2 95.1% vs Gen4 97%, gap 1.9%, within ±5% gate. Two more consecutive nights required to close condition.
- **Comparison CSV row completed for 2026-07-04/05** — HRV 18ms lowest recorded, five-night declining trend (36→32→31→26→18ms). Deep sleep 16%, clean baseline.
- **Shortcut absolute path fix committed** — `SHORTCUT_SCRIPT.txt` created for iPhone copy-paste.

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — tap lock screen widget before feet hit floor.

1. **Update iPhone Morning Pull shortcut Script field** — paste content of `pipeline/tools/SHORTCUT_SCRIPT.txt`. Absolute paths fix the silent failure.

2. **Execute Zone 2 protocol today** — HRV command is live and correct.

3. **Evening pull before sleep tonight**.

4. **Morning pull immediately at waking tomorrow** — lock screen widget. Track B condition #3 night 2 of 3.

5. **Watch the 2026-07-13 token expiry** — if subscription not renewed, Gen4 API vectors go dark. Decide before that date.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
