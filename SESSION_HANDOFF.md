<!--
UPDATE RULE: Claude Code must update the "Last session summary" and "Next session priority"
sections at the end of any session that produces a finding, structural change, or decoder
update. Do not skip this step.
-->

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
| `pipeline/` Track B | Active | 34 Gen3 pulls. 9 decoders validated, 14 partial. Decoder functions still inline in pull script — migration to `pipeline/decoders/` pending. Walk experiment inconclusive (Oura app BLE contention). |
| `parsers/` | Not started | Skeleton exists. No parsers built. |
| `engine/` | Not started | Skeleton exists. Logic still in `src/App.js`. |
| `firmware/` | Done | XIAO ESP32S3 PlatformIO project functional. |

---

## Last session summary

**Date:** 2026-06-30 / 2026-07-01

**Decoder work completed:**
- 0x80 green_ibi_quality_event: VALIDATED. Cross-validated against 0x6A avg_hr on 3 pulls (mean delta +0.9bpm). IBI=2000ms sentinel confirmed. Session-gated (9/29 pulls). Corrected wrong "activity-only" prior entry.
- 0x72 sleep_acm_period: PARTIAL DECODE. Format corrected to 6×u16 LE (open_ring reads u8 — wrong). f1=gravity axis confirmed (0 violations of f1=max(f0,f1,f2) across 215 packets). sleep_state=0 has ~2× higher motion than state=1.
- 0x5B ble_connection_ind: PARTIAL DECODE. 4-subtype structure discovered. BLE spec confirmed connection intervals (258.75ms sleep / 33.75ms active). MAC address in subtype 3.
- 0x50 activity_info_event: PARTIAL DECODE. b[0]=activity class enum. 13-sample intensity array in trailing bytes (missed by open_ring auto-extractor).
- 0x6C feature_session: b1 direction map extended to 5 values. b0=8=EHR_INHIBIT confirmed.
- 0x77 spo2_dc_event: Structural ceiling confirmed. Diagonal correlation matrix proves b[1:14] are time-series, not independent fields. b[0] vs SpO2 r≈0.
- 0x73 ehr_trace_event: PARTIAL DECODE. Firmware name confirmed as DHR (DHR_state:1 debug event). 4-packet burst structure: 14b(ch0)+5b(ch0)+14b(ch1)+5b(ch1) at ~1.58s intervals. open_ring decoder reads flat u8 — wrong.
- 0x56 unknown_56: NOT OBSERVED (0 packets, open_ring internal contradiction documented).
- 0x85 unknown_85: NOT OBSERVED (0 packets, low-cadence emitter).
- Walk experiment: INCONCLUSIVE. Oura app BLE contention drained step-feature events before pull script connected. Revised protocol documented.

**Infrastructure completed:**
- Gen4 baseline reference: 359 nights imported, `pipeline/data/findings/gen4_baselines.md` created.
- `gen3_vs_gen4_comparison.csv`: 3 new columns added (respiratory_rate, activity_balance, readiness_contributors_summary).
- ARCHITECTURE.md created — five-layer architecture documented with import rules, removability contract, build status, deferred decisions.
- SESSION_HANDOFF.md created (this file) — version-controlled, supersedes SESSION_HANDOFF_v9.md.
- Directory skeleton created: `pipeline/`, `engine/`, `parsers/`, `web/`, `firmware/` with READMEs in each.
- Physical file migration (audit pass 1): `tools/` → `pipeline/tools/`, `data/findings/` → `pipeline/data/findings/`, stray pull files → `data/raw_pulls/gen3_evening/`.
- Violation comments added to `web/src/App.js` and `pipeline/tools/oura_gen3_morning_pull.py`.
- `pipeline/data/findings/SCHEMA.md` created — full column schema for comparison CSV.
- Update rules prepended to `known_issues.md` and `open_ring_roadmap.md`.
- `data/raw_pulls/gen3_evening/` created with README. gitignore fixed to track README files in raw_pulls/.
- Morning pull timing operational pattern documented (4 confirmed instances).
- Pre-bed pull gen3_pull_20260630_215819.txt logged as clean SLEEP WINDOW.
- **Decoder extraction (Session 1 of 2):** 9 inline decode_* functions extracted from `pipeline/tools/oura_gen3_morning_pull.py` into individual `pipeline/decoders/0x??.py` files. `pipeline/decoders/__init__.py` uses importlib.util to load digit-named modules (can't use dotted from-imports). `pipeline/decoders/utils.py` holds _i8/_u32 helpers. Pull script now imports from `pipeline.decoders`.
- **Web layer migration (Session 2 of 2):** All web files (src/, public/, ios/, package.json, capacitor.config.ts, lockfiles, .eslintrc.json) moved into `web/`. Build verified passing from `web/`. `vercel.json` added at repo root so Vercel builds from `web/` without moving `api/`. Committed as "refactor: move web layer files into web/ directory".

---

## Next session priority

1. **Walk experiment (retry)** — Kill Oura app *before* walking. BT off on phone during walk. 20+ min walk. Pull immediately on return before relaunching app. This is the single remaining physical-action blocker for 0x7E/0x7F step decoder validation.

2. **Fresh Gen4 export** — Export Gen4 data from 2026-06-08 onward. Unlocks same-night cross-validation for all June 2026 pulls (current export ends 2026-06-07).

3. **Extract business logic from `web/src/App.js` into `engine/`** — Thresholds (L278-294), scoring, status labels (L640-658), and command strings (L484-525) are flagged violations sitting in the React component. Extract to `engine/thresholds.js`, `engine/scoring.js`, `engine/commands.js`. Update App.js to import from engine/.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
