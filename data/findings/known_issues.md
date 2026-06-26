# METHUSELAH // Known Issues — Gen3 Decoders

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

Working hypothesis (not yet tested): offset-3 is time-in-current-pfsm-
state. pfsm=6 is a longer-duration state (deep sleep?) accumulating more
ticks before the record fires; pfsm=5 resets frequently to ~30. The right
test is whether o3 at pfsm=6 correlates with elapsed time since the last
pfsm=5→6 transition — requires 0x6A sleep_state data from the same
boot_ts window to cross-reference.

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
