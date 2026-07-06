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

- **Gen4-only comparison row logged for 2026-07-05/06** — deep sleep 20% best night in dataset, recovery bounce confirmed after Zone 2 protocol. HRV 22ms — sixth consecutive night below 25ms threshold, not recovering yet. Zone 2 command still firing correctly.
- **Track B condition #3 still at 1/3** — no Gen3 sleep pull captured this morning. Morning shortcut fired but ring was out of Bluetooth range — checkmark on phone but no data.
- **⚠️ Oura token valid until 2026-07-13 — seven days remaining.**

---

## Next session priority

⚠️ **PULL BEFORE MOVING** — ring must be within Bluetooth range of Mac when shortcut fires.

1. **Decide morning pull approach** — Mac to nightstand vs immediate manual pull at desk vs shortcut with ring near Mac. Buffer rolls in ~2 min of walking; shortcut must fire before movement.

2. **Evening pull before sleep tonight**.

3. **Execute Zone 2 today** — HRV command still firing at 22ms.

4. **Track B condition #3 night 2 needs both Gen3 AND Gen4 data** — ring must be in BLE range at pull time.

---

## Open decisions

1. **Evening pull folder naming convention** — current: time-of-day (`gen3_morning` / `gen3_evening`). Alternative: classifier output (`sleep_window` / `active_window`). Provisional convention in place; revisit once two-pulls-a-day rhythm is established.

2. **Enoch / METHUSELAH data relationship** — Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer. Two separate Vercel deployments with no defined data relationship. Decision needed: permanently separate / future data bridge / unified platform. Parked until Track B and v2 are further along.

3. **Track B completion definition** — no formal definition of "done" exists yet. Needs owner decision before v2 work begins in earnest.

4. **v2 biomarker parser prototype** — blocked on LifeLabs PDF export. No parser built yet. First unblocked once a LifeLabs PDF is available.
