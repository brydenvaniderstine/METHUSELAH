"""0x5D — hrv_event (HrvEvent). Each pair: hr_bpm + rmssd_ms per 5-min window."""


def decode(p: bytes) -> dict:
    n = len(p)
    if n < 2 or n > 12 or n % 2 != 0:
        raise ValueError("invalid HRV payload size")
    pairs = []
    for i in range(0, n, 2):
        pairs.append({"hr_bpm": p[i], "rmssd_ms": p[i + 1]})
    return {"samples_5min": pairs}
