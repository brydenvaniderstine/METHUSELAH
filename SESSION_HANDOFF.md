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
| `engine/` | Done | THRESHOLDS/COMMANDS filled and live. `sources.js` implements the Gen3/Gen4 source selector, verified live in browser 2026-07-08. `AWAITING TELEMETRY` graceful-degradation state added same session. |
| `firmware/` | Done | XIAO ESP32S3 PlatformIO project functional. |

---

## Last session summary

**Date:** 2026-07-08

- **Source selector UI labels VERIFIED LIVE in browser** — the dev-server blocker from earlier sessions is fixed: added a root `package.json` (`{ start: "npm --prefix web start", build: "npm --prefix web run build" }`) so `.claude/launch.json`'s `npm start` resolves correctly; confirmed harmless to Vercel since `vercel.json` explicitly pins `buildCommand`/`installCommand` to `cd web && ...`, ignoring root. With no Oura token saved, live-screenshotted the app: CARDIAC LOAD tile correctly showed `65.1 BPM` with "● GEN3 BLE" in cyan (falling back to the real `gen3_latest.json` bridge data), HRV and REPAIR DEPTH correctly showed "AWAITING DATA" (no Gen3 decoder yet), and the command panel correctly fired "INITIATE ACTIVE RECOVERY PROTOCOL" off the Gen3-sourced RHR value — proving the resolved vector drives the command engine, not just the tile label. The tile code itself required no changes; it was already correct from the prior session, just never verified live until now.
- **Graceful degradation fixed — `AWAITING TELEMETRY` state added** — found a real gap: `evaluate()` had no way to distinguish "every vector is null" from "every vector is null-or-in-range," so with zero data connected it would still report `BIOLOGY OPTIMAL.` Added `COMMANDS.awaitingTelemetry` (`engine/commands.js`) and a check in `evaluate()` (`engine/index.js`) that returns it only when glucose, HRV, RHR, and deep sleep are *all* `null`; any partial data still falls through to the normal cascade or `BIOLOGY OPTIMAL` as before. Updated `App.js`'s command panel render so `level === "awaiting"` shows a "no sources connected" hint instead of a meaningless `EXECUTE PROTOCOL` button. Verified with direct `node` execution against the real engine: all-null → `AWAITING TELEMETRY.`; one in-range value present → `BIOLOGY OPTIMAL.`; one out-of-range value present → its normal command fires. Confirmed live in browser that the existing partial-data path (Gen3 RHR only) is unaffected.
- **`pipeline/tools/SOURCE_SELECTOR_TEST.md` written** — manual verification steps for methuselah.ca post-deploy (token removal → Gen3 fallback; blocking all sources → AWAITING TELEMETRY), since the automated checks above only prove the logic works in this session's dev environment, not on the deployed site.
- **Track B condition #5 REDEFINED — owner decision 2026-07-08** — original definition ("14 consecutive nights with both Gen3 AND Gen4 data") becomes permanently unsatisfiable after the Oura token expires 2026-07-13. Redefined to "14 consecutive nights with Gen3 morning SLEEP WINDOW data; Gen4 preferred but not required after July 13." Updated in `ARCHITECTURE.md`'s Track B completion tracker. Current status: 2/14 (streak: 2026-07-06/07 → 2026-07-07/08), reset by the missed 2026-07-05/06 morning pull — computed directly from `gen3_vs_gen4_comparison.csv`, not estimated.
- **Source selector built — `engine/sources.js`** — implements the Gen3/Gen4 interchangeable-input architecture. `resolveVectors(gen4, gen3, manual)` resolves RHR, HRV, deep sleep, and glucose independently: Gen4 wins when fresh (< 24h), Gen3 fills in only where a decoder is validated (RHR only, via 0x6A), manual covers glucose, and a vector is `null` only when nothing has data. HRV and deep sleep stay Gen4-only pending the 0x5D and 0x6A sleep-stage decoders — no silent fallback to invalid data.
- **`engine/index.js` extended, not rewritten** — added `evaluateSources(gen4, gen3, manual)` which wraps the existing `evaluate()`/`calculateBRI()` contracts (kept unchanged, since App.js's render depends on their exact shape — `cmd`/`color`/`level`/`rat`/`briefing`). `evaluateSources` returns the normal command result plus a `vectors` map of `{ value, source, ready }` per vector.
- **`web/src/App.js` wired to the selector** — `evaluate()` call site replaced with `evaluateSources(ouraData, gen3Bridge, { glucose: glucoseReading })`; HRV/RHR/deep-sleep display values and the BRI score now come from resolved vectors, not raw `ouraData`, so the UI reflects Gen3 fallback automatically. Added a `timestamp` field to `ouraData` (was missing) so Gen4 freshness can actually be checked. Vector tiles now show "● GEN3 BLE" in cyan when a value is Gen3-sourced, "● OURA LIVE" for Gen4, nothing when neither has data.
- **Verified against real data** — ran the selector directly (not via browser; see note below) against the actual `gen3_latest.json` fixture and three synthetic scenarios (Gen4 fresh, Gen4 stale >24h, both absent). Confirmed: RHR correctly falls back to Gen3 (65.1 bpm) when Gen4 is stale/absent and correctly prefers Gen4 when both are fresh; HRV/deep sleep correctly stay `null` with no Gen3 source until those decoders are validated; manual glucose entry unaffected.
- **Production build verified clean** — `npm run build` compiles with no errors (+378 B gzip for the new module).
- **Browser preview NOT verified** — the project's `.claude/launch.json` runs `npm start` from the repo root, but the CRA app lives in `web/`, so `preview_start` can't launch it in this environment (fails resolving `public/index.html`). Also found and killed a stale/broken `node` process wrongly bound to port 3000 from a prior session (was erroring on every request, not a working server). Live UI verification on methuselah.ca after deploy is still needed — see next session priority.
- **Found: GitHub PAT embedded in plaintext in `git remote -v`** — the `origin` URL contains a live-looking token. Recommend rotating it and switching to SSH or a credential helper; flagged to owner, not fixed (out of scope for this session).
- **Track B condition #3 (SpO2 cross-validation) CLOSED 2026-07-08** — third consecutive passing night logged: 2026-07-07/08, Gen3 SpO2 avg 93.8% vs Gen4 97%, gap 3.2%, within ±5% gate. Full sequence: 1.9% → 4.5% → 3.2%, all three passing. Row added to `pipeline/data/findings/gen3_vs_gen4_comparison.csv`. This data was confirmed in a claude.ai session the morning of 2026-07-08 from pull output and Oura screenshots but hadn't been logged yet because the Claude Code session that captured it compacted before logging completed — logged now from the owner's direct report. Gen3 IBI HR mean ~56.8 bpm cross-validated against 0x6A; 0x6B recorded no motion packets (clean sleep); sleep efficiency 71% (3h17m awake) is low for this dataset. Marked closed in `ARCHITECTURE.md`'s Track B completion tracker (condition #3) and its source-selector readiness table.
- **SpO2 wired into `engine/sources.js` as a resolved (telemetry-only) vector** — now that condition #3 is closed, `resolveVectors()` returns a `spo2` entry (Gen3 via `vectors.spo2_avg_pct`, Gen4 unplumbed so always Gen3 or null today). It intentionally does **not** join `evaluate()`'s priority cascade — no `THRESHOLDS.spo2`/`COMMANDS.spo2` exists, and `engine/index.js`'s own priority-order comment gates adding a fifth command vector behind a v3 discussion. This just makes its value/source resolvable and interchangeable, same as RHR.
- **⚠️ Oura token valid until 2026-07-13 — 5 days remaining.**
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
- **Timed walk experiment completed (2026-07-07)** — ~500 steps, phone BT OFF. Raw pull lost to buffer roll; 7 pairs of 0x7E/0x7F + 5 0x6B payloads recovered from terminal output and preserved in `walk_experiment_20260707_decoded.txt`.
- **0x6B step count CONFIRMED — promoted to DONE** — b[0] sum = 497 across 5 walk windows (0.6% from 500 ground truth). open_ring MOTION_STATE enum is WRONG for this field. `pipeline/decoders/0x6b.py` created, wired into pull script. b[1] cadence (116-120 spm) is a candidate pending second experiment.
- **0x7E/0x7F identified as FFT spectral features, NOT step counters** — boot_ts spacing 296-326 ticks (mean 307.8, timer-driven). No single byte column sums to ~500. b[9] of 7E consistently dominant (151-235). Status: IN PROGRESS — byte field names need firmware RE for FFTset sub-message schema.
- **0x5D HRV firing context CONFIRMED ACTIVITY-ONLY (2026-07-07)** — Audited all 10 sleep (morning) pulls and 9 evening pulls. 0x5D appears in exactly ONE file (MIXED activity pull). Sleep buffer window = 7-12 min at 3.70 ticks/sec — if 0x5D fired during sleep, it WOULD appear; it does not. Single corpus packet shows HR 70-72 bpm (activity HR), co-occurs with step features and EHR session boundary. Track B condition #2 (0x5D in 3 consecutive morning pulls) CANNOT be met as currently defined. Owner decision required: redefine using IBI-RMSSD, change pull timing, or remove gate.
- **FFT walk analysis tool built (2026-07-07)** — `pipeline/tools/analyze_fft_walk.py` analyzes 0x7E/0x7F byte statistics across pull files. Cross-file finding: 7E b[9] is 1.5-3x higher in controlled walk (mean 193.3) vs other activity (mean 60-125). 7F b[10] drops from 188-206 (activity) to 128 (walk). 7E b[0]↔b[8] track within <10 units in ALL files. Second walk at slow pace needed to separate pace-sensitivity from activity-type effect.
- **0x6B step count and cadence wired into bridge JSON** — `step_count` and `cadence_spm` added to vectors dict. Web app sys-log now shows STEPS field. Null in sleep window; populated in activity pulls with 0x6B packets.
- **0x5D HRV root cause logged and condition #2 formally revised** — Root cause: buffer displacement by Debug events + physiological state mismatch (HRV may not fire in morning pull window). Two hypotheses documented in `known_issues.md`. ARCHITECTURE.md condition #2 updated with three revision options (A/B/C) — owner decision required before condition can be closed.
- **Track B condition #2 REDEFINED — owner decision 2026-07-07** — Option A selected. Condition #2 is now "0x5D fires in three evening activity pulls within the Track B validation period." Status: 1/3 confirmed (2026-07-02 evening MIXED pull, 4 windows, 22–30ms RMSSD). Two more evening pulls with 0x5D events required.
- **⚠️ Oura token valid until 2026-07-13 — 6 days remaining.**

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — ring must be within Bluetooth range of Mac when shortcut fires.

1. **Run `pipeline/tools/SOURCE_SELECTOR_TEST.md` against methuselah.ca** — this session verified the source selector and `AWAITING TELEMETRY` fix locally (real browser, real `gen3_latest.json` data, screenshotted). The deployed site still hasn't been checked directly — run Test A (token removal → Gen3 fallback) and Test B (no sources → `AWAITING TELEMETRY`) there and confirm they match.
2. **Evening pull tonight — advance condition #2 to 2/3** — ring must be near Mac. Any evening activity pull that captures 0x5D events counts. Current: 1/3.
3. **Second FFT walk at slow shuffle pace** (~60-70 spm) — run `python3 pipeline/tools/analyze_fft_walk.py <new_file> <walk_exp_file>` to compare 7E b[9] between fast and slow. Tests cadence-sensitivity of the dominant frequency bin.
4. **Decide whether SpO2 becomes a fifth command vector** — it's resolved in `engine/sources.js` (telemetry only) since condition #3 closed, but adding `THRESHOLDS.spo2`/`COMMANDS.spo2` and a cascade branch in `engine/index.js` is a deliberate v3 discussion, not a default next step. Needs an owner decision on the threshold value and priority position before implementing.
5. **Track B — remaining conditions before completion**: #1 sleep_state full-night transitions (not started), #2 HRV redefined — 1/3 evening activity pulls with 0x5D confirmed, #4 0x77/0x7E/0x7F decoders still IN PROGRESS, #5 redefined this session (Gen3-only, 14 consecutive SLEEP WINDOW nights) — 2/14, streak reset 2026-07-05/06. Condition #3 (SpO2) is CLOSED.
6. **July 13th subscription decision** — Oura API token expires 2026-07-13, 5 days remaining. Decide whether to renew or accept Gen4 data freeze at that date.
7. **Rotate the GitHub PAT embedded in `origin` remote URL** — found in plaintext via `git remote -v`. Recommend switching to SSH or a credential helper.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
