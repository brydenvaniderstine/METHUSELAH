# METHUSELAH // open_ring Decoder Roadmap (COMPLETE — all 38 decoders tracked)

Scope: every single decoder that exists in open_ring's driver/decoders.py,
per the full inventory. Nothing omitted, including low-value diagnostic
sub-types. This supersedes the earlier partial roadmap.

## Rules of the road (apply to every decoder, no exceptions)
1. Real source only — read `~/Desktop/open_ring/driver/decoders.py`
   directly via `cat`/`sed`. Never trust web search or fetched GitHub
   pages about this repo (confirmed unreliable 2026-06-24).
2. No decoder is "working" until tested against real captured hex from
   your own ring.
3. Negative results (killed hypotheses) get logged, not discarded.
4. One decoder at a time.

## DONE — working, validated against real data (8)
- [x] 0x6A sleep_period_info_2 (sleep_state)
- [x] 0x5D hrv_event (HRV/RMSSD)
- [x] 0x61/0x14 fuel_gauge_statistics (battery %, voltage, capacity)
- [x] 0x75 sleep_temp_event (skin temp, degC)
- [x] 0x47 motion_event (3-axis accelerometer)
- [x] 0x6F spo2_event (SpO2, fixed with offset=+6, internal consistency
      confirmed; Gen4 cross-validation still open)
- [x] 0x53 wear_event — format: state:u8 + text:ascii (duration of prior
      state in seconds, as numeric string). STATE_CHANGE enum confirmed
      (states 1 and 3 validated against 2 real packets 2026-06-27).
- [x] 0x69 temp_period — i16 LE / 100 = °C. CONFIRMED 2026-06-27 by
      cross-check with 0x75 at ts=40728926/40728928 (2-tick gap, values
      match to within 0.06°C). Same formula as 0x75; 0x69 appears to be
      a single-value period average of the same skin-temp sensor.
- [x] 0x80 green_ibi_quality_event — VALIDATED 2026-06-30. Format:
      N×(b_low,b_high) pairs (payload always even; 345/361 pkts are 14 bytes = 7
      samples). 11-bit IBI: (b_low<<3)|(b_high&0x07). quality_a: (b_high>>3)&0x03.
      quality_b: (b_high>>5)&0x07. HR = 60000/IBI_ms.
      Cross-validated against 0x6A avg_hr on 3 pulls: delta −0.1 to +1.6bpm
      (mean +0.9bpm) — essentially perfect agreement. IBI=2000ms is a sentinel
      (60 exact hits = "no beat detected"; 11-bit max is 2047). Session-gated:
      only fires when GREEN_IBI session active — present in 9/29 pulls, absent
      in others by design (not a gap). quality_a=1 dominant (65%); qa=0/2/3
      semantics unresolved. NOT activity-only — fires in sleep, transitional,
      and active windows wherever the GREEN_IBI session is running.

## IN PROGRESS — real RE work started, not yet solved (5)
- [ ] 0x61/0x09 _dd_sleep_statistics — partial decode confirmed. Original
      u32 field layout (ticks_in_deep/sleep/awake) is wrong for our data.
      CONFIRMED (2026-06-26): offset-3 u16 = seconds in current pfsm state.
      CONFIRMED (2026-06-27): full layout is 6×u16 LE + 1×u8 pfsm_state.
      Layout: b1-b2=f0(unknown), b3-b4=o3(seconds in pfsm state), b5-b6=f2
      (dynamic, pfsm-dependent decay), b7-b8=0(padding), b9-b10=f4(dynamic,
      opposite direction to f2 in pfsm=6), b11-b12=f5(flag ∈{0,1}), b13=pfsm.
      KEY FINDING: f2 and f4 are dynamically updating — proven via orig/echo
      pair comparison (47 pairs). f2 always decays orig→echo; decay rate is
      pfsm-dependent: pfsm=6 retains 60%, pfsm=3 retains only 2.6%.
      f4 INCREASES in pfsm=6 echo (+20K avg/5s) and DECREASES in pfsm=3.
      Interpretation: f2/f4 appear to be biosignal metrics with short time
      constants, NOT simple cumulative time-in-state. f0 uncorrelated with
      everything. f5 flag (4 occurrences) has no clear predictor identified.
      CEILING: physical meaning of f0/f2/f4 unconfirmed without ground truth.
      STATUS: structure confirmed / meaning open — same ceiling as 0x6E/0x77.
