# METHUSELAH // open_ring Decoder Roadmap

Scope: this tracks ONLY the Gen3 BLE decoder-building work (reading
open_ring as reference, wiring/testing decoders in
tools/oura_gen3_morning_pull.py). Not the broader METHUSELAH product
roadmap.

## Rules of the road (apply to every decoder, no exceptions)
1. Real source only — read `~/Desktop/open_ring/driver/decoders.py`
   directly via `cat`/`sed`. Never trust web search or fetched GitHub
   pages about this repo (confirmed unreliable 2026-06-24).
2. No decoder is "working" until tested against real captured hex from
   your own ring. open_ring's docstring confidence level (verified vs.
   auto-extracted vs. raw passthrough) is a starting hint, not proof.
3. A negative result (hypothesis killed) is a real, loggable finding.
   Write it down so it's never re-tested from scratch.
4. One decoder at a time. Don't open a third investigation while two are
   already mid-flight.

## Status board

### DONE — working, validated against real data
- [x] sleep_state (0x6A)
- [x] HRV / RMSSD (0x5D)
- [x] Fuel gauge battery (0x61/0x14)
- [x] Sleep temperature (0x75)
- [x] Motion (0x47) — decodes cleanly, real values seen
- [x] SpO2 (0x6F) — fixed with offset=+6, internally consistent across
      21 real packets. Cross-validation against Gen4 still open (see below).

### IN PROGRESS / BLOCKED
- [ ] **0x61/0x09 (sleep statistics)** — confirmed broken, NOT a
      regression (never had a working baseline). Sub-byte and length
      check out; field layout/divisor still wrong. Tried: /60 (seconds),
      /32768 (RTC ticks), offset-shifting, u32 width. NEXT UNTRIED: u16
      field width instead of u32.
- [ ] **0x6E (SpO2 IBI+amplitude)** — 2 hypotheses killed (channel-split,
      byte-0 counter). NEXT UNTRIED: correlate bytes 1-6 against same-window
      0x6F SpO2 percent values.
- [ ] **0x77 (SpO2 DC event)** — zero real hex captured yet. Added to
      PRIORITY_TAGS; needs one fresh pull to get real data, then can
      actually start analysis.
- [ ] **SpO2 (0x6F) Gen4 cross-validation** — fix is internally consistent
      but not yet confirmed against a real same-night Gen4 SpO2 reading.
      Needs a clean night with both a Gen3 pull and Gen4 screenshot
      covering the same window.

### NOT STARTED (from original inventory, still real opportunities)
- [ ] 0x53 (wear event) — ring on/off wrist, useful for data-validity windows
- [ ] 0x76 (bedtime period) — wired in, never caught a real packet yet
- [ ] 0x61/0x24 (battery_level_changed) — wired in, never caught a real
      packet yet
- [ ] 0x69 (temp period), 0x6B (motion period) — Tier 1, not yet attempted

## Suggested next-session order
1. 0x77 — easiest win, just needs a pull (data should already be there
   waiting once you run one).
2. 0x61/0x09 — try the u16-width idea, the one untried lever left.
3. 0x6E — try the bytes 1-6 / SpO2 correlation idea.
4. Whichever of the untouched Tier 1 tags (0x53, 0x76, 0x69, 0x6B) sounds
   interesting that day — these don't have open hypotheses yet, so they're
   good "fresh start" tasks if the above three all stall.

## How to use this doc
Update the status board after each session — move things between
DONE/IN PROGRESS/NOT STARTED, and add any new killed-hypothesis notes
inline under the relevant bullet. This file IS the source of truth for
"what have we tried" — check it before re-attempting anything.
