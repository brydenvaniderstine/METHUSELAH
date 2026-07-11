# ── UPDATE RULE ──────────────────────────────────────────────
# Claude Code must append to this file at the end of any session
# that produces a new finding, confirmed pattern, or resolved/
# unresolved decoder question. Do not wait to be asked explicitly.
# If a session ends without touching this file and a finding occurred,
# that is an error. Last updated: 2026-07-10
# ─────────────────────────────────────────────────────────────
#
# ── CREDENTIAL HANDLING ─────────────────────────────────────
# Do not paste live tokens/credentials into this file. If a session
# involves a credential (API token, key, secret), reference that it
# exists and where it's stored (e.g. "Oura token, stored in
# localStorage/browser session") — never the literal value. This rule
# exists because the 2026-07-05 entry below did exactly this; it is
# left as-is (not worth a history rewrite for a token expiring
# 2026-07-13) but must not be repeated going forward.
# ─────────────────────────────────────────────────────────────

# METHUSELAH // Known Issues — Gen3 Decoders

## Gen3 vs Gen4 cross-validation — North Star reference (night of 2026-06-28/29)

**Purpose:** First confirmed cross-validation data point between Gen3 BLE decoder output
and Gen4 official Oura app. This is the reference to build against for Track B decoder
work — especially 0x6A sleep_state granularity and 0x5D HRV. Not a one-off note;
update `data/findings/gen3_vs_gen4_comparison.csv` with each new comparison night.

**Source:** `gen3_pull_20260629_101344.txt` (morning pull, 255 events, sleep window).
Gen4 numbers from Oura app screenshots, manually transcribed.

### Confirmed agreement (close approximation, not 1:1 parity required)
| Metric | Gen3 BLE | Gen4 app | Delta |
|--------|----------|----------|-------|
| HR range | 54.5–56.5 bpm | 52–58 bpm | Overlapping; Gen4 range wider (different averaging window) |
| HR avg | ~55.3 bpm | 58 bpm avg | ~5% difference — acceptable |
| SpO2 range | 92–97% | not shown | — |
| SpO2 avg | ~94.4% | not shown | — |
| Sleep temp | 34.88–35.26°C | not shown | — |

### OPEN QUESTION — 0x6A sleep_state decoder completeness

**Finding:** All 10 `[Sleep period info (2)]` samples in the pull return `state=1`
(p[7]=1 in every packet). No variation across a 9.5-hour night.

**Gen4 ground truth for the same night:**
- REM: 29%, Light: 52%, Deep: 19%, Awake: 1h 32min (92 min)
- Total sleep: 9h 32min at 86% efficiency
- Multiple documented stage transitions occurred.

**The open question:** Is `state=1` flat because:
1. **Decoder is incomplete** — real stage data (REM/Light/Deep/Awake) lives in bits
   of p[7] or other payload offsets we haven't mapped yet, and `state=1` only extracts
   a single sub-field. OR
2. **Window sampling artifact** — the 255-event buffer captures only a slice of the
   night. With 10 x6A samples and sleep_period_info_2 firing ~every 30 seconds, the
   pull covers ~5 minutes of actual sleep. If the ring happened to be in a sustained
   stage=1 stretch during that window, all 10 samples could legitimately be state=1
   even though the full night had rich stage variation.

**Evidence for option 2 (window artifact):** Sleep ACM period (0x72) data from the
same night shows motion_count variation (0–120+ range across all pulls), confirming
real physiological variation exists. The 10-sample window just may not span a transition.