- [ ] 0x7E/0x7F real_steps_features — 64 pairs across 3 activity pulls.
      CONFIRMED (2026-06-27): invalid pairs (7F[3]=7F[4]=7F[7]=0) caused
      by Feature session restart (payloads 02010400 / 02030400), recovery
      spans 1–2 windows. NOT timeout/fea-off (prior hypothesis revised).
      Strongest correlation: 7F[10] ↔ 7F[4] r=+0.526 — 7F[10] never hits
      zero, 7F[4] validity-flagged; same underlying signal at different
      smoothing. 7F[11] ↔ 7F[12] r=−0.568 (n=96) — anti-correlated, energy
      conservation FALSIFIED. diff(f11−f12) is the true signal: r=+0.337
      with f4, r=+0.293 with f10. Hypothesis: f11=cadence-band power,
      f12=low-freq/gravity artifact. 7E[4] ↔ 7F[6] r=+0.374 — tight cross-tag.
      7F[3] highest-variance field (stdev 61.4, range 7–230), primary step
      output candidate. u16 hypothesis falsified (7F[3]↔7F[4] r=−0.084,
      independent). CEILING: cannot label 7F[3]/7F[4]/7F[7] without
      ground-truth step count. NEXT: timed step session (count steps,
      pull immediately), correlate 7F[3] against known step count for
      the walk window — one 300-sec pair per 5-min segment.
- [ ] 0x6E spo2_ibi_and_amplitude_event — 3 hypotheses killed (channel-
      split, byte-0 counter, bytes-1-6 SpO2 correlation). Raw u8 values
      of bytes 1-6 are almost entirely 93-108 (= 87-102% under offset-6),
      consistent with SpO2 samples; b1/b2 r=0.626 and b2/b3 r=0.493 at
      lag=0 suggest b1-b3 are consecutive samples of the same slow signal.
      b4-b6 mutually independent — likely a different field (IBI or amp).
      Structural ceiling reached on sleep-session data; needs a higher-
      variance pull to confirm via correlation.
(0x80 moved to DONE — see above)
- [ ] 0x6B motion_period — 4 real packets captured (2026-06-27). open_ring
      decoder maps b[0] to MOTION_STATE (0-3), but all 4 observed b[0]
      values (6, 52, 61, 62) are outside the enum. Contextual correlation:
      b[0]=62 during active stepping, b[0]=6 near ring removal (wear event),
      consistent with a motion-intensity count rather than an enum.
      Variable payload length (8 or 14 bytes). 0xaa bytes appear as filler
      in unused slots of the 14-byte form. CEILING: need more packets across
      a range of activities to resolve b[0] and map the trailing bytes.
- [ ] 0x77 spo2_dc_event — structural analysis complete (2026-06-25),
      field meaning not yet decoded. Confirmed: byte 0 = channel field
      (alternates L/H bands 16-107 / 146-222, near-perfect per-packet),
      bytes 1-13 = 13 independent i8 fields centered near zero. Falsified:
      channel_index (range too wide), red/IR DC-level split (no mean
      difference between channels in i8), i16 pairing (stdev explodes).
      open_ring docstring (`beat_index, timestamp, dc[]`) is unimplemented
      hypothesis, no additional source hints. Ceiling reached on current
      data — needs activity-session pull for physiological correlation.

## NOT STARTED — Tier 1, high biometric value (3)
- [ ] 0x76 bedtime_period — wired into script, never caught a real packet
- [ ] 0x7E/0x7F real_steps_features — IN PROGRESS (2026-06-26). See IN
      PROGRESS section below.

## NOT STARTED — Tier 2, weaker/auto-extracted confidence (12)
- [ ] 0x49 sleep_summary_1 — Gen3 does NOT emit (0 packets across all 27 pulls)
- [ ] 0x4C sleep_summary_2 — Gen3 does NOT emit (0 packets)
- [ ] 0x4F sleep_summary_3 — Gen3 does NOT emit (0 packets)
- [ ] 0x4A ppg_amplitude_ind — 243 packets. Format 5×u16 LE (NOT just first u16
      as open_ring claims). ANALYSIS COMPLETE (2026-06-29):
      f0: r=−0.561 with SpO2; saturates at 65535 when SpO2=88%; f0=0 universally
      in activity (red/IR LED off). Interpretation: optical AGC / LED drive level
      — ring increases LED power when desaturation detected.
      f1-f4: sleep-only (all-zero in activity), range 0–30, r=0.89-0.99
      inter-field (one signal×4), r=+0.41-0.51 with motion_count. Best hypothesis:
      4-channel motion-artifact rejection counts within SpO2 measurement window.
      CEILING: f1-f4 semantic (artifact vs valid-sample count) needs firmware;
      f0 gain/drive interpretation needs optical register access.
