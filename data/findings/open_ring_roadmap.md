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
      smoothing. 7F[11] ↔ 7F[12] r=−0.539 — complementary pair, likely
      two frequency bands. 7E[4] ↔ 7F[6] r=+0.374 — tight cross-tag pair.
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
- [ ] 0x49 sleep_summary_1 — 2x u16, semantics unknown
- [ ] 0x4C sleep_summary_2 — u16+u32, semantics unknown
- [ ] 0x4F sleep_summary_3 — mixed widths, semantics unknown
- [ ] 0x4A ppg_amplitude_ind — raw PPG signal strength (normalized float)
- [ ] 0x50 activity_info_event — daytime activity, partial confidence
- [ ] 0x5B ble_connection_ind — BLE link-quality telemetry
- [ ] 0x5E selftest_event — ring self-test pass/fail counts
- [ ] 0x6C feature_session — session boundary markers
- [ ] 0x72 sleep_acm_period — sleep accelerometer period (seen often in pulls)
- [ ] 0x73 ehr_trace_event — exercise heart rate trace
- [ ] 0x80 green_ibi_and_amp_event — our old mystery tag, decoder exists but
      is raw-bytes-only (14x u8, no real field layout)
- [ ] 0x82/0x83 scan_start / scan_end — BLE scan boundary markers

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
8 done + 5 in progress + 3 not-started-T1 + 12 + 2 + 24 = **54 decoder entries tracked**
(some inventory rows bundle two tag IDs under one decoder, e.g. 0x7E/0x7F
and 0x82/0x83 — so the "35+" figure from earlier referred to distinct
*functions*, this board tracks distinct *tags/sub-types*, which is why the
count differs. Every tag-level entry from the original inventory is
represented above — nothing skipped.)

## Suggested next-session order (updated 2026-06-27)
Three decoders are now in the same "structure confirmed / meaning open"
ceiling category, all blocked on ground-truth data rather than analysis:
  - 0x7E/0x7F: needs timed step count to label 7F[3]/7F[4]/7F[7]
  - 0x61/0x09: needs ground truth to identify f0/f2/f4 physical meaning
  - 0x6E / 0x77: need activity pull WITH SpO2 present

1. **Ground-truth data collection round** — all three can be unblocked in
   a single deliberate session:
   a. Wear a second tracker (watch, phone pedometer) during a walk, then
      pull immediately → unlocks 0x7E/0x7F (7F[3] step-count hypothesis)
      AND may provide SpO2 if ring activates SpO2 during activity →
      unlocks 0x6E and 0x77 simultaneously.
   b. Correlate 0x09 f2/f4 dynamics against known sleep stages from the
      Oura app for the same night → unlocks 0x09 f2/f4 meaning.
2. **Tier 1 remaining**: 0x53 and 0x69 DONE (2026-06-27). 0x6B IN PROGRESS
   (b[0] enum mismatch — needs more motion-diverse packets). 0x76
   (bedtime_period) NOT STARTED — never caught a real packet yet.
3. **Tier 2 and 0x61 debug sub-types** — tracked but lower priority.

## How to use this doc
Check a box, move an item between sections, or add a note inline as
hypotheses get tested. This is the single source of truth for "have we
tried this tag yet" across the entire 38-entry surface — check here before
re-investigating anything.
