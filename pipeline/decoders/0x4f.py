"""0x4F — Sleep summary (3). Observed once: 2026-07-12 21:20 evening pull.

Payload: 11 bytes.
  payload = 6f 23 32 02 70 02 00 00 9e 01 00

Parsed as 5 × u16 LE + 1 trailing u8:
  u16[0]=9071  u16[1]=562  u16[2]=624  u16[3]=0  u16[4]=414  b10=0

No field interpretations are confirmed with n=1 data. Observations:
  u16[2]=624 is close to the 0x4C stage 1 count (636, LIGHT), possibly a
  variant count excluding some boundary epochs, but this is speculation.
  u16[0]=9071 is large enough to be a boot_ts delta or tick count.
  u16[3]=0 may be a flag or zeroed field.
Requires a second cluster occurrence for any hypothesis testing.

Fires as part of the 0x76/0x5A cluster alongside 0x49, 0x4C, 0x58.
"""

import struct


def decode(p: bytes) -> dict:
    if len(p) < 11:
        raise ValueError(f"Sleep summary (3) payload must be >=11 bytes, got {len(p)}")
    f = struct.unpack_from("<5H", p, 0)
    return {
        "u16_0": f[0],   # unknown
        "u16_1": f[1],   # unknown
        "u16_2": f[2],   # unknown; close to 0x4C stage1_epochs (636) — unconfirmed
        "u16_3": f[3],   # unknown; 0 in single observation
        "u16_4": f[4],   # unknown
        "b10":   p[10],  # unknown; 0 in single observation
        "raw": p[:11].hex(),
    }
