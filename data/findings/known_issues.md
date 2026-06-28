# METHUSELAH // Known Issues — Gen3 Decoders

## Gen3 ring flash buffer: 255-event circular FIFO — sleep data loss root cause (2026-06-28)

**Status:** Root cause confirmed. Hardware constraint. No software fix.

### 1. The constraint

The ring maintains a **255-event circular flash buffer**. Every event fired by the
firmware is written into this buffer; when full, the oldest entry is overwritten.
When you connect and request history (`10 09 00000000 ff ff ff ff ff`), you receive
the current contents of this buffer — at most 255 real events, no matter what
start timestamp you request.

Evidence:
- All 27 saved pull files return exactly **255 real events** (plus one `UNKNOWN (0x11)`
  frame = the ring's `_HISTORY_FETCH_RESP` response summary — not a real event).
- This is consistent across pulls taken 37 seconds apart AND pulls taken 9+ hours apart.
  If the buffer were larger and we were cap-limited, short-interval pulls would return
  fewer than 255 events. They don't — 255 every time.
- `max_events=0xFF=255` in our BLE request (`10 09` opcode) exactly matches the buffer
  size — intentional firmware design. open_ring's `_catchup()` docstring explicitly
  calls this a "circular buffer."

### 2. Event rates and data loss window

Event rates measured from real pull data (255 events per pull):

| Context | s/event | Buffer time window |
|---------|---------|-------------------|
| SLEEP (SpO2, IBI, HRV, temp, debug) | ~10 s/event | ~42 min |
| ACTIVE WAKE (step features, motion, temp, debug) | ~22–37 s/event | ~1.5–2.6 h |

During sleep the ring generates events rapidly (high sensor duty cycle), so the buffer
covers only ~42 minutes of sleep data at any moment. As soon as activity starts after
waking, wake events (at a slower per-event rate) progressively overwrite sleep events.
After **~2.6 hours of active walking**, all 255 buffer slots contain post-wake events
and all sleep data is permanently lost.

Confirmed data loss case (2026-06-28 morning pull, gen3_pull_20260628_074844.txt):
- 255 real events, all activity: Motion events, Real step features, Debug data, PPG amplitude
- boot_ts span: 51,038,541 → 51,047,881 = 9,340 seconds = 2.6 hours post-wake
- Zero sleep tags (0x6A, 0x5D, 0x6F, 0x75)
- Same pattern confirmed across prior data-loss incidents (missed nap, 6 AM bathroom break)

### 3. Script request is NOT the problem

The script correctly sends `10 09 00000000 ff ff ff ff ff`:
- ts = 0x00000000 (from the very beginning)
- max_events = 0xFF = 255 (the ring's own limit)
- flags = 0xFFFFFFFF (all event types)

This retrieves the **full contents of the ring's buffer**. There is no request-side
parameter that can reach further back — the data is already gone, overwritten in flash.

### 4. Fix

**The only fix is to pull sooner.** Specifically:

- Pull **within 1 hour of waking** to guarantee sleep data is still in the buffer.
  At ~37 s/event during activity, 1 hour = ~97 events overwritten, 158 sleep events
  still present. At ~10 s/event during sleep, the most recent ~25 minutes of sleep
  are in the final 158 slots — sufficient for classifier tags.
- **Hard upper limit: ~1.5–2.5 hours** post-wake before all sleep data is gone,
  depending on activity intensity. Intense activity (faster event rate) shortens this.
- Morning bathroom breaks or brief movement before pulling are fine if total active
  time is under an hour.

**Alternative mitigation (not yet implemented):** A lightweight background pull
scheduled 30 minutes after the alarm fires (before significant movement accumulates)
would guarantee capture on days when the normal pull runs late.

### 5. The 0x11 parsing artifact

Every pull file ends with `UNKNOWN (0x11)` at an anomalously high boot_ts value.
This is the ring's `_HISTORY_FETCH_RESP` response frame (`11 08 FF 00 <last_ring_ts:4LE>`),
which the script receives and saves as if it were a real event. Its "boot_ts" is
actually the ring's last_ring_timestamp from the delivery summary. It doesn't affect
data content but inflates the `newest_ts` calculation in per-file analysis. Harmless
artifact — just exclude `UNKNOWN (0x11)` from span calculations.

*Logged 2026-06-28. Based on analysis of all 27 pull files in data/raw_pulls/gen3_morning/.*

---

## SpO2 event decoder (0x6f) — FIX INCONSISTENT ACROSS NIGHTS, NOT FULLY SOLVED

**Status:** Fixed 2026-06-24. Flat offset of -6 applied to raw sample bytes.

**Root cause:** Raw payload bytes were `true_percent + 6`, not raw percent.
header_high/header_low (p[0] nibbles) were tested for correlation with the
needed correction and showed none — ruled out as a scale/calibration factor,
likely a sequence or quality byte instead.

**Evidence:**
- 190 real packets / 2,476 samples, retrieved via `grep -r "SPO2 event"`
  across 14 saved pull files (2026-06-19 to 2026-06-23) and pasted for
  analysis — offset=6 is the minimum correction eliminating all >100%
  violations (offset=5 leaves 5 violations; offset=7+ starts going low).
- Cross-checked against 2026-06-24 morning pull (21 fresh packets, not
  part of the original 190): same offset, zero violations, corrected
  range 91-99%, consistent with expected overnight SpO2 behavior.

**Still open:** Same-night Gen4/Oura SpO2 comparison is NOT available through
the Oura app UI — only a rolling multi-day average is shown (96.3% as of
2026-06-24), with no per-night breakdown on the sleep detail screen (confirmed
2026-06-24; the screen that shows per-night HR/HRV does not show per-night
SpO2). True ground-truth cross-validation may not be possible via this method
— the HRV/avg_bpm validation approach that worked has no SpO2 equivalent in
the app.

One data point for reference: Gen3 corrected (offset=6) avg for the 2026-06-24
partial-night pull = 93.41% (range 90-99%, 21 packets/273 samples) vs. Gen4
multi-day average = 96.3%. Gap of ~2.9 points, but NOT a valid same-window
comparison — Gen3 sample is a ~35min slice near wake time, not full-night;
Gen4 figure is multi-night, not single-night. Inconclusive either way, not
evidence for or against the fix.

Possible alternate validation paths, not yet attempted: Oura's raw data
export (if available via account settings), Oura's public API (if it exposes
per-night SpO2, separate from the cloud REST API already used for Gen4
vectors). Until/unless one of those pans out, treat as fixed-by-internal-
consistency only (zero >100% violations across 211 real packets / 2,749
samples total across all pulls analyzed to date) — this is the practical bar
for now, not a placeholder for an incoming confirmation.

---
*Logged 2026-06-23. Found during first live test of the SpO2 decoder
immediately after wiring it into the pull script. Fixed 2026-06-24.*

## SpO2 (0x6f) offset=6 fix — FAILED cross-validation on 2026-06-25 night

First real same-night Gen4 comparison (bedtime 9:49pm-5:20am, 2026-06-25):
Gen4 reports avg SpO2 97%, "time at or below 88%: none recorded." Gen3
corrected (offset=6) average for the same night = 88.0% (range 84.5-93.0,
17 packets) — sitting exactly at the floor Gen4 says never happened.

This is a real failure, not noise: offset=6 was derived from 211 packets
across two prior nights and held up internally (zero >100% violations), but
this third night's raw bytes came in lower to begin with (pre-correction
avg 94.0% vs ~100-104% in earlier pulls), so the same flat offset overshoots
and pushes Gen3 well below Gen4 ground truth.

