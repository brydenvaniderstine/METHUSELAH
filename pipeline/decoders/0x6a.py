"""0x6A — sleep_period_info_2 (SleepPeriodInfo2)."""
from .utils import _i8


def decode(p: bytes) -> dict:
    if len(p) < 10:
        raise ValueError("too short")
    motion_count = p[6]
    if motion_count >= 0x79:
        raise ValueError("motion_count out of range")
    sleep_state = _i8(p[7])
    if not (0 <= sleep_state < 3):
        raise ValueError("sleep_state out of range")
    cv_raw = p[8] | (p[9] << 8)
    return {
        "average_hr": p[0] * 0.5, "hr_trend": _i8(p[1]) * 0.0625,
        "mzci": p[2] * 0.0625, "dzci": p[3] * 0.0625,
        "breath": p[4] / 8.0, "breath_v": p[5] / 8.0,
        "motion_count": motion_count, "sleep_state": sleep_state,
        "cv": cv_raw / 65536.0,
    }