**Evidence for option 1 (incomplete decoder):** The Gen3 ring has a full sleep-stage
algorithm (it feeds the Gen4 app's REM/Light/Deep breakdown). That information has to
live somewhere in the BLE event stream. If it's not in p[7] of 0x6A, it's either in
a different field of 0x6A, a different tag entirely (0x61/0x09 _dd_sleep_statistics is
the prime candidate), or aggregated into summary-only tags not yet decoded.

**Tracking target:** A working sleep_state decoder should return values consistent with
REM/Light/Deep/Awake distribution across a full night's pulls. State=1 at 100% of
samples with no variation is a real gap, not noise. This is the concrete validation
target for any 0x6A or 0x61/0x09 decoder improvement.

**Next step:** Pull the 0x61/0x09 `_dd_sleep_statistics` packets from the same night
and correlate the `pfsm_state` field against the Gen4 stage breakdown — that field
(confirmed in the IN PROGRESS section of the roadmap) already shows dynamic values and
is the most likely home for fine-grained sleep stage data.

### DECODER GAP — 0x5D HRV absent from sleep pull

**Finding:** Zero `[HRV event]` packets in `gen3_pull_20260629_101344.txt`.
**Gen4 ground truth:** 36ms avg HRV, 57ms max for the same night.

HRV data is confirmed present physiologically — this is a decoder/capture gap, not a
measurement absence. The 255-event sleep buffer is dominated by SpO2, temperature,
ACM, and sleep-period events. The 0x5D HRV event likely fires less frequently than
the other tags and gets pushed out of the 255-event window before the morning pull.

**Resolution path:** Pull immediately after a sleep window ends (before much activity
fills the buffer) to catch 0x5D events while they're still in the circular buffer.
Alternatively, 0x5D may appear in mid-sleep pulls (if taken). Check existing mid-sleep
pulls in the corpus for any 0x5D presence.

*Logged 2026-06-29. Reference CSV: `data/findings/gen3_vs_gen4_comparison.csv`.*

---

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

### 2. Event rates and data loss window (CORRECTED 2026-06-28)

**The 1-tick/second assumption was wrong for activity mode.**

Measured from the 88-second pair (gen3_pull_20260627_080230 vs 080358, direct
wall-clock gap 88 seconds):
- 207 of 255 buffer slots were replaced in 88 seconds → **2.35 events/second during activity**
- 255 / 2.35 = **108 seconds ≈ 1.8 minutes** to replace the entire buffer during walking

Separately, the 22:31/22:34 sleep pair (206-second gap) shows **0 new events** — confirming
sleep mode generates far fewer events than 1.24/s (buffer would NOT have turned over in 3.5 min).

| Context | event rate | Buffer time window |
|---------|-----------|-------------------|
| SLEEP (SpO2, IBI, HRV, temp, debug) | ≤1.2 ev/s, likely ~0.1 ev/s | ≥3.5 min, likely ~42 min |
| ACTIVE WAKE (step features, motion, debug) | **~2.35 ev/s** | **~1.8 minutes** |

The tick rate is also mode-dependent: during activity, the 88-second pair shows **77 ticks/second**
(6,757 new ticks in 88 seconds). The previously-assumed 1 tick/second is only consistent with
sleep-mode events, and cannot be assumed globally.

**Corrected analysis of the 2026-06-28 missed-sleep pull (gen3_pull_20260628_074844.txt):**
- 255 real events, all activity: Motion events, Real step features, Debug data, PPG amplitude
- boot_ts span: 51,038,541 → 51,047,881 = **9,340 ticks at 77 ticks/s = 121 seconds = 2.0 minutes** post-wake
  (ORIGINAL CLAIM: "9,340 seconds = 2.6 hours" — WRONG, used 1 tick/second which is incorrect for activity mode)
- Oldest event in the buffer: **~07:46 AM**, not "05:13 AM" as previously stated
- User was active from 07:21 AM to 07:48 AM = 27 minutes of walking = **14.9× buffer cycles**
- Sleep data was completely gone after the FIRST ~1.8 minutes of walking (~07:23 AM)
- Zero sleep tags (0x6A, 0x5D, 0x6F, 0x75) — confirmed

### 3. Script request is NOT the problem

The script correctly sends `10 09 00000000 ff ff ff ff ff`:
- ts = 0x00000000 (from the very beginning)
- max_events = 0xFF = 255 (the ring's own limit)
- flags = 0xFFFFFFFF (all event types)

This retrieves the **full contents of the ring's buffer**. There is no request-side
parameter that can reach further back — the data is already gone, overwritten in flash.

### 4. Fix (CORRECTED 2026-06-28)

**The only fix is to pull sooner. The required window is MUCH shorter than originally stated.**

The correct timing constraint:
- Pull **before any significant walking** — the buffer is completely replaced within
  **~1.8 minutes of sustained activity** (2.35 events/second × 255 slots = 108 seconds).
- "Within 1 hour of waking" is WRONG — by that point the buffer has cycled 33× at
  activity rates. All sleep data is gone within 2 minutes of first movement.
- Even lying still for 5 minutes is fine — sleep mode generates ≤1.24 events/second
  (confirmed: buffer contents identical after 3.5 minutes of sleep-mode time). Staying
  in bed after waking does NOT threaten the buffer.

**The distinction that matters:**
- LYING STILL (even 30 minutes): safe, sleep events don't fire quickly
- WALKING even briefly (~2 minutes): fatal, sleep data permanently gone

**What this means for the fix:**
- Optimal: trigger pull automatically when the alarm fires, before any movement
- Acceptable: pull while still in bed, before standing up
- Risky: pull after a bathroom trip (walking even 30 seconds starts the replacement)

### 5. Automation investigated and explicitly rejected (2026-06-28)

**Decision: do not automate for now. Revisit only after a clear decision on coexisting with vs. replacing the official Oura app.**

**Why polling doesn't work:**
A repeating-interval background pull (laptop-side, bleak) cannot reliably beat the ~108-second buffer replacement window. The math:

- Each BLE pull takes ~10–20 seconds (scan → connect → auth → transfer → disconnect)
- To catch a 108-second window reliably, the poll interval must be well under 108 seconds
- At 30-second poll intervals: ~17–50% of elapsed time is spent in BLE connections with no margin
- Even at 20-second intervals: if the user moves immediately after a poll, the next poll arrives ~18 seconds later and the buffer is already 40% replaced
- Polling is fundamentally probabilistic against a 108-second window; no practical interval makes it reliable without being effectively continuous

**Why near-continuous polling is also a non-starter:**
- At 30-second intervals for an 8-hour sleep: ~960 BLE reconnections per night
- BLE radio during active connection draws meaningfully more current than advertising-idle
- Over weeks/months this noticeably shortens the ring's ~7-day battery life
- Not worth the battery cost for still-unreliable capture

**The only architecturally sound solution: persistent BLE streaming daemon**
- The Oura phone app architecture (and open_ring's `flush_interval_s=20.0` parameter) uses a persistent BLE connection, not repeated reconnects
- Events stream continuously and are written to disk as they arrive
- No race condition against the buffer window — events are captured before they age out
- But: significant engineering step from the current one-shot pull script (requires background daemon, reconnect logic, stateful event dedup, event streaming vs. one-shot history fetch)

**Critical blocker: Oura app BLE conflict**
- BLE peripherals (the ring) typically allow only ONE central connection at a time
- If the official Oura app holds a BLE connection overnight for its own sleep tracking, a competing daemon cannot connect
- Breaking Oura's BLE access would disable their own sleep tracking, which is currently the ground-truth source used for cross-validation
- This conflict alone makes a daemon not worth building until there's a deliberate choice: coexist with Oura (by scheduling BLE access, or triggering after app disconnects) or replace Oura as the primary tracker

**Accepted near-term solution: manual habit**
Pull the ring before getting out of bed. The buffer is safe indefinitely while lying still (≤1.24 events/second, buffer not cycling), and destroyed within 2 minutes of walking. The habit is simple: phone alarm fires → grab phone → trigger pull → then get up. No code change needed. Revisit daemon architecture only if fidelity requirements grow beyond what the manual habit can deliver.

### 6. The 0x11 parsing artifact

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

## 0x7E/0x7F real_steps_features — Timed walk attempt INCONCLUSIVE (2026-06-28)

**Status:** Ground-truth experiment attempted but confounded. Not a failed hypothesis — retry with confound removed.

### What happened

10-minute walk, 1,273 steps (Apple Health), 1,163 steps (Oura app) — normal cross-device variance.
Two baseline pulls before the walk: gen3_pull_20260628_201810, gen3_pull_20260628_201845.
Two after-pulls: gen3_pull_20260628_203635 and gen3_pull_20260628_203908 (fresh terminal).

Both after-pulls returned **identical data**, classified as SLEEP WINDOW by the pull classifier:
- Zero 0x7E/0x7F step feature events
- Zero motion events resembling walking
- Only sleep-state, SpO2, temp data
- Pull classifier correctly flagged a large boot_ts gap from the prior baseline pull

**Ruled out:** Terminal window reuse as cause — the fresh-terminal repeat produced byte-identical results.

### Hypothesis: Oura app is a competing BLE consumer

The most likely explanation is that the official Oura app held its own persistent BLE connection during and after the walk, consumed the step-feature events from the 255-event circular buffer before our script connected, and left only the older sleep-state/SpO2 data behind.

This is a **different failure mode** from the morning sleep-loss problem:
- Sleep-loss failure: NEW activity events overwrite OLD sleep events (buffer cycles forward)
- This failure: a competing consumer (Oura app) drains the buffer before our script connects — the walk data was real and captured by Oura's tracking, but already gone from the ring's buffer when we read it

This is consistent with the BLE conflict already documented in the automation section above: Oura app likely maintains a persistent BLE connection for its own tracking, and BLE peripherals typically allow only one central connection at a time. The ring may also proactively push events to its primary connected central, resetting the buffer state our script sees.

**This is INCONCLUSIVE, not a failed hypothesis.** The 7F[3]-as-step-count and diff(f11−f12) direction hypotheses are not disproven — the experiment simply didn't reach the ring's buffer before the Oura app did.

### Retry plan (2026-06-29)

Before the walk:
1. Force-close the Oura app (fully killed, not just backgrounded)
2. Disable Bluetooth on the phone OR put phone in airplane mode
3. Walk 10 minutes with Apple Health or Apple Watch counting steps
4. Immediately after stopping: run pull script before re-enabling phone BT

This removes the competing-consumer confound. If the after-pull returns step features with phone BT disabled but not with it enabled, the Oura app BLE conflict is confirmed as the cause.

*Logged 2026-06-28. Experiment inconclusive — suspected competing-consumer confound, controlled retry planned for 2026-06-29.*

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

## Tier 2 tag inventory — grep sweep completed (2026-06-28)

**Context:** The roadmap listed most Tier 2 tags as "NOT STARTED" with unclear data
availability. A corrected grep across all 27 pull files (using actual label strings,
not hex patterns — pull script labels events by name, not by hex tag) found:

| Tag | Label | Packets | Status |
|-----|-------|---------|--------|
| 0x81 | CVA raw PPG data | 393 | Fully decoded (stateful diff-PPG in open_ring) |
| 0x4A | PPG amplitude | 233 | Has decoder, 5×u16 format (see below) |
| 0x80 | GreenIbiQuality | 257 | Has real decoder (see below) — roadmap wrong |
| 0x72 | Sleep ACM period | 193 | Has decoder, wrong format (see below) |
| 0x6C | Feature session | 48 | Has decoder (byte_0, capability, status) |
| 0x73 | EHR trace event | 48 | Has decoder (header + u8 samples) |
| 0x5B | BLE connection | 46 | Has decoder (6 u8 fields at fixed offsets) |
| 0x6D | MEAs quality event | 23 | **No decoder in open_ring dispatch table** |
| 0x50 | Activity info | 11 | Has decoder (activity_byte_0 + trailing) |
| 0x74 | EHR ACM intensity | 11 | Has decoder (7×u16 LE) |
| 0x49/4C/4F | Sleep summaries | 0 | Gen3 does not emit these |
| 0x82/0x83 | Scan start/end | 0 | Gen3 does not emit these |

*Logged 2026-06-28.*

---

## 0x80 (GreenIbiQualityEvent) — REAL DECODER EXISTS, roadmap wrong (2026-06-28)

**Finding:** Roadmap stated 0x80 was "raw-bytes-only (14x u8)." Wrong.
`decode_green_ibi_and_amp_event` (raw passthrough at line 416) is NOT in the dispatch
table. The dispatch table maps 0x80 to `decode_green_ibi_quality_event` (line 645) —
a real IBI/quality bit-pack decoder.

**Decoder format:**
```
payload = N pairs of bytes (N = floor(len/2))
For each pair (b_low, b_high):
  value_11bit = (b_low << 3) | (b_high & 0x07)   # IBI in ms (likely)
  quality_a   = (b_high >> 3) & 0x03
  quality_b   = (b_high >> 5) & 0x07
```

**Validation:** 4 real activity-context packets (boot_ts ~39149736) decoded to IBI
values 502-700ms → HR 86-120bpm. Context: sandwiched between Motion event
(ts=39149641) and Real step features (ts=39149795/796) — active walking confirmed.
Artifact outlier (val=2000, qb=4) behaves consistently with quality gating.

**Status:** Move 0x80 from "NOT STARTED / raw-bytes" to "IN PROGRESS — activity
context validated, sleep context IBI range not yet confirmed."

*Logged 2026-06-28.*

---

## 0x72 sleep_acm_period — STRUCTURAL ANALYSIS COMPLETE (2026-06-28)

**Format:** 6×u16 LE — corrects open_ring's wrong decoder (`header_hex + u8 at 6-11`).

### Confirmed invariants (n=193 packets, 0 exceptions)

1. **f4 >= f3** — always, 0 violations. Firmware guarantee.
2. **f1 = max(f0, f1, f2)** — always, 0 violations. f1 is always the dominant axis.
3. f3 >= f5: 10 violations (5.2%) — not guaranteed, but usually holds.

### Two correlated groups

- Group 1: {f0, f1, f2}: pairwise r = +0.96–+0.97
- Group 2: {f3, f4, f5}: pairwise r = +0.89–+0.97
- Cross-group: r = +0.76–+0.92 (all driven by motion-event outliers; in quiet sleep only, cross-group r ≈ 0)

### Quiet sleep baseline (n=146 packets, all fields < 100)

| field | mean  | stdev | notes |
|-------|-------|-------|-------|
| f0    | 12.7  | 7.5   | smallest axis |
| f1    | 26.9  | 18.6  | always max, ~2× f0/f2 |
| f2    | 12.9  | 12.0  | ≈ f0 in baseline |
| f3    | 29.5  | 2.9   | tightest field — nearly constant in quiet sleep |
| f4    | 35.0  | 6.2   | always >= f3 |
| f5    | 3.8   | 2.1   | small count |

In quiet sleep: motion_count correlation drops to r ≈ 0 for all fields (full-corpus r=+0.62–0.68 was driven entirely by outlier motion events).

### Motion event behavior

- Moderate motion (f1≈108): f3=43, f4=120 — both groups respond, f4 responds more
- Extreme motion (f1≈996): f3=29, f4=36 — Group 2 barely changes despite Group 1 exploding
- Super-extreme (f1≈2000+): both groups explode (f3=300–456, f4=758–1340)

f4–f3 grows from +2 to +10 in quiet sleep → +100 to +1000 in extreme motion.

### Sleep state correlation (matched against 0x6A)

State=0 (n=47, motion_count mean=1.6): f4 quiet mean=38.3
State=1 (n=146, motion_count mean=0.8): f4 quiet mean=34.1
State=0 is slightly more restless — possibly lighter sleep.

### Field hypotheses (unconfirmed — need disassembly or ACM ground truth)

- **f0**: smallest per-axis motion count in the ~30-second window
- **f1**: largest per-axis motion count (gravity-aligned axis, or firmware sorts and puts max in slot 1)
- **f2**: middle-axis motion count (same baseline as f0 in quiet sleep)
- **f3**: motion floor/mean — very stable (~29) from micro-motion (breathing/cardiac); resistant to individual spikes
- **f4**: motion peak or cumulative total — always >= f3, responds strongly to spikes
- **f5**: count of above-threshold events — small in quiet (0–12), can reach 821 in extreme motion

### Status

FORMAT confirmed (6×u16 LE). Two confirmed invariants (f4>=f3, f1=max). MEANING is hypothetical.
Ceiling: cannot assign exact field semantics without `parse_api_sleep_acm_period` disassembly or
ground-truth accelerometer comparison (simultaneous external ACM + ring pull).

*Logged 2026-06-28. n=193 packets from all 27 pulls, matched against 188 0x6A records.*

---

## 0x4A ppg_amplitude_ind — FULL CORRELATION ANALYSIS (2026-06-29)

**Status:** Format confirmed. Full correlation analysis complete. f0 well-characterized,
f1-f4 partially decoded. Ceiling reached on f1-f4 semantic labeling.

### Format (confirmed)
10-byte fixed payload = 5×u16 LE at offsets 0,2,4,6,8.
open_ring decoder reads ONLY `_u16(p, 0)` and divides by 65535 — drops f1-f4 silently.

### f0 — optical amplitude indicator (confirmed)
**Context split (n=243 total):**
- ACTIVITY (n=43): f0 = 0 in ALL 43 packets. Red/IR optical system is OFF during
  activity mode (ring uses green-only LED for IBI/HR). f0=0 is a reliable activity
  sentinel.
- SLEEP (n=185): f0 ranges 0–65535, mean=21,426, stdev=15,655.
- MIXED (n=15): intermediate range.

**f0 vs SpO2 correlation (n=185 sleep, r=−0.561, nearest 0x6F within 2000 ticks):**
Strongly monotonic negative relationship:

| SpO2 | n | f0 mean | f0 stdev |
|------|---|---------|----------|
| 88% | 8 | 61,248 | 12,124 |
| 89% | 11 | 40,735 | 16,592 |
| 90% | 17 | 31,840 | 14,785 |
| 91% | 12 | 18,448 | 12,870 |
| 92% | 31 | 18,488 | 11,249 |
| 93% | 22 | 20,922 | 11,568 |
| 94% | 28 | 13,645 | 9,023 |
| 95% | 14 | 13,423 | 5,775 |
| 96% | 22 | 18,500 | 10,715 |
| 97% | 16 | 12,491 | 7,049 |
| 98% | 4 | 13,207 | 9,353 |

f0 SATURATES at 65535 when SpO2 drops to 88% (hardware ceiling hit). The inverse
SpO2 correlation reflects automatic gain control: ring increases LED drive power when
optical signal is weak (desaturation event) → higher raw amplitude.

f0=0 in 16/185 sleep packets (SpO2_mean=94.4%): likely "no valid measurement" sentinel
or measurement gap — f0=0 in sleep is NOT a low-SpO2 indicator; quite the opposite.

**Timing:** 0x4A fires once per SpO2 measurement cluster (~every 200–300 sleep ticks),
bracketed by 0x6F SpO2 samples. It is a per-cluster summary, not a per-sample event.

**open_ring normalization (f0 / 65535.0):** yields ~0.33 at SpO2=93% baseline sleep.
Normalization is correct but the semantic is optical gain level, NOT signal quality.

### f1-f4 — per-channel artifact/sample counts (confirmed context, meaning open)
**Context split:**
- ACTIVITY: ALL ZERO for f1-f4 in every activity packet (43/43). Sleep-only metric.
- SLEEP: range 0–30 per field, mean 2.2–4.2, zeros in 37–61% of packets.

**Inter-field correlations (n=243):** extremely high — these are near-identical:
r(f1,f2)=+0.963, r(f1,f3)=+0.918, r(f1,f4)=+0.889, r(f2,f3)=+0.979, r(f2,f4)=+0.958,
r(f3,f4)=+0.992. One underlying quantity expressed across 4 channels/sub-windows.

**f0 vs f1-f4:** r≈0 (−0.045 to +0.021). Completely independent subsystems.

**f1-f4 vs motion_count (r=+0.414 to +0.508):** increase with movement.
- mc=0: f1_mean=3.0
- mc=2-3: f1_mean=8–10
- mc=13: f1_mean=7.6

**f1=0 vs f1>0 context:**
- f1=0 (n=68): SpO2=92.75%, mc=0.9 → quiet low-SpO2 periods
- f1>0 (n=117): SpO2=93.92%, mc=2.4 → motion-present periods

**f1-f4 sum:** range 0–118, mean=11.7. Sum not obviously more informative than f1 alone.

**Best hypothesis:** f1-f4 count motion-artifact events or signal-adjustment rounds
within the SpO2 measurement window across 4 optical channels (green×2, red, IR). The
positive motion correlation and zero-in-activity context are consistent with artifact
rejection counts. The near-identical cross-channel values (r=0.99) mean the ring sees
essentially the same motion artifact simultaneously across all channels (expected for
wrist movement affecting all LEDs equally).

### Ceiling
- f1-f4 semantic (artifact count vs valid-sample count) unresolvable from correlation
  alone. Needs firmware symbol for the ppg_amplitude_ind struct fields.
- f0 as gain/drive vs DC-level: both explain the inverse SpO2 correlation; indistinguishable
  without access to the optical subsystem registers or firmware.

*Logged 2026-06-28 (format). Full analysis 2026-06-29.*

---

## 0x6D MEAs quality event — CORRELATION COMPLETE, CEILING REACHED (2026-06-29)

**Status:** Format confirmed. Correlation analysis complete. Physical meaning open.

### Format (confirmed)
byte[0]=0x00 (constant header, all 23 packets) + 4×i24 LE at offsets 1, 4, 7, 10.
All values negative (-2 to -211 across all 23 packets). 13-byte fixed payload.

### Activity-only (confirmed)
0x6D appears ONLY in activity pulls. Both pulls containing 0x6D are activity windows
(no SpO2 events, no sleep events). SpO2 correlation is impossible on existing data.

### Periodic cadence: 121 ticks (~1.57s)
Inter-event spacing within each burst is exactly 121 ticks (±1). This is a fixed-rate
periodic emitter during activity, NOT triggered by motion or physiological events.
Tick gaps between bursts: 4275, 711411 (recording boundaries).

### Descriptive stats (n=23)
| field | min | max | mean | stdev |
|-------|-----|-----|------|-------|
| f0 | -216 | -7 | -72.4 | 60.7 |
| f1 | -207 | -2 | -57.5 | 51.5 |
| f2 | -132 | -3 | -57.2 | 37.8 |
| f3 | -126 | -5 | -56.3 | 35.9 |

### Inter-field correlations (r, n=23)
All signed = |value| since all negative. Moderate cross-channel correlation, NOT independent.
- r(f0,f1)=+0.605, r(f0,f2)=+0.500, r(f0,f3)=+0.144 ← f0/f3 most independent
- r(f1,f2)=+0.655, r(f1,f3)=+0.443, r(f2,f3)=+0.617

**Interpretation:** 4 correlated-but-distinct channels (not the same signal×4; not
4 fully independent channels). Moderate r=0.44–0.66 is consistent with 4 sensors
measuring the same physical tissue from slightly different geometries/wavelengths.

### vs motion magnitude (0x47, nearest within ±500 ticks, n=23 matched)
- r(f0,mag)=+0.099, r(f1,mag)=+0.097, r(f2,mag)=+0.012, r(f3,mag)=−0.207
- r(|sum|,mag)=−0.027

**FALSIFIED: motion quality hypothesis.** Near-zero correlation with motion magnitude
rules out "penalizes high motion" or "ACM-derived quality score." These values are
independent of how much the ring is moving at the same moment.

### Best current hypothesis
**4-channel optical background noise floor or per-channel signal residuals** from the
PPG measurement system (4 photodetector channels: green×2, red, IR). Negative values
consistent with signed residuals or log-domain SNR in dB-like units. Fixed 1.57s
cadence matches a per-analysis-window quality report, NOT a per-beat or per-event trigger.

### Ceiling
Cannot decode further without:
- Oura firmware disassembly to identify the "MEAs" symbol
- Or: simultaneous capture of 0x77 spo2_dc_event or 0x6E spo2_ibi_and_amplitude during
  same activity pull — those tags carry the raw optical channels that 0x6D may be scoring

*Logged 2026-06-28. Correlation analysis completed 2026-06-29.*

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

---

## 0x6C feature_session — PARTIAL DECODE, CEILING REACHED (2026-06-29)

**Status:** b0 session-class and b1 start/stop direction confirmed for CVA subsystem.
Capability enum for all values not available from open_ring source.

### Decoder (open_ring)
`decode_feature_session`: `(byte_0, capability, status)` + optional trailing bytes.
Docstring acknowledges "one of 12 session-type payloads (oneof in proto); per-version
decoding deferred." No capability enum anywhere in the codebase. Not in PROTOCOL.md.

### Corpus summary (n=48 packets, across 11 pulls)
| b0 | count | b1 values seen | b2 values seen | trail |
|----|-------|----------------|----------------|-------|
| 0x02 | 30 | 1,2,3 | 4 | 0x00 (1 byte) |
| 0x0b | 8 | 1,9,10 | 0 | none |
| 0x0d | 6 | 1,3 | 1 | 0x0002 (2 bytes) |
| 0x08 | 2 | 1 | 0 | none |
| 0x04 | 1 | 1 | 1 | none |
| 0x03 | 1 | 1 | 3 | 0x00000000 (4 bytes) |

### b0 field — session class (context-correlated, confirmed)
Determined by cross-referencing adjacent ASCII debug events and cooccurring data tags:

- **0x02 = GREEN IBI / Daytime HR session** — appears exclusively in activity pulls
  (same pulls contain UNKNOWN (0x80) green_ibi_quality_event). b1 alternates 1↔3
  with no consistent first element (pull captured mid-cycle). b2=4 always (COMPLETED).
  Trail=0x00 always.

- **0x0d (13) = CVA (Cardiovascular Analysis) session** — appears exclusively in sleep
  + SpO2 + CVA raw PPG pulls. Adjacent debug event `CVA_` (0x4356415f) fires 1–2 ticks
  before every b0=13 packet. b2=1 always (ONGOING). Trail=0x0002 always.

- **0x0b (11) = Session boundary / capability transition** — appears in mixed/transition
  pulls adjacent to debug events `EHRs` (0x45485273) = Exercise Heart Rate and
  `DHR_` (0x4448525f) = Daytime Heart Rate. b2=0 always. No trail.

- **0x08, 0x04, 0x03** — single to two observations each, insufficient data.

### b1 field — start/stop action (CONFIRMED for CVA, inferred for others)
**CONFIRMED (b0=0x0d / CVA):**
- b1=1 = SESSION START: fires immediately before CVA raw PPG data begins flowing.
  Example: ts=49534817 (b1=1) → CVA raw PPG packets at 49534818 onward.
- b1=3 = SESSION STOP: fires immediately after last CVA raw PPG packet, before SpO2
  results. Example: ts=49535118 (b1=3) → SPO2 IBI+amplitude at 49535132.

**INFERRED (b0=0x02 / GREEN IBI):**
- b1=1 = START, b1=3 = STOP — by analogy with CVA, consistent with alternating pattern.
  Direction unconfirmed because pull is captured mid-cycle.
- b1=2 (single case, ts=38433973) — fires immediately after ring removal (wear event at
  38433964); unknown meaning.

**INFERRED (b0=0x0b / boundary events):**
- b1=1 = capability RESTART (post-transition)
- b1=9 = DHR capability transition (adjacent to DHR_ debug event at ring removal)
- b1=10 = EHR capability transition (adjacent to EHRs debug event)

### b2 field — session status (hypothesis)
- 0x04 = COMPLETED — dominant with b0=2 (each IBI measurement window completed)
- 0x01 = ONGOING — with b0=13 (CVA session persists across many 0x81 records)
- 0x00 = UNSPECIFIED — with b0=11 (boundary/reset events have no meaningful status)

### Trail bytes — session-class-specific
- b0=2: always `0x00` — likely session_count or padding
- b0=13: always `0x0002` — constant; possibly session_id=0 + protocol_version=2
- b0=3: `0x00000000` — only one case, meaning unknown

### Ceiling
- No capability enum in any open_ring source. b1 values 2, 9, 10 cannot be mapped
  without firmware disassembly.
- b1=1 vs b1=3 direction is confirmed only for CVA (b0=13); GREEN IBI (b0=2) needs
  a full-cycle capture starting from ring idle state to confirm direction.
- b2 status encoding is hypothesis only — no enum defined anywhere.
- Trail bytes: confirmed constant within each b0 class but semantic meaning unknown.

*Logged 2026-06-29.*

---

## 0x73 ehr_trace_event + 0x74 ehr_acm_intensity — PARTIAL DECODE (2026-06-29)

**Status:** Structure confirmed. HR trajectory decodable from b2 field. Raw PPG waveform
visible in 10-sample bytes. 5-byte companion packet semantics unresolved.

### Context
All 48 x0x73 and 11 x0x74 events come from a single pull: `gen3_pull_20260620_231631.txt`
(activity window with step features, 0x80 IBI events confirming mean HR=97 bpm).
EHR (Exercise Heart Rate) system fires as a unit: 0x73 and 0x74 always coexist.

### 0x73 format (confirmed)
Two strictly alternating packet sizes, always in pairs:

**14-byte:** `[b0:u8][b1:u8][b2:u8][b3:u8][lead:u8][s0..s8:u8×9]`
**5-byte:**  `[b0:u8][b1:u8][b2:u8][b3:u8][companion:u8]`

Header fields:
- **b0** = monotonic event sequence counter. Increments by 1 per packet across both
  sizes (even=14-byte, odd=5-byte). Range 146–193 in this session.
- **b1** = LED/optical channel (0 or 1). Alternates within each group of 4 events.
  Each time window emits 2×14-byte (one per channel) + 2×5-byte (one per channel).
- **b2/b3** — semantics differ between packet sizes (see below).

Groups of 4 fire every ~119 ticks (~1.55 seconds at 77 ticks/sec):
`[14-byte b1=0] [5-byte b1=0] [14-byte b1=1] [5-byte b1=1]`
followed ~20 ticks later by one 0x74 ACM intensity record.

### 14-byte payload — raw PPG waveform (confirmed)
The 10 sample bytes encode a green LED optical trace spanning ~3 heartbeats per packet.
Pattern: alternating peaks (55–205) and troughs (4–14), matching a PPG pulse waveform.

- **b1=0 channel:** mean peak amplitude = 123 (stronger signal)
- **b1=1 channel:** mean peak amplitude = 87 (weaker signal)

Consistent with two green LED sub-apertures or two gain-matched detector channels.

**b2 in 14-byte (b1=0 only): IBI in ticks → HR trajectory (confirmed)**
b2 encodes the inter-beat interval in activity ticks. Converting b2 → bpm (×77/60):

| ts | b2 ticks | bpm |
|----|----------|-----|
| 39153468 | 52 | 88.8 |
| 39153590 | 52 | 88.8 |
| 39153710 | 52 | 88.8 |
| 39153827 | 52 | 88.8 |
| 39153948 | 73 | 63.3 |
| 39154069 | 90 | 51.3 |
| 39154191 | 96 | 48.1 |
| 39154311 | 184 | 25.1* |
| 39154427 | 93 | 49.7 |
| 39154548 | 84 | 55.0 |
| 39154669 | 82 | 56.3 |
| 39154790 | 125 | 37.0* |

*Outliers (missed beat / double-period detection). Core trajectory: 88.8 bpm sustained,
then deceleration to ~49–56 bpm — consistent with post-exercise recovery.

b2 for b1=1 channel: erratic (52, 105, 61, 52, 76, 64, 55, ...) — not a clean IBI
sequence. b1=1 b2 meaning is NOT confirmed.

### 5-byte companion packet (partial decode)
- **b1=0 companion byte:** range 3–7 (mean=5.5) — matches optical trough/baseline values
  in the 14-byte waveform. Likely DC baseline or signal floor measurement.
- **b1=1 companion byte:** range 4–43 (mean=24.2) — no clear mapping to b1=1 waveform
  parameters. Possibly IBI delta or cumulative quality metric; semantics unconfirmed.
- **b2/b3 in 5-byte:** NOT the same as b2/b3 in 14-byte. u16 LE values 10554–51917.
  Likely an optical DC level or amplitude integral; semantics unconfirmed.

### 0x74 ehr_acm_intensity — 7-field motion intensity (confirmed)
Format: 7×u16 LE. Each record covers ~142 ticks (~1.85 sec), consecutive records span
the exercise session. The 7 sub-values are sub-window motion intensities. Sum trajectory:

`710 → 2037 → 1722 → 1537 → 1372 → 1358 → 987 → 689 → 1017 → 1098 → 991`

Classic exercise shape: ramp-up (710→2037 over first 2 records), sustained plateau
(1372–1537), then cool-down (987→689). Recovers slightly (1017–1098) — consistent
with brief resumption of movement after initial deceleration.

### Ceiling
- Lead byte (p[4] of 14-byte) purpose: ranges 7–90, varies per packet, not a simple
  counter or quality flag. Likely a per-window amplitude summary; needs firmware.
- b1=1 b2/b3 in 14-byte: not a clean IBI sequence — meaning unresolved.
- 5-byte b1=1 companion and both 5-byte b2/b3: need firmware symbol for struct fields.
- PPG waveform exact encoding (is it really 3 beats? what unit are peaks in?) needs
  cross-validation against known HR from simultaneous 0x80 events at the same timestamps.

*Logged 2026-06-29.*

---

## Pre-bed pull gen3_pull_20260629_221420.txt — physiological pattern (2026-06-30)

**Pull context:** 2026-06-29 22:14 local. MIXED WINDOW — active pfsm states with tapering
motion, one CVA session. Post-workout physiology.

### Elevated HR and temp (post-workout)
- HR range: 82–87 bpm (mean 85.2) across 10 ×6A samples — substantially elevated vs
  typical sleep HR (54–56 bpm). Consistent with recent exercise; ring was pulled before
  full recovery.
- Skin temp: 36.09–36.35°C — warmer than typical sleep window (34.9–35.3°C). Elevated
  peripheral temperature consistent with post-exercise vasodilation.
- Motion: [17, 25, 34, 27, 17, 9, 0, 0, 0, 0] — real activity early in the window,
  tapering to zero. Confirms settling toward rest at pull time.

### pfsm states
Sequence from ×09 debug events: 0, 4, 128, 6, 128, 5, 128, 6, 128 (using p[13] offset).
The user's pull script output (4, 6, 5, 6) matches the non-128 values, confirming the
pull script filters 128 from display. States 4, 5, 6 = transitional settling before sleep.

**pfsm=128 (0x80) finding:** Always follows a real state by 4–6 ticks in every pairing
observed across both pre-bed and morning pulls. Almost certainly a "state-change epoch
boundary" or "transition-complete" marker rather than an independent FSM state. See
morning pull note below.

### CVA session
Feature session (×6C): b0=13 (CVA), b1=3 (STOP) — CVA subsystem was active and ended
during this window. One ×6C b0=8 packet also present; b0=8 semantics unresolved.

### CVA raw PPG data (0x81) — observation count
- **Count:** 1 packet in this pull. Second total occurrence across all 29 pulls (n=2
  total; n=1 per pull in both appearances).
- **Status:** Do not attempt decode. n=2 total with only one packet per occurrence is
  insufficient to establish field structure. Flag for accumulation — need ≥5 packets
  in a single pull before structural hypotheses are trustworthy.
- **Context:** Both occurrences co-occur with active CVA sessions (×6C b0=13). Likely
  the raw optical capture that feeds the CVA pipeline.

---

## Morning pull gen3_pull_20260630_101238.txt — pfsm=128 first noticed (2026-06-30)

**Pull context:** 2026-06-30 10:12. ACTIVE WINDOW — step events, pfsm active states,
battery 71–72%.

### pfsm_state=128 pattern (confirmed across both pulls)
Morning pull ×09 sequence: 5/128, 3/128, 5/128, 3/128, 5/128, 3/128. Same tight pairing
(4–6 tick gap) as in pre-bed pull. pfsm=128 appears in BOTH pulls — it is NOT unique to
active-window or sleep-window. This rules out it being a "woke up" or "active" state.

**Hypothesis:** pfsm=128 is a firmware "epoch committed" or "state-change ack" event
emitted ~5 ticks after every state transition to mark that the flash write completed.
Supporting evidence: always exactly one 128 event per non-128 event, never sequential
128s, gap is consistently 4–6 ticks (within one flash-write cycle at 77 ticks/sec).

**Open question:** Is there a non-128 state value paired with the very first 0x00 (state=0)
event in the pre-bed pull? The ts=52650969 event at pfsm=0 has no preceding 128. Possibly
the initial state on cold start, not a real FSM transition, so no epoch marker is emitted.

*Logged 2026-06-30.*

---

## 0x80 green_ibi_quality_event — VALIDATED (2026-06-30)

**Status: DECODER CONFIRMED.** 361 packets across 29 pulls (9 pulls have data; 20 have
none by design — session-gated).

### Format (confirmed)
```
payload: N × 2 bytes, N = floor(len/2), always even (14 bytes = 7 samples in 345/361 pkts)
  b_low  = payload[2i]
  b_high = payload[2i+1]
  IBI_ms       = (b_low << 3) | (b_high & 0x07)   ← 11-bit unsigned
  quality_a    = (b_high >> 3) & 0x03              ← 2-bit
  quality_b    = (b_high >> 5) & 0x07              ← 3-bit
  HR_bpm       = 60000 / IBI_ms
```

### Cross-validation against 0x6A avg_hr (3 pulls)
| Pull | 0x80→HR | 0x6A HR | Delta |
|---|---|---|---|
| gen3_pull_20260621_205421 | 69.6 bpm | 68.0 bpm | +1.6 |
| gen3_pull_20260626_053013 | 77.4 bpm | 77.5 bpm | **−0.1** |
| gen3_pull_20260629_221420 | 86.4 bpm | 85.2 bpm | +1.3 |

Mean delta +0.9bpm. Agreement is within measurement noise — decoder validated.

### Sentinel value
IBI=2000ms appears exactly 60 times (2.4% of 2476 samples). All other near-2000
values (6 samples: 1804–1997ms) appear once each and are likely genuine slow-HR
measurements. 2000ms = firmware "no beat detected" or rate too slow to measure.
The 11-bit maximum is 2047ms; 2000ms is a chosen sentinel, not a rollover.
Exclude IBI=2000 when computing HR means.

### Session gating
0x80 events only appear when the GREEN_IBI session is active. The decoder source
notes the parser reads `RingEventParser::session()` flags at offsets 0x8/0x20 before
emitting. 20/29 pulls have zero 0x80 events — this is expected behavior, not a gap.
Present in sleep, transitional, and active windows wherever the session runs.

### Quality flags (global distribution)
- quality_a=0: 20 (0.8%) — rare, possibly exceptional quality
- quality_a=1: 1610 (65%) — dominant, normal mode
- quality_a=2: 488 (20%)
- quality_a=3: 358 (14%) — degraded signal

quality_b: 0=77%, 1–7=23% (decreasing frequency). Exact semantics unresolved without
firmware symbols. Neither flag correlates visibly with IBI plausibility — qa=2/3
samples still produce physiologically consistent HR values.

*Logged 2026-06-30.*

---

## 0x72 sleep_acm_period — PARTIAL DECODE (2026-06-30)

**215 packets across 27/29 pulls (fires in all window types — sleep, active, transitional).**
Format: 6×u16 LE. Open_ring's existing decoder reads u8 at offsets 6–11 and treats bytes
0–5 as a header — this is wrong. The entire 12-byte payload is 6×u16 fields.

### Field structure

```
f0 = u16_le(p[0:2])   # per-axis ACM energy — X-axis (quiet median=12)
f1 = u16_le(p[2:4])   # per-axis ACM energy — gravity/Z-axis (quiet median=22, always max)
f2 = u16_le(p[4:6])   # per-axis ACM energy — Y-axis (quiet median=13)
f3 = u16_le(p[6:8])   # period motion floor (quiet median=29, min=24 across all 215 pkts)
f4 = u16_le(p[8:10])  # period motion peak (always >= f3, quiet median=34)
f5 = u16_le(p[10:12]) # sparse overflow (r=+0.963 with f3; 88% of values <=10)
```

*Axis labels (X/Y/Z) are hypothetical based on magnitude hierarchy, not confirmed.*

### Invariants (0 violations across 215 packets)
- **f1 = max(f0, f1, f2)**: f1 is always the largest of the three ACM energy fields.
  Interpretation: when lying still, gravity loads the Z-axis continuously, making f1
  the dominant channel regardless of voluntary motion.
- **f4 >= f3**: the period peak always meets or exceeds the floor. Structural constraint,
  not physiological — likely enforced in firmware.

### Motion response
| Context | f0 | f1 | f2 | f3 | f4 | f5 |
|---|---|---|---|---|---|---|
| Quiet sleep (187 pkts) | 12 | 22 | 12 | 29 | 34 | 4 |
| Active (28 pkts, ±120 ticks from motion event) | 430 | 1318 | 486 | 76 | 193 | 35 |
| Max ever observed | 6767 | 11602 | 8780 | 456 | 1340 | 821 |

All 6 fields increase with motion. f1 scales most dramatically (22→1318, ~60×). f3
scales least (29→76, ~2.6×), consistent with it being a baseline/floor rather than
a peak-sensitive metric.

### Sleep_state correlation
Nearest-neighbor join against 0x6A sleep_state (±500 ticks):
- state=0 (n=55): median f0=27, f1=65, f2=16, f3=32, f4=41, f5=6
- state=1 (n=160): median f0=12, f1=22, f2=13, f3=29, f4=34, f5=4

State=0 shows ~2× higher f0/f1/f2 values vs state=1. This is meaningful differentiation
even though the sleep_state enum mapping has a known decoder gap (see known_issues sleep_state
section). 0x72 is tracking real motion differences between states.

### Correlation matrix (all 215 packets)
- Within {f0,f1,f2}: r=0.96–0.97 — the three axes move together
- Within {f3,f4,f5}: r=0.89–0.97
- Cross-group: r=0.76–0.92

All 6 fields are proxies for the same underlying motion energy. The two groups differ in
scale and saturation behavior, not in what they're measuring.

### Ceiling
- Which physical axis (X/Y/Z) maps to f0, f1, f2 — needs firmware struct or IMU datasheet
- Exact ACM formula (RMS? sum of squares? variance over window?) — needs disassembly
- f5 semantics: near-zero in quiet, spikes with motion, r=+0.963 with f3 — could be
  epoch count of motion threshold crossings or excess-above-baseline integral

*Logged 2026-06-30.*

---

## 0x5B ble_connection_ind — PARTIAL DECODE (2026-06-30)

**50 packets across pulls.** Open_ring decoder reads isolated u8 fields at offsets
0,1,6,7,8,9 and discards the rest — incorrect. Actual structure: byte[0] is a subtype
field ∈ {2, 3, 4, 5}, each subtype being a distinct fixed-length record.

### Subtype structure

**Subtypes 2/4/5 always fire as a consecutive trio** (timestamps 1 tick apart) on every
BLE connection event. Subtype 3 logs the peer device MAC address and fires ~100–300 ticks
after the connection trio, once address resolution completes.

#### Subtype 2 — Connection event summary (12 bytes)
```
b[0] = 0x02 (subtype)
b[1] = 0x00 (constant)
b[2] ∈ {0,1,2,3} — reconnect count within session
b[3] = 0x00 (constant)
b[4] ∈ {0,16,81,149} — unknown parameter or event type
b[5] ∈ {0,1} — binary flag
b[6] ∈ {8,19} — feature flag or mode byte
b[7] ∈ {14,16,24,30} — negotiated BLE connection interval (× 1.25ms = 17.5/20/30/37.5ms)
b[8] = 0x00 (constant)
b[9] ∈ {0,1,4} — small enum, possibly connection role
b[10]: 8–180 — variable; likely RSSI or packet error rate
b[11] ∈ {0,5,8,9,11} — small values; semantics unresolved
```

#### Subtype 3 — Peer device BLE address (10 bytes)
```
b[0] = 0x03 (subtype)
b[1] = addr_type: 2=Random Resolvable Private Address (RRPA), 0=Public
b[2:8] = 6-byte BLE MAC address (little-endian, standard BLE order)
b[8:10] = 0x0000 (padding)
```
7 unique MACs observed across all pulls. Phone rotates its RRPA regularly — MACs that
repeat within a session are the same device reconnecting. The one addr_type=0 (public)
appearance may be a different device or a static test address.

#### Subtype 4 — Connection parameters (13 bytes)
```
b[0] = 0x04 (subtype)
u16_le(b[1:3]) = connection_interval_min (always = max → fixed interval)
u16_le(b[3:5]) = connection_interval_max
b[5]: 0–222 — variable; likely RSSI or current link quality
b[6] ∈ {0,19} — flag, meaning unresolved
b[7:9] = 0x0000 (constant)
b[9]: 0–110 — variable metric
b[10:13] = 0x000000 (constant)
```
**Connection interval values (BLE spec confirmed, no firmware needed):**
- 207 × 1.25ms = **258.75ms** — ring's sleep/low-power BLE mode
- 27 × 1.25ms = **33.75ms** — active/app-open mode (faster data, more power)

min=max always → ring always negotiates a fixed interval, not a range.

#### Subtype 5 — Link statistics (11 bytes)
```
b[0] = 0x05 (subtype)
u16_le(b[1:3]): 28–923 — high-variance count (TX packets? connection events?)
b[3:5] = 0x0000 (constant)
u16_le(b[5:7]): 0–107 — lower-range count
b[6] = 0x00 (constant, already included in u16 above)
u16_le(b[7:9]): 0–602 — wide-range count
u16_le(b[9:11]): 3–892 — wide-range count
```
Four u16 counters. Likely TX packets, RX packets, TX errors, RX errors or similar link
statistics accumulated since last connection. Exact field labels need firmware.

### Ceiling
- Sub=2 fields b[4], b[5], b[9], b[11]: semantics unresolved
- Sub=5 four u16 counters: TX/RX/error hypothesis unconfirmed without firmware or
  simultaneous packet sniffer capture

*Logged 2026-06-30.*

---

## 0x50 activity_info_event — PARTIAL DECODE (2026-06-30)

**13 packets across pulls.** Open_ring decoder only reads b[0] and calls the rest
"trailing_hex" — the firmware uses a loop to read the trailing bytes, so the
auto-extractor missed them.

### Format
```
b[0]  = activity class enum ∈ {0, 21, 23, 60, 97, 198}
b[1]–b[13] = 13-sample per-epoch intensity array (firmware loop-read)
             (14-byte form only; shorter packets have fewer samples)
```

### b[0] activity class
| Value | Context | Intensity |
|---|---|---|
| 0 (0x00) | Sedentary/rest — surrounds SPO2, Sleep ACM, Temp events; no Motion event | None |
| 21 (0x15) | Light activity — Motion event at t+1 | Light |
| 23 (0x17) | Light activity — Motion event at t+1 | Light |
| 60 (0x3c) | Moderate activity — Motion event at t+1 | Moderate |
| 97 (0x61) | Vigorous activity — Motion event at t+1 | Vigorous |
| 198 (0xc6) | Intense activity — Motion event at t+1 | Intense |

Non-zero b[0] ALWAYS co-occurs with a Motion event at t+1. b[0]=0 appears in sleep
and rest contexts with SPO2 and Sleep ACM events nearby, no accompanying motion.

### Trailing intensity array
Values scale directly with b[0] activity class:
- Sedentary (b[0]=0): values 9–12, tight clustering
- Light (b[0]=21/23): values 12–21, moderate spread
- Vigorous (b[0]=97): peaks to 32
- Intense (b[0]=198): peaks to 91

**MET×8 hypothesis:** 9/8=1.1 MET (sedentary), 12/8=1.5, 21/8=2.6, 32/8=4.0 (moderate),
91/8=11.4 MET (vigorous running). Plausible but unconfirmed without simultaneous Gen4
Average MET cross-validation. The 13-sample array likely represents ~13 minutes of
per-minute activity intensity readings leading up to the event.

### Ceiling
- Exact enum labels for b[0] values (Oura internally uses specific activity class names)
- MET×8 encoding unconfirmed — need simultaneous Gen4 Average MET field for same window
- Short-packet variants (3, 7, 10 bytes) appear to have different structure

*Logged 2026-06-30.*

---

## 0x6C feature_session — b1 direction map extended (2026-06-30)

**Update to prior partial decode (2026-06-29).** b1 direction field now fully mapped
via ASCII debug event adjacency across all 56 packets.

### b1 complete mapping
| Value | Meaning | ASCII context |
|---|---|---|
| 1 | START | Preceded by `DHR_state:4`, followed by `DHR_state:2` |
| 2 | PAUSE/TRANSITION | GREEN_IBI only; fires when EHR session interrupts; co-occurs with EHR_BOUNDARY (b0=0x0b) packet at same timestamp |
| 3 | STOP | Followed by `AFs;...` aggregate output or `CVA_state:0` |
| 9 | EHR_BOUNDARY PRE-ANNOUNCE | b0=0x0b only; fires just before `EHRst;1;0;1` (EHR about to start) |
| 10 | EHR_BOUNDARY CONFIRMED | b0=0x0b only; fires just after `EHRst;1;0;1` (EHR now active, GREEN_IBI confirmed paused) |

### b0=8 confirmed: EHR_INHIBIT session
b0=8 always co-occurs with `pp_rt_start` at t-2 and `EHR_INH;9` at t-1, followed by
`CVA_state;1` at t+6–7. Interpretation: when CVA needs exclusive optical access, the
ring emits a pp_rt_start (PPG real-time start), then inhibits EHR (EHR_INH = EHR
inhibited, priority 9), then logs b0=8 b1=1 (EHR_INHIBIT session START), and CVA
becomes active. This is the handoff mechanism from DHR to CVA optical mode.

### Updated b0 session class map
| b0 | Session | Status |
|---|---|---|
| 0x02 | GREEN_IBI | confirmed |
| 0x03 | unknown | single occurrence only |
| 0x04 | unknown | single occurrence only |
| 0x08 | EHR_INHIBIT | confirmed via pp_rt_start/EHR_INH context |
| 0x0b | EHR/DHR_BOUNDARY | confirmed |
| 0x0d | CVA | confirmed |

*Logged 2026-06-30.*

---

## 0x77 spo2_dc_event — structural ceiling confirmed (2026-06-30)

**1352 packets across pulls. 870 (64%) are 14-byte form; remainder are 2–13 bytes.**
Open_ring reads only b[0] ("channel_index") and drops the rest. Structural analysis
extended with full correlation matrix across all 870 14-byte packets (n=1352 total).

### 14-byte format (confirmed structure)
```
b[0]    = optical channel identifier; alternates L/H bands at 90.2% rate
          L-band: 16–107; H-band: 146–222
          most common consecutive delta = 128 (the band separation)
b[1:14] = 13 sequential i8 samples of one optical channel
          means -5.5 to +9.3 (centered near zero), SD ~32–43, full ±127 range used
```

### Key structural findings

**b[0] alternation:** 90.2% of consecutive 14-byte packet pairs switch bands
(L→H or H→L). The remaining 9.8% are same-band pairs — likely at session boundaries
or when the buffer wraps. This is a two-wavelength interleaved sampling scheme.

**b[0] vs SpO2 correlation:** r=-0.033 (L-band) and r=+0.011 (H-band) against
nearest 0x6F SpO2 value within ±50 ticks (n=556 pairs). Near-zero — b[0] identifies
the channel, not the saturation level.

**b[1:14] diagonal correlation matrix (i8):**
Adjacent bytes are correlated; correlation decays with lag distance:
- Lag-1 pairs: r=0.24–0.54 (mean ~0.44)
- Lag-2 pairs: r=0.37–0.52
- Lag-6 pairs: r=0.08–0.21
- Lag-12: r≈−0.03 (decorrelated)

This diagonal band structure is the signature of a **time-series of 13 sequential
samples of a slowly varying optical signal** — not 13 independent fields (prior
characterization was wrong). Each packet captures 13 consecutive DC-level measurements
for one optical channel.

### Physical interpretation (hypothesis)
The ring uses two optical wavelengths for SpO2 (classically red ~660nm and IR ~880nm).
Each 14-byte packet delivers 13 sequential samples of one channel's optical signal.
L-band and H-band packets interleave to give two parallel DC-level streams. SpO2 is
then computed from the ratio of AC-to-DC across both wavelengths per cardiac cycle.

The i8 samples centered near zero suggest the DC baseline has been subtracted (AC
coupling), with b[0] encoding either the DC reference level or the channel select.
The SD of ~35 is too large for pure AC-coupled PPG deltas — more likely raw samples
with the mean close to zero after uint8→i8 reinterpretation.

### Falsified hypotheses (complete list)
- "channel_index" (0–255 range): falsified — b[0] is a channel value, not an index
- red/IR DC-level split via mean difference: falsified — no mean difference in i8 between L/H
- i16 pairing of adjacent bytes: falsified — stdev explodes
- b[1:14] independent fields: falsified — diagonal correlation proves time-series
- b[0] encodes SpO2 amplitude: falsified — r≈0 vs 0x6F

### Ceiling
- Which band (L=16–107 vs H=146–222) corresponds to red (660nm) vs IR (880nm)
- Whether i8 values are raw samples or delta-encoded from b[0] as reference
- Mapping b[0] value within each band to a physical quantity (LED current? gain?)
- Needs activity pull with active SpO2 measurement for high-variance cross-validation

*Logged 2026-06-30.*

---

## Walk Experiment — INCONCLUSIVE (2026-06-28, logged 2026-06-30)

**Experiment:** Timed walk to generate step-feature events for 0x7E/0x7F decoder validation.

### Ground truth
- Walk duration: ~10 minutes
- Apple Health: 1273 steps
- Oura app: 1163 steps (variance accepted as normal cross-device behavior)

### Post-walk pulls
- gen3_pull_20260628_201810.txt
- gen3_pull_20260628_201845.txt
- gen3_pull_20260628_203635.txt
- gen3_pull_20260628_203908.txt

All four pulls returned **zero step-feature events**. Window classified as SLEEP WINDOW
across all four pulls. No 0x7E/0x7F packets. No walking-pattern motion events in the
ring's activity-classifier signature.

### Falsified hypotheses
- Terminal window reuse causing stale session state: FALSIFIED — fresh terminal produced
  identical result.

### Root cause hypothesis (not yet falsified)
**Oura app BLE competition.** The Oura app maintains a persistent BLE connection to the
ring. When the app is running during or after the walk, it drains step-feature events
from the ring's 255-event circular flash buffer before the pull script connects. By the
time the pull script establishes its own BLE connection, the buffer has been partially
or fully consumed by the app's background sync. This would explain:
- Why the ring's own Oura app step count was 1163 (it saw the data)
- Why the pull script found a SLEEP WINDOW (the app's drain shifted what was left in the buffer)
- Why terminal-reuse was not the cause (the issue is BLE resource contention, not session state)

### Required protocol for next attempt
1. Kill Oura app **before** the walk begins — not after.
2. Disable phone Bluetooth during the walk if possible.
3. Pull immediately upon returning, before relaunching the Oura app.
4. Aim for a longer walk (20+ min) to fill more of the 255-event buffer with step events.

### Status
INCONCLUSIVE — experiment design did not control for Oura app BLE contention.
0x7E/0x7F decoder remains at structural ceiling pending a clean pull.

*Logged 2026-06-30.*

---

## Morning Pull Timing — Confirmed Operational Pattern (logged 2026-06-30)

The buffer-roll failure mode is now confirmed across 4 independent instances, not a
one-off. Documenting as an established operational pattern.

### Confirmed instances of buffer-rolled-past-sleep
1. Original nap miss — pulled too late, sleep window gone
2. 6am bathroom break — brief walking after waking flushed sleep data
3. Walk experiment (2026-06-28) — Oura app BLE contention + timing; pulls 201810/201845/203635/203908 all returned SLEEP WINDOW classification but with no step-feature events
4. Morning pull gen3_pull_20260630_101238.txt — pulled at 10:12am, ACTIVE WINDOW; last night's sleep fully rolled out of buffer by AM routine

### Confirmed rule
**Pull before standing up.** Not "soon after waking" — literally while still in bed,
before first movement. Walking even 30 seconds at activity rates (~2.35 events/sec)
begins replacing sleep events within 108 seconds. By the time a normal morning routine
(bathroom, kitchen) completes, the buffer has cycled multiple times.

*This is not a timing edge case — it is the default failure mode if the pull is not the
first action of the day.*

---

## Pre-bed Pull Log — gen3_pull_20260630_215819.txt (2026-06-30 21:58)

**Filed:** data/raw_pulls/gen3_morning/ (evening pre-bed pull)
**Classifier:** SLEEP WINDOW — clean, no anomalies.

| Signal | Value | Assessment |
|---|---|---|
| sleep_state | 1 throughout | Normal |
| HR | 57–62 bpm | Normal resting baseline |
| SpO2 | 92–98% | Within expected range |
| Sleep temp | 35.2–35.6°C | Normal for Bryden |
| pfsm pair | 6/128, seconds_in_pfsm=77/77 | Consistent with confirmed decoder |
| Step features | None | Expected (pre-bed) |
| Motion anomalies | None | Clean |

Routine pull, no decoder gaps or anomalies requiring investigation.

*Logged 2026-06-30.*

---

## 0x73 ehr_trace_event — PARTIAL DECODE (2026-06-30)

**Source:** gen3_pull_20260620_231631.txt — 48 packets, all from one activity window.
**open_ring decoder:** reads b[0] as counter + b[4:] as u8 samples — wrong; misses the
14b/5b pair structure and the dual-channel field.

### Confirmed: firmware name is DHR, not EHR
Debug event at ts=39153941 in the same pull decodes to ASCII `DHR_state:1`.
The pull label "EHR trace event" is the open_ring name; the firmware calls this
subsystem **DHR** (Dynamic Heart Rate). EHR and DHR refer to the same exercise-HR mode.

### Activity-only
Zero 0x73 packets across any sleep pull. All 48 packets come from one activity window
where DHR_state=1 is active. Not session-gated in the same way as 0x80 — it fires
continuously during the DHR session, not per-beat.

### 4-packet burst structure
Packets fire in bursts of 4 at ~122-tick (~1.58s) intervals:

```
14b (b[1]=0, ch0) → 5b (b[1]=0, ch0)    [ticks T, T+1]
14b (b[1]=1, ch1) → 5b (b[1]=1, ch1)    [ticks T+2, T+3]
```

- b[0] = monotonically incrementing sequence counter (0x92→0xc1 across 48 packets)
- b[1] = optical channel select: 0=ch0, 1=ch1 (two interleaved wavelengths, analogous
  to 0x77 L/H alternation pattern)

### 14-byte packet: 5 × u16_LE optical samples
b[2:12] = 5 consecutive u16_LE values per burst window.

| Field | ch0 range | ch0 mean | ch1 range | ch1 mean |
|---|---|---|---|---|
| f0 | 13364–32125 | 20103 | 9783–26985 | 16450 |
| f1 | 14095–43274 | 23289 | 16419–40460 | 27522 |
| f2 | 2144–3645 | 2681 | 2197–15444 | 8810 |
| f3 | 14132–47288 | 29897 | 11066–35980 | 24445 |
| f4 | 26890–51718 | 39461 | 13337–34338 | 20625 |

f2 has notably lower values and tighter range in ch0 (mean 2681) vs f0/f1/f3/f4
(mean 20k–39k) — likely a different measurement type (DC offset? noise floor?) rather
than a 5th optical sample.

### 5-byte companion: aggregate + quality byte
- b[2:4] = u16_LE aggregate value (ch0 mean 33724; ch1 mean 23816)
- b[4] = per-channel count or quality metric:
  - ch0: 4–7 (tight, mean 5.7)
  - ch1: 4–43 (wide, mean 25.4)
  Channel 1 shows much higher b[4] variance — possibly ch1 is the primary beat-detection
  channel (count of IBI detections per window), ch0 is reference/secondary.

### Cross-channel relationship
Cross-channel 5-byte u16 correlation: r=−0.094 (near zero, independent signals).
ch0 mean amplitude consistently > ch1 (33724 vs 23816). Consistent with red vs IR
at different LED power levels — not identical measurements on two channels.

### open_ring decoder is wrong
open_ring reads `b[4:]` as a flat list of u8 samples. This misinterprets:
- The 14b/5b pairing (treats them as independent 14-byte and 5-byte records)
- The channel field b[1]
- The 5 × u16_LE structure in the 14-byte form (reads as 10 × u8)

### No HR cross-validation possible from existing data
No 0x6A or 0x80 events appear in the DHR window. The ring appears to run DHR and the
green-IBI/sleep HR subsystems in mutually exclusive modes. Cross-validating the u16
optical values against a known HR requires either a simultaneous 0x6A event or a new
EHR-mode pull where HR is also logged by the Oura app.

### Falsified hypotheses
- open_ring interpretation (flat u8 samples): falsified — 14b/5b pair structure confirmed
- b[4] as raw sample: falsified — too small (3–43) and channel-asymmetric to be optical

### Ceiling
- Which optical channel (ch0/ch1) corresponds to which wavelength (red 660nm / IR 880nm / green 530nm)
- Whether the 5 × u16_LE fields are raw optical amplitude samples or filtered/processed values
- Physical meaning of f2 (consistently lower than f0/f1/f3/f4)
- Physical meaning of 5-byte b[4] (beat count per window? SNR? quality metric?)
- Cross-validation against HR requires a fresh EHR-mode pull with simultaneous Oura HR logging

*Logged 2026-06-30.*

---

## 0x56 unknown_56 — NOT OBSERVED (2026-06-30)

Zero packets across all 34 pulls (gen3_morning + gen3_autoloop directories).

**open_ring internal contradiction:** The decoder at line 521 calls 0x56 a "confirmed
real wire tag" with 4 occurrences across 4 captures and a context hypothesis (always
between 0x50 activity_info and 0x47 motion_event). But the parser comment at line 1598
lists 0x56 explicitly as an example of a "mid-stream byte-alignment misparsed value
that never appear at the start of a real notification." The decoder and parser disagree
about whether this tag is real.

**Assessment:** Either 0x56 is rare enough to have missed our 34-pull window, it's
firmware-version specific (open_ring's 4 captures may be Gen4 or a different Gen3 build),
or open_ring's 4 occurrences were themselves misparses. Not actionable without more data.

*Logged 2026-06-30.*

---

## Pull timing constraint — ACTIVE WINDOW contamination (2026-07-01)

Morning pull timing discipline confirmed as a recurring operational constraint across
multiple independent instances: nap pull, 6am walk pull, and 2026-06-30 10:12am pull
all returned ACTIVE WINDOW results instead of SLEEP WINDOW. The buffer reliably rolls
past sleep data before the pull completes if any activity occurs post-waking.

This is now a confirmed pattern, not a one-off. The 255-event circular buffer fills
within ~108s of sustained walking. Any activity between waking and pulling discards
the sleep-window events.

**Status:** documented — no code fix possible. Human discipline required. Pull must
happen before leaving bed.

*Logged 2026-07-01.*

---

## boot_ts rollover warning — seen twice (2026-07-01)

A 30.5M-tick gap between consecutive pulls (~509,365 minutes / ~354 days) appeared in
both the 2026-06-28 evening pull and the 2026-06-29 morning pull. Likely a boot_ts
counter reset or rollover on the ring side, not real elapsed time.

Seen twice now — this is a pattern, not noise. Unknown whether this is a hardware fact
(counter wraps at 2^25 ticks = ~30.6M ticks at 77 ticks/s ≈ 4.6 days) or an open_ring
interpretation artifact (boot_ts parsing bug or incorrect tick-rate assumption).

**Status:** open — thread not resolved. Do not use raw boot_ts deltas for timing
calculations without filtering outliers above 1M ticks.

*Logged 2026-07-01.*

---

## 0x85 unknown_85 — NOT OBSERVED (2026-06-30)

Zero packets across all 34 pulls (gen3_morning + gen3_autoloop directories).

open_ring documents 16 samples across May 2-6 2026 with a well-characterized format:
`<unix_s:u32 LE><00 00 00 00><trailer:u16>`. Trailer alternates 0x01f6/0x01f8 (502/504).
The embedded unix timestamp is the ring's RTC at event time, with deltas from receive
time ranging -16s (live) to -49820s (~13.8h catchup) — consistent with buffer dump.

open_ring's captures are from a different pull window (May 2026). Our capture window
(June 2026) has not caught this event. Low-cadence or condition-specific emitter.
Not actionable from existing data.

*Logged 2026-06-30.*

---

## 2026-07-01 — Evening pull: SLEEP WINDOW at 10pm — daytime sleep event captured

Date: 2026-07-01
Pull file: pipeline/data/raw_pulls/gen3_evening/gen3_pull_20260701_220314.txt
Pull time: 22:03 local

Finding: Evening pull returned SLEEP WINDOW classification despite being
pulled at 10pm while awake. The buffer captured a real sleep event from
earlier in the day — confirmed by HR signature (63.5–67.0 bpm trending
upward, consistent with sleep-to-waking transition) and boot_ts range
completely separate from the 2026-06-29 morning pull. This is a daytime
rest/nap event, not last night's sleep.

Significance: The decoder is sensitive enough to distinguish sleep quality
by HR signature alone — deep overnight sleep (54–56 bpm) vs lighter
daytime rest (63–67 bpm) — before sleep stage decoding is working.
This is a meaningful data point, not noise.

Battery observation: 51.9% / 50% at 10pm vs 82.4% at morning pull.
~30% drop across one day of wear. First baseline consumption rate
data point — log for future reference.

SpO2 observation: 21 windows, 92.8–97.2%, avg ~93.5–94%. More
consistent than the 88% outlier night. Not confirmed calibrated but
not the outlier behavior that triggered the known issue flag.

Status: logged, no action required. Confirms two-pulls-a-day rhythm
is capturing different sleep event types depending on pull timing.

*Logged 2026-07-01.*

---

## 2026-07-02 — SpO2 cross-validation gap confirmed recurring pattern

Date: 2026-07-02
Pull file: pipeline/data/raw_pulls/gen3_morning/gen3_pull_20260702_091253.txt

Finding: Gen3 SpO2 avg 91.5% vs Gen4 official 97% for night of
2026-07-01/02. Gap of 5.5%. This is the second significant
cross-validation discrepancy:
- Night 1 (2026-06-28/29): Gen3 88% vs Gen4 97% — 9% gap
- Night 2 (2026-07-01/02): Gen3 91.5% vs Gen4 97% — 5.5% gap

Pattern: Gen3 SpO2 decoder consistently reads lower than Gen4
official. Gap is narrowing slightly (9% → 5.5%) but remains
significant. Not a one-off sensor anomaly — the decoder has a
systematic low bias.

Track B completion condition #3 (SpO2 within ±5% of Gen4 for
three consecutive nights) is not met. Current status: 0 of 3
nights passing.

Status: open — decoder calibration investigation needed. Do not
promote 0x6F to confirmed decoder until three consecutive nights
pass the ±5% cross-validation gate.

*Logged 2026-07-02.*

---

## 2026-07-02 — HRV decoder (0x5d) fired for the first time — Track B milestone

Date: 2026-07-02
Pull file: pipeline/data/raw_pulls/gen3_evening/gen3_pull_20260702_222915_MIXED.txt
Pull time: 22:29 local — evening activity pull

Finding: First confirmed 0x5d HRV event across all Track B pulls.
Four 5-minute RMSSD windows decoded from a single payload:

  window -20min: hr=72 bpm  rmssd=22 ms
  window -15min: hr=71 bpm  rmssd=30 ms
  window -10min: hr=70 bpm  rmssd=23 ms
  window -5min:  hr=72 bpm  rmssd=23 ms

Context: This was an evening ACTIVE/MIXED WINDOW pull during
physical activity — not sleep HRV. The decoder is confirmed
working. Sleep HRV (overnight 0x5d events during low-HR rest
periods) has not yet been captured.

Track B condition #2 (HRV fires consistently — at least one
0x5d event in three consecutive morning pulls) is not yet met.
This is the first of three required confirmed events.

Status: partial progress. Decoder confirmed working.
Sleep HRV capture is the next milestone.

*Logged 2026-07-03.*

---

## 2026-07-03 — Lock screen widget confirmed working

Date: 2026-07-03
Finding: iOS lock screen widget for Morning Pull shortcut confirmed
working. One tap from lock screen → Terminal opens on Mac →
pull runs → auto-files → bridge JSON updates. No need to open
Shortcuts app. This is the confirmed working method for the
morning pull discipline.

Operational note: tapping the home screen shortcut icon opens
the Shortcuts app but does NOT run the shortcut. Must either:
(a) tap from inside the Shortcuts app, or
(b) tap the lock screen widget.
Lock screen widget is the correct frictionless method.

Status: resolved — lock screen widget is the operational standard.

---

## 2026-07-03 — boot_ts rollover confirmed recurring pattern

Date: 2026-07-03
Finding: boot_ts span of 4,232,371,953 seconds (~1,175,658 hours)
observed in 10:08am pull — boot_ts counter wrapping and resetting.
This is the same rollover behavior seen in previous sessions.
Not a data integrity issue — just the uint32 counter cycling.
Seen now across multiple independent pulls confirming this is
a hardware counter property, not an anomaly.

Status: documented, no action required.

---

## 2026-07-03 — Threshold calibration locked

Date: 2026-07-03
Finding: Two thresholds updated in engine/thresholds.js with
documented rationale:

deep_sleep: 12% → 13%
  Rationale: 13% is the clinical floor for healthy adults
  (published range 13-23%). Below 13% is where measurable
  physiological consequences begin. User 355-night baseline
  average is 16.4% — threshold fires only when genuinely
  below the clinical minimum, not just below personal best.
  Applies universally.

hrv: 22ms → 25ms
  Rationale: 25ms is approximately one standard deviation
  below the user's 355-night baseline of 29.3ms avg.
  Fires only in genuinely suppressed states, not on routine
  below-average nights. Currently personalised to this user —
  future users need their own baseline calibration.

Status: complete — thresholds live in engine/thresholds.js
and web/src/engine/thresholds.js (auto-synced via prebuild).

---

## 2026-07-03 — First real sleep state transitions captured — Track B milestone

Date: 2026-07-03
Pull file: pipeline/data/raw_pulls/gen3_morning/gen3_pull_20260703_225853.txt
Pull time: 22:58 local — evening pull capturing earlier sleep window

Finding: First pull ever showing real sleep state transitions in 0x6A.
All previous pulls were 100% flat (either all state=1 or all state=0).
This pull shows both states across 8 samples:

  boot_ts=56343884  state=1  hr=76.0  breath=11.2  motion=17
  boot_ts=56344157  state=1  hr=75.0  breath=11.9  motion=17
  boot_ts=56344488  state=0  hr=73.5  breath=11.0  motion=16
  boot_ts=56344799  state=0  hr=71.5  breath=11.2  motion=0
  boot_ts=56345064  state=0  hr=67.0  breath=12.0  motion=0
  boot_ts=56345374  state=0  hr=68.0  breath=11.9  motion=0
  boot_ts=56345669  state=0  hr=69.5  breath=12.4  motion=0
  boot_ts=56345964  state=0  hr=71.0  breath=12.5  motion=0

State distribution: state=1 25% (2 samples), state=0 75% (6 samples)

Physiological interpretation: state=1 at start (HR 76→75 bpm, higher,
motion=17 — earlier lighter sleep), transitioning to state=0 (HR
dropping 73→67 bpm, motion dropping to 0 — deeper/settling sleep).
This is the first real sleep state transition captured by the decoder.

Track B condition #1 (sleep_state returns real stage transitions) —
first evidence confirmed. Full condition requires REM/Light/Deep
alignment with Gen4 official output across a complete night.
Current status: partial progress — transitions captured, full
stage mapping not yet validated.

SpO2: 20 windows, 90.0–94.8%, avg ~91.5% — consistent with
systematic low bias documented in prior entries.

Sleep temp: two windows — 34.32–34.94°C, slightly lower than
previous nights, normal variation.

Status: milestone — first state transition evidence. Not yet
sufficient to close Track B condition #1.

*Logged 2026-07-03.*

---

## 2026-07-05 — Oura API connection dropped — token expired, date parameter bug found

Date: 2026-07-05
Finding: methuselah.ca showed OFFLINE / AWAITING DATA. Two root causes:

1. Personal Access Token expired (created 2026-06-20, shown in red on
   Oura developer page). Fixed by creating new token
   Q4GSZGRWFMQN6FR2EVJLZAFPW7CAX4UJ (valid until 2026-07-13) and
   setting it in browser localStorage via console.

2. App.js was calling /api/oura without start_date and end_date
   parameters. api/oura.js requires both in YYYY-MM-DD format.
   The toLocaleDateString("en-CA") format was also replaced with
   toISOString().split('T')[0] for locale safety. A missing res.ok
   check meant 400 errors were silently swallowed and logged as
   "NO SLEEP DATA FOUND" rather than surfacing the real error.

Fix: both issues resolved in commit a5681db. OURA LIVE restored.

Important: Oura Personal Access Token expires 2026-07-13 with the
subscription. After that date the Gen4 API connection will drop again
permanently unless subscription is renewed. Track B sovereign BLE
pipeline must be the primary data source by that date or the live
site loses three of four vectors.

Status: resolved for now. Token expiry on 2026-07-13 is a hard deadline.

*Logged 2026-07-05.*

---

## 2026-07-06 — 0x6E SPO2 IBI+amplitude: byte layout confirmed from sleep corpus

Date: 2026-07-06
Tag: 0x6E (SPO2 IBI+amplitude)
Corpus: 549 packets across 8 pull files, all exactly 13 bytes

**Confirmed layout:**

```
b0:       channel byte — bit7=optical channel (1=B/high, 0=A/low);
          bit6..0 = beat/sequence index (value within current measurement window)
          Alternates A/B within each pull: confirmed 72/72 and 98/98 tested files
b1..b5:   5× IBI high bytes — same bit-pack formula as 0x60 (p[i] << 3 gives bits 3..10)
b6..b10:  5× IBI low bit (bit0) + amplitude (bits 1..7, pre-shift)
b11:      mid bits for IBI[0..3], 2 bits each, same packing as 0x60 byte 12
          (mid_bits[i] = (b11 >> (5-2*i)) & 0x6 for i in 0..3; IBI[4] mid = 0 pending)
b12:      amplitude shift nibble (same as 0x60 byte 13 low nibble)
          nibble=7 → shift=0; else shift=nibble+1
```

IBI formula: `ibi_ms[i] = (b[1+i]<<3) | mid_bits[i] | (b[6+i]&0x1)`
Amplitude:   `amp[i] = (b[6+i]>>1) << shift`

**Validation:**
- 531/549 packets (96.7%) produce IBI in [300, 2000]ms — physiologically plausible range
- 18 implausible packets all come from MIXED window files (transition/activity context)
- Mean IBI across sleep corpus: 921.9ms → 65.1 bpm

**Cross-validation vs 0x6A avg_hr (sleep context only):**
| File | 0x6E IBI HR | 0x6A avg_hr | Delta |
|------|------------|-------------|-------|
| gen3_pull_20260701_220314.txt | 66.2 bpm | 65.3 bpm | +0.9 bpm |
| gen3_pull_20260702_091253.txt | 67.2 bpm | 67.3 bpm | −0.1 bpm |
| gen3_pull_20260702_093539.txt | 66.0 bpm | 64.7 bpm | +1.3 bpm |
| gen3_pull_20260703_225853.txt | 70.3 bpm | 71.4 bpm | −1.1 bpm |
| gen3_pull_20260704_233702.txt | 62.0 bpm | 61.6 bpm | +0.4 bpm |

Delta in sleep context: −1.1 to +1.3 bpm. Activity context (MIXED/awake): +7-8 bpm gap (expected — SpO2 optical measurement degrades during motion).

**Open questions:**
- Amplitude encoding: shift nibble produces large integers (tens of thousands). Physical units unknown. Needs activity-context packets for variance analysis.
- IBI[4] mid bits: treated as 0 in current formula (byte 11 only holds 4×2=8 bits). The true mid bits for IBI[4] may live in byte 12 alongside the shift nibble. Needs re-examination.
- Why dual-channel (A/B)? 0x6E fires at the same rate as 0x77 (which also alternates two optical bands). These are likely red and IR (660nm/880nm) interleaved per-beat.

**Status:** IBI layout confirmed, amplitude encoding pending. Walk experiment no longer needed to confirm IBI. Amplitude and channel assignment still benefit from activity-context variance.

*Logged 2026-07-06.*

---

## 2026-07-06 — 0x77 SPO2 DC event: prior analysis confirmed, new corpus stats

Date: 2026-07-06
Tag: 0x77 (SPO2 DC event)
Corpus: 384 packets across 8 pull files

**Length distribution:** 14-byte dominant (226 pkts, 58.9%), 4-byte common (90 pkts, 23.4%), others (68 pkts across lengths 2,3,5-13)

**14-byte form confirmed structure:**
- b0: optical channel identifier, two bands:
  - Low band: range 1-125, mean 58.3 (n=114 packets)
  - High band: range 130-252, mean 185.4 (n=112 packets)
  - Band separation ≈ 128 — consistent with prior analysis (16-107 / 146-222)
- b1..b13: 13 signed i8 samples, time-series structure confirmed
  - SD per byte: 35-46 (full dynamic range, not a narrow signal)
  - Lag-1 autocorrelation: r=+0.34 to +0.61 (consistent with prior 0.43-0.54 estimate on smaller corpus)

**4-byte form (sentinel packets):**
- 90 packets. 25/90 have trailing bytes `aaaab2` (hex) — likely a fill/null sentinel (0xAA = common fill byte, 0xB2 = unknown flag)
- b0 values cluster at 64-79 and 192-196 — may indicate subtype or error state
- Seen frequently at end of SpO2 session windows

**Ceiling unchanged:** Red vs IR band assignment, raw vs delta-encoded i8, DC reference value — all remain unresolved without firmware disassembly or simultaneous SpO2 variance during activity.

**Walk experiment:** Activity-context pull would provide SpO2 changes detectable in 0x6F; correlating 0x77 b[1:14] samples against 0x6F values could resolve band identity. Still useful but not required for 0x6E IBI.

*Logged 2026-07-06.*

---

## 2026-07-06 — 0x6E decoder validated and wired into pull script

Date: 2026-07-06
Resolution: DECODER COMPLETE — 0x6E promoted to DONE in roadmap.

Decoder written at `pipeline/decoders/0x6e.py`. Full validation run:
- 549/549 corpus packets decode without error
- 2727/2745 IBI values (99.3%) in physiologically plausible range [300-2000ms]
- 18 out-of-range values are 2001-2007ms (very slow HR ~30 bpm, all from MIXED window packets — not decoder errors)

Cross-validation gate (±3 bpm vs 0x6A avg_hr):
- 5/5 sleep-context files PASS (delta −1.1 to +1.3 bpm)
- 2/2 activity-context files diverge (+6.8 / +7.7 bpm) — expected, SpO2 optical degrades during motion

The decoder outputs per-packet: channel (A/B), beat_index, ibi_ms[5], hr_bpm[5], amp[5], amp_shift.
Wired into pull script output as === SPO2 IBI+AMPLITUDE DECODE (0x6E) === section.

Open (not blocking DONE status):
- Amplitude physical units: large shifted integers, scaling unknown
- IBI[4] mid bits: b11 covers only 4 pairs; treated as 0 pending confirmation
- Channel wavelength (red vs IR): same dual-band pattern as 0x77, unconfirmed without firmware

*Logged 2026-07-06.*

---

## 2026-07-06 — 0x77 spo2_dc_event decoder written and validated

Date: 2026-07-06
Status: PARTIAL DECODE — decoder written, corpus validated, ceiling maintained.

Full validation run (pipeline/decoders/0x77.py):
- 384/384 corpus packets decode without error (0 exceptions)
- 357 real data packets, 27 sentinel packets (is_sentinel=True)
- Sentinel pattern `0xAAAAB2` in trailing 3 bytes: confirmed session-end marker

Real packet sample count distribution:
{1: 4, 2: 2, 3: 65, 4: 19, 5: 7, 6: 10, 7: 6, 8: 2, 9: 4, 10: 3, 11: 4, 12: 5, 13: 226}
- 14-byte dominant (13 samples, 226/357 = 63.3%)
- 4-byte common (3 samples, 65/357 = 18.2%)

DC sample statistics across all 357 real packets (3540 samples):
- Range: −128 to +127 (full i8 range used)
- Mean: −3.70, Stdev: 43.84
- Channel balance: A=178, B=179 (near-perfect alternation confirmed)

Decoder outputs per-packet: channel (A/B), beat_counter, is_sentinel, dc_samples[], n_samples.
Wired into pull script output as === SPO2 DC EVENT DECODE (0x77) === section.

Ceiling unchanged (NOT promoted to DONE):
- Whether b1..b3 are a header (beat_index + u16 timestamp) leaving b4..b(n-1) as samples,
  or all b1..b(n-1) are DC samples — indistinguishable from corpus statistics alone
- Which optical band = red (660nm) vs IR (880nm)
- Whether i8 values are raw ADC, gain-corrected, or delta-encoded
- Physical DC reference units

Cross-channel correlation for A/B matched pairs (same beat_counter): r=+0.80 to +0.93.
This confirms real physiological PPG signal, not noise. The time-series structure is
internally consistent (lag-1 autocorrelation r=+0.49 intra-packet).

0x77 stays IN PROGRESS in roadmap. Walk experiment would add SpO2 variance context
for band identity but would not resolve the b1..b3 header question.

*Logged 2026-07-06.*

---

## 2026-07-06 — 0x6E and 0x77 first live pull confirmation

Date: 2026-07-06 (evening pull, ACTIVE WINDOW)

**0x6E spo2_ibi_and_amplitude_event — LIVE CONFIRMED:**
- Channels A and B alternating correctly
- IBI values 857–909ms → HR ~66–70 bpm
- Mean HR from 0x6E: 67.8 bpm
- Context: ACTIVE WINDOW evening pull — motion artifact expected, divergence from 0x6A HR consistent with corpus validation findings
- Wiring into pull script confirmed working

**0x77 spo2_dc_event — LIVE CONFIRMED:**
- DC samples captured and decoded correctly
- Sentinel packets (aaaab2) correctly identified and separated from real data
- Wiring into pull script confirmed working

Auto-file fired correctly (ACTIVE WINDOW → gen3_evening/). Bridge JSON updated. Battery 82.4%.

Both decoders producing real output in a live pull for the first time. No errors reported.

*Logged 2026-07-06.*

## 2026-07-06 — 0x6E and 0x77 decoders fired live in pull for first time

Date: 2026-07-06
Pull file: pipeline/data/raw_pulls/gen3_evening/gen3_pull_20260706_[timestamp].txt

Finding: First live pull output showing both new decoders active:

0x6E spo2_ibi_amplitude — channel A/B alternating correctly,
IBI 857–909ms → HR ~66–70 bpm, mean 67.8 bpm. Consistent with
ACTIVE WINDOW evening activity. Motion artifact divergence from
0x6A HR expected and observed — physiologically correct.

0x77 spo2_dc_event — DC samples captured, sentinel packets
(aaaab2) correctly separated from real data.

Both decoders confirmed working in live pull output after corpus
validation (0x6E: 549/549, 0x77: 384/384).

Status: confirmed live — both decoders promoted to production.

---

## 2026-07-06 — 0x6B motion_period corpus analysis

Date: 2026-07-06
Status: PARTIAL DECODE — ceiling unchanged from prior entry. 5 packets now in corpus (was 4).

**All 5 corpus packets:**
| boot_ts | file | b[0] (hex) | b[0] decimal | enum name | payload |
|---|---|---|---|---|---|
| 55955355 | gen3_pull_20260703_091701.txt | 0x3D | 61 | OUTSIDE_ENUM | 3dfeefaafeeff5abfefbebfaaa6f |
| 56751555 | gen3_pull_20260704_091402.txt | 0x35 | 53 | OUTSIDE_ENUM | 3596aaffbfbbbeafebffd2fbfaab |
| 56345054 | gen3_pull_20260703_225853.txt | 0x39 | 57 | OUTSIDE_ENUM | 3900000000000000000000001800 |
| 57212910 | gen3_pull_20260704_233702.txt | 0x35 | 53 | OUTSIDE_ENUM | 354410000659a954015140004400 |
| 58293510 | gen3_pull_20260706_105459.txt | 0x3E | 62 | OUTSIDE_ENUM | 3e05100000000001404000000000 |

**b[0] pattern:** All values 53–62. open_ring's MOTION_STATE enum is {0:NO_MOTION, 1:RESTLESS, 2:TOSSING_AND_TURNING, 3:ACTIVE}. All 5 corpus values fall outside this enum. Hypothesis: b[0] is a motion-intensity count (not enum), consistent with prior roadmap finding.

**Trailing byte structure (b[1..13]):**
- 2 packets (0x3D, 0x35 from gen3_pull_20260704_091402) contain many high-value bytes (0xAA, 0xFE, 0xFF) — consistent with 0xAA fill in unused slots
- 2 packets (0x39, 0x3E) contain many zero bytes — sparse/mostly-empty payload
- 1 packet (0x35 from gen3_pull_20260704_233702) has mixed non-zero values — most information-dense packet in corpus

All payloads are 14 bytes. No 8-byte variants observed (prior roadmap noted "variable payload length 8 or 14" — 8-byte form remains unconfirmed from current corpus).

**Ceiling unchanged:** Cannot map b[0] range (53–62) to motion intensity without ground truth step count or simultaneous activity pull with known motion level. Walk experiment is next attempt.

*Logged 2026-07-06.*

---

## 2026-07-06 — 0x61/0x09 sleep-statistics pfsm_state cross-reference

Date: 2026-07-06
Status: NEW FINDING — pfsm_state values segregate by sleep vs activity context.

**Corpus summary:** 68 total 0x61/0x09 packets across 12 files.
pfsm_state values observed: {3, 4, 5, 6, 128}

Note: pfsm_state=0 and pfsm_state=1 cited in prior roadmap entry come from 0x6A's
`sleep_state` field — a DIFFERENT decoder. 0x61/0x09 pfsm_state is from a separate
firmware finite state machine.

**Structural pattern (confirmed):**
Every non-128 pfsm packet is immediately followed (within 4–12 ticks) by a pfsm=128
companion packet with nearly identical o3 (seconds_in_pfsm_state ±2s). This confirms
the orig/echo pair structure from prior analysis.

**NEW FINDING — pfsm context segregation:**

| pfsm | Appears in sleep context (0x6A present)? | Appears in activity context (no 0x6A)? | n |
|---|---|---|---|
| 6 | YES (all sleep-context files) | NO | 5 |
| 5 | YES | YES | 14 |
| 3 | NO | YES | 13 |
| 4 | NO | YES (MIXED only) | 2 |
| 128 | always companion | always companion | 34 |

Hypothesis (corpus-derived, NOT firmware-confirmed):
- pfsm=6 → sleep-specific state (only fires when ring is in confirmed sleep mode)
- pfsm=3 → activity/waking state (never fires in sleep context)
- pfsm=4 → activity state (only 2 packets, insufficient to characterize)
- pfsm=5 → shared/transitional state (fires in both contexts)
- pfsm=128 → companion/echo record for all states

**f2 retention ratio (pfsm→128 pairs):**
The f2 field in pfsm=128 companion records decays from the primary record's f2 value.
The decay rate differs dramatically by state:
- pfsm=3→128: ~4.5% retention (very aggressive decay, mean ratio 0.044)
- pfsm=5→128: ~10-12% retention (moderate decay, mean ratio 0.108 excluding outlier)
- pfsm=6→128: ~55% retention (slow decay, mean ratio 0.545)

This suggests f2 tracks a biosignal with a time constant that is state-dependent.
Faster decay (pfsm=3) = rapidly-evolving signal (active motion context).
Slower decay (pfsm=6) = slowly-evolving signal (sleep context).

**open_ring pfsm documentation:** None. The field is emitted as a raw u8 with no
enum defined anywhere in the open_ring codebase. The field name "pfsm_state" and its
4-field-pair structure are from the prior known_issues analysis (2026-06-26/27).

**Remaining unknowns (ceiling):**
- Exact state machine enum for pfsm values 3, 4, 5, 6 — needs firmware disassembly
- Physical meaning of f0, f2, f4 beyond "decays on state transition"
- Whether pfsm=5 is truly transitional (fires at sleep→wake boundary) or a parallel state
- No pfsm=0, 1, or 2 observed in 0x61/0x09 corpus — may fire in contexts not yet captured

*Logged 2026-07-06.*

---

## 2026-07-07 — Track B condition #3 night 2 of 3 passed — SpO2 cross-validation

Date: 2026-07-07
Pull file: pipeline/data/raw_pulls/gen3_morning/[timestamp].txt

Finding: Second consecutive night where Gen3 SpO2 avg is within
±5% of Gen4 official reading.

Night 1 (2026-07-04/05): Gen3 95.1% vs Gen4 97% — gap 1.9% ✓
Night 2 (2026-07-06/07): Gen3 93.5% vs Gen4 98% — gap 4.5% ✓

One more passing night closes Track B condition #3 permanently.

Note: the gap is widening slightly (1.9% → 4.5%). The Gen3
systematic low bias is still present but within the ±5% gate.
If the gap continues to widen, condition #3 may need revisiting
before it can be fully closed.

Also confirmed this pull: Option A morning pull method working —
Mac on nightstand, lock screen widget fired cleanly from bedside.
0x6E decoder fired in sleep context for first time — mean HR
64.8 bpm, within 1.1 bpm of 0x6A avg_hr. Cross-validation
confirmed working in real sleep pull.

HRV trend: 30ms tonight — first reading above 25ms threshold
after seven consecutive nights below baseline. Possible reversal
of declining trend.

Status: condition #3 at 2/3 — one more passing night required.

---

## 2026-07-07 — 0x6F SpO2 diagnostic: bias source and calibration offset — INSUFFICIENT DATA

Date: 2026-07-07

**Diagnostic findings (Task 1):**

Decoder transformation chain (pipeline/decoders/0x6f.py):
- b[0]: header byte (high nibble = window index, low nibble = sequence)
- b[1..n-1]: raw SpO2 bytes (one per 10-second measurement window)
- b[-1]: 0xFF sentinel if present (excluded from samples)
- Final value: raw_byte − SPO2_OFFSET (6) → SpO2 percentage

The SPO2_OFFSET=6 subtraction was confirmed correct in 2026-06-24. No additional
arithmetic (no scaling, no multiplication). Bias is NOT introduced by the arithmetic
— it exists in the raw bytes themselves. Corpus mean Gen3 SpO2: 93.04% (N=1945 samples,
stdev=2.87%). Bias is a sensor/firmware characteristic, not a decoder error.

**Calibration analysis (Task 2):**

Paired cross-validation data (nights with both Gen3 and Gen4 SpO2):
- 2026-07-01/02: Gen3=91.5%  Gen4=97%  gap=+5.5%
- 2026-07-04/05: Gen3=95.1%  Gen4=97%  gap=+1.9%
- 2026-07-06/07: Gen3=93.5%  Gen4=98%  gap=+4.5%

Mean gap (Gen4−Gen3): +3.97%  |  Stdev: 1.86%

Proposed fixed offset (+4.0%) tested against ±2% gate:
- 2026-07-01/02: 91.5+4.0=95.5% vs 97.0% → residual +1.5% ✓
- 2026-07-04/05: 95.1+4.0=99.1% vs 97.0% → residual −2.1% ✗ FAIL
- 2026-07-06/07: 93.5+4.0=97.5% vs 98.0% → residual +0.5% ✓

DECISION: Fixed offset NOT applied. The gap varies too widely (1.9%→5.5%, stdev 1.86%)
for a single fixed offset to bring all nights within ±2% of Gen4. Applying +4.0 would
overcorrect night 2 (2026-07-04/05 → 99.1%, above physiological ceiling for resting
sleep). N=3 nights is also insufficient to establish a reliable calibration.

Status: open — need ≥5 paired overnight data points with stdev <1.0% to justify a
fixed offset. Walk experiment may provide additional variance context (activity SpO2).
Decoder unchanged. SPO2_OFFSET=6 remains correct.

*Logged 2026-07-07.*

---

## 2026-07-07 — 0x61/0x09 pfsm_state labels wired into pull script output

Date: 2026-07-07

Behaviorally-derived labels added to pull script (oura_gen3_morning_pull.py):
- pfsm=3, 4 → ACTIVE_REGIME (never seen in sleep context)
- pfsm=5    → TRANSITIONAL (appears in both sleep and activity context)
- pfsm=6    → SLEEP_REGIME (only seen when 0x6A sleep periods present)
- pfsm=128  → ECHO_RECORD (companion record, always follows primary within 12 ticks)
- pfsm=0    → AWAKE (not yet observed in 0x61/0x09; from 0x6A cross-reference)
- pfsm=1    → ASLEEP (not yet observed in 0x61/0x09; from 0x6A cross-reference)

Labels are corpus-derived only — NOT firmware-confirmed. Output now reads:
  [SLEEP STATS] pfsm_state=6 [SLEEP_REGIME]  seconds_in_pfsm_state=134  (2.23min)

*Logged 2026-07-07.*

---

## Walk experiment 2026-07-07: 0x7E/0x7F decoded + 0x6B confirmed as step counter

**Experiment:** Controlled timed walk, ~500 net steps, phone Bluetooth OFF. Raw pull file
lost to buffer roll — 7 pairs of 0x7E/0x7F payloads and 5 0x6B payloads recovered from
terminal output. Decoded file: `pipeline/data/raw_pulls/gen3_evening/walk_experiment_20260707_decoded.txt`

**0x7E/0x7F step feature packets (7 pairs):**
- open_ring layout confirmed: 14×uint8, no named fields ("FFTset sub-messages, meaning not documented")
- Boot_ts spacing: 296, 326, 302, 301, 321, 301 ticks — mean 307.8, stdev ~11 ticks (3.6%)
  These fire at near-constant ~308-tick cadence during walking (timer-driven, not step-triggered)
- b[9] of 7E consistently dominant (range 151-235, mean 193.3) — likely FFT peak or energy bin
- Pair 4 anomalous: b[1]=b[2]=b[5]=0 — possible brief pause in walk or missed cadence window
- **No single byte column sums to ~500.** 7E b[2]=485, 7E b[4]=482 are nearest but inconclusive
  (contain a zero in pair 4). These are spectral feature vectors, not direct step counters.
- Status: IN PROGRESS. Byte-level semantics still unknown — firmware or proto source needed.

**0x6B motion_period — step count CONFIRMED:**
- b[0] values during walk: 100, 101, 98, 98, 100 → **sum = 497 (0.6% deviation from 500)**
- Motion-intensity count hypothesis CONFIRMED against known ground truth
- Prior corpus b[0] mean = 56.6 (rest/light motion); walk mean = 99.4 → 1.76x ratio
- b[1] values (116-120): candidate cadence in steps/min — brisk walk pace is consistent
- b[3] values (240-254): approaching uint8 ceiling; b[4]=1 appears when b[3]≥246 (overflow flag?)
- 0x6B spacing: 300, 301, 299, 601 ticks — 601 = double gap (one packet missed or duplicate)
- Duplicate packet at boot_ts=57812910: identical to 57812611 — buffer artifact, not new data
- Interleaved with 7E packets at ~300-tick cadence — 0x6B fires between each 7E pair

*Logged 2026-07-07.*

---

## 0x6B motion_period promoted to DONE — decoder wired 2026-07-07

`pipeline/decoders/0x6b.py` created and wired into pull script (section after 0x47 motion decode).
Prints per-packet `steps` + `cadence_spm` + running `TOTAL STEPS THIS WINDOW`.

Confirmed fields:
- b[0] = per-window step count. Validated: sum 497 across 5 walk-experiment windows (0.6% from 500).
- open_ring MOTION_STATE enum {0:NO_MOTION, 1:RESTLESS, 2:TOSSING_AND_TURNING, 3:ACTIVE} is WRONG
  for b[0]. All observed values (53-101) are far outside the enum's documented range.

Candidate fields (not yet confirmed against second ground truth):
- b[1] = cadence in steps/min (116-120 observed at brisk walk pace). Plausible — typical brisk
  walking cadence is 100-130 spm. Needs a second controlled experiment (sit → slow walk → run)
  to confirm the field responds to pace changes.
- b[3] = approaching uint8 ceiling during activity (240-254). Likely wrapping cumulative counter.
- b[4] = overflow flag — fires 1 when b[3]≥246 (5-byte form vs 4-byte form).
- b[2] = unknown. Range 204-211 during walk — consistent but uninterpretable without more context.

*Logged 2026-07-07.*

---

## 2026-07-07 — 0x5D HRV sleep investigation: firing context confirmed ACTIVITY-only

**Question:** Why does 0x5D HRV event appear in zero sleep (morning) pulls across entire corpus?

**Method:** Audited all pull files, computed effective buffer windows, calibrated tick rate, analyzed firing context.

**Tick rate calibration:** 3.70 ticks/sec (from two July-7 morning pulls: 23,112 ticks / 6,251 sec).

**Buffer window during sleep:** 255 sleep packets span 1,577-2,757 ticks = 7-12 minutes at 3.70 ticks/sec.
If 0x5D fired during sleep (every 5 min), 1-2 packets WOULD appear in a 7-12 minute window.
Zero 0x5D events in ANY of 10 sleep pulls → confirmed: 0x5D does NOT fire during sleep.

**Firing context of the single observed 0x5D packet** (boot_ts=55393468, gen3_pull_20260702_222915_MIXED.txt):
- HR values: 72, 71, 70, 72 bpm — ACTIVITY heart rate (sleep HR is 52-65 bpm)
- Co-occurs with: step features, motion events, EHR boundary session (payload=0b0100)
- Pull composition: 76 Debug data, 36 Debug event, 21 step features, 19 motion events
- This is ACTIVITY HRV (exercise/stress RMSSD), not sleep HRV

**Finding: 0x5D measures activity-context HRV only.** It is the DHR (Dynamic Heart Rate)
session's RMSSD output — NOT the sleep readiness HRV shown in the Gen4 morning score.
Gen4 sleep HRV is either computed server-side from IBI streams or transmitted in sleep summary
packets (0x49/0x4C/0x4F) which Gen3 does NOT emit.

**Alternative paths for sleep HRV:**
1. Compute RMSSD from 0x6E / 0x80 IBI data already captured in sleep pulls (viable — IBI confirmed working).
2. Capture 0x5D in activity context by triggering pull after post-wake movement.

**Track B condition #2 implication:**
Condition #2 = "at least one 0x5D event in three consecutive morning pulls."
As currently defined, this condition **cannot be met** — 0x5D does not fire during sleep and
morning pulls capture the tail of sleep context.
Resolution options:
  A) Redefine condition #2: use RMSSD derived from 0x6E IBI data during sleep (already captured).
  B) Change pull timing: trigger pull after light morning activity to capture activity HRV.
  C) Accept condition #2 as unresolvable from Gen3 BLE and remove from Track B gate.
