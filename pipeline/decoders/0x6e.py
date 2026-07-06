"""0x6E — spo2_ibi_and_amplitude_event.

open_ring documents this as "fixed 13 bytes; 13× uint8, like 0x60 but for SpO2
measurement context; bit-pack pattern is similar but with a different payload size,
suggesting fewer beats per record" and emits a conservative raw passthrough.

Confirmed layout (reverse-engineered from 549 corpus packets, cross-validated
against 0x6A avg_hr — delta −1.1 to +1.3 bpm in sleep context, 96.7% of packets
produce physiologically plausible IBI [300-2000ms]):

    b0:       channel byte
                bit7 = optical channel (1=B/high-band, 0=A/low-band)
                bit6..0 = beat/sequence index within current SpO2 window
                Alternates A/B per-beat (near-perfectly within a pull).
    b1..b5:   5× IBI high bytes — bits 3..10 of IBI in ms (p[i] << 3)
    b6..b10:  5× IBI low bit (bit0) + amplitude pre-shift (bits 1..7)
    b11:      packed mid bits for IBI[0..3], 2 bits each:
                mid[0]=(b11>>5)&0x6, mid[1]=(b11>>3)&0x6,
                mid[2]=(b11>>1)&0x6, mid[3]=(b11<<1)&0x6
    b12:      amplitude shift nibble (low 4 bits):
                shift = 0 if nibble==7 else nibble+1

IBI formula (same bit-pack as 0x60, 5 pairs instead of 6):
    ibi_ms[i] = (b[1+i] << 3) | mid_bits[i] | (b[6+i] & 0x1)

Amplitude formula:
    amp[i] = (b[6+i] >> 1) << shift

Note: IBI[4] mid bits are set to 0 — b11 covers only 4 pairs; the b12 high
nibble is a candidate but assignment unconfirmed without firmware disassembly.
Amplitude physical units are unknown; the shift produces large integers whose
scaling to optical amplitude requires further calibration.
"""


def decode(p: bytes) -> dict:
    if len(p) != 13:
        raise ValueError(f"spo2_ibi_and_amplitude_event must be 13 bytes, got {len(p)}")

    b11 = p[11]
    b12 = p[12]

    mid_bits = [
        (b11 >> 5) & 0x6,   # IBI[0] bits 1-2
        (b11 >> 3) & 0x6,   # IBI[1] bits 1-2
        (b11 >> 1) & 0x6,   # IBI[2] bits 1-2
        (b11 << 1) & 0x6,   # IBI[3] bits 1-2
        0,                   # IBI[4] — mid bits unconfirmed, treated as 0
    ]

    ibi_ms = []
    for i in range(5):
        ibi_ms.append((p[1 + i] << 3) | mid_bits[i] | (p[6 + i] & 0x1))

    nibble = b12 & 0x0F
    shift = 0 if nibble == 7 else nibble + 1
    amp = [(p[6 + i] >> 1) << shift for i in range(5)]

    return {
        "channel":    "B" if (p[0] & 0x80) else "A",
        "beat_index": p[0] & 0x7F,
        "ibi_ms":     ibi_ms,
        "hr_bpm":     [round(60000 / v, 1) if v > 0 else None for v in ibi_ms],
        "amp":        amp,
        "amp_shift":  shift,
    }
