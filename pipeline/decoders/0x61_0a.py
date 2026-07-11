"""0x61/0x0a — _dd_flash_usage_statistics (debug data sub-type 0x0a). VALIDATED.

CONFIRMED 2026-07-11 against all 57 real packets in the current 29-file
corpus. Layout matches open_ring's documented wire format exactly (13
bytes: sub:1 + 3x u32 LE) -- unlike 0x61/0x09, where the analogous u32
layout was proven wrong, here the byte length matches open_ring's claim
exactly and the decoded values are internally consistent (see below).

  p[1:5]:  ticks_reading_flash (u32 LE)
  p[5:9]:  ticks_writing_flash (u32 LE)
  p[9:13]: ticks_erasing_flash (u32 LE)

This tag always fires as part of a fixed trio with 0x61/0x0c and 0x61/0x0d
(consecutive boot_ts, always in order 0x0a -> 0x0d -> 0x0c), itself firing
immediately after each 0x61/0x09 sleep_statistics event -- a periodic
diagnostic snapshot bundle, not an independent/random emission.

Cross-validation: ticks_reading is 0 in all 57 samples (flash reads
apparently not tracked or never occurred in this window); write/erase
ticks are small (0-3568 / 0-18) relative to the ticks_measuring_last_period
values seen in the companion 0x0c record from the same bundle (which run
into the millions) -- consistent with flash I/O being a rare, brief
operation relative to total elapsed time, not a decode artifact.

Ceiling: units unconfirmed (raw MCU ticks, not yet mapped to a real time
unit here — see 0x61/0x0c's systime_spent_in_last_state_s for the tick
rate open_ring claims elsewhere, 1 tick = 0.1s. Applying that here is
untested).
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 13:
        raise ValueError(f"flash_usage_statistics payload too short, got {len(payload)} bytes")
    if payload[0] != 0x0A:
        raise ValueError(f"not a flash_usage_statistics record (sub_byte={payload[0]:#x})")
    return {
        "ticks_reading_flash": payload[1] | (payload[2] << 8) | (payload[3] << 16) | (payload[4] << 24),
        "ticks_writing_flash": payload[5] | (payload[6] << 8) | (payload[7] << 16) | (payload[8] << 24),
        "ticks_erasing_flash": payload[9] | (payload[10] << 8) | (payload[11] << 16) | (payload[12] << 24),
    }
