# pipeline/decoders/

One file per BLE event tag. No cross-imports between decoder files.

## File naming convention
`0x{tag_hex}.py` — e.g. `0x6a.py` for sleep_period_info_2, `0x5d.py` for hrv_event.

## Interface contract
Each decoder file exposes one function:

```python
def decode(payload: bytes) -> dict:
    ...
```

The returned dict uses snake_case keys matching the field names documented in
`../data/findings/known_issues.md`.

## Shared utilities
`utils.py` — the only place for helpers shared across decoders (e.g. ring timestamp
conversion, struct unpack wrappers, IBI encoding formula). Import from here, not from
each other.

## Current state
Decoder functions currently live inline in `../tools/oura_gen3_morning_pull.py`.
Migration to individual files here is planned but not yet done — do not duplicate
or refactor until that task is scheduled.
