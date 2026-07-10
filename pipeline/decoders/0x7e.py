"""
0x7E — real_step_feature_1 (Real step feature (1)) — FFT spectral feature packet

Layout: 14 x uint8, all fields UNRESOLVED except b[9] (see below). Fires as
0x7E/0x7F pairs on a ~308-tick hardware timer (spacing 296-326 ticks, mean
307.8, stdev ~11 / 3.6%) -- confirmed via boot_ts analysis of the 2026-07-07
walk experiment. NOT step-triggered -- step count lives in 0x6B b[0] (DONE,
confirmed against ~500-step ground truth, 0.6% error). open_ring: "FFTset
sub-messages, meaning not documented" -- no proto schema available; the
byte role below is corpus-derived, not spec-derived.

CONFIRMED (cross-file, WALK vs. OTHER ACTIVITY -- 2026-07-07, 8 pull files,
92 total 7E packets):
  b[9]: WALK-RESPONSIVE. Walk mean=193.3 (stdev=31, n=7, range 151-235) vs
        other-activity mean=60-125. Walk is 1.5-3x higher. Suggests b[9]
        encodes a cadence-band spectral peak, but the mechanism is a
        hypothesis, not confirmed.
  b[0] <-> 0x7E b[8] (companion payload from the same tag): track within
        <10 units across ALL files (walk and non-walk) -- likely correlated
        or redundant signal, not independently meaningful on its own.

NOT CONFIRMED -- important distinction: the finding above is WALK vs. OTHER
ACTIVITY, not fast-vs-slow PACE. A second walk experiment at slow shuffle
pace (2026-07-09) was intended to test pace-sensitivity of b[9], but that
pull captured ZERO 0x7E/0x7F packets (buffer/timing capture failure -- see
known_issues.md, 2026-07-09 entry). Pace-sensitivity of b[9], or any other
byte, remains completely untested. Do not treat b[9] as "pace-sensitive"
until a second walk actually produces comparable data.

UNRESOLVED -- insufficient data to classify: b[1]-b[7], b[10]-b[13].
STEP COUNT GATE (tested and REJECTED): no single byte column sums to ~500
across the one walk's 7 packets. Nearest: b[2]=485, b[4]=482 -- both fail
(one packet has b[1]=b[2]=b[5]=0, an anomaly, not robust). These are
spectral features, not step counters.

Ceiling: full field meanings require firmware reverse-engineering or the
FFTset proto schema. This decoder returns all 14 raw bytes; only b[9] has
any confirmed interpretation, and even that is walk-vs-activity, not a
decoded physical quantity.
"""


def decode(payload: bytes) -> dict:
    if len(payload) != 14:
        raise ValueError(f"real_step_feature_1 payload must be exactly 14 bytes, got {len(payload)}")
    return {f"b{i}": payload[i] for i in range(14)}
