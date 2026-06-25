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
unresolved. Stopped here, not exhausted.

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

**Next steps, not yet attempted:**
1. Check whether bytes 1-6 correlate with the SAME-window decode_spo2_event
   (0x6f) corrected values, which we already trust (offset=6 fix) — if
   bytes 1-6 track the same physiological trend across the same boot_ts
   range, that's real corroborating evidence for what this band represents.
3. Bytes 7-12 may simply be legitimately noisy raw data (AC component,
   not DC) — worth checking against known PPG AC/DC theory rather than
   assuming it must decode to something smooth.

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

**Next steps, not yet attempted:**
1. ~~Test byte 0 as channel_index per open_ring's own docstring hypothesis~~
   FALSIFIED 2026-06-25: byte 0 ranges 16-222 across 43 packets, alternating
   between a low band (~16-63) and high band (~146-222) — far too wide a
   range to be a simple channel_index (would expect 0/1 or small int).
   Ruled out as stated; could still be some other field, not investigated
   further today.
2. Investigate why short packets (2, 4, 13 bytes) exist — possibly
   truncated/edge records, or a genuinely different record format.

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
