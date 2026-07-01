"""0x61/0x24 — _dd_battery_level_changed (debug data sub-type 0x24)."""


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
