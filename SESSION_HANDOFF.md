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

**Date:** 2026-07-07

- **Gen4-only comparison row logged for 2026-07-05/06** — deep sleep 20% best night in dataset, recovery bounce confirmed. HRV 22ms — sixth consecutive night below 25ms threshold. Zone 2 command firing correctly.
- **Track B condition #3 still at 1/3** — no Gen3 sleep data from morning shortcut (ring out of BLE range).
- **0x6E IBI decoder WRITTEN AND VALIDATED** — 549/549 corpus packets decode without error. Layout confirmed: b0=channel byte (bit7=A/B), b1-5=5× IBI high, b6-10=5× IBI low+amp, b11=mid bits, b12=shift nibble. Cross-validated vs 0x6A avg_hr: −1.1 to +1.3 bpm across 5 sleep files. Wired into pull script. Promoted to DONE.
- **0x77 spo2_dc_event decoder WRITTEN AND VALIDATED** — 384/384 corpus packets decode without error. 357 real (13 i8 samples dominant), 27 sentinel (aaaab2). DC range −128 to +127, mean −3.70, stdev 43.84. Cross-channel A/B correlation r=+0.80 to +0.93 confirms real PPG signal. Wired into pull script. Stays IN PROGRESS (ceiling: b1..b3 header vs all-samples indistinguishable, band identity unknown).
- **0x6E and 0x77 both LIVE-CONFIRMED in evening pull (2026-07-06)** — first live fire for both decoders. 0x6E: channels A/B alternating, IBI 857–909ms, mean HR 67.8 bpm (ACTIVE WINDOW, motion artifact expected). 0x77: DC samples and sentinel separation both correct. Auto-file → gen3_evening/, bridge updated, battery 82.4%.
- **0x6F SpO2 calibration diagnostic (2026-07-07)** — Systematic low bias confirmed in raw sensor bytes (not decoder arithmetic). SPO2_OFFSET=6 is correct. Mean Gen4−Gen3 gap: +3.97% (stdev 1.86%, N=3 nights). Fixed offset +4.0% REJECTED — fails ±2% gate on 2026-07-04/05 (99.1% vs 97.0%). Need ≥5 paired nights with stdev <1.0%. Decoder unchanged.
- **0x61/0x09 pfsm_state labels wired** — Pull script now prints pfsm labels: SLEEP_REGIME(6), ACTIVE_REGIME(3/4), TRANSITIONAL(5), ECHO_RECORD(128). Behaviorally derived from corpus context segregation, NOT firmware-confirmed.
- **0x6E mean HR added to bridge JSON** — `ibi_hr_bpm` field added to `vectors` dict. Will populate on next pull when 0x6E fires. Web app sys-log now shows `IBI_HR X.X BPM` alongside RHR.
- **Web app rebuilt and ready** — All changes compiled cleanly (67.67 kB gzip).
- **Track B condition #3 at 2/3** — Night 2 (2026-07-06/07): Gen3 SpO2 93.5% vs Gen4 98% — gap 4.5%, within ±5% gate. Gap widening (1.9%→4.5%) — worth watching but not failing yet. One more passing night closes condition #3 permanently.
- **Option A morning pull confirmed working** — Mac on nightstand, lock screen widget fired cleanly. First successful SLEEP WINDOW pull via this method.
- **0x6E fired in sleep context for the first time** — mean HR 64.8 bpm, within 1.1 bpm of 0x6A avg_hr. Sleep-context cross-validation confirmed working.
- **HRV 30ms — first above 25ms threshold in 7 nights** — trend was 36→32→31→26→18→22→30ms. Possible reversal beginning.
- **0x6B motion_period corpus re-analysis** — 5 packets confirmed (was 4). All b[0] values (53-62) outside the MOTION_STATE enum (0-3). Hypothesis: motion-intensity count not enum. 8-byte payload form still unobserved. Walk experiment is next attempt.
- **0x61/0x09 pfsm_state cross-reference — NEW FINDING** — 68 packets across corpus. pfsm_state values segregate by sleep vs activity: pfsm=6 fires ONLY in sleep context (co-present with 0x6A); pfsm=3/4 fire ONLY in activity context; pfsm=5 fires in both. f2 retention ratio differs by state: pfsm=3→128 ~4.5%, pfsm=5→128 ~10-12%, pfsm=6→128 ~55%. open_ring has no pfsm enum — raw u8 only. Ceiling: firmware needed to confirm state machine definitions.
- **Gen4 CSV export merged into comparison dataset** — `pipeline/tools/merge_oura_csv.py` ran; 6 overnight rows updated, 28 fields filled. `gen4_hrv_avg` added as new column (HRV trend: 31→31→26→18→22ms across comparison period). Source: `/Desktop/oura_2026-05-29_2026-07-10_trends.csv`. Note: `2026-07-03 evening` row left n/a — no unambiguous Gen4 counterpart. `gen4_respiratory_rate` now populated for all rows via CSV (previously n/a on several rows).
- **Walk experiment still required for 0x7E/0x7F** — zero packets in corpus. Protocol documented in `pipeline/tools/WALK_EXPERIMENT.md`.
- **⚠️ Oura token valid until 2026-07-13 — seven days remaining.**

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — ring must be within Bluetooth range of Mac when shortcut fires.

1. **Execute timed walk experiment** — 500 steps, phone Bluetooth OFF before starting, pull immediately on return. Protocol: `pipeline/tools/WALK_EXPERIMENT.md`. Primary target: 0x7E/0x7F (zero packets). Secondary: 0x6E amplitude units, 0x77 band identity, 0x6B motion context.

2. **Evening pull tonight** — ring must be near Mac.

3. **Morning pull tomorrow — Track B condition #3 night 3** — one more Gen3 SpO2 within ±5% of Gen4 closes condition #3 permanently. ⚠️ Oura API token expires 2026-07-13 — 6 days remaining.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
