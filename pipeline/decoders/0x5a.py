"""0x5A — Sleep phase data (SleepPhaseData).

Chunked transmission: one 14-byte packet per chunk (1-byte chunk index +
13 bytes of data). CHUNK COUNT IS VARIABLE, not fixed at 23 — corrected
2026-07-21 after the original single-night (2026-07-12) observation was
wrongly generalized as a fixed 23-packet/299-byte structure. Full-corpus
re-scan (2026-07-24, 38 distinct bouts after boot_ts de-dup — see
known_issues.md 2026-07-24) shows the range is even wider than first
found: complete cycles from 1 chunk up to 29 chunks. This scales with how
many epochs have accumulated in the current sleep bout — 0x5A fires in
the same cluster as 0x4C, which is independently confirmed (known_issues.md
2026-07-19/20) to be a per-bout accumulator, not a fixed-size nightly
summary. `decode()`'s reassembly logic already handles this correctly via
`max(chunk_index)+1`; a SEPARATE hardcoded-23 bug in the `complete`/
`missing_chunks` fields (not the reassembly) was found and fixed
2026-07-24 — see known_issues.md for the operational impact (bogus
partial-capture warnings in oura_gen3_morning_pull.py).

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

Cross-validation against 0x4C Sleep Summary (2) — RE-VERIFIED 2026-07-24
at full-corpus scale (38 distinct bouts after de-duplicating retransmitted
backlog copies by boot_ts — see pipeline/tools/analyze_0x5a_stage3_gap.py
and known_issues.md 2026-07-24; up from the 2026-07-21 sample of 6 bouts
picked from only the 5 daemon files that existed then). Matches each 0x5A
cycle to the time-nearest 0x4C record from the same cluster firing.

Stages 0/1/2: EXACT MATCH in 31/31 bouts with 2+ chunks (100%) — confirms
the encoding and chunk-reassembly logic at 5x the original sample size.
CAVEAT (unchanged): this is an internal Gen3-vs-Gen3 consistency check
between two tags produced by the same ring firmware, not validation
against external ground truth (Gen4 or polysomnography). It confirms
the *decode* is correct, not that the underlying stage classifier is
physiologically accurate. Per the project's dashboard design rules,
this does not change deep-sleep%/stage-breakdown's discard/
AWAITING-DATA status — see the methuselah skill file.
NEW CAVEAT: single-chunk (idx=0-only) bouts are NOT exact-match — 0x5A's
stage-0 count runs far ahead of 0x4C's in every 1-chunk case seen (7/7).
One inspected byte-for-byte: a real-looking 8-epoch LIGHT/stage-3 segment
followed by 36 straight epochs of `0x00` bytes that 0x4C does not
corroborate. UNCONFIRMED lead, not chased further yet: `0x00` may be a
second ambiguous byte value like `0xFF` — zero-padding on a freshly-started
accumulator's unwritten tail, not necessarily 4 real WAKE epochs. Only
shows up in 1-chunk bouts (nothing to pad in a fully-populated 18-29 chunk
one). See known_issues.md 2026-07-24 Finding 3.

Stage 3: at n=38 (n=31 excluding the 1-chunk bouts above), tested the
literature-informed hypothesis that 0xFF bytes cluster adjacent to stage-3
runs specifically (vs. just correlating with total 0xFF count, already
falsified 2026-07-21) — motivated by external research on deep sleep being
the hardest/most-reclassified stage industry-wide (output/
sleep-stage-science-ppg-hrv.md, agent workspace, not itself decoder
evidence). Result: NOT supported. Adjacency-specific correlation
(r≈0.21-0.23) is weaker than the cruder total-0xFF-count correlation
(r≈0.50), and that total-count correlation is itself substantially
confounded by bout length (chunks-vs-total_none r≈0.73). No evidence 0xFF
bytes specifically cluster around stage-3 boundaries beyond what bout
length alone predicts. Stage 3's real encoding remains an open, unresolved
ceiling — this round of testing narrowed what it ISN'T without resolving
what it IS. Full writeup: known_issues.md 2026-07-24.

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
    if not packets:
        return {"error": "no packets provided", "complete": False}

    # Completeness is relative to THIS bout's own accumulated length, not a
    # fixed 23 -- chunk count is variable (see module docstring). A prior
    # version hardcoded expected_chunks = set(range(23)), which silently
    # mis-flagged every complete bout with <23 chunks as PARTIAL and printed
    # bogus "missing chunks" warnings in oura_gen3_morning_pull.py. Found via
    # corpus-wide re-verification 2026-07-24 (known_issues.md).
    expected_chunks = set(range(max(packets.keys()) + 1))
    present = set(packets.keys())
    missing = sorted(expected_chunks - present)

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
