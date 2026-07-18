"""0x5A — Sleep phase data (SleepPhaseData).

Chunked transmission: 23 packets per sleep session, each with a 1-byte chunk index
(0-22) followed by 13 bytes of data. Reassembles into a 299-byte structure.

Encoding: 2-bit little-endian (LSB-first) per byte, 4 epochs per byte.
Total: 299 × 4 = 1196 epochs at ~30s each ≈ 10h coverage.

Stage mapping (single-night dataset, 2026-07-12; only stage 1 confirmed):
  0 (0x00 bytes) — UNCERTAIN (WAKE candidate; 109 epochs ≈ 54 min)
  1 (0x55 bytes) — LIGHT SLEEP — HIGH CONFIDENCE (53.2% matches Gen4 53% exactly)
  2 (0xAA bytes) — REM candidate (295 epochs ≈ 147 min vs Gen4 142 min, ~3.7% off)
  3              — UNCERTAIN (DEEP or second WAKE; see 0xFF note below)
  0xFF byte      — AMBIGUOUS: can be NO DATA (empty buffer slot) OR stage-3 data
                   (0xFF = 4× bit-pair 11 = four stage-3 epochs in 2-bit encoding).
                   The decoder conservatively excludes all 0xFF bytes as NO_DATA.

Cross-validation (2026-07-11/12 overnight, via 0x4C Sleep Summary (2)):
  0x4C stage counts {stage0:109, stage1:636, stage2:295, stage3:68} vs
  0x5A decoded counts {stage0:109, stage1:636, stage2:295, stage3:60}.
  Stages 0/1/2: EXACT MATCH (3 for 3) — confirms encoding beyond doubt.
  Stage 3: 0x4C=68 vs 0x5A=60 — gap of 8 epochs (2 bytes).
  Implication: firmware counts 2 of the excluded 0xFF bytes as real stage-3
  epochs, not NO_DATA. The 0xFF ambiguity is real — this decoder undercounts
  stage 3 by exactly 8 epochs (2 bytes × 4 epochs/byte) on this one night.

Fires as a cluster: 0x76, 0x49, 0x4C, 0x4F, 0x58, 0x5A together within ~143 ticks.
Only observed once (2026-07-12 21:20 evening pull). Hypothesis: requires a fully
completed sleep session still resident in the ring's circular buffer at pull time.
See pipeline/data/findings/known_issues.md (2026-07-12 entry) for full analysis.
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
