"""0x61/0x24 — _dd_battery_level_changed (debug data sub-type 0x24). VALIDATED.

CONFIRMED 2026-07-11 against all 10 real packets in the current 29-file
corpus (5-byte payload, fixed length, zero exceptions):
  p[1]:   battery_percentage (u8, plain integer percent — no scaling)
  p[2:4]: battery_voltage_mv (u16 LE)
  p[4]:   reason (u8) -- candidate, not firmware-confirmed:
            0 = standalone/periodic reading (4/10 packets, no adjacent
                charging-sequence packets)
            2 = charging-sequence start (2/10 packets; one of these is the
                first packet of the 2026-07-10 23:36 charging climb
                86%->93%, known_issues.md 2026-07-10)
            3 = charging-sequence continuation (4/10 packets, all four are
                the remaining steps of that same climb)

All 10 decoded percentages/voltages are physically plausible (46-93%,
3808-4191mV -- correct Li-ion range) with zero out-of-range values, unlike
the historical 0x61/0x09 u32-misread bug -- this field was correctly
identified from the start, no structural ambiguity.

Ceiling: the reason-code interpretation above is a pattern match across a
small sample (2x reason=2, 4x reason=3, all from a single observed charging
event), not firmware-confirmed. Needs another real charging session to
verify the reason=2-starts/reason=3-continues pattern holds, or a
non-charging reason=0->2 transition to rule out reason simply meaning
"delta direction" (rising=2/3, falling/flat=0) instead.
"""


def decode(p: bytes) -> dict:
    if len(p) < 5:
        raise ValueError("battery_level_changed payload too short")
    if p[0] != 0x24:
        raise ValueError(f"not a battery_level record (sub_byte={p[0]:#x})")
    return {
        "battery_percentage": p[1],
        "battery_voltage_mv": p[2] | (p[3] << 8),
        "reason": p[4],
    }
