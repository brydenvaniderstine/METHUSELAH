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

## Founding rationale
Before making any product or feature decision, read:
`pipeline/data/findings/why_not_conventional_trackers.md`
This document defines what METHUSELAH is explicitly built against.
Every feature must pass the design test at the bottom of that file
before it ships. This is not optional — it is the North Star.

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

---

## Deferred decisions

These decisions have been identified and deliberately parked.
They are not forgotten — they live here until conditions change.

### DGX Spark acquisition
- Hardware: NVIDIA Grace Blackwell, 1 PFLOPS FP4, 128GB unified memory, ~$3–4K USD
- Use case: local LLM inference for METHUSELAH v2 — data sovereignty, no token costs, clinical compliance
- Buy signal: API costs become meaningful OR a clinical partner requires data residency
- Status: watching, not buying. No action until one of the two buy signals fires.

### Enoch / METHUSELAH data relationship
- Enoch (enoch.ca) is the psychological self-awareness companion; METHUSELAH is the biological execution layer
- Currently two separate Vercel deployments with no defined data relationship
- Decision needed: permanently separate / future data bridge / unified platform
- Status: parked until METHUSELAH Track B and v2 are further along

### Evening pull folder naming convention
- Current: time-of-day (gen3_morning / gen3_evening)
- Alternative: classifier output (sleep_window / active_window)
- Status: provisional time-of-day convention in place — revisit once two-pulls-a-day rhythm is established

### Track B completion definition — DRAFT (not yet approved)

Track B is considered complete when all of the following are true:

1. **sleep_state (0x6A)** returns real stage transitions across a full night --
   not a flat "100% state=1" result. At minimum: REM, Light, and Deep stages
   must appear in a single night's pull with timestamps that roughly align
   with Gen4 official app output.

2. **HRV (0x5D)** fires consistently -- at least one 0x5D event present in
   three consecutive morning pulls. Currently returning zero events.

3. **SpO2 (0x6F)** cross-validation passes -- Gen3 decoded SpO2 avg within
   +-5% of Gen4 official app reading for three consecutive nights.
   Currently showing one confirmed inconsistency (88% vs 97%).

4. **Five blocked decoders** (0x6E, 0x77, 0x7E/0x7F, 0x6B) either:
   (a) decoded to a confirmed working state, or
   (b) formally documented as unresolvable with available data and closed.

5. **Comparison CSV** contains a minimum of 14 consecutive nightly rows
   with both Gen3 and Gen4 data present (not Gen4-only rows).

When all five conditions are met, Track B is closed and v2 parser work
begins. This definition can be revised -- but only in a dedicated session
with an explicit reason for changing the bar.

**Current status: 0 of 5 conditions met.**

---

## Known design tensions

These are not bugs and not deferred decisions — they are structural
tensions surfaced by the design test and acknowledged as real. Every
future feature must be checked against these before shipping.

### #6 — Burnout: no adherence acknowledgment
The command engine issues the same command text on day 1 and day 30
of consecutive correct execution. A person who has executed
"EXECUTE 45-MIN ZONE 2 OUTPUT" correctly for two weeks receives no
acknowledgment of that effort — the briefing text is identical every
time. This is the burnout failure mode from the founding rationale
applied to METHUSELAH itself.

Status: acknowledged, not resolved. The tap-to-expand briefing does
not worsen this — but does not solve it. Future decision: should
briefings include a consecutive-execution count or an adherence signal?
Do not add this without a dedicated design session — it risks drift
toward engagement mechanics.

### #7 — Reliability: briefings cite values from hardware with known gaps
The briefing templates cite specific measured values ("your HRV read
35ms") derived from Gen3 BLE decoding. The Gen3 decoder has a
documented cross-validation gap: SpO2 read 88% on a night where Gen4
official read 97% (known_issues.md). A person reading a briefing will
likely treat the cited value as authoritative, with no awareness of
the measurement uncertainty.

Status: acknowledged, not resolved. No reliability caveat exists in
the briefing templates as written. Future decision: should briefings
include a confidence qualifier or data-source attribution? Do not add
this without confirming it doesn't tip the briefing into information
overload.

### #8 — Override: briefings add authority without an escape valve
The tap-to-expand mechanic is opt-in — a person who ignores the tap
never sees the authority claim. This partially mitigates the override
risk. However, once tapped, the briefing has no acknowledgment that
the person is the final authority. "Your HRV read 35ms, Zone 2
stimulates parasympathetic recovery" carries implicit authority with
no "if you feel genuinely fine, you may be right" qualifier.

Status: partially mitigated by the opt-in tap mechanic, not fully
resolved. The original silent command had no authority claim at all —
the briefing adds one. Future decision: does the briefing need a
single closing line that returns authority to the person? Candidate
language: "You are the final authority. If this doesn't match how
you feel, trust yourself." Do not add without pressure-testing against
the prime directive — it risks softening the command into a suggestion.

### Threshold calibration — personal vs universal

Current thresholds:
- deep_sleep: 13% — clinical floor, applies universally (healthy adult range 13–23%)
- hrv: 25ms — personalised to 355-night baseline of 29.3ms avg (−1 standard deviation)
- glucose: 5.8 mmol/L — standard clinical threshold, applies universally
- rhr: 60 bpm — standard clinical threshold, applies universally

The HRV threshold is the only one currently personalised to this user.
When METHUSELAH expands to additional users, HRV threshold must be
derived from each user's own baseline — not inherited from this calibration.

Decision needed before multi-user: an onboarding flow that establishes
a personal HRV baseline (minimum 30 nights of data) before the engine
can fire accurate HRV commands for that user. Until that exists,
the 25ms threshold is accurate for this user only.

Rationale for deep_sleep at 13%: clinical literature places the healthy
adult floor at 13% of total sleep time. Below 13% is where measurable
physiological consequences begin regardless of personal baseline.
Personal baseline (16.4% avg over 355 nights) sits in the healthy
middle of the 13–23% range — using 13% as threshold fires only when
genuinely below the clinical minimum, not just below personal best.