**Status: NOT solved.** offset=6 is not a universal constant — do not treat
this fix as final or closed. Real per-night variance in raw byte baseline
remains unexplained.

---
*Logged 2026-06-25.*

## Tier 1 NOT STARTED tags (0x53, 0x69, 0x6B, 0x7E/0x7F) — zero packets across 2 pulls

**Status:** Real spec pulled for 0x53 (wear_event = alias for
decode_state_change_ind, `<state:u8><text:ascii>`, STATE_CHANGE enum
confirmed from enums.py — state 1 = STATE_NOT_IN_FINGER, exactly "ring off
wrist"). Decoder written but NOT yet wired into the script — zero real
packets captured to test against.

All five tags added to PRIORITY_TAGS 2026-06-25. Two pulls since (7:14pm,
7:25pm) — neither captured a single packet for any of these five tags.
Likely conclusion: these are rare/event-driven (wear on/off transitions,
step counts) rather than steady background telemetry like SpO2/IBI, so
short pulls during steady sleep/rest won't naturally trigger them.

**Next steps:** Either wait for a pull that spans a real wear-state change
(taking the ring off, putting it back on) or activity period (for
0x7E/0x7F steps), or consider whether the pull script's request window
needs adjustment to reach further back in the ring's buffer where these
events might already be sitting unflushed.

---
*Logged 2026-06-25.*

## Debug data sleep statistics decoder (0x61/0x09) — BROKEN, NEVER VALIDATED

**2026-06-25 update:** Tested 32768Hz tick-rate divisor against 4 fresh
records (2 pairs, two different nights) — `deep` field lands in a plausible
1-10.6min range but `sleep`/`awake` stay near-zero, same misalignment as
before. Brute-force u16 scan across all offsets found no clean 3-field
layout. Tested cumulative-delta hypothesis (deep/sleep/awake as since-boot
counters, checked deltas between same-pair records 5 seconds apart): deltas
are roughly the right order of magnitude (~5s) but inconsistent in sign and
not a clean match — partial lead, not resolved.

**2026-06-25 update, u16 width test:** Tried u16 fields at offsets 1,3,5,7,9,11.
Offset 3 is small and consistent within same-night pairs (5.32/5.27 min vs
0.48/0.50 min) — solid, reproducible signal, worth keeping as a real lead.
Tried extending to a 3-field sum (offset3+5+9 as total sleep duration) —
this did NOT hold up; sums vary 3x within the same ~5s window, ruled out.
Offset 3 alone remains a live thread; the rest of the byte layout is still
unresolved.

**2026-06-25 update, third pull (7:14pm, post-nap):** Tested offset3 on 3
more pairs/records (5 total records, 2 clean pairs + 1 singleton). Result:
4-for-4 consistency holds across every same-pair comparison tested so far
(0.50/0.50min, 1.82/1.80min, plus the original 5.32/5.27 and 0.48/0.50).
This is now a SOLID, REPRODUCIBLE FACT: offset3 is internally consistent
within same-pair records, confirmed across 3 separate pulls/sessions.

**2026-06-25 update, full corpus analysis (55 unique records across all pulls):**

pfsm=128 is a near-exact mirror of the preceding non-128 record (diff
always -4 to +2, mean -0.16) — dual-buffer write, not a distinct
measurement. All 27 pfsm=128 records can be treated as echoes.

pfsm_state strongly predicts offset-3 magnitude:
  pfsm=6 (n=7):  mean 196.7, range 77-429  ← consistently largest
  pfsm=3 (n=6):  mean 62.7,  range 33-148
  pfsm=5 (n=12): mean 38.0,  range 15-101  ← consistently smallest
  pfsm=1 (n=1):  0   pfsm=2 (n=1): 4  pfsm=4 (n=1): 40

Within-pull pattern across every pull with 2+ non-128 records:
pfsm=6 always pairs with the large o3 value, pfsm=5 always pairs with
the small o3 value. Three morning pulls in sequence:
  (319,pfsm6)/(29,pfsm5), (170,pfsm6)/(32,pfsm5), (102,pfsm6)/(30,pfsm5)
pfsm=6 holds ~10× more o3 than pfsm=5 in every case.

Tested and FALSIFIED (2026-06-25): offset-3 accumulates based on time
since the previous 0x09 record. Pearson r = -0.094 between consecutive-
record delta_ts and delta_o3 (same-pull pairs only, n=43). Ruled out.

**CONFIRMED (2026-06-26): offset-3 u16 = seconds spent in current pfsm state.**

Evidence:
1. Direct measurement: pull 20260624_203119 has one visible 0x6A state
   transition (→state=1) at ts=42359632. pfsm=6 record fires at
   ts=42359801. Elapsed = 169 ticks, o3 = 170. Ratio = 1.006 — near-
   exact 1:1. At 1 tick/sec this is 169s ≈ 170s.
2. Tick-rate corroboration: 0x6A fires every ~303-306 ticks; known
   behavior is ~5-min period → 305 ticks = 5.08 min at 1 tick/sec.
   Consistent.
3. Activity-pull contrast: 20260626 waking/activity pull gives pfsm=6
   o3=5 (5s) and o3=65 (65s) — brief transient pfsm=6 episodes during
   rapid state cycling while waking. Sleep pulls give pfsm=6 o3=77–429
   (1.3–7.2 min) — sustained episodes during stable deep sleep.
4. Open_ring corroboration: 0x61/0x0c (_dd_period_info_statistics) has
   a parallel field named `systime_spent_in_last_state_raw` with the
   same `pfsm_state` byte. Its unit is raw_u32/10.0 for seconds (higher
   resolution). Our 0x09 offset-3 field uses whole seconds (÷1, not ÷10)
   — same concept, coarser resolution.

Tested and FALSIFIED (also 2026-06-26): "elapsed since last 0x6A record"
as a proxy. r=-0.434 (all pfsm) / r=-0.473 (pfsm=6 only). Negative
because 0x6A fires continuously every ~5 min — elapsed since last packet
is random position within a 5-min interval, not time-in-state.

**pfsm_state enum: NOT in open_ring.** Searched decoders.py, enums.py,
state.py, PROTOCOL.md, README.md — pfsm_state is emitted raw (u8) with
no symbolic names anywhere in the repo. Values seen in real data:
  1, 2, 3, 4, 5, 6, 128
State meanings are unknown from source; must be inferred empirically.
Observed pattern: pfsm=6 → longest durations (deep sleep candidate),
pfsm=5 → short resets (~30s), pfsm=3 → intermediate, pfsm=128 → echo.

**What offset-3 gives us:** seconds the ring's internal sleep state
machine has been in its current state at the moment the 0x09 record
fires. This is real physiological data — duration in the current
firmware sleep classification, not a tick counter or arbitrary offset.

**Status:** Broken since first wired in. NOT a regression — checked
ring_decoder_inventory.md (2026-06-24): the doc only ever flagged 0x09 as a
promising target to build, never claimed it was tested against real data.
No known-good baseline ever existed. Do not use sleep stats output until
fixed.

**Symptom:** `decode_debug_data_sleep_statistics()` produced physically
impossible values on the 2026-06-24 morning pull:
- `deep=111924.3min` (~77.7 days) and `deep=111344.9min` in the same
  session, four records total, all wildly out of range
- `pfsm_state=128` appearing twice, vs. small single-digit values
  (5, 6) seen previously — may indicate two different packet sub-formats
  being routed through the same decoder

**Likely cause:** Unconfirmed. Possible struct misalignment, or these
0x61/0x09 packets have a different internal layout than the ones the
decoder was originally validated against. Needs investigation before
trusting deep-sleep-duration output again.

**Next steps:**
1. Pull raw hex for these specific records (boot_ts=42166360, 42166365,
   42166971, 42166976) and inspect byte-by-byte against the documented
   layout (ticks_in_deep_sleep, ticks_in_sleep, ticks_awake, pfsm_state).
2. Check whether pfsm_state=128 packets are a distinct variant from
   pfsm_state=5/6 packets — may need a sub-format branch.
3. Do not log any sleep-stats rows to any comparisons CSV until resolved.

---
*Logged 2026-06-24. Found during 2026-06-24 morning pull, same session as
the SpO2 fix.*

## SPO2 IBI+amplitude decoder (0x6e) — NOT YET DECODED, structural findings only

**Status:** Open investigation, started 2026-06-24. No working decoder exists.
open_ring's own `decode_spo2_ibi_and_amplitude_event()` is a raw passthrough
(`{"u8_values": list(p)}`) — confirmed directly from source, not assumed from
docs. Its docstring explicitly says "Conservative decode: emit raw bytes for
downstream analysis," meaning open_ring's own authors did not crack this
field layout either. This is real reverse-engineering from scratch, not a
known decoder to port.

**Confirmed structural facts** (from 85 real packets, 2026-06-24 morning pull,
transcribed directly from PRIORITY EVENTS output, all verified 13 bytes):

- **Byte 0**: highly variable (range 0-186, 34 unique values across 85
  packets), alternates in a clear pattern between high-nibble values (8-11)
  and low-nibble-dominant values (1-3) on roughly every other packet.
  Sequence: 10,2,9,2,9,1,9,1,9,1,9,1,9,1,11,4,8,0,8,1,8,1,9,1,9,1,8,1,8,1,8,1,
  8,0,8,1,9,1,9,1,9,1,11,3,11,2,8,1,8,1,8,1,10,2,9,1,9,1,9,1,8,1,9,1,8,1,9,1,
  9,1,9,1,9,1,9,1,9,1,9,1,9,1,9,1 (high_nibble values shown).
- **Bytes 1-6**: consistently low-variance across ALL 85 packets (mean
  ~125-130, stdev 8-25). Likely a slow-moving/stable signal — candidate:
  DC baseline or similar.
- **Bytes 7-12**: consistently high-variance across ALL 85 packets (range
  hits 0 and 250+ regularly, stdev ~48-52). Likely a genuinely noisy
  signal (e.g. raw AC component or per-sample amplitude) rather than a
  decode artifact — see falsified hypothesis below.

**Falsified hypothesis:** Byte-0's alternating high/low-nibble pattern was
tested as a possible red/IR channel split (consistent with real pulse-
oximetry hardware using two LED wavelengths, and consistent with open_ring's
own `0x77` docstring naming a `channel_index` concept). Split the 85 packets
into two sub-sequences by high_nibble>=8 vs <8, then checked whether bytes
7-12 (the noisy band) became smooth within either sub-sequence. **It did
not** — both sub-sequences remained equally noisy in bytes 7-12. This
specific channel-split theory is ruled out; byte 0 alternation remains
unexplained.

**Falsified hypothesis #2:** Byte 0 as a raw incrementing/decrementing
counter. Checked consecutive-packet deltas across all 85 packets — deltas
alternate between roughly -110/-140 and +100/+160, never a steady increment.
Ruled out.

**Bytes 1-6 vs 0x6F SpO2 correlation (2026-06-25, n=94 0x6E packets,
17 0x6F packets in same window):**
Pearson r at all 6 positions: -0.17 to +0.09 (u8 and i8 both tested).
No statistically meaningful correlation. However, the raw u8 values are
the more important finding: bytes 1-6 are almost entirely in the 93-108
range (with ~5 outlier packets), which under the same offset-6 encoding
as 0x6F gives 87-102% — squarely in the SpO2 range. Near-zero r is
expected when both signals barely vary (sleep session, SpO2 only 90-99%,
stdev 2.78%) and pairing noise dominates the ~8-point physiological range.

Internal correlation matrix (bytes 1-6 u8):
- b1/b2: r=0.626 at lag=0 only (drops to noise at all other lags)
- b2/b3: r=0.493 at lag=0, also elevated at lag=-2 and lag=-1 (~0.4)
- b4, b5, b6: mutually independent (r < 0.12 between any pair)
This is consistent with b1-b3 being consecutive SpO2 samples from the
same measurement window (adjacent slow-signal samples correlate), and
b4-b6 being a different measurement type (IBI or amplitude per the tag
name "SPO2 IBI+amplitude").

Outliers (b1=58 at ts=43015768/769, b5=50 at ts=43015856, b6=131/135
at ts=43015725/726 and 43015863) — ~5 packets, likely motion artifact
or encoding edge cases, same pattern seen in prior 0x6E analysis.

**Working hypothesis (not yet confirmed):** bytes 1-3 = 3 SpO2 percent
samples (raw, offset-6 encoding same as 0x6F); bytes 4-6 = 3 IBI or
amplitude samples (different encoding, values in same u8 range but
mutually independent). Needs a higher-variance session to confirm or
falsify via correlation.

**Next steps:**
- Structural ceiling same as 0x77: sleep-session pulls don't provide
  enough physiological variance to confirm the SpO2-sample hypothesis
  via correlation. Richer pull (daytime activity, wider SpO2 range)
  is the right next step for both 0x6E and 0x77.
- Bytes 7-12 remain the noisy band — likely AC component or raw
  amplitude, not investigated further this session.

---
*Logged 2026-06-24. No decoder shipped — findings only, to save re-deriving
this structure next session.*

## SPO2 DC event (0x77) — REAL DATA CAPTURED, structural findings only

**Status:** Open investigation, started 2026-06-25. No working decoder yet.
51 real packets pulled from the 2026-06-25 night pull (PRIORITY_TAGS fix
worked).

**Confirmed structural facts:**
- Variable length confirmed: 43 packets at 14 bytes (dominant case), 6 at
  4 bytes, 1 at 13 bytes, 1 at 2 bytes — matches open_ring's "variable size"
  docstring claim.
- 14-byte packets (n=43): per-position stats show NO calm/stable band —
  every byte position 0-13 has high variance (stdev ~68-108), unlike 0x6e
  which had a clear stable band at bytes 1-6. Byte 0 is somewhat tighter
  (stdev 68 vs ~100-108 elsewhere) but still highly variable, not a fixed
  header.

**Short packet analysis (2026-06-25, from boot_ts sequence):**
Short packets cluster at two spots in the boot_ts stream, both interrupting
otherwise clean 14-byte pair sequences:
- Cluster 1 (boot_ts 43016183-43016185): 13-byte + two "clean" 4-byte packets
  (`40a23301`, `c3b0ee00`). The 13-byte has byte-0=0xb2 (in 14-byte range,
  178) — looks like a truncated 14-byte record missing its last byte. The two
  4-byte packets end in `01`/`00`; no fill pattern; format unclear at n=2.
- Cluster 2 (boot_ts 43017475-43017505): 2-byte (`0610`) followed by three
  4-byte packets, two of which contain `0xAA 0xAA` in the middle bytes
  (`caaaaab2`, `48aaaab2`). 0xAA is a standard uninitialized-memory fill
  byte — these are confirmed buffer corruption artifacts, not valid records.
  The 2-byte `0610` (byte-0=6, outside 14-byte range) is a framing error.

**Conclusion:** Short packets are NOT truncated 14-byte records. Prefix
comparison against same-band 14-byte packets shows 0-2 byte matches out
of 13 (13-byte case) and 0/4 for both clean 4-byte packets — bytes
diverge immediately from position 1. These are a genuinely different
sub-format emitted transiently under the same 0x77 tag, possibly summary
or boundary-marker records. The 0xAA-fill cluster-2 packets remain
confirmed buffer corruption. All non-14-byte packets should be excluded
from structural analysis; n is too small (1 and 2) to decode the clean
short variants, but they are not the same format as the 14-byte packets.

**Next steps, not yet attempted:**
1. ~~Test byte 0 as channel_index per open_ring's own docstring hypothesis~~
   FALSIFIED 2026-06-25: byte 0 ranges 16-222 across 43 packets, alternating
   between a low band (~16-63) and high band (~146-222) — far too wide a
   range to be a simple channel_index (would expect 0/1 or small int).
   Ruled out as stated; could still be some other field, not investigated
   further today.
2. ~~Investigate why short packets (2, 4, 13 bytes) exist~~ — RESOLVED
   2026-06-25: truncation + buffer corruption artifacts, not a real format.
**Byte-0 alternation (2026-06-25, 43 14-byte packets):**
Byte-0 alternates between two well-separated bands in boot_ts order:
- Low band: 16-107, mean 49.2, n=22
- High band: 146-222, mean 175.1, n=21
- Gap 108-145 — no values observed there
- Pattern is nearly perfect L/H/L/H alternation with only 3 breaks
  (at ts 43015675, 43015776, 43016260 — early in sequence, then locks
  into perfect alternation for the final ~30 packets)
- This is almost certainly two interleaved channels (red/IR photodiode,
  consistent with standard pulse-ox hardware design)

Note: this is a DISTINCT finding from 0x6E's falsified channel-split
hypothesis. For 0x6E, we split by high-nibble of byte-0 and checked
whether the noisy band (bytes 7-12) became smooth within either
sub-sequence — it did not. Here for 0x77, we confirmed the alternation
pattern itself exists. The next question (whether splitting on byte-0
reveals structure in bytes 1-13) has NOT been tested yet.

Per-position stats after splitting on byte-0 band: bytes 1-13 show
near-identical means and stdevs in both sub-groups (largest diff ~44-46
at positions 8 and 13, but stdev ~100+ in both halves). No byte quiets
down inside either sub-group — the remaining 13 bytes stay chaotic
regardless of which channel you're in.

**Break-point analysis (2026-06-25):**
All 3 breaks in the L/H alternation pattern are explained:
- Break 1 (ts=43015675, apparent H→H): a 0x6E packet at ts=43015676
  sits between the two 0x77 packets — the alternation is correct in the
  ring's full output stream; the break is an artifact of viewing 0x77
  in isolation. Not a real break.
- Breaks 2 and 3 (ts=43015776 L→L, ts=43016260 L→L): genuine
  same-channel consecutive pairs with no intervening packet to blame.
  Consistent with occasional same-channel dropout (one channel packet
  lost, its pair emitted twice, or ring briefly emits two same-channel
  records). No correlation with short-packet clusters (those are at
  ts=43016183 and ts=43017475, well away from all 3 breaks).

**Conclusion:** Byte-0 alternation is confirmed real channel structure.
Breaks are plausible dropout, not a separate phenomenon.

**Signed (i8) reinterpretation (2026-06-25, 43 14-byte packets):**
Reinterpreting bytes 1-13 as i8 (signed) instead of u8 collapses stdev
dramatically at every position:
- Pos 1:  u8 stdev 102.7 → i8 stdev  41.5  (Δ61.2)
- Pos 2:  u8 stdev 106.0 → i8 stdev  34.5  (Δ71.5)
- Pos 3:  u8 stdev 107.2 → i8 stdev  25.6  (Δ81.6) ← tightest
- Pos 4:  u8 stdev 101.7 → i8 stdev  45.9  (Δ55.8)
- Pos 5:  u8 stdev 102.4 → i8 stdev  38.8  (Δ63.6)
- Pos 6:  u8 stdev  99.6 → i8 stdev  45.2  (Δ54.4)
- Pos 7:  u8 stdev 106.0 → i8 stdev  30.0  (Δ76.1)
- Pos 8:  u8 stdev 107.6 → i8 stdev  32.9  (Δ74.8)
- Pos 9:  u8 stdev 105.9 → i8 stdev  36.4  (Δ69.5)
- Pos 10: u8 stdev 107.5 → i8 stdev  31.5  (Δ76.0)
- Pos 11: u8 stdev 106.4 → i8 stdev  34.8  (Δ71.5)
- Pos 12: u8 stdev 103.9 → i8 stdev  45.8  (Δ58.2)
- Pos 13: u8 stdev 108.5 → i8 stdev  33.7  (Δ74.8)
All i8 means land within ±10 of zero (range: -2.8 to +10.0).
Byte 0 is unaffected (u8 stdev 68.1 → i8 stdev 70.0) — confirms it is
a separate channel-indicator field, not the same signed-delta encoding.

**Conclusion:** The u8 interpretation was folding signed values across
the 128/0 boundary and creating artificial full-range noise. Bytes 1-13
are signed fields centered near zero — consistent with PPG DC offset
deltas or differential measurements, not absolute readings.

**Next steps:**
1. ~~Finish short-packet prefix check~~ DONE 2026-06-25.
2. ~~Test signed (i8) interpretation~~ DONE 2026-06-25: confirmed,
   stdev collapses 55-82 points at every position 1-13.
3. ~~Split Low-b0 vs High-b0 in i8 space~~ DONE 2026-06-25: NULL RESULT.
   No position shows a consistent signed offset between the two channels
   (diffs +/-2 to -22, none exceeding one pooled stdev, no consistent
   direction). Rules out red/IR DC-level-difference as the distinction
   between byte-0 bands. Both channels carry the same kind of signed
   data in the same range. Red/IR interleaving may still be present but
   the channels are not distinguishable by mean level in i8 space.
4. ~~Check pos-3 i8 vs same-window 0x6F / 0x47~~ DONE 2026-06-25:
   NULL RESULT. Pearson r = -0.126 vs SpO2 (n=43, no correlation).
   Motion: only 1 packet in the entire window (sleep session, ring
   essentially still) — no usable motion signal to correlate against.
   Data-availability constraint: this pull is a sleep session with
   SpO2 varying only ~90-99% and near-zero motion. Signed values in
   bytes 1-13 are real structure, but no known-good signal in this
   window tracks them.
5. ~~i16 pairing test~~ DONE 2026-06-25: NULL RESULT. All i16 pairings
   (LE natural, LE offset-by-1, BE natural) produce stdev 6,000-12,000 —
   ~256× wider than the i8 values, exactly what uncorrelated byte pairs
   produce. Bytes 1-13 are 13 independent i8 fields, not paired i16s.

6. ~~open_ring source check~~ DONE 2026-06-25: no additional field layout
   beyond what was already known. decode_spo2_dc_event() docstring says
   `channel_index, beat_index, timestamp, dc[]` but the body is a raw
   passthrough — this is a hypothesis open_ring's own authors never
   implemented. No other decoder in decoders.py touches 0x77 layout.
   The dc_value field at line 1011 is in 0x61/0x35 (PPG signal quality
   stats), not related to 0x77.

**Structural ceiling reached (2026-06-25).** Confirmed packet layout:
  [channel:u8][13× independent i8 fields]
What the 13 signed fields represent is not answerable from variance and
correlation alone on the available data. Evening pulls (19:14, 19:26)
checked — SpO2 variance still narrow (1.2-1.7% stdev), motion still
1-2 packets per pull, no better than the sleep session pull.

Two paths forward, not yet committed to either:
(a) Capture a pull during genuine activity (walking, exercise) where
    SpO2, motion, and PPG signals vary more — better correlation surface
    for the 13 signed fields.
(b) Accept 0x77 as structurally characterized but not decoded for now,
    and move on to other tags with more traction (0x6E bytes-1-6 vs 0x6F
    correlation, or 0x61/0x09 u16 thread).

---
*Logged 2026-06-25.*

**Status:** Blocked on data availability, as of 2026-06-24.

**Finding:** `0x77` was never in `PRIORITY_TAGS` in `oura_gen3_morning_pull.py`,
so despite 54 SPO2 DC event packets appearing in this morning's pull (per the
Event type breakdown), zero individual packets had their raw hex printed —
only the aggregate count. open_ring's own decoder for this tag
(`decode_spo2_dc_event`) only extracts byte 0 (`channel_index`); the rest is
dumped as `trailing_hex`, with a docstring hypothesis (`channel_index,
beat_index, timestamp, dc[]`) that was never actually implemented/verified
by open_ring's own authors either.

