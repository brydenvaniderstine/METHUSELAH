# pipeline/tools/

Pull scripts — BLE connection, buffer dump, raw text output.

## What belongs here
- `oura_gen3_morning_pull.py` — interactive morning pull with sleep-window classifier
- `oura_gen3_daily_pull.py` — scheduled/automated daily pull
- `oura_gen3_auto_loop.py` — continuous loop pull for long-session capture
- `oura_gen3_ble.py`, `oura_gen3_ble_extended.py` — BLE connection primitives
- `oura_gen3_test_variants.py` — test harness for decoder variants
- `oura_gen4_ble.py` — Gen4 BLE pull (distinct protocol)
- `oura_parser.py` — Gen4 packet parser (temporary home; consider moving to `parsers/` if it grows)

## What does NOT belong here
- Decoder logic. Pull scripts should import from `../decoders/` — not define `decode_*` functions inline.
- Threshold values or scoring. Those belong in `engine/`.