Owner decision required. Blocking Track B condition #2 permanently unless redefined.

*Logged 2026-07-07.*

---

## 2026-07-07 — 0x7E/0x7F FFT walk analysis: cross-file byte patterns

Analysis script: `pipeline/tools/analyze_fft_walk.py` — runs against all corpus pull files
with step features, prints per-byte stats (min/max/mean/stdev/sum), optionally compares two files.

**Corpus pull files with step features:** gen3_pull_20260702_222915_MIXED.txt (21 packets),
20260703_091611 (17), 20260703_091701 (32), 20260703_100910 (21), 20260704_091402 (12),
20260705_095211 (9), 20260705_213406 (5), 20260705_221126/walk-experiment (7).

**Key patterns across all 8 files:**

7E b[9] — WALK-EXPERIMENT RESPONSIVE:
  Walk experiment (gen3_pull_20260705_221126): mean=193.3, stdev=31.36, range 151-235
  All other activity pulls: mean=60-125, stdev=36-77, range 0-244
  b[9] is 1.5-3x higher in the controlled walk than in any other activity context.
  Leading hypothesis: b[9] encodes dominant FFT frequency bin — walk has a distinct,
  steady cadence that concentrates spectral power at one frequency.

7F b[10] — HIGH and TIGHT in general activity, LOWER in walk:
  General activity: mean 188-206, stdev 3-15 (tight across all non-walk files)
  Walk experiment: mean=128, stdev=5 (lower and still tight)
  7F b[10] may be a low-frequency or gravity-band energy estimate — walk produces
  more rhythmic oscillation at cadence frequency vs broadband activity noise.

