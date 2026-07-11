"""0x61/0x0d — _dd_ble_usage_statistics (debug data sub-type 0x0d). VALIDATED.

CONFIRMED 2026-07-11 against all 57 real packets in the current 29-file
corpus. Layout matches open_ring's documented wire format exactly (13
bytes: sub:1 + 3x u32 LE):

  p[1:5]:  ticks_fast_mode (u32 LE)
  p[5:9]:  ticks_slow_mode (u32 LE)
  p[9:13]: ticks_advertising_mode (u32 LE)

Always 0 for ticks_fast_mode and ticks_slow_mode across all 57 samples in
this corpus -- consistent with these snapshots being taken during
undisturbed idle/monitoring periods (no active phone/app BLE connection),
not evidence of a decode error.

ticks_advertising_mode matches this record's companion 0x61/0x0c
ticks_measuring_last_period value within single digits in every sample
(see 0x61_0c.py docstring for the full cross-validation) -- the ring
spends effectively all of its "last period" time in BLE advertising mode
when not connected, which is exactly what you'd expect physically. This
agreement across independently-decoded fields from a different tag is the
main evidence these u32 LE offsets are correct.

Always fires as part of a fixed trio with 0x61/0x0a and 0x61/0x0c
(consecutive boot_ts, order 0x0a -> 0x0d -> 0x0c), itself immediately
following each 0x61/0x09 sleep_statistics event.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 13:
        raise ValueError(f"ble_usage_statistics payload too short, got {len(payload)} bytes")
    if payload[0] != 0x0D:
        raise ValueError(f"not a ble_usage_statistics record (sub_byte={payload[0]:#x})")
    return {
        "ticks_fast_mode": payload[1] | (payload[2] << 8) | (payload[3] << 16) | (payload[4] << 24),
        "ticks_slow_mode": payload[5] | (payload[6] << 8) | (payload[7] << 16) | (payload[8] << 24),
        "ticks_advertising_mode": payload[9] | (payload[10] << 8) | (payload[11] << 16) | (payload[12] << 24),
    }
