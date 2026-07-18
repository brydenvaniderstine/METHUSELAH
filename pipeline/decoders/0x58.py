"""0x58 — Sleep summary (4). Observed once: 2026-07-12 21:20 evening pull.

Payload: 7 bytes = 7 × u8.
  payload = 62 42 64 56 46 3a 21
  values  = [98, 66, 100, 86, 70, 58, 33]

Hypothesis (unconfirmed, n=1): the 7 bytes are contributor scores (0-100)
matching Gen4's own 7-field contributor score shape:
  deep_sleep / efficiency / latency / rem_sleep / restfulness / timing / total_sleep

Cross-check against real 2026-07-11/12 Gen4 contributor scores found one
exact match per night and several near-misses within ±3 points, but field-order
alignment was ambiguous — the mapping above is Gen4's canonical order, NOT the
confirmed Gen3 byte order.

Gen4 ground truth permanently closed 2026-07-13 (API token expired). This
hypothesis cannot be re-tested until a new comparison source is available.

Fires as part of the 0x76/0x5A cluster alongside 0x49, 0x4C, 0x4F.
"""


def decode(p: bytes) -> dict:
    if len(p) < 7:
        raise ValueError(f"Sleep summary (4) payload must be >=7 bytes, got {len(p)}")
    return {
        "scores_u8": list(p[:7]),  # 7 values 0-100; field order UNCONFIRMED
        "raw": p[:7].hex(),
    }