**Fix applied:** `0x77` added to `PRIORITY_TAGS` in `oura_gen3_morning_pull.py`
on 2026-06-24, so the next regular pull will print real hex for this tag.
No decode function added yet — need real data first.

---
*Logged 2026-06-24.*

## Real step features (0x7E / 0x7F) — initial characterization (2026-06-26)

**Status:** First real packets captured (20260626 activity pull, 10 pairs).
No working decoder yet. Initial structural analysis complete.

**Source:** open_ring `decode_real_steps_features()` — raw passthrough
(14× u8), docstring says "FFTset sub-messages (first/second/third FFT),
signal-processing meaning not yet documented." Both tags share the same
decoder. Treated as a hint, not a structural assumption.

**Confirmed structural facts (10 pairs, 20260626 pull):**
- Both tags: fixed 14 bytes, always appear as consecutive pairs
  (0x7E at ts N, 0x7F at ts N+1).
- 0x7E and 0x7F are structurally distinct — means differ at every
  position (diffs +26 to -99), tight/loose positions don't align.
  They carry complementary, not identical, data.

**Tight positions (low stdev — candidate stable/slow fields):**
- 0x7E pos 4: stdev 15.4, range 51-95, mean 66
- 0x7E pos 7: stdev 26.1, mean 91
- 0x7E pos 8: stdev 26.2, mean 93 (pos 7 and 8 nearly identical stats)
- 0x7F pos 6: stdev 11.5, range 33-76, mean 62  ← tightest overall
- 0x7F pos 9: stdev 17.3, range 33-93, mean 72
- 0x7F pos 11: stdev 22.0, mean 94

