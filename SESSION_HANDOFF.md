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

**Date:** 2026-07-06

- **Gen4-only comparison row logged for 2026-07-05/06** — deep sleep 20% best night in dataset, recovery bounce confirmed. HRV 22ms — sixth consecutive night below 25ms threshold. Zone 2 command firing correctly.
- **Track B condition #3 still at 1/3** — no Gen3 sleep data from morning shortcut (ring out of BLE range).
- **0x6E IBI layout CONFIRMED from existing sleep corpus** — 549 packets analysed. Layout: b0=channel byte (bit7=optical channel A/B), b1-5=5× IBI high, b6-10=5× IBI low+amp, b11=mid bits, b12=shift nibble. Same bit-pack as 0x60 but 5 pairs instead of 6. Cross-validated vs 0x6A avg_hr: −1.1 to +1.3 bpm delta across 5 sleep files (−0.1 bpm tightest). Walk experiment no longer needed for 0x6E IBI.
- **0x77 prior analysis confirmed** — 384 packets, 14-byte dominant (226). b0 channel bands (mean 58.3 low / 185.4 high, separation ≈128) and i8 time-series structure (lag-1 r=+0.34 to +0.61) both consistent with prior work. Red/IR assignment still ceiling-blocked.
- **Walk experiment still required for 0x7E/0x7F** — zero packets in corpus. Protocol documented in `pipeline/tools/WALK_EXPERIMENT.md`.
- **⚠️ Oura token valid until 2026-07-13 — seven days remaining.**

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — ring must be within Bluetooth range of Mac when shortcut fires.

1. **Execute timed walk experiment** — 500 steps, phone Bluetooth OFF before starting, pull immediately on return. Protocol: `pipeline/tools/WALK_EXPERIMENT.md`. Primary target: 0x7E/0x7F (zero packets — confirmed still needed). Secondary: 0x6E amplitude units, 0x77 band identity, 0x6B motion context.

2. **Morning pull in BLE range** — ring must be near Mac before shortcut fires. Buffer rolls in ~2 min of walking.

3. **Evening pull before sleep tonight**.

4. **Track B condition #3 night 2 needs both Gen3 AND Gen4 data** — ring must be in BLE range at pull time.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
