# METHUSELAH // Gen3 sleep_state Enum Mapping — Findings Log

## Status: HYPOTHESIS — CONFIRMED BY INDEPENDENT GROUND TRUTH (state 0/1 only;
## state 2 still unobserved)

## Background
The Gen3 ring's `0x6a` event (`Sleep period info (2)`) includes a `sleep_state`
field, an 8-bit signed integer bounded to the range [0, 2] per the verified
open_ring decoder (see `decode_sleep_period_info_2`,
open_ring/driver/decoders.py line 774). The semantic meaning of each value
was not documented in the source and had to be inferred empirically.

## Evidence

### Observation 1 — Overnight pulls (June 19-20)
Every `sleep_state` sample captured shortly after waking from overnight
sleep showed **state = 1** (23 samples total across three separate pulls).
Average HR 62.0-68.0 bpm, breathing rate 13.5-16.0 breaths/min — consistent
with restful sleep.

### Observation 2 — Daytime auto-loop test (June 20, 5:21pm-6:14pm)
~53-minute auto-loop run during known-awake activity. All 20 `sleep_state`
samples across four successful pulls showed **state = 0**, zero exceptions.

### Observation 3 — In-window transition (June 21, 9:15am pull)
A single continuous pull captured a transition: six samples at state=1
(boot_ts 39783261-39784772), then two at state=0 (39785067, 39785363).
motion_count rose steadily through the state=1 samples (1,1,2,9,10,11)
immediately before the flip, then dropped after (10,3) — a "stirring before
waking" pattern consistent with a real wake transition.

### Observation 4 — Cross-referenced against Gen4 official wake time [NEW, CONFIRMING]
Gen4's Oura app recorded sleep for the same night as **11:27pm-9:11am**
(8h37min total sleep, 9h45min time in bed). The Gen3 auto-loop pull that
captured the 1→0 transition (Observation 3) was run at **9:15am** — only
4 minutes after Gen4's independently-recorded wake time of 9:11am.

This is a direct, independent timing cross-reference: the state=1→0
transition observed in raw Gen3 data lands almost exactly at the moment
Oura's own official algorithm (running on a separate device, processing
separate raw sensor data, using Oura's proprietary wake-detection logic)
also determined the person woke up. Two independent measurement paths
agree on the wake moment within a few minutes.

Gen4 also recorded average HRV 24ms for the night with values visibly
climbing into the 30s-40s ms range in the final hour before 9:11am wake —
consistent with the general physiological pattern expected around waking,
though this wasn't directly cross-checked against Gen3 HRV due to lack of a
long enough same-window IBI capture.

## Confirmed mapping

| sleep_state value | Meaning | Confidence |
|---|---|---|
| 0 | **Awake** | **High** — confirmed via independent Gen4 wake-time cross-reference (Obs. 4), corroborated by motion_count pattern (Obs. 3) and daytime-only sample (Obs. 2) |
| 1 | **Asleep** (specific stage within sleep not yet distinguished — light/deep/REM all likely collapse to this single value) | **High** — same confirming evidence as above, plus three independent overnight pulls (Obs. 1) |
| 2 | Unknown | None — never observed in any pull to date |

## Remaining open question: state=2
State=1 appears to represent "asleep" as a single undifferentiated value —
it does NOT appear to break out light/deep/REM separately (those come from
other fields/events, e.g. `deep_sleep_duration` in the Oura API, or
potentially from amplitude/CV fields within the same 0x6a payload that
haven't been analyzed yet). It remains unknown whether state=2 represents:
- A specific sleep sub-stage (e.g. REM specifically)
- A different axis entirely (e.g. "drowsy"/transitional, or a data-quality
  flag rather than a behavioral state)
- Something unrelated to sleep/wake at all

### Next steps to resolve
1. Attempt an overnight auto-loop run (8hr/15min interval) to maximize the
   chance of capturing whatever triggers state=2, if it exists as a
   meaningfully common state.
2. If state=2 is never observed even across a full night, consider the
   possibility it's a rare/edge-case value (e.g. signal-quality fallback)
   rather than a regular part of the sleep cycle.
3. Once more 0x6a payloads are captured, examine the `mzci`/`dzci`/`cv`
   fields (currently decoded but not yet analyzed) for correlation with
   state value — these may encode finer-grained stage information
   independent of the 3-value sleep_state enum.

## Caveats
- Confidence is high for the 0=awake/1=asleep binary specifically because
  of the independent cross-reference in Observation 4. This is no longer
  pure inference from internal consistency alone.
- Sample sizes remain modest (single-digit to low-double-digit samples per
  observation window). The mapping should be treated as well-supported but
  not exhaustively validated — continued logging of future nights will
  further strengthen or could still surface exceptions.
- This mapping is specific to the Gen3 unit/firmware tested. Not yet
  verified whether it generalizes to Gen4 (blocked pending the encryption
  issue) or other ring generations.

---
*Updated 2026-06-21 (second update). Original hypothesis logged 2026-06-20;
first transition observed 2026-06-21 morning; confirmed via independent
Gen4 wake-time cross-reference same day.*