- [ ] 0x50 activity_info_event — PARTIAL DECODE (2026-06-30). 13 packets.
      b[0] = activity class enum ∈ {0,21,23,60,97,198}. b[0]=0 → sedentary/rest
      (surrounds SPO2, Sleep ACM, Temp events); non-zero → active (always followed
      by Motion event at t+1). Values scale with intensity: 21/23=light, 60=moderate,
      97=vigorous, 198=intense. Trailing bytes (loop-read by firmware — auto-extractor
      missed them): 13-sample per-epoch intensity array for 14-byte packets. Values
      9–16 in rest/light context, up to 91 in intense context. MET×8 encoding plausible
      (9/8=1.1 MET rest, 91/8=11.4 MET vigorous). Short packets (3, 7, 10 bytes) are
      rare variants; structure differs from 14-byte form.
      CEILING: exact activity class enum labels (only 6 values observed); MET×8 unconfirmed
      without simultaneous Gen4 Average MET cross-validation.
- [ ] 0x5B ble_connection_ind — PARTIAL DECODE (2026-06-30). 50 packets across
      pulls. Open_ring decoder reads isolated u8s at offsets 0,1,6,7,8,9 — wrong.
      Actual structure: byte[0] = subtype ∈ {2,3,4,5}; each subtype is a distinct
      fixed-size record. Subtypes 2/4/5 always fire as a consecutive trio (1 tick
      apart) on every BLE connection event; subtype 3 logs the peer MAC separately.
      Sub=3: bytes[1]=addr_type (2=random-resolvable, 0=public), bytes[2:8]=6-byte
      BLE MAC address. 7 unique MACs across all pulls (phone rotates random address).
      Sub=4: u16_le(p[1:3])=u16_le(p[3:5]) always (min=max=fixed interval).
      207×1.25ms=258.75ms (sleep/low-power mode); 27×1.25ms=33.75ms (active/app-open
      mode). BLE spec confirmed — no firmware needed for these two fields.
      Sub=2: b[7]∈{14,16,24,30} = negotiated connection interval (×1.25ms);
      b[10]=8–180 = likely RSSI or packet error metric; b[2]∈{0,1,2,3} = reconnect
      count within session.
      Sub=5: 4×u16_le at offsets 1,5,7,9 — ranges 0–923 — likely TX/RX packet
      counts or error counters; exact labels need firmware.
- [ ] 0x5E selftest_event — 0 packets. Gen3 may not emit or very rare.
- [ ] 0x6C feature_session — PARTIAL DECODE extended (2026-06-30). b0 session classes:
      0x02=GREEN_IBI, 0x03=unknown, 0x04=unknown, 0x08=EHR_INHIBIT,
      0x0b=EHR/DHR_BOUNDARY, 0x0d=CVA. b1 direction now fully mapped via ASCII context:
      b1=1=START (all types; preceded by DHR_state:4, followed by DHR_state:2)
      b1=2=PAUSE/TRANSITION (GREEN_IBI only; EHR session interrupting GREEN_IBI)
      b1=3=STOP (all types; followed by AFs aggregate or CVA_state:0)
      b1=9=EHR_BOUNDARY PRE-ANNOUNCE (fires before EHRst;1;0;1 — EHR about to start)
      b1=10=EHR_BOUNDARY CONFIRMED (fires after EHRst;1;0;1 — EHR now active)
      b0=8 confirmed: always co-occurs with pp_rt_start + EHR_INH;9 + CVA_state:1 →
      EHR_INHIBIT session (EHR suppressed to give CVA exclusive optical access).
      b2: 4=COMPLETED(activity), 1=ONGOING(CVA), 0=UNSPECIFIED(boundary).
      CEILING: b0=3 and b0=4 session classes unidentified (single occurrence each);
      b1=9 vs b1=10 distinction (pre-announce vs confirmed) needs more EHR start events.
