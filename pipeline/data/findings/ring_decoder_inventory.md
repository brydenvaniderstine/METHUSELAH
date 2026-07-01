# METHUSELAH // Gen3 Ring Decoder Inventory

Full catalog of every event-type decoder available in open_ring
(LogosIsLife/open_ring, GPL-3.0), captured 2026-06-23. We currently use only
3 of these (sleep_period_info_2, ibi_and_amplitude_event, hrv_event). This
doc tracks what else is available so we can build out the pipeline
systematically rather than rediscovering this each session.

REMINDER: GPL-3.0 code must be removed before any commercial release of
METHUSELAH (already on the "remove before commercial" checklist along with
NOOP-derived code). Use this as a reference for protocol facts (tags, field
layouts) and reimplement decode logic independently when building toward a
commercial-safe version.

## Tier 1 — Strong-decode (verified end-to-end), high biometric value

| Tag | Decoder | What it gives us | METHUSELAH relevance |
|---|---|---|---|
| 0x46 | decode_temp_event | Skin temperature | Body temp trend, illness detection |
| 0x47 | decode_motion_event | Real motion/accelerometer | Activity vector, sleep disturbance |
| 0x4a | decode_ppg_amplitude_ind | Raw PPG signal strength | Signal quality validation |
| 0x53 | decode_wear_event | Ring on/off wrist | Data validity windows - know when readings are real vs. ring removed |
| 0x5d | decode_hrv_event | **HRV (RMSSD) per 5-min window** | ALREADY IN USE - core HRV vector |
| 0x60 | decode_ibi_and_amplitude_event | Raw IBI + amplitude | ALREADY IN USE - core HR/HRV foundation |
| 0x69 | decode_temp_period | Temperature over a period | Aggregated temp trend |
| 0x6b | decode_motion_period | Motion over a period | Likely feeds activity tracking |
| 0x6f | decode_spo2_event | **Blood oxygen (SpO2)** | New vector - we've seen this data in every pull but never decoded it |
| 0x76 | decode_bedtime_period | Sleep start/end boundaries | Could directly give sleep window without inferring from state transitions |
| 0x7e/0x7f | decode_real_steps_features | Step counting | Activity vector |

## Tier 2 — Promoted from auto-extracted wire format (real but weaker confidence)

| Tag | Decoder | Notes |
|---|---|---|
| 0x49 | decode_sleep_summary_1 | 2x u16, no confirmed semantics |
| 0x4c | decode_sleep_summary_2 | u16+u32, no confirmed semantics |
| 0x4f | decode_sleep_summary_3 | mixed widths, no confirmed semantics |
| 0x50 | decode_activity_info_event | Daytime activity, partial confidence |
| 0x5b | decode_ble_connection_ind | BLE link events |
| 0x5e | decode_selftest_event | Ring self-test results |
| 0x6c | decode_feature_session | Feature session boundaries |
| 0x6e | decode_spo2_ibi_and_amplitude_event | Combined SpO2+IBI |
| 0x72 | decode_sleep_acm_period | Sleep accelerometer period (seen frequently in our pulls) |
| 0x73 | decode_ehr_trace_event | Exercise heart rate trace |
| 0x75 | decode_sleep_temp_event | Sleep-specific temp |
| 0x77 | decode_spo2_dc_event | SpO2 DC component (seen frequently in our pulls) |
| 0x80 | decode_green_ibi_quality_event | **This is our mystery "UNKNOWN (0x80)" tag from past pulls** |
| 0x82/0x83 | decode_scan_start/end | BLE scan boundaries |
| 0x56/0x85 | decode_unknown_56/85 | Even open_ring's authors haven't identified these |

## Tier 3 — Debug/diagnostic telemetry (0x61 sub-types)

Operationally important per Bryden's note: battery/hardware health data
prevents silent data-loss from a dead ring. All routed through tag 0x61
(API_DEBUG_DATA), dispatched by a sub-byte at payload offset 0.

