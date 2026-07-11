"""0x61/0x33 — _dd_open_afe_ppg_settings_data (debug data sub-type 0x33). PARTIAL.

CONFIRMED 2026-07-11 against all 68 real packets in the current 29-file
corpus. Two length variants observed (8 and 14 bytes), matching open_ring's
documented behavior exactly: the firmware's own lib requires len > 12 for
the full settings record; shorter (8-byte) records are the lib's own
"truncated" / RepParseError case.

  p[1]: chip_variant (u8) -- open_ring enum {1: MAX86171, 2: MAX86173,
        3: MAX86178}. **All 68 samples in this corpus read chip_variant=1
        -- the Gen3 ring's PPG sensor is a MAX86171**, consistent across
        every observed record. This is real hardware identification, not
        an inference.
  p[2:]: settings_hex (vendor-specific PD/LED/ADC/DAC register dump,
        chip-variant-specific format) -- surfaced as raw hex only, per
        open_ring's own admission that decoding it needs a per-vendor
        (MAX86171) register-map decoder they don't provide either.

Ceiling: settings_hex is not field-decoded. Would need the MAX86171
datasheet/register map to go further -- this is a real chip-specific
vendor register dump, not something reverse-engineerable from behavioral
correlation alone the way the debug-stats tags were.
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
    }
    if len(payload) >= 14:
        result["settings_hex"] = payload[2:].hex()
        result["truncated"] = False
    else:
        result["settings_hex"] = payload[2:].hex()
        result["truncated"] = True
    return result
