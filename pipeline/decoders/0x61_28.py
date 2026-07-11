"""0x61/0x28 — _dd_afe_statistics_values (debug data sub-type 0x28). PARTIAL.

CONFIRMED 2026-07-11 against all 114 real packets in the current 29-file
corpus (largest untouched sample from the Tier 3 sweep). 14-byte payload,
stateful per open_ring: byte[1] distinguishes record kind within a
multi-record session.

  p[1]:   kind_byte (u8) -- observed {0, 1} (open_ring: 1=session-header,
          0=continuation; our records alternate kind=0 then kind=1 in
          consecutive boot_ts pairs, e.g. 55393476/55393477 -- a fixed
          pair, not open_ring's exact stated order, worth re-checking
          against more sessions before trusting the header/continuation
          labels literally)
  p[2:]:  stats_hex (raw, per-LED measurement-count fields open_ring
          declined to fully decode -- "full structured aggregation would
          mirror CvaPpgDecoder, left as future work")

**104 of 114 records (91%) have non-zero stats bytes** in this corpus --
notably richer than open_ring's own reference capture, where "all 2,710
records carry zero-stats." This means there is real data here to push the
decode further than open_ring did, just not attempted in this pass.

Ceiling: the per-LED measurement-count field boundaries within p[2:] are
not decoded -- this needs the same kind of correlation/invariant analysis
already applied successfully to 0x50/0x72/0x6C, not yet done here given
the volume of tags covered in this sweep. Good next candidate given real,
non-zero data is available.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 14:
        raise ValueError(f"afe_statistics_values payload too short, got {len(payload)} bytes")
    if payload[0] != 0x28:
        raise ValueError(f"not an afe_statistics_values record (sub_byte={payload[0]:#x})")
    kind_byte = payload[1]
    return {
        "record_kind": "header" if kind_byte == 1 else ("continuation" if kind_byte == 0 else f"unknown_{kind_byte}"),
        "kind_byte": kind_byte,
        "stats_hex": payload[2:].hex(),
        "all_stats_zero": all(b == 0 for b in payload[2:]),
    }