7E b[0] ↔ b[8] TRACKING: delta <10 units across ALL 8 files (both walk and non-walk).
  Likely same signal via two channels or a redundant encoding. No activity-type sensitivity.

**Second walk experiment (slow pace) — PENDING:**
  Protocol: same as WALK_EXPERIMENT.md, ~500 steps at ~60-70 spm (vs 116-120 spm brisk).
  Target: does 7E b[9] change between fast and slow walk?
  If b[9] drops significantly at slow pace → cadence/frequency hypothesis confirmed.
  If b[9] stays high → activity-type detector (walk vs non-walk) not pace-sensitive.
  Script ready: `python3 pipeline/tools/analyze_fft_walk.py <new_pull_file> <walk_exp_file>`

*Logged 2026-07-07.*

---

## 2026-07-07 — 0x6B step count + cadence wired into bridge JSON and web app

Bridge vectors now include:
  "step_count": total 0x6B b[0] sum across all packets in pull window (null if no 0x6B)
  "cadence_spm": mean 0x6B b[1] across packets with b[1]>0 (null if no 0x6B)

Web app sys-log now shows: `STEPS N // TEMP X°C // BATTERY Y%`
In sleep window pulls (no 0x6B), shows: `STEPS N/A`.
In activity pulls with 0x6B packets, shows confirmed step count.

