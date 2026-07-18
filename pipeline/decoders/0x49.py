"""0x49 — Sleep summary (1). Observed once: 2026-07-12 21:20 evening pull.

Payload: 4 bytes.
  payload = 63 02 08 00
  byte[0] = 0x63 = 99

byte[0] = 99 matches a plausible overall sleep score for 2026-07-12 (night of
good sleep, Gen4 scores 98-100 on contributor fields), but Gen4 ground truth
for an overall score on this exact night is unavailable — this is an n=1
hypothesis, not a confirmed field mapping.

bytes[1:4] = [2, 8, 0] — unknown. Could be sub-scores, counters, or flags.
Field order and meaning require a second cluster occurrence for cross-reference.

Fires as part of the 0x76/0x5A cluster alongside 0x4C, 0x4F, 0x58 —
only when a completed sleep session is in the ring's circular buffer.
"""


def decode(p: bytes) -> dict:
    if len(p) < 4:
        raise ValueError(f"Sleep summary (1) payload must be >=4 bytes, got {len(p)}")
    return {
        "score_candidate": p[0],  # 99 on 2026-07-12 — plausible overall score, UNCONFIRMED
        "b1": p[1],               # unknown
        "b2": p[2],               # unknown
        "b3": p[3],               # unknown
        "raw": p[:4].hex(),
    }
