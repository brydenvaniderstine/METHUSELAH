"""
tst_from_stages.py — rough total sleep time from the nightly stage breakdown.

TST = light + rem + deep        (wake subtracted)

Rough by design. The stage subdivision is unreliable; the SUM is not sensitive to
that, because misfiling light-as-REM or REM-as-deep does not change the total.
Only the sleep/wake boundary affects this number. Expect it to run slightly long --
wearables tend to score quiet wakefulness as sleep.

Reads the real bridge shape: bridge["sleep_stages"] = {wake_min, light_min,
rem_min, deep_min, source_tag}.  (gen3_bridge.py:41-42)
"""

from __future__ import annotations

MIN_TIB_MIN = 120.0     # under 2h in bed: not a night
MAX_TIB_MIN = 960.0     # over 16h in bed: register is broken, not a long sleep


def compute_tst_from_stages(bridge: dict):
    """Return (hours: float | None, meta: dict). None means we couldn't get a number."""
    stages = bridge.get("sleep_stages") or {}

    vals = {}
    for key in ("wake_min", "light_min", "rem_min", "deep_min"):
        v = stages.get(key)
        if v is None:
            return None, {"ok": False, "reason": "missing_stages", "missing": key}
        try:
            vals[key] = float(v)
        except (TypeError, ValueError):
            return None, {"ok": False, "reason": "non_numeric", "field": key}

    if min(vals.values()) < 0:
        return None, {"ok": False, "reason": "negative_minutes"}

    tib = sum(vals.values())
    tst = tib - vals["wake_min"]

    if not (MIN_TIB_MIN <= tib <= MAX_TIB_MIN):
        return None, {"ok": False, "reason": "tib_out_of_range", "tib_min": round(tib, 1)}
    if tst <= 0:
        return None, {"ok": False, "reason": "tst_non_positive"}

    h, m = int(tst // 60), int(round(tst % 60))
    deep_frac = vals["deep_min"] / tst

    return round(tst / 60.0, 2), {
        "ok": True,
        "tst_min": round(tst, 1),
        "tib_min": round(tib, 1),
        "hhmm": f"{h}h{m:02d}m",
        "efficiency": round(tst / tib, 3),
        "deep_fraction": round(deep_frac, 3),
        # logged, never a decline -- the total does not depend on the subdivision
        "deep_anomaly": deep_frac < 0.08 or deep_frac > 0.35,
        "source_tag": stages.get("source_tag"),
        "provisional": True,
    }


if __name__ == "__main__":
    nights = [
        ("2026-08-08", {"wake_min": 93.0, "light_min": 327.5, "rem_min": 159.0, "deep_min": 55.5}),
        ("2026-08-09", {"wake_min": 34.0, "light_min": 386.5, "rem_min": 167.5, "deep_min": 27.5}),
        ("missing",    {"wake_min": 34.0, "light_min": 386.5}),
        ("blown reg",  {"wake_min": 34.0, "light_min": 2200.0, "rem_min": 167.5, "deep_min": 27.5}),
    ]
    for label, st in nights:
        hrs, meta = compute_tst_from_stages({"sleep_stages": st})
        if hrs:
            flag = "  [deep anomaly logged]" if meta["deep_anomaly"] else ""
            print(f"{label:<12} {hrs} hrs ({meta['hhmm']}){flag}")
        else:
            print(f"{label:<12} no number — {meta['reason']}")
