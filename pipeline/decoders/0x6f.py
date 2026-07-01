"""0x6F — spo2_event (Spo2Event). VALIDATED — offset +6 confirmed 2026-06-24."""

SPO2_OFFSET = 6  # raw byte = true % + 6; see pipeline/data/findings/known_issues.md


def decode(p: bytes) -> dict:
    if len(p) < 1:
        raise ValueError("Spo2Event payload too short")
    samples_end = len(p) - 1 if len(p) > 1 and p[-1] == 0xff else len(p)
    return {
        "header_high": p[0] >> 4,
        "header_low": p[0] & 0x0F,
        "spo2_percent": [b - SPO2_OFFSET for b in p[1:samples_end]],
    }
