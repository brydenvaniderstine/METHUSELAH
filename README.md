# METHUSELAH

Biometric data sovereignty platform. Five isolated layers — nothing bleeds between them.

```
METHUSELAH/
├── web/          ← React PWA (methuselah.ca). Imports from engine/ only.
├── pipeline/     ← BLE RE work: pull scripts, decoders, raw data, findings.
│   ├── tools/
│   ├── decoders/
│   └── data/
│       ├── raw_pulls/
│       └── findings/
├── parsers/      ← One parser per lab/device source. All expose the same output dict.
│   ├── lifelabs/
│   ├── siphox/
│   └── insidetracker/
├── engine/       ← Thresholds, scoring, commands, cross-vector logic. The only thing web/ imports.
└── firmware/     ← XIAO ESP32S3 PlatformIO BLE bridge project.
```

## Layer rules (enforced by README in each directory)
1. `web/` imports from `engine/` only — never from `pipeline/`, `parsers/`, or `firmware/`.
2. Each decoder in `pipeline/decoders/` is self-contained — shared utilities only in `pipeline/decoders/utils.py`.
3. Every parser in `parsers/` exposes the same output interface — a standard biomarker dict — so `engine/` is source-agnostic.

## Current file locations (pre-migration)
Until files are physically moved into the skeleton above, existing code lives at the repo root:
- React PWA: `src/`, `public/`, `api/`, `package.json`, `capacitor.config.ts`, `ios/`
- Pull scripts: `tools/`
- Raw data: `data/raw_pulls/`, `data/findings/`, `data/reference/`, `data/comparisons/`
- Firmware: `firmware/` (already in place)