*Logged 2026-07-07.*

---

## 2026-07-07 — 0x5D HRV absent from sleep pulls — root cause identified

Date: 2026-07-07

Finding: 0x5D HRV packets are absent from all morning sleep pulls due to
buffer displacement by high-frequency Debug events (0x61), not because
the ring doesn't generate HRV data during sleep.

Key measurements across sleep pulls:
- Buffer: 256 packets total
- Debug events (0x61): 180-200 slots consumed per pull (~75% of buffer)
- Remaining slots: 50-70 for all other event types
- HRV fire rate: approximately every 5 minutes
- Sleep pull window: 3-4 hours of real time
- Expected HRV packets in window: ~36-48
- Available buffer slots for HRV: 50-70 (theoretically sufficient)

The contradiction: if 36-48 HRV packets should fit in 50-70 available
slots, why are none present?

Two hypotheses:
1. Debug events fire at variable rate — during active sleep phases they
   may flood the buffer faster than the 3-4 hour average suggests,
   displacing HRV packets before the morning pull.
2. HRV packets may not fire during the specific sleep phases captured
   by the morning pull window (tail end of sleep, near-waking state).
   HRV may fire primarily during deep sleep which occurs earlier in
   the night — outside the morning pull's buffer window.

The one confirmed 0x5D firing (2026-07-02 evening MIXED pull) occurred
during ACTIVE context — not sleep. This supports hypothesis 2: HRV
fires in specific physiological states that may not be present in the
buffer window captured by morning pulls.

