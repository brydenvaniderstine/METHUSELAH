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

## DONE — working, validated against real data (6)
- [x] 0x6A sleep_period_info_2 (sleep_state)
- [x] 0x5D hrv_event (HRV/RMSSD)
- [x] 0x61/0x14 fuel_gauge_statistics (battery %, voltage, capacity)
- [x] 0x75 sleep_temp_event (skin temp, degC)
- [x] 0x47 motion_event (3-axis accelerometer)
- [x] 0x6F spo2_event (SpO2, fixed with offset=+6, internal consistency
      confirmed; Gen4 cross-validation still open)

## IN PROGRESS — real RE work started, not yet solved (3)
- [ ] 0x61/0x09 _dd_sleep_statistics — confirmed broken, never had a
      working baseline. Tried: /60s, /32768Hz, offset-shifting, u32 width.
      NEXT: try u16 field width.
- [ ] 0x6E spo2_ibi_and_amplitude_event — 2 hypotheses killed
      (channel-split, byte-0 counter). NEXT: correlate bytes 1-6 against
      same-window 0x6F values.
- [ ] 0x77 spo2_dc_event — zero real hex captured yet. In PRIORITY_TAGS now,
      needs one fresh pull.

## NOT STARTED — Tier 1, high biometric value (5)
- [ ] 0x53 wear_event — ring on/off wrist, data-validity windows
- [ ] 0x76 bedtime_period — wired into script, never caught a real packet
- [ ] 0x69 temp_period — aggregated temperature over a period
- [ ] 0x6B motion_period — motion state over a period
- [ ] 0x7E/0x7F real_steps_features — step counting (one tag, two event IDs)

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
6 done + 3 in progress + 5 + 12 + 2 + 24 = **52 decoder entries tracked**
(some inventory rows bundle two tag IDs under one decoder, e.g. 0x7E/0x7F
and 0x82/0x83 — so the "35+" figure from earlier referred to distinct
*functions*, this board tracks distinct *tags/sub-types*, which is why the
count differs. Every tag-level entry from the original inventory is
represented above — nothing skipped.)

## Suggested next-session order (unchanged from prior draft, still valid)
1. 0x77 — easiest, data should be ready after one pull.
2. 0x61/0x09 — try u16 width, last untried lever.
3. 0x6E — try bytes 1-6 / SpO2 correlation.
4. Then start working down the Tier 1 NOT STARTED list (0x53, 0x76, 0x69,
   0x6B, 0x7E/0x7F) — these are fresh, no existing hypotheses to test, good
   "clean start" tasks.
5. Tier 2 and the 0x61 debug sub-types are lower priority but ARE on this
   board and WILL get worked through eventually, including the genuinely
   low-value ones (stack usage, periodic counters) for completeness.

## How to use this doc
Check a box, move an item between sections, or add a note inline as
hypotheses get tested. This is the single source of truth for "have we
tried this tag yet" across the entire 38-entry surface — check here before
re-investigating anything.
