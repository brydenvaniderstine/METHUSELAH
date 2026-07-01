"""0x76 — bedtime_period (BedtimePeriod). Never observed in 34 pulls (as of 2026-06-30)."""
from .utils import _u32


def decode(p: bytes) -> dict:
    if len(p) < 8:
        raise ValueError("BedtimePeriod payload must be >=8 bytes")
    return {"start_ring_time": _u32(p, 0), "end_ring_time": _u32(p, 4)}