- [ ] 0x6D MEAs quality event — 23 packets. NOT ON ORIGINAL ROADMAP. No open_ring
      decoder (raw hex fallback). Format CONFIRMED (2026-06-29): byte[0]=0x00 +
      4×i24 LE, all values negative (-2 to -216). ACTIVITY-ONLY (no sleep pulls
      contain this tag). Fires every 121 ticks (~1.57s) fixed cadence. Inter-field
      r=0.44–0.66 (4 distinct correlated channels, NOT identical×4). Zero
      correlation with motion magnitude — FALSIFIED motion-quality hypothesis.
      Best hypothesis: 4-channel optical noise floor / per-channel SNR residuals
      from PPG system (green×2, red, IR). Ceiling: needs firmware disassembly or
      simultaneous 0x77/0x6E in same activity pull to progress.
- [ ] 0x72 sleep_acm_period — PARTIAL DECODE (2026-06-30). 215 packets across
      27/29 pulls (all window types). Format: 6×u16 LE (open_ring reads u8 at
      offsets 6–11, incorrect). Invariants hold at 0 violations across 215 pkts:
      f4>=f3, f1=max(f0,f1,f2).
      {f0,f1,f2} = per-axis ACM energy. f1=gravity axis (dominant lying down;
      quiet medians 12/22/13; heavy motion peaks 6767/11602/8780). All 3 corr
      r=0.96-0.97 with each other, r=0.76-0.92 cross-group.
      {f3,f4,f5} = motion summary. f3=period floor (min=24, quiet median=29);
      f4=period peak (always >=f3, quiet median=34, active median=193); f5=sparse
      overflow (r=+0.963 with f3; 88% of values <=10).
      Sleep_state split: state=0 has ~2x higher all-field medians vs state=1,
      confirming 0x72 tracks real motion differences between sleep states even
      with the sleep_state enum gap.
      CEILING: which physical axis maps to f0/f1/f2, exact ACM formula (RMS?
      variance?), and f5 overflow semantics need firmware disassembly.
- [ ] 0x73 ehr_trace_event — 48 packets. Has decoder (header + u8 samples).
      EHR = exercise heart rate. Semantics not confirmed.
- [x] 0x80 green_ibi_quality_event — DONE 2026-06-28. See DONE section above.
- [ ] 0x82/0x83 scan_start / scan_end — 0 packets. Gen3 does not emit.

## NOT STARTED — unidentified/low-confidence (2)
- [ ] 0x56 unknown_56 — 1-byte flag, semantics never identified even by
      open_ring's own authors
- [ ] 0x85 unknown_85 — 10-byte record with a timestamp + unexplained trailer

## NOT STARTED — Tier 3, debug/diagnostic sub-types under 0x61 (24)
All dispatched via sub-byte at payload offset 0, tag 0x61 itself.
- [ ] 0x61/0x04 _dd_alt_text — ASCII debug strings
- [ ] 0x61/0x0A _dd_flash_usage_statistics — flash read/write/erase ticks
- [ ] 0x61/0x0C _dd_period_info_statistics — period measurement timing
- [ ] 0x61/0x0D _dd_ble_usage_statistics — BLE connection mode ticks
- [ ] 0x61/0x0F _dd_security_failure — auth/security failure events
- [ ] 0x61/0x15 _dd_finger_detection — wear/contact detection (raw u64 bits)
- [ ] 0x61/0x1A _dd_event_sync_statistics — sync performance stats
- [ ] 0x61/0x1B _dd_bootloader_debug_log — bootloader logs
- [ ] 0x61/0x1E _dd_fuel_gauge_register_dump — raw battery chip registers
- [ ] 0x61/0x1F _dd_ring_hw_information — hardware info dump
- [ ] 0x61/0x20 _dd_charging_ended_statistics — charging session stats
- [ ] 0x61/0x21 _dd_fuel_gauge_logging_registers — more battery registers
- [ ] 0x61/0x23 _dd_event_sync_cache_statistics — cache vs flash read counts
- [ ] 0x61/0x24 _dd_battery_level_changed — battery % + voltage + reason
      code at moment of change (wired into script already, never caught
      a real packet yet)
- [ ] 0x61/0x25 _dd_hardware_test_start_values — hw self-test, phase 1/3
- [ ] 0x61/0x26 _dd_hardware_test_result_values — hw self-test, phases 2-3
      (stateful, 3-record sequence)
- [ ] 0x61/0x27 _dd_charging_ended_statistics_continued — more charging stats
- [ ] 0x61/0x28 _dd_afe_statistics_values — PPG sensor chip stats (stateful)
- [ ] 0x61/0x29 _dd_acm_configuration_changed — accelerometer/gyro config
- [ ] 0x61/0x2A _dd_field_test_information — field test data
- [ ] 0x61/0x2B _dd_stack_usage_statistics — firmware stack usage (debug-only,
      genuinely zero biometric value, include only for completeness)
