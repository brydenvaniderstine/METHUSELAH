"""0x76 — bedtime_period (BedtimePeriod). Observed once: 2026-07-12 21:20 evening pull.

Was listed as "CONFIRMED NON-FIRING" on 2026-07-12 morning, then fired the same evening.
Payload: 8 bytes = 2 × u32 LE (start_ring_time, end_ring_time).
  Observed payload: 0e 04 c5 03 b7 8a ca 03
  start_ring_time = 0x03c5040e = 63,373,326 ticks
  end_ring_time   = 0x03ca8ab7 = 63,739,575 ticks
  span = 366,249 ticks (confirmed matches the ~362,153-tick sleep session
  independently measured from 0x6A samples — within expected rounding)

Layout matches open_ring's decode_bedtime_period (2x uint32 LE) exactly.
Fires as part of the 0x76/0x5A cluster alongside 0x49, 0x4C, 0x4F, 0x58 —
only when a completed sleep session is still in the ring's circular buffer."""
from .utils import _u32


def decode(p: bytes) -> dict:
    if len(p) < 8:
        raise ValueError("BedtimePeriod payload must be >=8 bytes")
    return {"start_ring_time": _u32(p, 0), "end_ring_time": _u32(p, 4)}
