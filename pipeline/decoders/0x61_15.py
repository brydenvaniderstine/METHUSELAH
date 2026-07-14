"""0x61/0x15 — _dd_finger_detection (debug data sub-type 0x15). PARTIAL.

CONFIRMED 2026-07-11: 9-byte payload matches open_ring's documented length
exactly (sub:1 + u64 LE). Only 4 real packets in the 29-file corpus at the
time -- too few to hypothesis-test.

PUSHED FURTHER 2026-07-12: the BLE daemon's continuous polling grew the
corpus to 11 unique real samples (18 raw log lines, but several are
duplicate re-observations across daemon restarts sharing the same
boot_ts -- deduplicated). Real structure found:

**Fires on a strict periodic schedule, not on wear-transition events.**
7 consecutive samples from one continuous daemon session are exactly
36000 boot_ts ticks apart, every time, zero variance -- a fixed ~30-minute
periodic status report (at the ~14-24 ticks/sec rates measured elsewhere
today), not something that fires when the ring detects finger on/off. The
tag's open_ring name may be misleading about *when* it fires, even if the
payload content does relate to contact/finger detection.

**Byte-level entropy split (p[1:9], 8 bytes total) -- some bytes are
near-constant, most are not:**
  - byte[1] (p[2]): near-constant at 3 across the whole daemon session
    (one anomalous 4).
  - byte[3] (p[4]): near-constant WITHIN a session but differs BETWEEN
    sessions -- consistently 1 across four older pulls (2026-07-02/05/05/07)
    vs consistently 2 across today's daemon session (one exception).
    Reads as a coarse, slow-changing state/generation counter, not noise.
  - byte[7] (p[8], the MSB): low-entropy (only 0/1/2 observed across all
    11 samples) and shows a clean one-time transition from 0 to 1 exactly
    halfway through the 7-sample daemon session (0,0,0,1,1,1,1 in boot_ts
    order) -- a real state change caught mid-transition, not noise.
  - bytes[0,2,4,5,6]: high entropy, wide ranges, no pattern found yet --
    likely the actual sensor/detection payload data.

Ceiling: still don't know what physical quantity byte[0]/[2]/[4]/[5]/[6]
represent, or what byte[3]/byte[7]'s slow-changing values actually count.
Would need either firmware access or a deliberate remove-ring/put-back-on
experiment during a capture session to watch for a value transition tied
to a real physical event. Not promoted to DONE.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 9:
        raise ValueError(f"finger_detection payload too short, got {len(payload)} bytes")
    if payload[0] != 0x15:
        raise ValueError(f"not a finger_detection record (sub_byte={payload[0]:#x})")
    return {
        "detection_u64": int.from_bytes(payload[1:9], "little"),
        "bytes": list(payload[1:9]),
    }
