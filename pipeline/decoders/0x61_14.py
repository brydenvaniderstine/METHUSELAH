"""0x61/0x14 — fuel_gauge_statistics (debug data sub-type 0x14). VALIDATED."""


def decode(p: bytes) -> dict:
    if len(p) < 14:
        raise ValueError("fuel_gauge_statistics payload too short")
    if p[0] != 0x14:
        raise ValueError(f"not a fuel_gauge record (sub_byte={p[0]:#x})")
    battery_pct_raw = p[1] | (p[2] << 8)
    voltage = p[3] | (p[4] << 8)
    return {
        "battery_percentage": battery_pct_raw / 256.0,
        "average_battery_voltage_mv": voltage,
        "remaining_capacity": p[9] | (p[10] << 8),
    }
