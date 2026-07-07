"""
0x6B — motion_period: per-window step count decoder

Confirmed against timed walk experiment 2026-07-07:
- Known ground truth: ~500 net steps
- Decoded sum: 497 steps (0.6% error across 5 windows)
- b[0] = per-window step count (NOT the open_ring MOTION_STATE enum)
- open_ring enum {0:NO_MOTION, 1:RESTLESS, 2:TOSSING_AND_TURNING, 3:ACTIVE}
  is WRONG for this field — observed values 98-101 are far outside enum range

Field layout (confirmed):
  b[0]: per-window step count (uint8, ~300-tick window)
  b[1]: cadence candidate in steps/min (uint8, 116-120 observed during brisk walk)
  b[2]: unknown
  b[3]: approaching uint8 ceiling during activity (240-254 observed)
  b[4]: overflow flag — fires 1 when b[3] >= 246, else absent/0
  b[5+]: unresolved

Real-data discipline: b[0] confirmed by ground truth. b[1] cadence hypothesis
pending second experiment. b[2]-b[5+] labeled unknown. Do not promote remaining
bytes without additional ground-truth validation.
"""


def decode(p: bytes) -> dict:
    if len(p) < 2:
        raise ValueError(f"motion_period payload too short ({len(p)} bytes, need ≥2)")
    return {
        "step_count": p[0],
        "cadence_spm": p[1],
        "b2_unknown": p[2] if len(p) > 2 else None,
        "b3_unknown": p[3] if len(p) > 3 else None,
        "b4_overflow_flag": p[4] if len(p) > 4 else None,
    }