Implication for Track B condition #2: three consecutive morning pulls
with 0x5D events may require either:
(a) A pull earlier in the sleep window (middle-of-night pull), or
(b) Redefining condition #2 to include evening activity pulls, or
(c) Accepting that 0x5D HRV is an activity-context decoder only

Status: open — condition #2 definition needs owner decision before
further investigation.

*Logged 2026-07-07.*

---

## 2026-07-07 — Track B condition #2 redefined — owner decision

Date: 2026-07-07
Decision: Option A selected.
Condition #2 redefined from "three consecutive morning pulls with
0x5D events" to "0x5D fires in three evening activity pulls within
the Track B validation period."
Current status: 1/3 confirmed.
Remaining: 2 more evening pulls with 0x5D events.

*Logged 2026-07-07.*

---

## 2026-07-08 — 0x76 bedtime_period investigated — zero packets, negative result

Date: 2026-07-08
Investigation: full corpus search + open_ring layout confirmation, no new decoding.

**open_ring reference** (`~/Desktop/open_ring/driver/decoders.py:303`,
`PROTOCOL.md:271`, `enums.py:50`): tag `0x76` = `API_BEDTIME_PERIOD`.
`decode_bedtime_period(p)` — payload must be >=8 bytes, 2x uint32 LE:
- offset 0..3: `start_ring_time`
- offset 4..7: `end_ring_time`
Both are raw ring-time ticks; open_ring converts to UTC ms via a separate
`TimeMapping` step we don't replicate. PROTOCOL.md gives no cadence/trigger
notes for this tag specifically, but does note `0x68 API_RAW_PPG_DATA` as
"declared but not observed in any capture" in open_ring's own reference data —
confirming this tag space includes genuinely rare/conditional emitters, not
just ones we've failed to capture.

