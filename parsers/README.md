# parsers/

One subdirectory per external biomarker data source. Each source is a plugin, not a dependency.

## Plugin model
Adding a source: create a new subdirectory with the standard output interface. Nothing else changes.
Removing a source: delete its directory, update `engine/` to stop reading that source. `web/`, `pipeline/`, and `firmware/` are unaffected.

Each source directory is fully self-contained and independently removable. If `lifelabs/`
is removed tomorrow because the approach changes, nothing in `web/`, `pipeline/`, `engine/`,
or `firmware/` breaks — provided `engine/` is updated to stop consuming that source first.

## Interface contract (every parser must implement this)

```python
def parse(filepath: str) -> dict[str, float | str | None]:
    """
    Returns a flat dict of biomarker keys → values.
    Keys are the canonical names from engine/schema.py.
    Missing or unparseable fields return None — never raise.
    """
```

Example output (same shape regardless of source):
```python
{
    "glucose_mmol":     5.4,
    "hba1c_pct":        5.1,
    "ferritin_ug_l":    42.0,
    "vitamin_d_nmol_l": 87.0,
    "hscrp_mg_l":       0.4,
}
```

## Import rules
- Parsers import the canonical key list from `engine/schema.py`. Nothing else.
- `web/` never imports from `parsers/` directly — only via `engine/`.
- Parsers never import from `pipeline/`, `web/`, or `firmware/`.

## Removability
This entire directory can be removed without breaking `web/`, `pipeline/`, or `firmware/`.
`engine/` would need to be updated to remove references to parser outputs, but the interface
change is local to `engine/`.

## Sources (all future)
| Directory | Source | Format | Status |
|---|---|---|---|
| `lifelabs/` | LifeLabs blood panels | PDF | Not built |
| `siphox/` | SiPhox at-home tests | CSV | Not built |
| `insidetracker/` | InsideTracker results | CSV | Not built |
