# METHUSELAH // Known Issues — Gen3 Decoders

## SpO2 event decoder (0x6f) — FIXED (pending Gen4 cross-validation)

**Status:** Fixed 2026-06-24. Flat offset of -6 applied to raw sample bytes.

**Root cause:** Raw payload bytes were `true_percent + 6`, not raw percent.
header_high/header_low (p[0] nibbles) were tested for correlation with the
needed correction and showed none — ruled out as a scale/calibration factor,
likely a sequence or quality byte instead.

**Evidence:**
- 190 real packets / 2,476 samples, retrieved via `grep -r "SPO2 event"`
  across 14 saved pull files (2026-06-19 to 2026-06-23) and pasted for
  analysis — offset=6 is the minimum correction eliminating all >100%
  violations (offset=5 leaves 5 violations; offset=7+ starts going low).
- Cross-checked against 2026-06-24 morning pull (21 fresh packets, not
  part of the original 190): same offset, zero violations, corrected
  range 91-99%, consistent with expected overnight SpO2 behavior.

**Still open:** No same-night Gen4/Oura official SpO2 comparison yet (the
validation method used successfully for HRV). Treat as fixed-by-internal-
consistency, not yet ground-truth-confirmed. Once available, cross-check
and update this status to fully confirmed.

---
*Logged 2026-06-23. Found during first live test of the SpO2 decoder
immediately after wiring it into the pull script. Fixed 2026-06-24.*

## Debug data sleep statistics decoder (0x61/0x09) — BROKEN, NOT TRUSTWORTHY

**Status:** New regression, found 2026-06-24. Do not use sleep stats output
until fixed.

**Symptom:** `decode_debug_data_sleep_statistics()` produced physically
impossible values on the 2026-06-24 morning pull:
- `deep=111924.3min` (~77.7 days) and `deep=111344.9min` in the same
  session, four records total, all wildly out of range
- `pfsm_state=128` appearing twice, vs. small single-digit values
  (5, 6) seen previously — may indicate two different packet sub-formats
  being routed through the same decoder

**Likely cause:** Unconfirmed. Possible struct misalignment, or these
0x61/0x09 packets have a different internal layout than the ones the
decoder was originally validated against. Needs investigation before
trusting deep-sleep-duration output again.

**Next steps:**
1. Pull raw hex for these specific records (boot_ts=42166360, 42166365,
   42166971, 42166976) and inspect byte-by-byte against the documented
   layout (ticks_in_deep_sleep, ticks_in_sleep, ticks_awake, pfsm_state).
2. Check whether pfsm_state=128 packets are a distinct variant from
   pfsm_state=5/6 packets — may need a sub-format branch.
3. Do not log any sleep-stats rows to any comparisons CSV until resolved.

---
*Logged 2026-06-24. Found during 2026-06-24 morning pull, same session as
the SpO2 fix.*