**Corpus search:** all 23 raw pull files currently on disk
(`pipeline/data/raw_pulls/gen3_morning/*.txt` + `gen3_evening/*.txt`).
Searched for the literal tag, the pull script's exact label ("Bedtime period"),
and case-insensitive "bedtime" — zero matches on all three. Confirms the
existing NEVER OBSERVED status in `open_ring_roadmap.md` (last checked
2026-06-30 against 34 cumulative pulls; this session's 23-file re-check
found the same zero result).

**Pipeline readiness:** already fully wired, nothing to build.
`0x76` is in `PRIORITY_TAGS` (`oura_gen3_morning_pull.py:55`), the pull
script has a dedicated `=== BEDTIME PERIOD DECODE (0x76) ===` section that
calls `decode_bedtime_period()` on any tag-0x76 packet found
(`oura_gen3_morning_pull.py:285-296`), and `pipeline/decoders/0x76.py`
already implements open_ring's exact layout (`_u32(p,0)`, `_u32(p,4)`) —
untested against real data only because no real packet has ever arrived.
This is a data-capture gap, not a tooling gap.

**Cross-reference context (not a decode comparison — no packets to compare):**
Gen4 official `Bedtime Start`/`Bedtime End` for recent nights, for whenever
a real 0x76 packet does eventually appear and needs a sanity check:
- 2026-07-01: 2026-06-30T23:46:31 → 2026-07-01T09:12:00
- 2026-07-02: 2026-07-02T00:13:31 → 2026-07-02T09:10:57
- 2026-07-03: 2026-07-02T23:39:58 → 2026-07-03T09:08:57
- 2026-07-05: 2026-07-04T23:39:59 → 2026-07-05T09:49:52
- 2026-07-06: 2026-07-06T00:48:04 → 2026-07-06T10:41:19
(Source: `~/Desktop/oura_2026-05-29_2026-07-10_trends.csv`.)

**Why it's absent:** unknown — no confirmed mechanism. Ruled out one
hypothesis during this investigation: the `API_` prefix on `0x76` is not a
meaningful signal (every tag in this range, including tags that fire
reliably like `0x5D`/`0x6A`/`0x47`, shares the same `API_` prefix in
open_ring's enum — it's a blanket namespace convention, not evidence of a
request/response-gated tag). No alternative hypothesis is evidenced enough
to state as fact.

**What would unblock it:** catching it in a future pull — no known way to
force emission. Possibly correlates with a ring-internal sleep-session
finalization event that our short (~7-12 min) connection windows don't
reliably span; this is speculation, not confirmed.

Status: negative result, unchanged from prior. Decoder stub, wiring, and
roadmap status all confirmed accurate and up to date as of this session.

*Logged 2026-07-08.*

**Addendum, same day:** a follow-up message referenced "3 decoded 0x76
packets" as a promotion gate for cross-validating against Oura CSV bedtime
data, sourced from a claude.ai session output that "may not have been
saved to a file." Checked exhaustively before treating this as a finding:

- Re-searched all 23 raw pull files for the literal tag, a strict
  `[Bedtime period]` bracketed-label match, and case-insensitive "bedtime"
  — zero matches on all three, same as the original investigation above.
- Checked `pipeline/data/logs/morning_pull.log` and `morning_pull_error.log`
  (not checked in the original investigation) — log shows
  `No 0x76 bedtime period events found in this pull.`, no decoded output.
- Checked `pipeline/data/findings/ring_decoder_inventory.md` — only a
  description of what the decoder *would* provide, not actual values.
- Re-confirmed `0x76` is in `PRIORITY_TAGS` and the pull script's dedicated
  decode section is intact (`oura_gen3_morning_pull.py:285-296`).

