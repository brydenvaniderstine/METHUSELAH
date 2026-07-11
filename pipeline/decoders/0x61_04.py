"""0x61/0x04 — _dd_alt_text (debug data sub-type 0x04). VALIDATED — raw ASCII.

CONFIRMED 2026-07-11 against 2 real packets (only 2 in the current 29-file
corpus): payload[1:] is plain ASCII debug text. Both observed instances read
"EHRts;47" and "EHRts;45" — an EHR (see 0x6C feature_session's DHR/EHR
session-boundary debug strings, same "EHRst;..." pattern already documented
there) timestamp-tag breadcrumb, value likely a tick/second count. No
decoding ambiguity — this is literal text, not inferred structure.

Ceiling: only 2 samples, both from the same pull. What "47"/"45" actually
count (ticks? seconds? a sequence number?) is unconfirmed — would need more
occurrences alongside other EHR-related tags (0x6C, 0x73) to correlate.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 2:
        raise ValueError(f"alt_text payload too short, got {len(payload)} bytes")
    if payload[0] != 0x04:
        raise ValueError(f"not an alt_text record (sub_byte={payload[0]:#x})")
    return {
        "text": payload[1:].decode("ascii", errors="replace"),
    }
