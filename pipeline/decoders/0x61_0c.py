"""0x61/0x0c — _dd_period_info_statistics (debug data sub-type 0x0c). VALIDATED.

CONFIRMED 2026-07-11 against all 57 real packets in the current 29-file
corpus. Layout matches open_ring's documented wire format exactly (10
bytes: sub:1 + u32 LE + u32 LE + u8):

  p[1:5]: ticks_measuring_last_period (u32 LE)
  p[5:9]: systime_spent_in_last_state_raw (u32 LE); open_ring claims
          seconds = raw / 10.0 (untested here, see ceiling below)
  p[9]:   pfsm_state (u8)

Strong cross-tag validation: ticks_measuring_last_period matches this
record's companion 0x61/0x0d ticks_advertising_mode value within single
digits in every one of the 57 samples (e.g. 8405455 vs 8405447,
21853312 vs 21853307) -- two independently-decoded fields from different
debug sub-types, always fired within 1-2 ticks of each other as part of
the same diagnostic bundle, agreeing almost exactly. This is strong
evidence the u32 LE offsets here (and in 0x61/0x0d) are correct.

pfsm_state values observed here (3, 4, 5, 6) match exactly the already-
CONFIRMED pfsm_state field from 0x61/0x09 -- this is a second, independent
emission of the same state value within the same diagnostic bundle.

Ceiling: the /10.0 seconds-scaling for systime_spent_in_last_state is
open_ring's claim, not independently re-derived here — plausible (produces
values like 256.5s, 135.0s, all clean single-decimal numbers consistent
with a real /10 fixed-point encoding) but not cross-validated against an
independent clock the way the u32 offsets themselves were.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 10:
        raise ValueError(f"period_info_statistics payload too short, got {len(payload)} bytes")
    if payload[0] != 0x0C:
        raise ValueError(f"not a period_info_statistics record (sub_byte={payload[0]:#x})")
    ticks_measuring = payload[1] | (payload[2] << 8) | (payload[3] << 16) | (payload[4] << 24)
    systime_raw = payload[5] | (payload[6] << 8) | (payload[7] << 16) | (payload[8] << 24)
    return {
        "ticks_measuring_last_period": ticks_measuring,
        "systime_spent_in_last_state_s": systime_raw / 10.0,
        "pfsm_state": payload[9],
    }
