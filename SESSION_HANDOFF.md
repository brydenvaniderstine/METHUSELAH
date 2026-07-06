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

- **Shortcut absolute path fix applied** — `pull_morning.sh` and `pull_evening.sh` rewritten with absolute paths (`REPO=`, `LOG=`, `ERR=` vars). Tilde expansion and relative paths silently fail via SSH → osascript → Terminal. Fix confirmed working: `gen3_pull_20260705_213406.txt` filed to `gen3_evening/` at 21:34 by tonight's test run.
- **Error log clarification** — `morning_pull_error.log` contains errors from a previous run with OLD code (before the auto-file `outpath` mutation fix). Not a regression. The fixed code is confirmed working.
- **`SHORTCUT_SCRIPT.txt` created** — `pipeline/tools/SHORTCUT_SCRIPT.txt` contains the exact string to paste into iPhone shortcut Script field (absolute paths, no tilde).
- **MILESTONE: First real sleep state transitions captured** — `gen3_pull_20260703_225853.txt`. Track B condition #1 has first evidence.
- **Partial Gen3 row logged for 2026-07-03 evening** — Gen4 screenshots still pending.

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — tap lock screen widget before feet hit floor. Confirmed working method.

1. **Update iPhone shortcut** — paste content of `pipeline/tools/SHORTCUT_SCRIPT.txt` into the shortcut's Script field. This replaces the old `~/` path that was silently failing.

2. **Morning pull** — tap lock screen widget immediately on waking. Do not get up first.

3. **Complete 2026-07-03 evening comparison row** — Gen4 Oura screenshots (sleep stages, HR, SpO2) to fill the n/a fields in `gen3_vs_gen4_comparison.csv`.

4. **Evening pull tonight** — tap lock screen widget before sleep.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
