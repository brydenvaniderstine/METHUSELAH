"""0x77 — spo2_dc_event.

open_ring documents this as variable-size with proto: `channel_index, beat_index,
timestamp, dc[]` (one DC sample stream per channel). The loop pattern hides the
per-sample reads; open_ring emits only channel_index (b0) + raw trailing hex.

Reverse-engineered from 384 corpus packets (analysis 2026-07-06):

    b0:  channel_index (u8)
           bit7 = optical band (0=A/low-band, 1=B/high-band)
           bit6..0 = beat_counter — cycles per-beat; A/B packets sharing the
                     same beat_counter carry the same PPG beat at two wavelengths.
           Two distinct bands: low mean ≈58 (range 1-127), high mean ≈193 (range 130-253),
           separation ≈128 — consistent with red/IR LED alternation.
           Channel alternation: 92-100% of consecutive packets in a pull.

    b1..b(n-1): (n-1) signed i8 DC samples from the optical channel.
           Variable length (most commonly 14-byte → 13 samples).
           Time-series structure confirmed: intra-packet lag-1 autocorrelation r=+0.49.
           Cross-channel correlation (A/B pairs sharing beat_counter): r=+0.80 to +0.93
           — confirms these bytes represent real PPG DC signal.

UNCERTAIN — cannot resolve without firmware:
- Whether the proto's "beat_index" and "timestamp" fields occupy b1..b3 as a header
  (leaving b4..b(n-1) as DC samples) or whether all b1..b(n-1) are DC samples.
  Cross-channel correlation is equivalent under both interpretations.
- Which optical band corresponds to red (660nm) vs IR (880nm).
- Physical units of DC values (raw ADC, gain-corrected, or normalised).
- Semantics of the 4-byte aaaab2 sentinel form (session-end marker).

SENTINEL pattern: payload ending in 0xAAAAB2 (e.g. 4daaaab2) — always identical
trailing bytes, not physiologically plausible DC data. These are returned as
is_sentinel=True with no dc_samples.

Status: PARTIAL DECODE. DC samples confirmed real; field sub-structure uncertain.
Walk experiment with known SpO2 variance would add physiological correlation context
but would not resolve the b1..b3 header question.
"""

SENTINEL_TAIL = bytes([0xAA, 0xAA, 0xB2])


def decode(p: bytes) -> dict:
    if len(p) < 1:
        raise ValueError(f"spo2_dc_event payload too short ({len(p)} bytes)")

    channel = "B" if (p[0] & 0x80) else "A"
    beat_counter = p[0] & 0x7F

    # Detect sentinel packets (session markers, not real DC data)
    if len(p) >= 4 and p[1:4] == SENTINEL_TAIL:
        return {
            "channel":      channel,
            "beat_counter": beat_counter,
            "is_sentinel":  True,
            "dc_samples":   [],
            "n_samples":    0,
        }

    # All remaining bytes as signed i8 DC samples (Hypothesis A — conservative)
    dc_samples = [v if v < 128 else v - 256 for v in p[1:]]

    return {
        "channel":      channel,
        "beat_counter": beat_counter,
        "is_sentinel":  False,
        "dc_samples":   dc_samples,
        "n_samples":    len(dc_samples),
    }
