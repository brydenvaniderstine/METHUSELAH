# pipeline/decoders/

One file per BLE event tag. No cross-imports between decoder files.

## File naming
`0x{tag_hex}.py` — e.g. `0x6a.py` for sleep_period_info_2, `0x5d.py` for hrv_event.

## Interface contract
Each decoder file exposes one function:

```python
def decode(payload: bytes) -> dict:
    ...
```

The returned dict uses snake_case keys matching field names in
`../data/findings/known_issues.md`.

## Shared utilities
`utils.py` — the only place for helpers shared across decoders (timestamp conversion,
struct unpack wrappers, IBI encoding formula). Import from here, never from each other.

## Removability
Each decoder file is independently removable. Deleting `0x77.py` has zero effect on
any other decoder, on `tools/`, or on anything outside `pipeline/`. No decoder imports
another decoder — the only allowed imports are `utils.py` and the Python standard library.

If a tag is determined to be noise or irrelevant, delete its file. Nothing else changes.

## Adding a new decoder
1. Create `0x{tag}.py` with a `decode(payload: bytes) -> dict` function.
2. Add findings to `../data/findings/known_issues.md`.
3. Update `../data/findings/open_ring_roadmap.md` status.
4. Import from `tools/` scripts as needed. Nothing else changes.

## Current state
Decoder functions currently live inline in `tools/oura_gen3_morning_pull.py` (lines 46–145).
Migration to individual files here is planned. Do not add new decoders to the pull script —
put them here directly.