**Zero-clustering finding:**
0x7F pos3+pos4 go to zero together on 4 of 10 packets. Confirmed NOT
driven by motion magnitude — resting-period packets (acm mag ~119)
produce both zero and non-zero values. Zeros are algorithm-state-driven:
they correspond to epochs where the ring's own step-detection state
machine has just timed out, just restarted, or is in an invalid state.

Evidence from State change debug strings in the same pull:
  ts=49357574/75: 0x7F zero → 'timeout' fires ts+73
  ts=49358798/99: 0x7E p1+p2 AND 0x7F p3+p4 both zero → isolated reset
  ts=49360776/77: 0x7F zero → immediately after 'fea off' + position
                  change (acm z-axis flips sign at ts=49360498)
  ts=49361078/79: 0x7F zero → 'timeout' fires ts+145

Active step-detection epochs (between 'motion det' and 'timeout'/'fea
off' events) consistently produce non-zero pos3+pos4 in 0x7F.

**Cross-tag coincidence:** 0x7E pos1+pos2 and 0x7F pos3+pos4 go to zero
together on two of the four zero packets (ts=49358798/99, 49360776/77).
The other two zero 0x7F packets have non-zero 0x7E pos1+pos2. These four
bytes across the two tags may form a related validity or count field.

**Ruled out:**
- Motion magnitude as driver of zeros (tested directly, not correlated)

**State machine strings visible in this pull (from State change events):**
  'timeout', 'motion det', 'hr enable', 'fea off'
  These are the ring's own debug labels for internal step-detector state.
  byte0 of State change payload = state enum (0x03, 0x04, 0x05, 0x06).

**Next steps (fresh thread):**
1. Decode what the non-zero values in 0x7F pos3+pos4 represent —
   step count? cadence? amplitude? Needs more activity pulls with known
   step counts to correlate against.
2. Investigate the tight positions (0x7F pos6 stdev 11.5, 0x7E pos4
   stdev 15.4) — slow-varying fields, good candidates for a stable
   feature like cadence or stride interval.
3. Check whether 0x7E pos1+pos2 / 0x7F pos3+pos4 form a u16 pair
   (LE or BE) across the two tags — cross-tag field hypothesis.

---
*Logged 2026-06-26. Based on 10 real pairs from gen3_pull_20260626_053013.*

---

## Pull classifier — FEATURE ADDED 2026-06-27

**Status:** Implemented and tested.

**What it does:**
Classifies each pull as SLEEP WINDOW / ACTIVE WINDOW / MIXED WINDOW / UNCLEAR
immediately after the event-type breakdown, before any decode sections.

Sleep tags: 0x6A, 0x5D, 0x6F, 0x75
Activity tags: 0x7E, 0x7F, or ≥3× 0x47 (motion events)

Rules:
- SLEEP WINDOW: sleep tags present, no activity tags
- ACTIVE WINDOW: activity tags present, no sleep tags
- MIXED WINDOW: both present
- UNCLEAR: neither fires

Also checks boot_ts gap against most recent prior pull file in
data/raw_pulls/gen3_morning/; warns if gap >1800 ticks (~30 min),
indicating a possible buffer rollover.

**Test results (against real saved pulls):**
- gen3_pull_20260627_080230.txt → ACTIVE WINDOW ✓
- gen3_pull_20260627_080358.txt → ACTIVE WINDOW ✓
- gen3_pull_20260625_052605.txt → SLEEP WINDOW ✓

*Logged 2026-06-27.*

---

## 0x7E/0x7F real_steps_features — Session 2 findings (2026-06-27)

**Status:** Structural analysis deepened with 64 pairs across 3 activity-window pulls.

### 1. Invalid pair causation — CONFIRMED

Pairs where 7F[3]=7F[4]=7F[7]=0 are caused by Feature session restart events.

Two distinct Feature session payloads observed:
- `02010400` — precedes the invalid pair with a full DHR_state sequence (1→4→2) + "hr enable" State change (state_byte=0x5)
- `02030400` — precedes the invalid pair with DHR_state:0 only; no "hr enable"

The ring's step algorithm takes 1–2 consecutive 300-tick windows to recover after a feature session restart. "Orphan" invalid pairs (no trigger event visible in a 500-tick lookback) are explained by this: the Feature session event fires 300–900 ticks before the invalid pair, outside any short lookback window. All 10 invalid pairs in the corpus are consistent with this explanation.

**Ruled out:** Motion magnitude as a driver (confirmed in prior session). Confirmed: zero fields are algorithm-validity flags, not measurement outputs.

### 2. Cross-position correlations (n=54 valid pairs)

Strongest notable correlations found:

| Pair | r | Interpretation |
|------|---|---|
| 7F[10] ↔ 7F[4] | +0.526 | Strongest link found. 7F[10] never hits zero; 7F[4] zeros during invalid windows. Hypothesis: 7F[10] is a persistent/smoothed version of the same metric as 7F[4]. |
| 7F[11] ↔ 7F[12] | −0.539 | Anti-correlated complementary pair. Consistent with energy in two complementary frequency bands (e.g., low-freq / high-freq split of accelerometer spectrum). Neither hits zero — always populated. |
| 7E[4] ↔ 7F[6] | +0.374 | Cross-tag correlation among tight always-populated fields. |
| 7E[4] ↔ 7F[10] | +0.330 | Cross-tag, consistent with 7E[4]↔7F[6] cluster. |
| 7F[6] ↔ 7F[12] | +0.336 | |
| 7E[4] ↔ 7F[4] | +0.337 | 7E[4] (tight) correlates with 7F[4] (validity-flagged) — suggests 7E[4] tracks the same signal as 7F[10]/7F[4]. |
| 7F[12] ↔ 7F[3] | +0.296 | |
| 7F[12] ↔ 7F[4] | −0.280 | 7F[12] anti-correlates with 7F[4] — consistent with 7F[11]↔7F[12] anti-corr cluster. |

Low-correlation pairs (effectively independent): 7F[3]↔7F[4] r=−0.084, 7F[3]↔7F[7] r=0.161, 7F[4]↔7F[7] r=0.308.

### 3. Per-field ranges in valid pairs (n=54)

7F[3]: mean=139.0, stdev=61.4, range=7–230 — widest range, most likely primary output
7F[4]: mean=77.2, stdev=25.7, range=25–161
7F[7]: mean=74.5, stdev=33.0, range=0–149
7F[10]: mean=159.6, stdev=32.8, range=80–204 — consistently high, no zeros ever
7F[11]: mean=92.9, stdev=23.1, range=44–144
7F[12]: mean=115.9, stdev=25.4, range=47–185
7E[4]: mean=77.3, stdev=17.7, range=38–124 — tightest 7E position
7F[6]: mean=72.9, stdev=16.1, range=33–109 — tightest 7F position

### 4. Structural ceiling

Cannot label 7F[3], 7F[4], 7F[7] as step_count / cadence / confidence without ground-truth correlation. The FFT-sub-message hypothesis (from open_ring docstring) is untested.

**Designed next experiment:** Do a timed walk (5–10 min, count steps or sync with Oura app step count), pull immediately after, and correlate each of the three zero-capable fields against the known step count for the walk period. The highest-variance field (7F[3], stdev=61.4) is the most likely step count candidate and should be tested first.

*Logged 2026-06-27. Based on 64 real pairs: 10 from gen3_pull_20260626_053013, 27 from gen3_pull_20260627_080230, 27 from gen3_pull_20260627_080358.*

---

## 0x61/0x09 sleep_statistics — Session 3 findings (2026-06-27)

**Status:** Major structural progress. Layout confirmed. Dynamic behavior characterized.

### 1. u16 LE layout CONFIRMED (n=48 unique real records, n=47 echo pairs)

The payload is 14 bytes structured as 6 × u16 LE + 1 × u8 (pfsm_state):

| offset | field | u16 LE? | value range | confirmed meaning |
|--------|-------|---------|-------------|-------------------|
| b0 | sub_byte | — | 9 (constant) | record type |
| b1-b2 | f0 | u16 LE | 0–65487 | unknown |
| b3-b4 | f1=o3 | u16 LE | 0–429 | seconds in current pfsm state ← CONFIRMED |
| b5-b6 | f2 | u16 LE | 1214–52987 | unknown (dynamically updating, see below) |
| b7-b8 | f3 | u16 LE | 0 always | padding / reserved field |
| b9-b10 | f4 | u16 LE | 940–56879 | unknown (dynamically updating, see below) |
| b11-b12 | f5 | u16 LE | 0 or 1 | binary flag (4 occurrences in corpus) |
| b13 | pfsm_state | u8 | 1–6 | ring sleep-state machine state ← CONFIRMED |

Evidence: b7=b8=0 in ALL 48 real records (zero stdev). b12=0 in all records.
b11 ∈ {0, 1} in all records. This uniquely constrains the layout — the open_ring
u32 interpretation is wrong; correct layout is u16 LE fields.

### 2. f0, f2, f4 are dynamically updating values — CONFIRMED

Proven by comparison of original vs echo records (pfsm=128 records are written
~4–11 ticks after the original, same pfsm state). The confirmed fields o3 and
pfsm_state are stable (Δo3 ≤ ±2), but f0/f2/f4 differ substantially.

### 3. f2 decay rate is pfsm-dependent — CONFIRMED (n=47 echo pairs)

f2 ALWAYS decreases from original to echo (no exception found across all 47 pairs).
The fraction retained after ~5 ticks depends strongly on pfsm state:

| pfsm | n | mean f2 retained (orig→echo) | avg Δt |
|------|---|------|---|
| 3 | 14 | **2.6%** retained (97.4% lost) | 4.7 ticks |
| 4 | 3  | **3.7%** retained (96.3% lost) | 5.7 ticks |
| 5 | 19 | **11.4%** retained (88.6% lost) | 6.1 ticks |
| 6 | 9  | **60.1%** retained (40.0% lost) | 5.1 ticks |

f2 is nearly stable during pfsm=6 (deep sleep?) and collapses almost to zero
during pfsm=3/4. This is the sharpest behavioural contrast found in any field.

### 4. f4 direction is pfsm-dependent — CONFIRMED

| pfsm | n | pos/neg Δ | mean Δf4 |
|------|---|-----------|----------|
| 3 | 14 | 1 pos / 13 neg | **−18766** |
| 4 | 3  | 0 pos / 3 neg  | **−1822** |
| 5 | 19 | 12 pos / 7 neg | **+1027** |
| 6 | 9  | 7 pos / 2 neg  | **+19937** |

f4 decreases in pfsm=3/4 (same direction as f2), is neutral in pfsm=5, and
strongly INCREASES in pfsm=6. f4 and f2 thus show OPPOSITE dynamics in pfsm=6.

Combined: during pfsm=6, f2 decays slowly (-40%/5s) while f4 grows rapidly
(+20K in 5 ticks on average). During pfsm=3, both f2 and f4 collapse to near-
zero rapidly. This anti-correlated behaviour between f2 and f4 in pfsm=6
contrasts with their positive correlation in static snapshots (r=+0.485).

### 5. Correlations (n=48 real records)

| pair | r | note |
|------|---|------|
| f2 ↔ f4 | +0.485 | strongest pair — same signal at different scales? |
| f2 ↔ o3 | +0.363 | when more time in current state, f2 is larger |
| o3 ↔ pfsm | +0.314 | confirms pfsm=6 has longest per-state durations |
| f0 ↔ anything | ≈0 | f0 is independent of all other fields |

### 6. Structural ceiling

- f0 has zero meaningful correlation with any other field — completely opaque.
- Physical meaning of f2/f4 not confirmed. Candidates: EWMA of a biosignal
  (short τ for pfsm=3/4, long τ for pfsm=6); or two complementary sleep-state
  accumulators (time in deep vs. light sleep). The pfsm=6 f4 growth rate of
  ~4K per tick rules out simple seconds-in-state at 1:1 tick rate.
- f5 flag (4 occurrences: pfsm=6 o3=429, pfsm=6 o3=319, pfsm=3 o3=148,
  pfsm=5 o3=33) — no clear predictor identified; not reliably linked to large o3.

### 7. Negative results

- f0+f2+f4 sum is NOT constant within or across sessions (one coincidental near-
  constant pair found in session 8, ruled out as general pattern).
- f2 and f4 are NOT simple cumulative time-in-state at 1:1 second rate.
- open_ring's "ticks_in_deep_sleep/sleep/awake" field names remain unverified —
  the u32 layout they assume is wrong; the semantic labels are still plausible
  but cannot be confirmed without ground truth.

*Logged 2026-06-27. Based on 48 unique real records and 47 echo pairs across
all 26 pull files in data/raw_pulls/gen3_morning/.*

---

## 0x7E/0x7F real_steps_features — Session 3: 7F[11]/7F[12] analysis (2026-06-27)

**Status:** Structural analysis complete. Energy-split hypothesis partially confirmed,
energy-conservation sub-hypothesis falsified. Ceiling reached on existing data.

### 1. Anti-correlation confirmed (n=96 valid pairs, all 26 pull files)

r(7F[11], 7F[12]) = **−0.568** (was −0.539 at n=54; strengthens with more data).
Both fields always populated (no zeros, ranges 44–149 and 47–185 respectively).

### 2. Energy conservation falsified

FFT-band complementarity hypothesis: "f11+f12 = constant (total spectral energy)."

Observed: stdev(f11+f12) = **21.3** — essentially equal to stdev(f11) = 21.2.
Sum NOT stabilized by the anti-correlation. This is exactly what the correlation
structure predicts (σ²(sum) = σ²(f11) + σ²(f12) + 2cov = 449.4 + 580.8 − 580.6 = 449.6
→ σ = 21.2). No additional constraint on the sum beyond what the correlation alone produces.

Sum max = 255 observed only ONCE in 96 pairs (1.0%). Not a firmware ceiling.

**Conclusion:** f11 and f12 are NOT complementary partitions of a fixed total.
Simple "two bands summing to a constant energy" model is wrong.

### 3. Diff(f11−f12) is the informative signal

| Pair | r |
|------|---|
| diff ↔ 7F[4] | **+0.337** |
| diff ↔ 7F[10] | **+0.293** |
| diff ↔ 7F[3] | −0.255 |
| diff ↔ 7F[8] | −0.270 |
| sum ↔ anything | ≤±0.180 (noise) |

The difference (f11−f12) tracks the step-output cluster (f4, f10) better than
either f11 or f12 alone. Sum shows no meaningful correlation with any field.

f12 > f11 in 65/96 pairs (67.7%), mean diff = −16.1. f12 is the dominant field
on average, but when f11 wins (positive diff), step output fields are higher.

### 4. 7F[8] — new position highlighted

7F[8] clusters with f12: r(f11, 7F[8])=−0.213, r(f12, 7F[8])=+0.263.
May be a third member of the "competing/suppressor" cluster alongside f12.

### 5. Full per-field correlations (7F positions with |r|>0.15):

| 7F pos | r(f11) | r(f12) | r(diff) | r(sum) |
|--------|--------|--------|---------|--------|
| 3 | −0.156 | +0.287 | −0.255 | +0.170 |
| 4 | +0.249 | −0.342 | +0.337 | −0.139 |
| 5 | −0.133 | +0.252 | −0.221 | +0.153 |
| 8 | −0.213 | +0.263 | −0.270 | +0.085 |
| 10| +0.187 | −0.323 | +0.293 | −0.180 |

Pattern: f12 shares sign with 7F[3/5/8]; f11 opposes that cluster.
The diff amplifies both directions.

### 6. Interpretation hypothesis (not yet testable without ground truth)

f11 = cadence-frequency band power (accelerometer FFT near step-rate, ~1–3 Hz)
f12 = low-frequency / gravity-artifact band power

Walking → periodic step motion → cadence band wins (f11 > f12, diff > 0, f4/f10 higher).
Stationary or irregular → gravity/low-freq dominates (f12 > f11, diff < 0, step output suppressed).

Anti-correlation arises because spectral mass at cadence frequency is not available
at low frequency — they compete but their total is not conserved.

**Testable during planned timed-walk session:** diff(f11−f12) should shift positive
during walking vs. resting. This can be confirmed alongside the 7F[3] step-count
hypothesis in the same single data-collection session.

*Logged 2026-06-27. Based on 96 valid pairs from all 26 pull files.*

---

## 0x53 wear_event — DECODER CONFIRMED 2026-06-27

**Status:** DONE. Validated against 2 real packets (grep across all 26 pull files).

**Decoder:** `decode_wear_event` (alias for `decode_state_change_ind`).
Format: `state:u8 + text:ascii` where `text` is the duration in the previous
state, as a numeric string (seconds).

**Source:** open_ring `driver/decoders.py` + `enums.py` STATE_CHANGE enum.

**Confirmed packets** (from gen3_pull_20260625_052605.txt, both at ts≈38433964):
- `ts=38433964`: `state=1 (STATE_NOT_IN_FINGER), text='50009'`
  → ring removed from finger; had been on-wrist for 50,009 s ≈ 13.9 hours
- `ts=38434063`: `state=3 (STATE_FINGER_USER_ACTIVE), text='1469'`
  → ring put back on; had been off-wrist for 1,469 s ≈ 24.5 min

**Key finding:** Text field = duration of the *previous* state in seconds.
  STATE_NOT_IN_FINGER text ("50009") = how long ring was on-wrist before removal.
  STATE_FINGER_USER_ACTIVE text ("1469") = how long ring was off-wrist before replacement.
  Note: Δts between the two events is only 99 ticks (1.6 min), NOT the 1469s text.
  This confirms text is a firmware-maintained counter, not derived from boot_ts delta.

**STATE_CHANGE enum confirmed values:**
  1=STATE_NOT_IN_FINGER, 3=STATE_FINGER_USER_ACTIVE (both validated)
  Full enum in enums.py goes to state 30; see enums.py for all values.

**Decoder works. No more packets needed to confirm the format.**

*Logged 2026-06-27.*

---

## 0x69 temp_period — DECODER CONFIRMED 2026-06-27

**Status:** DONE. Validated against 7 real packets, cross-checked against 0x75.

**Decoder:** `decode_temp_period`. Format: `i16 LE / 100 = °C`.
Fixed 2-byte payload. Same formula as the already-confirmed 0x75 decoder.

**Source:** open_ring `driver/decoders.py` `decode_temp_period()` → `{"temp_raw": _i16(p, 0)}`.
Units were "TBD" in open_ring — now confirmed °C via cross-check (see below).

**Real packets (7 total, from 3 pull files, grep across all 26):**
All raw values / 100 → range 33.82–36.12°C; all plausible skin-temperature readings.

**Cross-validation against 0x75 (confirmed skin-temp decoder):**
Two near-timestamp pairs found:
1. `ts=40728926` (0x75): samples include [36.09, 36.09, 36.42, 36.09, 36.09, 36.09, 36.35]°C
   `ts=40728928` (0x69, Δt=2): raw=3612 → **36.12°C** — matches 0x75 mean of 36.18°C ✓
2. `ts=39784292` (0x75): last sample 35.13°C
   `ts=39784294` (0x69, Δt=2): raw=3513 → **35.13°C** — EXACT MATCH ✓

**Interpretation:** 0x69 is a single-value period summary of the same skin-temperature
sensor that 0x75 samples every ~30s. The 0x69 value closely tracks the mean/last
sample of the surrounding 0x75 window. Both use identical encoding: i16 LE / 100 = °C.

*Logged 2026-06-27.*

---

## 0x6B motion_period — ENUM MISMATCH 2026-06-27

**Status:** IN PROGRESS. 4 real packets captured. open_ring decoder partially wrong.

**Decoder claim:** `decode_motion_period()` → `{"motion_state_30s": p[0], ...}`,
where p[0] is supposed to index MOTION_STATE enum: {0:NO_MOTION, 1:RESTLESS,
2:TOSSING_AND_TURNING, 3:ACTIVE}.

**Observed b[0] values from 4 real packets:**
| ts | b[0] (u8) | payload len | context |
|----|-----------|-------------|---------|
| 38433969 | 6 | 8 bytes | 5 ticks after 0x53 wear_event (ring removal) |
| 42165470 | 61 (0x3d) | 14 bytes | morning wake-up context |
| 50240030 | 62 (0x3e) | 14 bytes | 1 tick after 0x7E real step feature (active walking) |
| 50373571 | 52 (0x34) | 14 bytes | later in same activity pull |

**Finding:** ALL four b[0] values are OUTSIDE the MOTION_STATE enum range (0–3).
The enum mapping in open_ring is either incomplete for this firmware version, or
b[0] is NOT a MOTION_STATE enum value in these packets.

**Hypothesis — b[0] is a motion intensity count, not an enum:**
- b[0]=62 during active stepping, b[0]=6 near ring removal — directionally consistent
  with "more motion = higher count." But 4 data points is too few to confirm vs. reject.
- Values 52, 61, 62 cluster together; 6 is an outlier (brief wear-event context).

**Payload structure:**
- Variable length: 8 bytes (n=1) vs 14 bytes (n=3). Both forms share b[0].
- 0xaa bytes appear in some 14-byte payloads in trailing positions — standard
  uninitialized-memory filler, consistent with a fixed-size buffer only partially
  filled for shorter motion periods.
- The 14-byte trailing bytes (b1–b13) show values in range 0–68 for the
  wake-context packet, and values up to 233 for the active-stepping packet,
  with 0xaa filler where the period was short. No u16 pattern visible at n=4.

**Negative result:** open_ring MOTION_STATE enum (0–3) is NOT a complete map for
this firmware — it does not account for the observed values (6, 52, 61, 62).

**Next steps:** Capture more 0x6B packets across diverse motion contexts (rest, walk,
sleep, brief wear events) to test the count hypothesis and map the trailing bytes.
The 8-byte vs 14-byte format split also needs more data before it can be explained.

*Logged 2026-06-27.*
