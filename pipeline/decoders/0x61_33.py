"""0x61/0x33 — _dd_open_afe_ppg_settings_data (debug data sub-type 0x33). PARTIAL.

CONFIRMED 2026-07-11 against all 68 real packets in the (then) 29-file
corpus. Two length variants observed (8 and 14 bytes), matching open_ring's
documented behavior exactly: the firmware's own lib requires len > 12 for
the full settings record; shorter (8-byte) records are the lib's own
"truncated" / RepParseError case.

  p[1]: chip_variant (u8) -- open_ring enum {1: MAX86171, 2: MAX86173,
        3: MAX86178}. **All samples in the corpus read chip_variant=1
        -- the Gen3 ring's PPG sensor is a MAX86171**, consistent across
        every observed record. This is real hardware identification, not
        an inference.

PUSHED FURTHER 2026-07-12 against the full 34-file corpus (88 records, 45
full-length / 43 truncated). settings_hex (p[2:14], 12 bytes) splits
cleanly into **two structurally-identical 6-byte halves** -- a per-channel
(A/B) register pair, consistent with the same dual-PPG-channel pattern
already confirmed elsewhere in this ring's protocol (0x6E SPO2 IBI, 0x77
SPO2 DC event both alternate channel A/B):

  - byte[2] (first half) / byte[8] (second half): channel-half marker.
    39/45 records (87%) show exactly `(0x01, 0x10)` -- reads as a literal
    "half 1 / half 2" tag. The 6 exceptions (0x11 in one or both slots)
    are unexplained, likely a mode/status bit, not yet isolated.
  - byte[3] (first half) / byte[9] (second half): CONSTANT `0xCC` in
    100% of records, both halves -- a fixed register-address byte, not
    config data.
  - byte[5] / byte[11]: equal in 44/45 records (98%) -- same value
    mirrored across both channel halves.
  - byte[0] / byte[6]: byte[6] = byte[0] + 17 in 39/45 records (87%) --
    a near-fixed per-channel calibration offset; the 6 exceptions include
    one outlier pair (-63/+65) not yet explained.
  - byte[1] / byte[7], byte[4] / byte[10]: less consistently paired
    (byte[1]==byte[7] only 29/45) -- likely genuine per-channel gain/DAC
    settings that legitimately differ between the two PPG channels,
    rather than a decode gap.

Ceiling (as of 2026-07-12): the two-halves structure is now solid, but
individual byte IDENTITY within each half (which register: LED current?
PD gain? ADC range?) is still unknown without the MAX86171
datasheet/register map. Not promoted to DONE.

TESTED 2026-07-21 against pipeline/data/findings/max86171_register_reference.md
(real ADI MAX86171 datasheet extract) on the grown corpus (9,456
full-length raw records / 63 unique settings blobs across 35 files).
Hypothesis: the two 6-byte halves map to MEASn Configuration 1/2/3
register fields (PDSEL/TINT/AVER, SINC3_SEL/FILT_SEL/LED_RGE/ADC_RGE,
PD_SETLNG/LED_SETLNG/DACOFF). FALSIFIED:
  - byte[3]/byte[9] ("constant register-address byte", 0xCC with a rare
    0xFC variant -- not 100% constant as first thought) falls outside
    the documented MEASn config register address range (0x19-0x33).
    Not a real register address.
  - byte[0]/byte[6] ("near-fixed calibration offset") spans 9-11
    distinct raw values across the corpus -- inconsistent with
    DACOFF[1:0] or ADC_RGE[1:0], both pure 2-bit (4-value) fields.
  - Neither candidate 3-byte grouping within a half decomposes cleanly
    into the documented field layout; byte[2]/byte[8] is demonstrably a
    channel-select bitmask (bit0=chan A, bit4=chan B, both set in a
    rare ~1% minority), not a register value, which rules out the
    byte[0..2]=Config1/2/3 grouping outright.
Full writeup: known_issues.md 2026-07-21. Register-level field identity
remains unresolved -- needs actual Oura firmware, not just the generic
chip datasheet (datasheet gives register shape, not Oura's specific
byte arrangement). Still PARTIAL, not promoted to DONE. No decode logic
changed by this test -- the channel_a/channel_b split below was already
correct.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 2:
        raise ValueError(f"open_afe_ppg_settings_data payload too short, got {len(payload)} bytes")
    if payload[0] != 0x33:
        raise ValueError(f"not an open_afe_ppg_settings_data record (sub_byte={payload[0]:#x})")
    chip = payload[1]
    chip_name = {0x01: "MAX86171", 0x02: "MAX86173", 0x03: "MAX86178"}.get(chip, f"unknown_0x{chip:02x}")
    result = {
        "chip_variant": chip,
        "chip_variant_name": chip_name,
        "settings_hex": payload[2:].hex(),
        "truncated": len(payload) < 14,
    }
    if len(payload) >= 14:
        settings = payload[2:14]
        result["channel_a"] = list(settings[0:6])
        result["channel_b"] = list(settings[6:12])
    return result
