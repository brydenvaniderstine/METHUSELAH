# METHUSELAH // Gen3 sleep_state Enum Mapping — Findings Log

## Status: CONFIRMED (state 0=awake, 1=asleep) WITH AN IMPORTANT TIMING
## CAVEAT (see "Buffer timing is not a reliable proxy" below).
## State 2 still unobserved.

## Background
The Gen3 ring's `0x6a` event (`Sleep period info (2)`) includes a `sleep_state`
field, an 8-bit signed integer bounded to [0, 2] per the verified open_ring
decoder (`decode_sleep_period_info_2`, open_ring/driver/decoders.py line
774). Semantic meaning was not documented in source; inferred empirically.

## Evidence

### Observation 1 — Overnight pulls (June 19-20)
23 samples across three pulls, all state=1, during/after overnight sleep.
HR 62.0-68.0 bpm, breathing 13.5-16.0 br/min — consistent with sleep.

### Observation 2 — Daytime auto-loop (June 20, 5:21pm-6:14pm)
20 samples across four pulls, all state=0, during known-awake activity.

### Observation 3 — First in-window transition (June 21, 9:15am pull)
Six state=1 samples followed by two state=0 samples, with motion_count
rising before the flip (1,1,2,9,10,11 → 10,3) then settling after — a
"stirring before waking" pattern.

### Observation 4 — Cross-referenced against Gen4 wake time (June 21)
Gen4 recorded sleep ending at 9:11am. The Observation 3 transition (pull run
at 9:15am) landed within 4 minutes of that independently-recorded wake time.

### Observation 5 — Second in-window transition, opposite direction (June 22, 5:31am pull)
Nine samples: three at state=0 (boot_ts 40541373-40541971), then six at
state=1 (40542255-40543765). HR nearly flat throughout (64.0-65.5 bpm),
motion=0 for all nine samples — a much quieter transition than Observation 3.

This pull was run at 5:31am, 11 minutes after Bryden's actual wake time of
5:20am (confirmed via Gen4). Naively this looked like a contradiction: if
state=0→1 means "falling asleep," why would that appear right after waking,
not right before?

### Observation 6 — Resolution via Gen4 hypnogram (June 22)
Gen4's official hypnogram for the same night (9:47pm-5:20am, 6h39min asleep)
shows three distinct "Awake" segments: one at sleep onset (~9:47pm-9:48pm,
expected latency), and two closely-spaced brief awake blips clustered around
roughly 1am-2am — consistent with Bryden's own account of waking briefly to
use the bathroom, then falling back asleep shortly after.

This resolves Observation 5 cleanly: the Gen3 pull's small rolling buffer
almost certainly was NOT capturing data from the 5:20am final wake at all.
It was likely still holding events from the ~1am-2am bathroom-wake episode
(awake briefly, then back asleep) — a real state=0→1 transition, just not
the one a naive "pull ran shortly after waking" assumption would predict.

## Confirmed mapping

| sleep_state value | Meaning | Confidence |
|---|---|---|
| 0 | **Awake** | High — confirmed across 5 separate observations, both directions of transition, and one direct Gen4 cross-reference |
| 1 | **Asleep** (single value; does not break out light/deep/REM separately) | High — same supporting evidence |
| 2 | Unknown | None — never observed in any pull to date |

## IMPORTANT: Buffer timing is not a reliable proxy for "this pull reflects
## right now"
Observation 5/6 revealed a real limitation in how we've been interpreting
pulls: **running a pull shortly after a known event (e.g., waking up) does
NOT guarantee the captured buffer window reflects that specific event.**
The ring's small rolling buffer holds whatever recent events haven't yet
been evicted, which may be from an earlier point in the night (a middle-of-
the-night wake, a stage change hours ago) rather than the most recent or
most behaviorally significant moment.

**Practical implications:**
- Do not assume a pull's sleep_state transition corresponds to "what just
  happened" without independently verifying via boot_ts continuity or a
  cross-referenced wall-clock anchor.
- This is exactly the kind of gap that mature, continuously-logging systems
  (like Gen4 + the Oura app) don't have, because they aren't working from a
  small rolling buffer sampled intermittently. This is a current limitation
  of our system (Gen3 + manual/scripted terminal pulls), not a flaw in the
  ring's sensors or in Oura's broader approach. Same hardware lineage,
  different level of pipeline maturity — see "Gen3 vs Gen4 framing" note
  below.
- The auto-loop tool (15-30 min interval) is the right mitigation: more
  frequent pulls reduce the chance of missing or misattributing events, by
  shrinking the gap between consecutive captured windows.

## Gen3 vs Gen4 framing (for future reference, not just this finding)
Per Bryden's framing (June 22): Gen3 and Gen4 are "essentially the same
ring doing the same task," and discrepancies between our raw decode and
Oura's official numbers should generally be attributed to **system
maturity** (Oura's years-refined algorithms and continuous background
logging vs. our few-days-old prototype working from small buffer snapshots)
rather than to any inherent inferiority of the ring hardware itself or a
flaw in our decode logic. Keep this lens when evaluating future
discrepancies before concluding the decoder is wrong.

## Resolved side-issue: apparent stale Gen4 data (June 21 evening)
Bryden observed the Oura app still showing June 20's sleep data
(11:27pm-9:11am) when checked again the evening of June 21, despite it
being a new day. Initially flagged as a possible "Oura only updates once
per wake cycle" structural issue. Confirmed resolved by the next morning
(June 22): app correctly showed the new night (9:47pm-5:20am) once checked
fresh. Most likely cause: a temporary ring-to-phone sync delay, not a
systemic Oura limitation. Bryden's hypothesis that Oura's headline numbers
refresh primarily around the wake event (rather than continuously through
the day) remains a reasonable, separate question worth testing via a
pre-bed daytime screenshot check - not yet confirmed either way.

## Remaining open question: state=2
Still never observed. Next steps unchanged from prior version:
1. Attempt an overnight auto-loop run (8hr/15min) to maximize odds of
   catching it, if it occurs at all during normal sleep.
2. Examine unused decoded fields (`mzci`, `dzci`, `cv`) for correlation
   with state, in case they encode additional resolution.
3. Consider it may be a rare/edge-case value not part of routine cycling.

## Caveats
- Confidence in the core 0/1 mapping is high, but the *timing* of any given
  observed transition should be treated as approximate, not precise, per
  the buffer-timing caveat above.
- Mapping confirmed specific to this Gen3 unit/firmware. Not yet verified
  on Gen4 (blocked pending the encryption issue).

---
*Updated 2026-06-22 (third update). History: hypothesis logged 2026-06-20;
first transition + Gen4 cross-reference 2026-06-21; second transition
investigated and buffer-timing caveat added 2026-06-22.*
