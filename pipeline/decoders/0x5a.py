"""0x5A — Sleep phase data (SleepPhaseData).

Chunked transmission: one 14-byte packet per chunk (1-byte chunk index +
13 bytes of data). CHUNK COUNT IS VARIABLE, not fixed at 23 — corrected
2026-07-21 after the original single-night (2026-07-12) observation was
wrongly generalized as a fixed 23-packet/299-byte structure. Real corpus
data (2026-07-21, 6 independent complete bouts across 3 nights) shows
20, 22, 23, 24, and 29-chunk cycles, chunk index observed up to 28. This
scales with how many epochs have accumulated in the current sleep bout —
0x5A fires in the same cluster as 0x4C, which is independently confirmed
(known_issues.md 2026-07-19/20) to be a per-bout accumulator, not a
fixed-size nightly summary. `decode()` below already reassembles
`max(chunk_index)+1` chunks generically, so no code change was needed —
only this docstring was wrong.

Encoding: 2-bit little-endian (LSB-first) per byte, 4 epochs per byte,
~30s/epoch.

Stage mapping (only stage 1 has a confirmed label; 0/2/3 are structurally
confirmed as distinct real epoch-count fields via 0x4C cross-validation
but their WAKE/REM/DEEP physiological labels remain unconfirmed):
  0 (0x00 bytes) — UNCERTAIN (WAKE candidate)
  1 (0x55 bytes) — LIGHT SLEEP — HIGH CONFIDENCE (2026-07-12: 53.2% matched Gen4's 53% exactly)
  2 (0xAA bytes) — REM candidate
  3              — UNCERTAIN (DEEP or second WAKE; see 0xFF note below — this
                   stage's count is NOT reliable, see 2026-07-21 finding)
  0xFF byte      — AMBIGUOUS: can be NO DATA (empty buffer slot) OR stage-3 data
                   (0xFF = 4× bit-pair 11 = four stage-3 epochs in 2-bit encoding).
                   The decoder conservatively excludes all 0xFF bytes as NO_DATA.

Cross-validation against 0x4C Sleep Summary (2) — RE-VERIFIED 2026-07-21
at much larger scale (6 independent bouts, 3 separate nights: 2026-07-12,
2026-07-18/19, 2026-07-20), matching each 0x5A cycle to the time-nearest
0x4C record from the same cluster firing:

  bout           chunks   5A stage0/1/2      4C stage0/1/2      stage3 gap (4C-5A)
  63610354 (07-12)   23   109/636/295        109/636/295        8
  72958131 (07-20)   20   150/516/253        150/516/253        2
  74792521 (07-20)   22   159/539/286        159/539/286        38
  75892380 (07-20)   29   183/570/436        183/570/436        -5
  68815528 (07-18/19) 23  132/550/225        132/550/225        47
  69667118 (07-18/19) 24  231/549/280        231/549/280        57

Stages 0/1/2: EXACT MATCH in all 6/6 bouts — confirms the encoding and
chunk-reassembly logic beyond doubt, at three different chunk counts.
IMPORTANT CAVEAT: this is an internal Gen3-vs-Gen3 consistency check
between two tags produced by the same ring firmware, not validation
against external ground truth (Gen4 or polysomnography). It confirms
the *decode* is correct, not that the underlying stage classifier is
physiologically accurate. Per the project's dashboard design rules,
this does not change deep-sleep%/stage-breakdown's discard/
AWAITING-DATA status — see the methuselah skill file.

Stage 3: gap between 0x4C's count and 0x5A's non-0xFF count is
8/2/38/-5/47/57 across the 6 bouts above — NOT small, NOT fixed, and
once (75892380) 0x5A actually *overcounts* relative to 0x4C. This
FALSIFIES the original 2026-07-18 theory ("2 of the excluded 0xFF bytes
are secretly stage-3, undercounts by exactly 8 epochs") — the gap
doesn't scale with 0xFF byte count either (24/24/24/64/60/38 respectively
across the same bouts, no consistent ratio). Stage 3's real encoding
remains an open, and now clearly deeper, ceiling — not a small rounding
discrepancy. Full writeup: known_issues.md 2026-07-21 (session 2).

Fires as a cluster: 0x76, 0x49, 0x4C, 0x4F, 0x58, 0x5A together. First
observed 2026-07-12 21:20; now confirmed to fire repeatedly through a
full overnight daemon session (dozens of times per night), not a
one-time event — most cluster firings yield incomplete/partial chunk
captures (BLE reconnect/timing gaps), only some reassemble into a
complete cycle. See known_issues.md 2026-07-12 and 2026-07-21 (session 2).
"""

