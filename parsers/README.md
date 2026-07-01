# parsers/

One subdirectory per external biomarker data source. Not yet built.

## Purpose
Parse raw exports from lab and consumer health sources into a standardised
biomarker dict that `engine/` consumes. The engine never knows or cares which
source a value came from.

## Interface contract (applies to every parser)
Each parser's entry point returns:

```python
def parse(filepath: str) -> dict[str, float | str | None]:
    """
    Returns a flat dict of biomarker keys → values.
    Keys are standardised across all parsers (see engine/schema.py when created).
    Unknown or missing fields return None, never raise.
    """
```

Example output shape (same structure regardless of source):
```python
{
    "glucose_mmol":     5.4,
    "hba1c_pct":        5.1,
    "ferritin_ug_l":    42.0,
    "vitamin_d_nmol_l": 87.0,
    "hscrp_mg_l":       0.4,
    # ...
}
```

## Planned parsers
- `lifelabs/` — LifeLabs PDF blood panel results
- `siphox/` — SiPhox at-home blood test CSV export
- `insidetracker/` — InsideTracker CSV export

## Import rules
- Parsers import from `engine/schema.py` for the canonical key list — never the reverse.
- `web/` never imports from `parsers/` directly.
