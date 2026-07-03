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

- **First confirmed 0x5d HRV event** — evening activity pull 2026-07-02 22:29. Decoder confirmed working. Four RMSSD windows: 22/30/23/23 ms at HR 70–72 bpm. Sleep HRV not yet captured.
- **Auto-file MIXED bug fixed** — destination renamed, not source. FileNotFoundError resolved. `outpath` no longer mutated before `shutil.move()`.
- **Gen4-only comparison row logged for 2026-07-02/03** — deep sleep 11% (lowest in dataset, below 12% threshold). HRV 26ms (lowest recorded, down 36→32→31→26ms four consecutive nights). Buffer rolled before morning pull — ACTIVE WINDOW at 09:16.
- **Morning pull buffer rollover confirmed again** — ACTIVE WINDOW at 09:16. Lock screen widget is the fix.
- **Sleep protocol threshold breached** — HRV 26ms below 22ms threshold and deep sleep 11% below 12% threshold. Sleep protocol command should fire tonight.

**Task 2 complete — Python-to-React bridge fully wired (commit 641ee72).**
- Pull script writes `pipeline/data/bridge/gen3_latest.json` after every run (classifier, vectors, pull_file, timestamp, source tag).
- `web/package.json` prebuild/prestart copies bridge JSON to `web/public/` so CRA can serve it.
- `web/src/App.js`: bridge fetch useEffect on mount; `gen3Bridge` state; GEN3 INTERCEPT line renders at top of sys-log when data present (shows classifier, RHR, SpO2, temp, battery — cyan, timestamped).
- Bridge file gitignored (data); `.gitkeep` committed to track directory.
- iOS Shortcut wrappers at `pipeline/tools/pull_morning.sh` / `pull_evening.sh`; setup guide at `pipeline/tools/SHORTCUT_SETUP.md`.
- Build clean at 67.61 kB gzip.

**Earlier this session — Live site verified 2026-07-01 22:xx — all systems nominal, tap-to-expand confirmed working in production.**
- Smoke test found: 8 local commits had never been pushed. Also found npm/typescript peer dep conflict (react-scripts@5 requires TS ^3||^4, package.json has TS 5.7.2) — was silently handled by pnpm, fatal under npm. Fixed with `web/.npmrc` legacy-peer-deps=true. Deployed, bundle hash updated to c8fa7be5, 200/400 confirmed.

**Evening pull filed — first day of two-pulls-a-day rhythm.**
- `gen3_pull_20260701_220314.txt`: SLEEP WINDOW at 22:03 — daytime rest event captured (not overnight sleep). HR 63–67 bpm trending upward, consistent with sleep-to-waking transition. Distinct from deep overnight baseline (54–56 bpm).
- `known_issues.md`: evening pull finding appended — HR signature distinguishes sleep quality before stage decoding is working. Battery 51.9%/50% at 10pm (~30% daily drain, first baseline data point). SpO2 avg ~94%, no outlier.
- `gen3_vs_gen4_comparison.csv`: partial Gen3-only row added for 2026-07-01 evening. Gen4 fields n/a — pending tomorrow morning screenshots.

**V1 architecture fully closed (earlier today):**
- Auto-sync: `prebuild`/`prestart` scripts in `web/package.json`. Engine-to-web copy is automatic.
- Known design tensions (#6, #7, #8) in `ARCHITECTURE.md`. Engine canonical. Tap-to-expand live.

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — morning pull must happen before leaving bed. Tap iOS shortcut. Script ready.

1. **Lock screen widget** — add Morning Pull shortcut as a lock screen widget so one tap from the lock screen runs it without opening the Shortcuts app. This is the fix for the buffer rollover problem.

2. **Evening pull tonight** — open Shortcuts app, tap Morning Pull (or Evening Pull) before sleep.

3. **Monitor deep sleep recovery tonight** — after sleep protocol fires today. Log result to CSV.

4. **Begin 0x5d sleep HRV investigation** — why does HRV fire during evening activity pulls but not overnight sleep pulls. Start by comparing the boot_ts ranges and pfsm_state windows between the one HRV pull and the overnight sleep pulls.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
