"""0x4C — Sleep summary (2). Observed once: 2026-07-12 21:20 evening pull.

Payload: 14 bytes = 7 × u16 little-endian.
  payload = 44 00 27 01 7c 02 6d 00 c7 02 3c 4f 0a 07
  u16[0]=68  u16[1]=295  u16[2]=636  u16[3]=109  u16[4]=711  u16[5]=20284  u16[6]=1802

CONFIRMED cross-validation (2026-07-12) against 0x5A sleep phase data:
  u16[0] = 68  → stage 3 epoch count (DEEP? — non-0xFF real epochs)
  u16[1] = 295 → stage 2 epoch count (REM? candidate)
  u16[2] = 636 → stage 1 epoch count (LIGHT — confirmed stage label)
  u16[3] = 109 → stage 0 epoch count (WAKE? candidate)

These four values match 0x5A's stage_counts exactly. Confidence: HIGH.
The counts are of 30-second epochs; multiply by 30/60 for minutes.

u16[4] = 711  — unknown. Not an epoch count (doesn't match any 0x5A stage).
u16[5] = 20284 — unknown. Could be a duration in seconds (~338 min = 5.6h)
                  or a boot_ts delta. Insufficient data to confirm.
u16[6] = 1802  — unknown.

Fires as part of the 0x76/0x5A cluster alongside 0x49, 0x4F, 0x58.
"""

import struct

EPOCH_SECS = 30  # matches 0x5A decoder


def decode(p: bytes) -> dict:
    if len(p) < 14:
        raise ValueError(f"Sleep summary (2) payload must be >=14 bytes, got {len(p)}")
    f = struct.unpack_from("<7H", p, 0)
    return {
        "stage3_epochs": f[0],  # DEEP? (non-0xFF stage 3) — CONFIRMED matches 0x5A
        "stage2_epochs": f[1],  # REM? — CONFIRMED matches 0x5A
        "stage1_epochs": f[2],  # LIGHT — CONFIRMED matches 0x5A
        "stage0_epochs": f[3],  # WAKE? — CONFIRMED matches 0x5A
        "stage_durations_min": {
            0: round(f[3] * EPOCH_SECS / 60, 1),
            1: round(f[2] * EPOCH_SECS / 60, 1),
            2: round(f[1] * EPOCH_SECS / 60, 1),
            3: round(f[0] * EPOCH_SECS / 60, 1),
        },
        "u16_4": f[4],   # unknown
        "u16_5": f[5],   # unknown
        "u16_6": f[6],   # unknown
        "raw": p[:14].hex(),
    }
