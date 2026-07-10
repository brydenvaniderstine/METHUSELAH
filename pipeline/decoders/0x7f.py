"""
0x7F — real_step_feature_2 (Real step feature (2)) — FFT spectral feature packet

Layout: 14 x uint8, all fields UNRESOLVED except b[10] (see below). Fires
paired with 0x7E on the same ~308-tick hardware timer (see 0x7e.py for the
boot_ts spacing analysis) -- NOT step-triggered. Step count lives in 0x6B
b[0] (DONE). open_ring: "FFTset sub-messages, meaning not documented" -- no
proto schema available; the byte role below is corpus-derived, not
spec-derived.

CONFIRMED (cross-file, WALK vs. OTHER ACTIVITY -- 2026-07-07, 8 pull files):
  b[10]: WALK-RESPONSIVE, opposite direction from 0x7E's b[9]. Walk
         mean=128 (stdev=5, n=7) vs other-activity mean=188-206
         (stdev 3-15) -- LOWER during walk. Mechanism unconfirmed.

Prior cross-file analysis (still valid, not re-verified with a second data
point): b[3] noted as highest-variance field (stdev 61.4, range 7-230) --
a candidate for further investigation, not yet characterized. One packet
per walk experiment had b[3]=b[4]=b[7]=0, caused by a Feature session
restart, not a decode error.

NOT CONFIRMED -- important distinction: the b[10] finding above is WALK vs.
OTHER ACTIVITY, not fast-vs-slow PACE. A second walk experiment at slow
shuffle pace (2026-07-09) was intended to test pace-sensitivity, but that
pull captured ZERO 0x7E/0x7F packets (buffer/timing capture failure -- see
known_issues.md, 2026-07-09 entry). Pace-sensitivity of b[10], or any other
byte, remains completely untested.

UNRESOLVED -- insufficient data to classify: b[0]-b[2], b[4]-b[9], b[11]-b[13].

Ceiling: full field meanings require firmware reverse-engineering or the
FFTset proto schema. This decoder returns all 14 raw bytes; only b[10] has
any confirmed interpretation, and even that is walk-vs-activity, not a
decoded physical quantity.
"""


def decode(payload: bytes) -> dict:
    if len(payload) != 14:
        raise ValueError(f"real_step_feature_2 payload must be exactly 14 bytes, got {len(payload)}")
    return {f"b{i}": payload[i] for i in range(14)}
