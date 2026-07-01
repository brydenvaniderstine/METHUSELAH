"""0x75 — sleep_temp_event (SleepTempEvent). VALIDATED — i16 LE / 100 = °C."""


def decode(p: bytes) -> dict:
    n = len(p)
    if n == 0 or n & 1:
        raise ValueError("SleepTempEvent payload size must be even and >0")
    n_samples = n // 2
    temps_c = [(p[i] | (p[i + 1] << 8)) / 100.0 for i in range(0, n, 2)]
    return {"n_samples": n_samples, "temps_c": temps_c}
