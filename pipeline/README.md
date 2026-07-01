# pipeline/

BLE reverse-engineering work: pull scripts, decoders, raw data, findings.
This layer never gets imported by `web/`. It is offline tooling only.

## Structure

```
pipeline/
├── tools/       ← Pull scripts. Connect to the ring, dump the buffer, write raw_pulls/.
├── decoders/    ← One file per tag (0x6a.py, 0x5d.py, etc.). Shared helpers in utils.py only.
└── data/
    ├── raw_pulls/
    │   ├── gen3_morning/    ← Morning sleep-window pulls
    │   └── gen3_evening/    ← Pre-bed and activity pulls
    └── findings/            ← Decoder notes, roadmap, comparison CSVs, baselines
```

## Import rules
- `pipeline/` has no consumers. Nothing in `web/`, `engine/`, or `parsers/` imports from here.
- Each decoder in `decoders/` is self-contained. Cross-imports between decoder files are forbidden.
- Shared decoder utilities go in `decoders/utils.py` only.

## Current violations (do not fix yet — listed for future cleanup)
- `tools/oura_gen3_morning_pull.py` contains full decoder function definitions inline (`decode_sleep_period_info_2`, `decode_hrv_event`, `decode_spo2_event`, `decode_sleep_temp_event`, `decode_motion_event`, etc. — lines 46–145). These belong in `decoders/` as individual files. The pull script should import from `decoders/`, not define its own.
