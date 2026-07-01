# pipeline/

BLE reverse-engineering work: pull scripts, decoders, raw data, findings.
Offline tooling only — nothing in `web/`, `engine/`, or `parsers/` imports from here.

## Structure
```
pipeline/
├── tools/       ← Pull scripts. Connect to ring, dump buffer, write to raw_pulls/.
├── decoders/    ← One file per tag. Shared helpers in decoders/utils.py only.
└── data/
    ├── raw_pulls/
    │   ├── gen3_morning/
    │   └── gen3_evening/
    └── findings/
```

## Import rules
`pipeline/` has no runtime consumers. `web/` and `engine/` never import from here.
Pull scripts in `tools/` import from `decoders/` — not the other way around.

## Removability
This entire directory can be removed without breaking `web/`, `engine/`, `parsers/`,
or `firmware/`. It is offline research tooling. If the BLE RE work is complete and
decoders are productionised into `engine/`, this directory becomes archival.

Individual subdirectories are also independently removable:
- Remove `decoders/` → `tools/` scripts lose their imports but nothing outside `pipeline/` changes.
- Remove `data/raw_pulls/` → findings docs become reference-only. No code breaks.
- Remove `data/findings/` → documentation loss only. No code breaks.

## Current violations (flagged, not yet fixed)
| File | Lines | Violation | Correct home |
|---|---|---|---|
| `tools/oura_gen3_morning_pull.py` | 46–145 | Decoder functions (`decode_sleep_period_info_2`, `decode_hrv_event`, `decode_spo2_event`, `decode_sleep_temp_event`, `decode_motion_event`, etc.) defined inline in a pull script | `pipeline/decoders/0x6a.py`, `0x5d.py`, `0x6f.py`, `0x75.py`, `0x47.py`, etc. |