- [ ] 0x61/0x30 _dd_alt_periodic_counter — periodic heartbeat counter
- [ ] 0x61/0x33 _dd_open_afe_ppg_settings_data — PPG chip variant + settings
- [ ] 0x61/0x35 _dd_ppg_signal_quality_stats — SNR/signal quality, tells us
      how trustworthy other readings are (genuinely valuable, multi-field
      bit-packed structure, real RE effort needed)
- [ ] 0x61/0x36 _dd_charger_information — charger link params, firmware/serial
      via dock (stateful, multi-record)
- [ ] 0x61/0x3B _dd_alt_afe_period_tick — AFE sample rate (25/50Hz)
- [ ] 0x61/0x3C _dd_alt_ppg_cont — PPG continuation records
- [ ] 0x61/0x3D _dd_charger_debug_information — charger debug info (stateful)
- [ ] 0x61/0x3F _dd_daily_drop_sample — daily diagnostic sample

## Count check
8 done + 6 in progress + 1 not-started-T1 + ~12 + 2 + 24 = **~55 decoder entries tracked**
(Updated 2026-06-28: 0x80 promoted from NOT STARTED to IN PROGRESS. 0x6D added as new
Tier 2 entry not previously on roadmap. 0x49/4C/4F confirmed Gen3 does not emit —
can be deprioritized. 0x82/0x83 same. Count is approximate due to bundles.)

## Suggested next-session order (updated 2026-06-28)

**BLOCKED until controlled walk (tomorrow, 2026-06-29 or later):**
- 0x7E/0x7F: timed walk with phone BT disabled, kill Oura app before walk
- 0x6E / 0x77: same activity pull (need SpO2 activation during activity)
- 0x61/0x09: Oura app sleep-stage cross-reference for same night

**IMMEDIATELY actionable from existing 27 pulls:**

1. ~~**0x72 sleep_acm_period**~~ — PARTIAL DECODE logged 2026-06-30. See IN PROGRESS section.

2. ~~**0x80 green_ibi_quality_event**~~ — DONE 2026-06-30. See DONE section.

3. **0x6B motion_period** — collect more packets by capturing pull during
   deliberate motion (sit→walk→sit transitions). Only 4 packets currently.

4. **0x76 bedtime_period** — has never fired. Not actionable from existing data.

## Gen4 Ground Truth Reference (added 2026-06-30)

**File:** `data/reference/gen4_official_trends_2025-06-14_2026-06-07.csv`
**Full baseline doc:** `data/findings/gen4_baselines.md`
**Coverage:** 359 nights, 2025-06-14 → 2026-06-07 (no gaps)

Personal reference bands for decoder validation — use these to sanity-check any decoded value:

| Signal | Typical range (p25–p75) | Clear outlier threshold |
|---|---|---|
| Average RHR | 59–67 bpm | <52 or >75 bpm |
| Lowest RHR | 52–57 bpm | <47 or >63 bpm |
| HRV (RMSSD) | 24–35 ms | <15 ms (suppressed) / >45 ms (peak) |
| Respiratory rate | 12.75–13.38 br/min | <12 or >14.5 br/min |
| Skin temp deviation | −0.21 to +0.29°C | >+0.6°C likely illness |
| Total sleep | 7.1–8.5 h | <5.9 h or >9.6 h |
| Deep sleep | 61–88 min | <45 min or >107 min |
| REM sleep | 93–130 min | <68 min or >153 min |
| Sleep efficiency | 84.5–90% | <75% |

**Gap warning:** Export ends 2026-06-07. All Gen3 pulls from 2026-06-28 onward fall
outside this window. Export a fresh Gen4 CSV (2026-06-08+) to enable same-night
cross-validation for the current pull set.

**Highest-priority retrospective target:** 2025-12-20 (HRV=10ms, temp+2.59°C, readiness=29
— absolute extremes across 359 nights). If Gen3 boot_ts can be aligned to that date's
flash window, it is the single best test of whether physiological decoders track illness.

## How to use this doc
Check a box, move an item between sections, or add a note inline as
hypotheses get tested. This is the single source of truth for "have we
tried this tag yet" across the entire 38-entry surface — check here before
re-investigating anything.
