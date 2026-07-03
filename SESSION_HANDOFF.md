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

**Date:** 2026-07-03

- **Wrapper scripts updated to osascript** — `pull_morning.sh` and `pull_evening.sh` now use `osascript -e 'tell app "Terminal" to do script "..."'` instead of direct python3 call. Direct python3 via SSH fails (CoreBluetooth blocks in headless context); osascript opens Terminal with GUI context and is confirmed working.
- **North Star doc confirmed present** — `pipeline/data/findings/why_not_conventional_trackers.md` verified in repo. No action needed.
- **Three findings logged to known_issues.md** — lock screen widget operational standard confirmed, boot_ts rollover documented as recurring hardware property, threshold calibration locked with rationale.
- **Thresholds calibrated and live** — `engine/thresholds.js`: `deepSleep: 13` (clinical floor, universal), `hrv: 25` (personal baseline −1SD). Architecture note added to `ARCHITECTURE.md`.
- **First confirmed 0x5d HRV event** — evening activity pull 2026-07-02 22:29. Decoder working. Sleep HRV not yet captured.

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — tap lock screen widget before feet hit floor. Confirmed working method.

1. **Morning pull** — tap lock screen widget immediately on waking. Do not get up first.

2. **Log deep sleep result** — was last night's deep sleep above 13% (recovery from two consecutive 11% nights)? Add to `gen3_vs_gen4_comparison.csv` with Gen4 screenshots.

3. **Evening pull tonight** — tap lock screen widget before sleep.

4. **Begin 0x5d sleep HRV investigation** — why does HRV fire during evening activity pulls but not overnight sleep pulls. Compare boot_ts ranges and pfsm_state windows between the confirmed HRV pull and overnight sleep pulls.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
