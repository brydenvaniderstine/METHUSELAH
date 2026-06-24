# METHUSELAH // Known Issues — Gen3 Decoders

## SpO2 event decoder (0x6f) — VALUES OUT OF RANGE, NOT TRUSTWORTHY

**Status:** Provisional/broken. Do not use for any real SpO2 readings until fixed.

**Symptom:** `decode_spo2_event()` (per open_ring's documented field layout:
`header_high`, `header_low`, `spo2_percent` list as raw uint8 values) produces
values ranging 94-104% in real captured data (2026-06-23 pull). SpO2 is
physically capped at 100% - any value above that is impossible, meaning the
decode is wrong.

**Likely cause:** The open_ring docstring's own "verified" example
(`68 5d 5d 5d...` -> all 93%) is a single flat-value sample that happened to
decode plausibly by coincidence. Real samples show smooth upward/downward
drift crossing the 100% boundary (e.g. one window: 97,98,99,100,101,101,102...)
suggesting these bytes are NOT raw percentages but some other encoding -
possibly a baseline-relative delta, a different fixed-point scale, or values
that need the header_high/header_low fields applied as a correction/offset
that the current decoder ignores entirely (header fields are extracted but
never used in the returned percent values).

**Real data for reference (2026-06-23 pull, boot_ts=41497176):**
samples=[100, 99, 98, 97, 96, 95, 94, 94, 94, 95, 95, 95, 97] decoded as
"96.1% avg" - the *shape* of this curve (smooth dip and recovery) looks like
real physiological SpO2 behavior, just offset/scaled wrong. This is
encouraging - the underlying signal seems real, the math mapping it to a
percentage is what's broken.

**Working decoders, for contrast (same pull, same session):**
- Sleep temp (0x75): 35.5-36.0 degC - sane, trustworthy
- Fuel gauge battery (0x61/0x14): 56.4%, 3807mV - sane, trustworthy
- Sleep state (0x6a): consistent state=1 throughout - sane, trustworthy

## Next steps
1. Try incorporating header_high/header_low into the percent calculation
   (currently decoded but unused) - possible they're a scale/offset factor.
2. Check if `decode_spo2_dc_event` (0x77, not yet read in detail) or
   `decode_spo2_ibi_and_amplitude_event` (0x6e, decoded as raw bytes only)
   contain calibration data this event type depends on.
3. Consider cross-referencing against Gen4/Oura's official SpO2 % for the
   same night (Oura app does report this under sleep details) once we have
   a same-night comparison opportunity - same validation method used
   successfully for HRV.
4. Do not log any SpO2 comparison rows in the comparisons CSV until this is
   resolved - would just be logging garbage numbers.

---
*Logged 2026-06-23. Found during first live test of the SpO2 decoder
immediately after wiring it into the pull script.*
