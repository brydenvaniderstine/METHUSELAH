"""0x61/0x15 — _dd_finger_detection (debug data sub-type 0x15). RAW ONLY.

CONFIRMED 2026-07-11: 9-byte payload matches open_ring's documented length
exactly (sub:1 + u64 LE). Only 4 real packets in the current 29-file
corpus -- too few to hypothesis-test bit/field structure.

  p[1:9]: detection_u64 (u64 LE) -- open_ring itself does not decode this
          further ("proto field semantics not exposed"). The 4 observed
          values look close to full-range/high-entropy, not a small set of
          clean flag combinations, so this is surfaced raw rather than
          guessed at.

Ceiling: needs (a) more samples, and (b) known ground truth for wear/
no-wear transitions at capture time to correlate against, before
attempting a bitfield or threshold interpretation. Not attempted this
session given n=4.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 9:
        raise ValueError(f"finger_detection payload too short, got {len(payload)} bytes")
    if payload[0] != 0x15:
        raise ValueError(f"not a finger_detection record (sub_byte={payload[0]:#x})")
    return {
        "detection_u64": int.from_bytes(payload[1:9], "little"),
    }
