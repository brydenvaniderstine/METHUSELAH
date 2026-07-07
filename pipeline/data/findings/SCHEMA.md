# data/findings/gen3_vs_gen4_comparison.csv — Schema

Authoritative column definition for the cross-validation comparison log.
Read this before adding a column or interpreting a value.

---

## Column definitions

| Column | Type | Source | Units | Gaps / ambiguities |
|---|---|---|---|---|
| `date` | string | Manual | Night covered, e.g. `2026-06-28/29` | Represents the sleep night (date of lights-out through waking), not a single calendar date. Cross-date nights (e.g. Jun 28 evening → Jun 29 morning) are written as `YYYY-MM-DD/DD`. |
| `gen3_hr_min` | float | Gen3 BLE — decoded IBI via 0x80 green_ibi_quality_event | bpm | Derived from minimum IBI across the pull window, not a direct sensor field. Only populated when a GREEN_IBI session was active (9/29 pulls have data). |
| `gen3_hr_max` | float | Gen3 BLE — decoded IBI via 0x80 | bpm | Same session-gating caveat as gen3_hr_min. |
| `gen3_hr_avg` | float | Gen3 BLE — decoded IBI via 0x80 and/or 0x6a avg_hr field | bpm | Cross-validated against 0x6a avg_hr where both are present (mean delta +0.9bpm). |
| `gen4_hr_lowest` | float | Gen4 Oura app screenshot — manual transcription | bpm | Lowest RHR for the night as reported by Gen4. Not instantaneous minimum. |
| `gen4_hr_avg` | float | Gen4 Oura app screenshot — manual transcription | bpm | Average HR for the night as reported by Gen4. |
| `gen3_spo2_min` | float | Gen3 BLE — 0x6f spo2_event decoder (offset +6 confirmed) | % | Minimum across all 0x6f samples in the pull window. Pull window may not cover full night. |
| `gen3_spo2_max` | float | Gen3 BLE — 0x6f spo2_event decoder | % | Maximum across all 0x6f samples. |
| `gen3_spo2_avg` | float | Gen3 BLE — 0x6f spo2_event decoder | % | Mean across all 0x6f samples in pull window. |
| `gen4_spo2_avg` | float | Gen4 Oura app screenshot — manual transcription | % | Nightly average SpO2 as reported by Gen4. Empty in current data — Gen4 SpO2 not shown in available screenshots. |
| `gen3_sleep_temp_min` | float | Gen3 BLE — 0x75 sleep_temp_event decoder | °C | Minimum skin temperature sample across the pull window. |
| `gen3_sleep_temp_max` | float | Gen3 BLE — 0x75 sleep_temp_event decoder | °C | Maximum skin temperature sample across the pull window. Note: a single-event pull returns min=max. |
| `gen4_total_sleep` | string | Gen4 Oura app screenshot — manual transcription | e.g. `9h 32m` | Stored as a human-readable string, not a numeric duration. Parse before any arithmetic. |
| `gen4_sleep_efficiency` | float | Gen4 Oura app screenshot — manual transcription | % | Sleep efficiency as reported by Gen4. |
| `gen3_sleep_state_coverage` | string | Gen3 BLE — 0x6a sleep_period_info_2 decoder | e.g. `state=1 across all 10 samples` | Qualitative summary of sleep_state enum distribution across 0x6a packets in the pull. Known gap: sleep_state decoder returns state=1 for all samples regardless of true stage — see known_issues.md. |
| `gen4_rem_pct` | float | Gen4 Oura app screenshot — manual transcription | % | REM as % of total sleep for the night. |
| `gen4_light_pct` | float | Gen4 Oura app screenshot — manual transcription | % | Light sleep as % of total sleep. |
| `gen4_deep_pct` | float | Gen4 Oura app screenshot — manual transcription | % | Deep sleep as % of total sleep. |
| `gen4_awake_min` | integer | Gen4 Oura app screenshot — manual transcription | minutes | Total awake time during sleep window as reported by Gen4. |
| `gen4_hrv_avg` | float | Gen4 Oura CSV export — `Average HRV` field | ms | Average HRV for the night from Oura Gen4 export CSV. Added 2026-07-06. |
| `gen4_respiratory_rate` | float | Gen4 Oura app Readiness card — manual transcription | breaths/min | From Readiness card, not Sleep card. Personal baseline: 13.09 ± 0.43 br/min (359 nights). |
| `gen4_activity_balance` | string | Gen4 Oura app Readiness card — manual transcription | Optimal / Good / Fair / Poor | Qualitative contributor rating from Gen4 Readiness card. |
| `gen4_readiness_contributors_summary` | string | Gen4 Oura app Readiness card — manual transcription | Free text | Full qualitative summary of all Readiness card contributors for the night. Long field — may contain commas; handle CSV quoting carefully. |
| `notes` | string | Manual | Free text | Decoder gaps, anomalies, cross-validation flags, known issues for that row. Also long — handle CSV quoting carefully. |

---

## Schema change log

| Date | Change |
|---|---|
| 2026-06-30 | Initial schema documented. Columns `gen4_respiratory_rate`, `gen4_activity_balance`, `gen4_readiness_contributors_summary` added mid-stream on first day of logging — not present in the original header. |
| 2026-07-06 | `gen4_hrv_avg` column added. Source: Oura Gen4 CSV export (`Average HRV` field). Backfilled via `pipeline/tools/merge_oura_csv.py` for all overnight rows with confirmed Oura wake-date. Captures HRV trend across Track B comparison period: 31→31→26→18→22ms (declining six-night run bottoming at 18ms on 2026-07-05, partial recovery to 22ms on 2026-07-06). Note: `2026-07-03 evening` row left `n/a` — no unambiguous Gen4 wake-date counterpart (July 4 already claimed by `2026-07-04/05`). |

---

## Rules for future additions

Add a column only when it has at least one real data point. Document it here before adding it to the CSV. Back-fill prior rows with `n/a` — never leave a column silently absent from earlier rows.
