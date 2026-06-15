#!/usr/bin/env python3
"""
METHUSELAH // Oura Gen4 BLE Parser
Converts raw BLE packets into HRV, RHR, and sleep duration.
Decoders ported from open_ring/driver/decoders.py (verified against on-device DB).
"""

import struct
import math
from datetime import datetime

# ── Time anchor (from 0x42 TimeSync record in stream) ─────────────────────
# payload[0:4] = unix_time, bytes[2:6] = ring_time
# offset = unix_time - ring_time
# Update this each session from the latest 0x42 packet

RING_TIME_OFFSET = 1777324215 - 274484781  # unix - ring

def ring_ts_to_wall(ring_ts: int) -> datetime:
    return datetime.fromtimestamp(ring_ts + RING_TIME_OFFSET)

# ── Inner record parser ────────────────────────────────────────────────────

def parse_record(raw: bytes):
    """Parse a raw BLE notification into (type_byte, ring_ts, payload)."""
    if len(raw) < 6:
        return None, None, None
    type_byte = raw[0]
    ring_ts = struct.unpack_from('<I', raw, 2)[0]
    payload = raw[6:]
    return type_byte, ring_ts, payload

# ── 0x60 IBI decoder (from open_ring — verified against on-device DB) ─────

def decode_ibi(payload: bytes):
    """0x60 — 14-byte bit-packed IBI + amplitude record.
    Returns list of 6 IBI values in ms (400-2000ms range = 30-150bpm).
    """
    if len(payload) != 14:
        return []
    b12 = payload[12]
    b13 = payload[13]
    mid_bits = [
        (b12 >> 5) & 0x6,
        (b12 >> 3) & 0x6,
        (b12 >> 1) & 0x6,
        (b12 << 1) & 0x6,
        (b13 >> 5) & 0x6,
        (b13 >> 3) & 0x6,
    ]
    ibi_ms = []
    for i in range(6):
        high = payload[i] << 3
        low  = payload[6 + i] & 0x1
        mid  = mid_bits[i]
        val  = high | mid | low
        if 300 < val < 2000:  # valid physiological range
            ibi_ms.append(val)
    return ibi_ms

# ── RMSSD from IBI list ────────────────────────────────────────────────────

def rmssd(ibi_list: list) -> float:
    """Root mean square of successive differences — standard HRV metric."""
    if len(ibi_list) < 2:
        return 0.0
    diffs = [ibi_list[i+1] - ibi_list[i] for i in range(len(ibi_list)-1)]
    sq_diffs = [d*d for d in diffs]
    return math.sqrt(sum(sq_diffs) / len(sq_diffs))

# ── RHR from IBI list ─────────────────────────────────────────────────────

def rhr_from_ibi(ibi_list: list) -> float:
    """Lowest sustained HR = 5th percentile of bpm values derived from IBI."""
    if not ibi_list:
        return 0.0
    bpm_list = [60000 / ibi for ibi in ibi_list if ibi > 0]
    bpm_list.sort()
    idx = max(0, len(bpm_list) // 20)  # 5th percentile
    return bpm_list[idx]

# ── Sleep duration from 0x61 session records ──────────────────────────────

def decode_session_duration(payload: bytes) -> int:
    """0x61 sub=0x09 session block — duration in seconds at payload[4:8]."""
    if len(payload) < 8:
        return 0
    return struct.unpack_from('<I', payload, 4)[0]

# ── Main pipeline ─────────────────────────────────────────────────────────

def parse_packets(raw_packets: list, sleep_start_ring_ts: int = 0) -> dict:
    """
    Parse a list of raw BLE packet bytes into biometric summary.
    
    Args:
        raw_packets: list of bytes objects from BLE notification stream
        sleep_start_ring_ts: ring timestamp to filter from (yesterday 9pm)
    
    Returns:
        dict with keys: hrv_ms, rhr_bpm, sleep_duration_min, sample_count
    """
    all_ibi = []
    sleep_duration_s = 0
    
    for raw in raw_packets:
        type_byte, ring_ts, payload = parse_record(raw)
        if type_byte is None:
            continue
        
        # Skip records before sleep window
        if ring_ts < sleep_start_ring_ts:
            continue
        
        # 0x60 — IBI data (heartbeat intervals)
        if type_byte == 0x60:
            ibi_vals = decode_ibi(payload)
            all_ibi.extend(ibi_vals)
        
        # 0x61 — Debug/session records
        elif type_byte == 0x61 and len(payload) > 0:
            sub = payload[0]
            data = payload[1:]
            # sub=0x09 = session block with duration
            if sub == 0x09 and len(data) >= 8:
                dur = decode_session_duration(data)
                # Only count sessions > 10min (filter noise)
                if 600 < dur < 86400:
                    sleep_duration_s = max(sleep_duration_s, dur)
    
    hrv = rmssd(all_ibi) if len(all_ibi) >= 10 else 0.0
    rhr = rhr_from_ibi(all_ibi) if len(all_ibi) >= 10 else 0.0
    
    return {
        "hrv_ms":           round(hrv, 1),
        "rhr_bpm":          round(rhr, 1),
        "sleep_duration_min": sleep_duration_s // 60,
        "ibi_sample_count": len(all_ibi),
        "sleep_duration_s": sleep_duration_s,
    }


if __name__ == "__main__":
    # Self-test against last night's captured packets
    test_packets = [
        bytes.fromhex('601208a59a10787571707478bc9a9d802e2fd1b2'),
        bytes.fromhex('601209a59a107a7b7a7b7d545c6385928f3ca0e1'),
        bytes.fromhex('60124ca59a10a177757375768c779082705c42c1'),
        bytes.fromhex('60129fa59a107a7d7b7d787a575979759ba2cf51'),
        bytes.fromhex('6012e3a59a107b7777767779949b8bb7a5a80cd1'),
        bytes.fromhex('601228a69a10787672717477aca7a7b2a7aa6b41'),
        bytes.fromhex('601229a69a10747577797976b8b9afaaa5c1fe01'),
        bytes.fromhex('60126ca69a10747779797975c8b9b6b8aacdf691'),
        bytes.fromhex('6012b1a69a10797474747276c5c1b4877e6273c1'),
        bytes.fromhex('6012f5a69a107c7f7f7c76794e59677fb8c7c531'),
        bytes.fromhex('61124eb39a100993fe57011b670000d9f9000006'),
    ]
    
    result = parse_packets(test_packets, sleep_start_ring_ts=278570166)
    print("METHUSELAH // OURA PARSER SELF-TEST")
    print(f"  HRV:        {result['hrv_ms']}ms")
    print(f"  RHR:        {result['rhr_bpm']}bpm")
    print(f"  Sleep:      {result['sleep_duration_min']}min")
    print(f"  IBI samples:{result['ibi_sample_count']}")
