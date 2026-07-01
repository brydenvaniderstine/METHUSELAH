"""0x47 — motion_event (MotionEvent). VALIDATED — 3-axis ACM, i8×8 = mg."""
from .utils import _i8


def decode(p: bytes) -> dict:
    n = len(p)
    if n < 4 or n > 6:
        raise ValueError("MotionEvent payload size must be in [4..6]")
    return {
        "flags_high": p[0] >> 5, "flags_low": p[0] & 0x1F,
        "acm_x": _i8(p[1]) * 8, "acm_y": _i8(p[2]) * 8, "acm_z": _i8(p[3]) * 8,
    }
