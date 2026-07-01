# METHUSELAH — Architecture

Biometric data sovereignty platform. Bryden Van Iderstine, 2026.
Read this before touching any file.

---

## What this is

A personal health intelligence system that ingests data from wearables, lab panels, and
continuous sensors, runs it through a decision layer, and surfaces actionable commands
via a mobile PWA. The design principle is data sovereignty: raw data never leaves the
device unless the user explicitly chooses to export it.

---

## The five layers

```
web/          React PWA — methuselah.ca + iOS (Capacitor)
pipeline/     BLE reverse-engineering: pull scripts, decoders, raw data, findings
parsers/      Lab and device importers — one directory per source
engine/       Thresholds, scoring, commands, cross-vector logic
firmware/     XIAO ESP32S3 BLE bridge (PlatformIO)
```

### Import rules — enforced, not optional

```
web/       → engine/ only
engine/    → parsers/ only
parsers/   → nothing (pure input transforms)
pipeline/  → nothing (offline tooling, no runtime consumers)
firmware/  → nothing (isolated embedded project)
```

Violations are listed in each layer's README. The rule is: if a change in `pipeline/`
requires a change in `web/`, a boundary has been crossed.

---

## Removability contract

Every layer and every component within a layer is designed to be independently
removable. Nothing has a hard dependency on the existence of any other specific
component — only on the *interface* that component exposes.

- Remove `parsers/lifelabs/` → update `engine/` to stop reading that source. `web/` unchanged.
- Remove `pipeline/decoders/0x77.py` → delete the file. Nothing else changes.
- Remove a data vector from `engine/` → `web/` reads fewer fields. No structural change.
- Add a new parser (`parsers/whoop/`) → create the directory with the standard output dict. Nothing else changes.

---

## Build status

| Layer | Status | Notes |
|---|---|---|
| `web/` | **Built** | React PWA live at methuselah.ca. Capacitor iOS wrapper exists. Business logic not yet extracted to `engine/` — violations documented in `web/README.md`. |
| `pipeline/` | **In progress** | 34 Gen3 pulls captured. 9 decoders validated, 14 partial. Decoder functions currently inline in `tools/oura_gen3_morning_pull.py` — migration to `pipeline/decoders/` is pending. |
| `parsers/` | **Future** | Directory skeleton exists. No parsers built. Targets: LifeLabs PDF, SiPhox CSV, InsideTracker CSV. |
| `engine/` | **Future** | Directory exists. Logic currently lives in `src/App.js` — extraction pending. |
| `firmware/` | **In progress** | XIAO ESP32S3 PlatformIO project exists. BLE bridge functional. |

---

## Key files

| File | Purpose |
|---|---|
| `pipeline/data/findings/open_ring_roadmap.md` | Decoder status tracker — check before starting any pipeline work |
| `pipeline/data/findings/known_issues.md` | Per-decoder findings, falsified hypotheses, pull logs |
| `pipeline/data/findings/gen4_baselines.md` | Personal percentile reference bands for cross-validation |
| `pipeline/data/findings/gen3_vs_gen4_comparison.csv` | Night-by-night Gen3/Gen4 cross-validation |
| `engine/README.md` | Lists all pending extractions from `src/App.js` |
| `web/README.md` | Lists all current layer violations in the frontend |

---

## Adding a new data source

1. Create `parsers/{source}/` with a `parse.py` exposing `parse(filepath) -> dict`.
2. Use the canonical key names from `engine/schema.py` (when created).
3. Update `engine/` to consume the new source.
4. Nothing in `web/`, `pipeline/`, or `firmware/` changes.

## Adding a new BLE decoder

1. Create `pipeline/decoders/0x{tag}.py` with a `decode(payload: bytes) -> dict` function.
2. Import it from `pipeline/tools/` scripts as needed.
3. Document findings in `pipeline/data/findings/known_issues.md`.
4. Nothing in `web/`, `engine/`, `parsers/`, or `firmware/` changes.

## Adding a new hardware sensor (e.g. second XIAO for GSR)

1. Add firmware in `firmware/` for the new sensor.
2. Add a decoder in `pipeline/decoders/` for its protocol.
3. Add the new vector to `engine/` — thresholds, scoring weight, command impact.
4. `web/` reads the new value from `engine/`. No structural change to `web/` required.
