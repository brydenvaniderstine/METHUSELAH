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

- **MILESTONE: First real sleep state transitions captured** — evening pull 22:58 from `gen3_pull_20260703_225853.txt`. First pull in Track B history showing state=1 → state=0 transitions across 8 x6A samples (25%/75% split). HR 76→67 bpm across transition consistent with physiological settling. Track B condition #1 has first evidence — full stage mapping not yet validated.
- **Partial Gen3 row logged** — 2026-07-03 evening: HR 67.0–76.0 bpm, SpO2 90.0–94.8% avg 91.5%, temp 34.32–34.94°C. Gen4 screenshots pending — row to be completed tomorrow morning.
- **Wrapper scripts updated to osascript** — `pull_morning.sh` and `pull_evening.sh` now use `osascript` instead of direct python3 (headless SSH blocks CoreBluetooth).
- **Thresholds calibrated and live** — `deepSleep: 13`, `hrv: 25`. Architecture note added.
- **First confirmed 0x5d HRV event** — evening activity pull 2026-07-02. Decoder working. Sleep HRV not yet captured.

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — tap lock screen widget before feet hit floor. Confirmed working method.

1. **Morning pull** — tap lock screen widget immediately on waking. Do not get up first.

2. **Complete 2026-07-03 evening comparison row** — take Gen4 Oura screenshots (sleep stages, HR, SpO2) for tonight's sleep and add to `gen3_vs_gen4_comparison.csv` row dated "2026-07-03 evening." This row is partial — Gen4 fields are all n/a.

3. **Evening pull tonight** — tap lock screen widget before sleep.

4. **Begin 0x5d sleep HRV investigation** — why does HRV fire during evening activity pulls but not overnight sleep pulls. Compare boot_ts ranges and pfsm_state windows between the confirmed HRV pull and overnight sleep pulls.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