| Sub-byte | Function | What it gives us |
|---|---|---|
| 0x09 | _dd_sleep_statistics | ticks_in_deep_sleep, ticks_in_sleep, ticks_awake - **direct deep sleep duration, pre-computed on-device** |
| 0x0a | _dd_flash_usage_statistics | Flash read/write/erase ticks - buffer health |
| 0x0c | _dd_period_info_statistics | Period measurement timing |
| 0x0d | _dd_ble_usage_statistics | BLE connection mode ticks |
| 0x0f | _dd_security_failure | Auth/security failure events |
| 0x14 | _dd_fuel_gauge_statistics | **Battery %, voltage, current draw, remaining capacity** |
| 0x15 | _dd_finger_detection | Wear/contact detection (raw bits) |
| 0x1a | _dd_event_sync_statistics | Sync performance (connection interval, bytes synced) |
| 0x1b | _dd_bootloader_debug_log | Bootloader logs |
| 0x1e | _dd_fuel_gauge_register_dump | Raw battery chip register dump |
| 0x1f | _dd_ring_hw_information | Hardware info |
| 0x20 | _dd_charging_ended_statistics | Charging session stats |
| 0x21 | _dd_fuel_gauge_logging_registers | More battery chip registers |
| 0x23 | _dd_event_sync_cache_statistics | Cache vs flash read counts |
| 0x24 | _dd_battery_level_changed | **Battery % + voltage at moment of change, with reason code** |
| 0x25/0x26 | _dd_hardware_test_*_values | Hardware self-test results (3-phase) |
| 0x27 | _dd_charging_ended_statistics_continued | More charging stats |
| 0x28 | _dd_afe_statistics_values | Analog front-end (PPG sensor chip) stats |
| 0x29 | _dd_acm_configuration_changed | Accelerometer/gyro config changes |
| 0x2a | _dd_field_test_information | Field test data |
| 0x2b | _dd_stack_usage_statistics | Firmware stack usage (debugging) |
| 0x30 | _dd_alt_periodic_counter | Periodic heartbeat counter |
| 0x33 | _dd_open_afe_ppg_settings_data | PPG sensor chip variant + settings |
| 0x35 | _dd_ppg_signal_quality_stats | **SNR, signal quality, ibi_quality_percentage - tells us how trustworthy our other readings are** |
| 0x36 | _dd_charger_information | Charger link params, firmware/serial via charging dock |
| 0x3b | _dd_alt_afe_period_tick | AFE sample rate (25Hz/50Hz) |
| 0x3c | _dd_alt_ppg_cont | PPG continuation records |
| 0x3d | _dd_charger_debug_information | Charger debug info |
| 0x3f | _dd_daily_drop_sample | Daily diagnostic sample |
| 0x04 | _dd_alt_text | ASCII debug strings (same family as tag 0x43) |

## Immediate priorities identified from this catalog

1. **`0x61/0x09` (_dd_sleep_statistics) is a major find** — gives
   `ticks_in_deep_sleep`, `ticks_in_sleep`, `ticks_awake` directly,
   pre-computed by the ring's own firmware. This may be the actual deep
   sleep % answer we've been trying to approximate via sleep_state
   percentages. Should be the next decoder we wire in and test.
2. **`0x14`/`0x24` (battery)** — operationally critical per Bryden's
   feedback. A dead ring produces no data at all; monitoring battery state
   protects every other vector.
3. **`0x6f` (SpO2)** and **`0x53` (wear event)** — real new vectors we've
   been blind to despite seeing the raw packets in every pull.
4. **`0x80`** — finally explains our recurring "UNKNOWN (0x80)" mystery tag
   from multiple past pulls.

## Build approach going forward
Add tags incrementally to the pull script's decode section (same pattern as
sleep_state and HRV), prioritizing Tier 1 + the sleep_statistics/battery
debug sub-types first. Test each against real captured data before trusting
output, same validation discipline used for sleep_state and HRV.