EPOCH_SECS = 30
NO_DATA_SENTINEL = 0xFF

# Stage labels — stage 1 is the only confirmed mapping
STAGE_LABELS = {
    0: "WAKE?",        # uncertain
    1: "LIGHT",        # confirmed
    2: "REM?",         # strong candidate (one night)
    3: "DEEP?",        # uncertain; only non-0xFF stage-3 epochs counted
}


def decode(packets: dict) -> dict:
    """
    Decode a set of 0x5A chunk packets into a sleep hypnogram.

    Args:
        packets: dict mapping chunk_index (int) to payload bytes (13 bytes each).
                 Build from raw pulls: idx = payload[0], data = payload[1:].

    Returns dict with:
        - epochs: list of int (0-3) for each epoch, None for NO DATA slots
        - stage_counts: dict stage → count (excludes NO DATA)
        - stage_durations_min: dict stage → minutes (at EPOCH_SECS/epoch)
        - total_epochs: int
        - valid_epochs: int (excludes NO DATA)
        - total_duration_min: float (valid epochs only)
        - complete: bool (True if all 23 chunks present)
        - missing_chunks: list of missing indices
    """
    expected_chunks = set(range(23))
    present = set(packets.keys())
    missing = sorted(expected_chunks - present)

    if not packets:
        return {"error": "no packets provided", "complete": False}

    # Reassemble in index order (gaps left as None)
    data_bytes = []
    for i in range(max(packets.keys()) + 1):
        if i in packets:
            chunk = packets[i]
            if len(chunk) != 13:
                raise ValueError(f"chunk {i}: expected 13 bytes, got {len(chunk)}")
            data_bytes.extend(chunk)
        else:
            data_bytes.extend([None] * 13)

    # Decode 2-bit LSB-first per byte
    epochs = []
    for byte in data_bytes:
        if byte is None:
            epochs.extend([None, None, None, None])
        elif byte == NO_DATA_SENTINEL:
            epochs.extend([None, None, None, None])  # empty buffer slot
        else:
            for shift in [0, 2, 4, 6]:
                epochs.append((byte >> shift) & 0x3)

    # Stage counts (None/NO_DATA excluded)
    from collections import Counter
    valid_epochs = [e for e in epochs if e is not None]
    cnt = Counter(valid_epochs)

    stage_durations = {
        s: round(c * EPOCH_SECS / 60, 1)
        for s, c in cnt.items()
    }

    return {
        "epochs": epochs,
        "stage_counts": dict(cnt),
        "stage_durations_min": stage_durations,
        "stage_labels": STAGE_LABELS,
        "total_epochs": len(epochs),
        "valid_epochs": len(valid_epochs),
        "no_data_epochs": len(epochs) - len(valid_epochs),
        "total_duration_min": round(len(valid_epochs) * EPOCH_SECS / 60, 1),
        "epoch_secs": EPOCH_SECS,
        "complete": len(missing) == 0,
        "missing_chunks": missing,
    }


def decode_from_raw_packets(raw_payloads: "list[bytes]") -> dict:
    """
    Convenience wrapper: takes a list of raw 14-byte payloads (as transmitted)
    where payload[0] = chunk index and payload[1:] = 13 data bytes.
    """
    packets = {}
    for p in raw_payloads:
        if len(p) != 14:
            raise ValueError(f"expected 14-byte payload, got {len(p)}")
        idx = p[0]
        packets[idx] = bytes(p[1:])
    return decode(packets)


def summarize(result: dict) -> str:
    """Return a human-readable one-line summary."""
    if "error" in result:
        return f"0x5A ERROR: {result['error']}"
    counts = result["stage_counts"]
    durs = result["stage_durations_min"]
    labels = result["stage_labels"]
    parts = []
    for s in sorted(counts):
        parts.append(f"{labels[s]}={durs.get(s,0)}min({counts[s]}ep)")
    status = "COMPLETE" if result["complete"] else f"PARTIAL({len(result['missing_chunks'])} missing)"
    return (f"0x5A [{status}] {' '.join(parts)} "
            f"| valid={result['valid_epochs']}ep / {result['total_duration_min']}min "
            f"| no_data={result['no_data_epochs']}ep")