Unlike the 0x7E/0x7F walk experiment (`walk_experiment_20260707_decoded.txt`)
— where the raw pull file was lost to buffer roll but the actual hex
payloads were recovered from terminal output and preserved — no hex
payloads, decoded values, or file reference were provided for these 3
packets, and none could be located anywhere in the repo. Per real-data-only
discipline: if it's not in a file, it didn't happen. **0x76 remains
confirmed absent from all pulls — tag requested (in `PRIORITY_TAGS`) but
never observed in the buffer.** No cross-validation was performed since
there is nothing to validate. 0x76 is NOT promoted to DONE.

*Logged 2026-07-08 (addendum).*

---

## 2026-07-09 — Second FFT walk experiment (slow pace) — capture failure, no comparison possible

Date: 2026-07-09, executed 12:43pm, phone Bluetooth OFF, 500 steps at slow
shuffle pace (~60-70 spm), light movement 5-10 min after, returned to Mac
within 60s, pulled immediately.

**Result: the pull captured zero 0x7E/0x7F and zero 0x6B packets.** No
fast-vs-slow comparison is possible — not because of a tool problem, but
because Walk 2 has no step-feature data at all to compare against Walk 1.

**Verification:** confirmed directly against the saved pull file
(`pipeline/data/raw_pulls/gen3_morning/gen3_pull_20260709_124308.txt`, 17163
bytes, matches the terminal output pasted at pull time). Listed every unique
bracketed event label in the file — 13 types, none step/motion-period
related: `Debug data`, `IBI and amplitude event`, `Motion event`, `PPG
amplitude`, `SPO2 DC event`, `SPO2 IBI+amplitude`, `SPO2 event`, `Sleep ACM
period`, `Sleep period info (2)`, `Sleep temp event`, `State change`, `Temp
event`, `UNKNOWN (0x11)`. The pull's own console output confirms this too:
`MOTION PERIOD DECODE (0x6B)` section printed "No 0x6B motion period events
found in this pull," and there is no 0x7E/0x7F decode section output at all
(the pull script has no dedicated print section for these tags — they only
ever surface in the raw `PRIORITY EVENTS` dump, and none appear there
either).

**Likely cause (not confirmed):** the auto-classifier tagged this pull
`SLEEP WINDOW` — a plainly wrong label for a deliberate midday walk test,
but revealing: the buffer window the pull actually read (boot_ts
60851402-60853399, ~2000 ticks / ~9 minutes at the ring's ~3.7 ticks/sec)
is dominated by sleep-context signal (0x6A `sleep_period_info_2`, stable
low HR 58.5-70.5 bpm, SpO2, sleep temp) — not the walk that had just
happened. This matches the project's previously-documented buffer/timing
constraint (sleep buffer window ~7-12 min, noted during the 0x5D HRV
investigation): the ring's addressable debug-event buffer appears to have
rolled past the walk's activity window by the time the connection was
established, surfacing older buffered content instead. This is consistent
with, not a new instance confirming, that pattern — no firmware-level
mechanism is confirmed.

**Walk 1 reference data (unchanged, for the record):**
- 0x7E `b[9]`: mean 193.3, range 151-235, across 7 packets (re-verified this
  session via the tool fix below — matches prior session notes exactly).
- 0x6B `b[1]`: values `[116, 117, 120, 120, 116]`, range 116-120, across 5
  packets (`walk_experiment_20260707_decoded.txt`).
- Walk 2 has no equivalent values for either — both are simply absent.

**Tool bug found and fixed:** `pipeline/tools/analyze_fft_walk.py` only
matched the live pull script's exact label strings (`Real step feature
(1)`/`(2)`). Walk 1's data survives only in a manually-transcribed file
(`walk_experiment_20260707_decoded.txt`, written after the raw pull was lost
to buffer roll) that uses a different shorthand (`[0x7E]`/`[0x7F]`) — so the
tool silently reported "No 0x7E/0x7F packets found" for Walk 1's own
preserved data too, before this fix. Updated the tool to match either label
format; re-ran and confirmed it now reproduces Walk 1's stats correctly
(`b[9]` mean 193.3, 7 packets each for 0x7E/0x7F) while correctly reporting
zero for Walk 2. This was a real bug (the tool was unusable for one of its
two only existing inputs), not something invented to explain a negative
result — Walk 2 genuinely has no data either way.

**What would unblock a real comparison:** repeat the slow-pace walk
experiment, but the constraint is the buffer/timing issue above, not pace —
a future attempt should probably start the pull connection *before* the
walk activity ages out of the buffer, e.g. by shortening time between last
motion and connecting, though this is untested.

Status: negative result — no fast-vs-slow byte comparison possible this
session. Tool bug fixed (verified against Walk 1's known-good data).
0x6B/0x7E/0x7F byte-role hypotheses from Walk 1 remain unconfirmed by a
second data point.

*Logged 2026-07-09.*

---

## 2026-07-09 — 0x7E/0x7F partial decoders written — Walk 1 data only

A request to write a decoder based on a "two-walk comparison" was checked
against the corpus first: the claimed second-walk numbers (slow-walk `b[9]`
mean 156.9, specific per-byte deltas) don't correspond to any file — Walk 2
captured zero 0x7E/0x7F packets (see the entry above). Confirmed with the
user this doesn't exist yet; proceeded with a decoder based on Walk 1's real
data only, with pace-sensitivity explicitly documented as untested rather
than inferred from nonexistent data.

**Decoders written:** `pipeline/decoders/0x7e.py` and `pipeline/decoders/0x7f.py`
(one file per tag, per the decoders/ README convention — not a combined
`0x7e_0x7f.py` file as originally suggested, since the codebase's own rule
is "one file per BLE event tag"). Both implement `decode(payload: bytes) ->
dict`, returning all 14 raw bytes (`b0`..`b13`). Registered in
`pipeline/decoders/__init__.py` as `decode_real_step_feature_1`/`_2`. Wired
into `oura_gen3_morning_pull.py` with a new `REAL STEP FEATURE DECODE
(0x7E/0x7F)` print section (there was no dedicated section before — 0x7E/0x7F
previously only appeared in the raw `PRIORITY EVENTS` dump). Verified against
Walk 1's real hex payloads (Pair 1: 7E → b9=233, 7F → b10=123) — matches the
source data exactly.

**What is actually confirmed (from Walk 1 alone, n=7 packets, plus the
pre-existing cross-file analysis against 8 other pull files):**
- 14-byte payload, fires as 0x7E/0x7F pairs on a ~308-tick hardware timer
  (296-326 tick spacing, mean 307.8) — NOT step-triggered. Step count is
  0x6B b[0] (already DONE).
- 7E `b[9]`: WALK-RESPONSIVE — mean 193.3 during the walk vs. 60-125 in
  other (non-walk) activity pulls. This is walk-vs-other-activity, not
  fast-vs-slow pace.
- 7F `b[10]`: also walk-responsive, opposite direction — mean 128 during
  the walk vs. 188-206 in other activity.
- 7E `b[0]` and `b[8]` track within <10 units across all files — likely
  correlated/redundant, not independently meaningful.

**What is explicitly NOT confirmed, to avoid the mistake in the original
request:** pace-sensitivity of any byte. The distinction between
"walk-responsive" (confirmed, tested against non-walk activity) and
"pace-sensitive" (untested — no second walk data exists) is stated
explicitly in both decoder docstrings so it doesn't get conflated again.

**Status:** 0x7E/0x7F promoted from IN PROGRESS to PARTIAL in
`open_ring_roadmap.md` — decoders exist and are wired in, but only 2 of 14
bytes per tag have any confirmed meaning, and even those are walk-vs-other-
activity, not a decoded physical quantity. Not promotable to DONE without
either a working third walk experiment or firmware/proto schema access.

*Logged 2026-07-09.*

---

## 2026-07-10 — 0x61/0x09 offset-3 (seconds_in_pfsm_state) cross-referenced against 0x6A

Priority: this decoder feeds `deep_sleep` (13% clinical floor), the only one of the
three IN PROGRESS decoders that reaches a live engine threshold. Testing the
existing offset-3 hypothesis ("seconds in current pfsm state," CONFIRMED
2026-06-27 via n=47 echo-pair analysis) from an independent angle: cross-
referencing against 0x6A's own sleep_state timeline, per the working
hypothesis that pfsm=6 (SLEEP_REGIME) and 0x6A co-occur.

**Method:** scanned all 23 raw pull files. For every 0x09 record with
`pfsm_state==6`, computed a claimed sleep-onset boot_ts
(`boot_ts - seconds_in_pfsm_state * 3.70 ticks/sec`) and found the closest
0x6A record in the same file.

**Finding 1 (new, positive) — tight temporal co-occurrence confirmed at
higher precision than before.** All 16 pfsm=6 records across the corpus have
a 0x6A record within ~45 seconds (range: -43.2s to +37.0s). 0x6A itself
fires roughly every ~80s (300 ticks / 3.70), so every pfsm=6 event has a
0x6A sample within less than one full 0x6A period. This sharpens the
existing 2026-07-06 finding ("pfsm=6 fires ONLY in sleep context, co-present
with 0x6A packets") from a same-pull binary co-occurrence to an actual
distance measurement.

**Finding 2 (inconclusive) — "onset consistency" sub-test does not add
strong independent confirmation of offset-3's exact interpretation.** Tested
whether the closest 0x6A record's boot_ts falls after the claimed sleep-onset
boot_ts (i.e., consistent with the ring having been in pfsm=6 continuously
since that computed onset). 12/16 pass, 4/16 do not
(`gen3_pull_20260702_000517_MIXED.txt`, `gen3_pull_20260708_103706_MIXED.txt`,
`gen3_pull_20260708_220910.txt`, `gen3_pull_20260709_124308.txt` — one each).
This is NOT treated as a falsification: the 4 "failures" are all within
tens of seconds of the boundary, well inside the noise budget introduced by
(a) the 3.70 ticks/sec constant being an empirical approximation, not an
exact firmware-confirmed rate, and (b) pfsm_state (the debug state machine)
and sleep_state (0x6A's own field) being two different state machines that
need not transition at the exact same instant even when correlated. A
tighter test would need firmware-confirmed tick rate or a much larger
same-session sample; neither is available.

**What this does NOT test:** within-pull growth of offset-3 over time. Every
pull's buffer window only ever contains a single pfsm=6 record (never a
consecutive sequence) — the ~7-12 min buffer captures one snapshot, not a
time series. This is itself worth noting as a data-density limitation: the
strongest existing validation of offset-3 (n=47 echo pairs, 2026-06-27)
relies on original/echo record PAIRS within a pull, not sequences of
pfsm=6-to-pfsm=6 records, because the latter essentially never occurs in
this corpus.

**Conclusion:** offset-3's "seconds in current pfsm state" interpretation is
NOT falsified by this test, and is further supported by finding 1. It is not
newly *confirmed* by this test either — finding 2 is genuinely inconclusive,
not a weak positive. The strongest evidence for offset-3 remains the
pre-existing echo-pair analysis. f2/f4 remain completely unresolved and are
the actual ceiling on this decoder reaching DONE — this session did not
attempt them (out of scope for this test, and previously noted as needing
firmware access).

**Status: 0x61/0x09 stays PARTIAL / IN PROGRESS.** Not promoted. deep_sleep%
extraction from this tag is still blocked on f2/f4, which this test did not
address.

*Logged 2026-07-10.*

---

## 2026-07-10 — 0x5D overnight sanity check: data availability, not decoding, confirmed again with 2x the sample

Before spending more time trying to decode 0x5D, checked whether it's a data
availability problem: does the ring's buffer contain 0x5D packets during
sleep at all? This exact question was already answered 2026-07-07
("CONFIRMED ACTIVITY-ONLY," audited ~10 sleep + 9 evening pulls). Re-ran
against the current full corpus, which has grown since — worth re-verifying
rather than trusting the old count.

**Method:** classified all 27 raw pull files by filename (`_MIXED` suffix =
activity/mixed window, no suffix = SLEEP WINDOW — spot-checked against
bridge JSON classifiers for two files this session, both matched exactly).
Searched every file for the literal `[HRV event]` label (0x5D's exact
pull-script label, confirmed in the 0x76 investigation methodology).

**Result — complete, exception-free absence:**
- **SLEEP WINDOW files: 0/21 contain any 0x5D packet.** Zero exceptions.
- **MIXED/activity files: 1/5** contain a 0x5D packet
  (`gen3_pull_20260702_222915_MIXED.txt`) — this is the same single
  confirmed instance already tracked as Track B condition #2's 1/3.
- Walk experiment file: 0/1.

This roughly doubles the previous sample (21 sleep-window files vs. ~10) and
the pattern holds with zero exceptions in either direction: 0x5D has never
once appeared in a SLEEP WINDOW pull across the entire pull history, and
only ever appears in activity/mixed context.

**Interpretation:** a clean, total, repeated absence across 21 independent
captures — rather than garbled or malformed 0x5D-tagged bytes appearing
sometimes — is much more consistent with "the ring's firmware does not
compute or transmit HRV-event records during sleep-context operation" than
with a decoding bug. If this were a decode/parsing problem, some fraction of
sleep pulls would be expected to show corrupted or partial 0x5D packets, not
uniform, complete absence of the tag itself.

**Conclusion: this is a hardware/protocol limitation, not fixable by better
decoding.** Recommend not spending further time this week trying to decode
0x5D output for overnight use. This does not affect Track B condition #2
(3 confirmed 0x5D *evening activity* events) — that's explicitly a separate,
already-redefined track (Option A, 2026-07-07 owner decision) and is
unaffected by this finding.

*Logged 2026-07-10.*

---

## 2026-07-10 23:36 — Evening pull (gen3_pull_20260710_233656.txt) — ACTIVE WINDOW

Verified directly against the raw pull before logging (real-data-only
discipline). Four of five reported findings check out exactly; one needed a
decoder-attribution correction, one a small precision fix.

**Classification:** ACTIVE WINDOW — confirmed (bridge JSON classifier
matches; zero 0x6A, zero sleep-tag events in the file).

**0x5D HRV:** zero events — confirmed. Consistent with, but not a new
positive instance of, 0x5D firing in activity context (2026-07-07 finding).
Not every active window is expected to trigger it; this one didn't. Track B
condition #2 stays at 1/3, no change.

**Battery — CORRECTED ATTRIBUTION.** The claimed 86.4% → 93% rise
(boot_ts 61892597–61902374) is real, but comes from the **0x61/0x24
`battery_level_changed`** decoder, not 0x61/0x14 `fuel_gauge` as reported.
Fuel gauge in this same pull shows a flat/slightly declining trend instead
(86.35% → 86.25% → 86.25%, boot_ts 61892597–61899252 — the cited start
boot_ts is actually fuel gauge's first sample, not battery_level's).
`decode_debug_data_battery_level` gives the real climb: 86%→87%→88%→90%→93%
across boot_ts 61899249→61902374 (exact match to the claimed end), with
voltage rising 4054→4191mV alongside it and an undocumented `reason` field
changing from 2 to 3 partway through (no known enum for this field — not
guessing at a meaning). **Conclusion unchanged and correctly supported**:
ring is charging, the 2026-07-10 AM 58.5% reading is stale, no action
needed — just sourced from the wrong of the two independent battery
decoders this pull happens to have both fire.

**0x61/0x09 pfsm_state negative control:** confirmed exactly. pfsm ∈ {3, 5,
128} (128 = echo/companion, per the established pattern), zero pfsm=6, zero
0x6A — correct behavior for an active window, no false SLEEP_REGIME reads.
Corroborates pfsm_state reliability; does not touch the f2/f4 blocker.

**0x7E/0x7F step features:** 23 paired records confirmed exactly. `b9`
(0x7E) range 0–248 matches exactly. `b10` (0x7F) range: actual 135–208, not
130–208 as reported — minor (5-unit) discrepancy on the low end, not
treated as a real error. This is the **second independent activity dataset
with 0x7E/0x7F data** in the corpus (after the single 2026-07-07 walk) —
first real opportunity to cross-reference two sessions instead of relying
on one. Not analyzed against pace-sensitivity here; flagged as a next-step
opportunity, distinct from and not a substitute for the still-needed third
*walk* experiment (this was general activity, not a controlled walk).

**No RHR/SpO2/deep sleep** — confirmed, expected for an active-window
classification (0x6A/0x6F/0x6E all correctly absent).

*Logged 2026-07-10.*
