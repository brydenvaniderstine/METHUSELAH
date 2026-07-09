"""0x76 — bedtime_period (BedtimePeriod). Never observed. Re-verified 2026-07-08
against all 23 raw pull files on disk (literal tag, label text, and case-insensitive
"bedtime" all checked) — zero matches. Layout below matches open_ring's
decode_bedtime_period exactly (2x uint32 LE) but is unvalidated against a real
packet — no packet has ever been captured to confirm it."""
from .utils import _u32


def decode(p: bytes) -> dict:
    if len(p) < 8:
        raise ValueError("BedtimePeriod payload must be >=8 bytes")
    return {"start_ring_time": _u32(p, 0), "end_ring_time": _u32(p, 4)}
