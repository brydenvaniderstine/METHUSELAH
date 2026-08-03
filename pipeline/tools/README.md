# pipeline/tools/

Pull scripts — BLE connection, buffer dump, raw text output.

## What belongs here
- `oura_gen3_ble_daemon.py` — persistent-connection overnight daemon (current, live wake-detection)
- `gen3_daemon_watchdog.py` — supervises the daemon, restarts on a silent BLE stall
- `oura_gen3_morning_pull.py` — safety-net pull fired after the daemon, also runnable standalone
- `gen3_ble_connection.py` — shared connect/auth/setup + incremental history-request primitives
- `gen3_bridge.py` — shared bridge JSON construction + live-site push
- `oura_gen3_daily_pull.py` — scheduled/automated daily pull
- `oura_parser.py` — Gen4 packet parser (temporary home; consider moving to `parsers/` if it grows)

Removed 2026-08-03 (superseded by the daemon, unreferenced by any script/plist,
real duplicate-handshake DRY violation — see `known_issues.md`):
`oura_gen3_auto_loop.py`, `oura_gen3_ble.py`, `oura_gen3_ble_extended.py`,
`oura_gen3_test_variants.py`, `oura_gen4_ble.py` (Gen4 is also permanently
closed as a data source, see the METHUSELAH skill).

## What does NOT belong here
- Decoder logic. Pull scripts should import from `../decoders/` — not define `decode_*` functions inline.
- Threshold values or scoring. Those belong in `engine/`.
