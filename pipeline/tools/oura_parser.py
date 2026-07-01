#!/usr/bin/env python3
"""
METHUSELAH // Oura Gen4 BLE Parser
Converts raw BLE packets into HRV, RHR, and sleep duration.
Decoders ported from open_ring/driver/decoders.py (verified against on-device DB).

HRV method: per-packet RMSSD with artifact rejection (IBI spread >200ms),
            median across valid packets. Eliminates cross-packet inflation.
"""

import struct
import math
from datetime import datetime

RING_TIME_OFFSET = 1777324215 - 274484781  # unix - ring_time (from 0x42 TimeSync)

def ring_ts_to_wall(ring_ts: int) -> datetime:
    return datetime.fromtimestamp(ring_ts + RING_TIME_OFFSET)

def parse_record(raw: bytes):
    if len(raw) < 6:
        return None, None, None
    return raw[0], struct.unpack_from('<I', raw, 2)[0], raw[6:]

def decode_ibi(payload: bytes):
    """0x60 — 14-byte bit-packed IBI decoder from open_ring (verified against on-device DB)."""
    if len(payload) != 14:
        return []
    b12, b13 = payload[12], payload[13]
    mid_bits = [
        (b12 >> 5) & 0x6, (b12 >> 3) & 0x6,
        (b12 >> 1) & 0x6, (b12 << 1) & 0x6,
        (b13 >> 5) & 0x6, (b13 >> 3) & 0x6,
    ]
    ibi_ms = []
    for i in range(6):
        val = (payload[i] << 3) | mid_bits[i] | (payload[6 + i] & 0x1)
        if 300 < val < 2000:
            ibi_ms.append(val)
    return ibi_ms

def rmssd_packet(ibi_list: list):
    """Per-packet RMSSD with artifact rejection. Returns None for artifact packets."""
    if len(ibi_list) < 2:
        return None
    if max(ibi_list) - min(ibi_list) > 200:
        return None
    diffs = [ibi_list[i+1] - ibi_list[i] for i in range(len(ibi_list)-1)]
    return math.sqrt(sum(d*d for d in diffs) / len(diffs))

def rhr_from_ibi(ibi_list: list) -> float:
    """5th percentile bpm from IBI list — lowest sustained HR."""
    if not ibi_list:
        return 0.0
    bpm_list = sorted(60000 / ibi for ibi in ibi_list if ibi > 0)
    return bpm_list[max(0, len(bpm_list) // 20)]

def decode_session_duration(payload: bytes) -> int:
    """0x61 sub=0x09 — duration in seconds at payload[4:8]."""
    if len(payload) < 8:
        return 0
    return struct.unpack_from('<I', payload, 4)[0]

def parse_packets(raw_packets: list, sleep_start_ring_ts: int = 0) -> dict:
    """
    Parse raw BLE packet bytes into biometric summary.
    Returns: hrv_ms, rhr_bpm, sleep_duration_min, ibi_sample_count
    """
    all_ibi = []
    packet_rmssd_vals = []
    sleep_duration_s = 0

    for raw in raw_packets:
        type_byte, ring_ts, payload = parse_record(raw)
        if type_byte is None or ring_ts < sleep_start_ring_ts:
            continue

        if type_byte == 0x60:
            ibi_vals = decode_ibi(payload)
            all_ibi.extend(ibi_vals)
            r = rmssd_packet(ibi_vals)
            if r is not None:
                packet_rmssd_vals.append(r)

        elif type_byte == 0x61 and len(payload) > 0:
            sub, data = payload[0], payload[1:]
            if sub == 0x09 and len(data) >= 8:
                dur = decode_session_duration(data)
                if 600 < dur < 86400:
                    sleep_duration_s = max(sleep_duration_s, dur)

    hrv = 0.0
    if packet_rmssd_vals:
        packet_rmssd_vals.sort()
        hrv = packet_rmssd_vals[len(packet_rmssd_vals) // 2]

    rhr = rhr_from_ibi(all_ibi) if len(all_ibi) >= 10 else 0.0

    return {
        "hrv_ms": round(hrv, 1),
        "rhr_bpm": round(rhr, 1),
        "sleep_duration_min": sleep_duration_s // 60,
        "ibi_sample_count": len(all_ibi),
        "sleep_duration_s": sleep_duration_s,
    }


if __name__ == "__main__":
    test_pkts = [
        '601208a59a10787571707478bc9a9d802e2fd1b2',
        '601209a59a107a7b7a7b7d545c6385928f3ca0e1',
        '60124ca59a10a177757375768c779082705c42c1',
        '60129fa59a107a7d7b7d787a575979759ba2cf51',
        '6012e3a59a107b7777767779949b8bb7a5a80cd1',
        '601228a69a10787672717477aca7a7b2a7aa6b41',
        '601229a69a10747577797976b8b9afaaa5c1fe01',
        '60126ca69a10747779797975c8b9b6b8aacdf691',
        '6012b1a69a10797474747276c5c1b4877e6273c1',
        '6012f5a69a107c7f7f7c76794e59677fb8c7c531',
        '61124eb39a100993fe57011b670000d9f9000006',
    ]
    result = parse_packets([bytes.fromhex(h) for h in test_pkts], sleep_start_ring_ts=278570166)
    print("METHUSELAH // OURA PARSER SELF-TEST")
    print(f"  HRV:   {result['hrv_ms']}ms  (expected ~22ms)")
    print(f"  RHR:   {result['rhr_bpm']}bpm (expected ~57bpm)")
    print(f"  Sleep: {result['sleep_duration_min']}min (expected 439min)")
