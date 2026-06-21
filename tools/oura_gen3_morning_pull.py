#!/usr/bin/env python3
import asyncio, struct, time, sys
from bleak import BleakClient
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

ADDR        = "71E77907-1EE9-4949-801C-02979071309C"
AUTH_KEY    = bytes.fromhex("bdc2c37e63ce24c445b7de1eba6e1a65")
WRITE_CHAR  = "98ed0002-a541-11e4-b6a0-0002a5d5c51b"
NOTIFY_CHAR = "98ed0003-a541-11e4-b6a0-0002a5d5c51b"
received = []

EVENT_TAGS = {
    0x41: "Ring start", 0x42: "Time sync", 0x43: "Debug event", 0x44: "IBI event",
    0x45: "State change", 0x46: "Temp event", 0x47: "Motion event",
    0x48: "Sleep period info", 0x49: "Sleep summary (1)", 0x4A: "PPG amplitude",
    0x4B: "Sleep phase info", 0x4C: "Sleep summary (2)", 0x4D: "Ring sleep feature info",
    0x4E: "Sleep phase details", 0x4F: "Sleep summary (3)", 0x50: "Activity info",
    0x51: "Activity summary (1)", 0x52: "Activity summary (2)", 0x53: "Wear event",
    0x54: "Recovery summary", 0x55: "Sleep heart rate", 0x56: "Alert event",
    0x57: "Ring sleep feature info (2)", 0x58: "Sleep summary (4)", 0x59: "EDA event",
    0x5A: "Sleep phase data", 0x5B: "BLE connection", 0x5C: "User information",
    0x5D: "HRV event", 0x5E: "Self-test event", 0x5F: "Raw ACM event",
    0x60: "IBI and amplitude event", 0x61: "Debug data", 0x62: "On-demand MEAs",
    0x63: "PPG peak event", 0x64: "Raw PPG event", 0x65: "On-demand session",
    0x66: "On-demand motion", 0x67: "Raw PPG summary", 0x68: "Raw PPG Data",
    0x69: "Temp period", 0x6A: "Sleep period info (2)", 0x6B: "Motion period",
    0x6C: "Feature session", 0x6D: "MEAs quality event", 0x6E: "SPO2 IBI+amplitude",
    0x6F: "SPO2 event", 0x70: "SPO2 smoothed event", 0x71: "Green IBI+amplitude",
    0x72: "Sleep ACM period", 0x73: "EHR trace event", 0x74: "EHR ACM intensity",
    0x75: "Sleep temp event", 0x76: "Bedtime period", 0x77: "SPO2 DC event",
    0x79: "Self-test data event", 0x7A: "Tag event", 0x7E: "Real step feature (1)",
    0x7F: "Real step feature (2)", 0x81: "CVA raw PPG data", 0x82: "Scan start",
    0x83: "Scan end",
}

PRIORITY_TAGS = {0x44, 0x49, 0x4B, 0x4C, 0x4E, 0x4F, 0x55, 0x58, 0x5D, 0x60, 0x6A, 0x6E, 0x71, 0x72}

def _i8(b):
    return b - 0x100 if b & 0x80 else b

def decode_sleep_period_info_2(p):
    if len(p) < 10:
        raise ValueError("too short")
    motion_count = p[6]
    if motion_count >= 0x79:
        raise ValueError("motion_count out of range")
    sleep_state = _i8(p[7])
    if not (0 <= sleep_state < 3):
        raise ValueError("sleep_state out of range")
    cv_raw = p[8] | (p[9] << 8)
    return {
        "average_hr": p[0] * 0.5, "hr_trend": _i8(p[1]) * 0.0625,
        "mzci": p[2] * 0.0625, "dzci": p[3] * 0.0625,
        "breath": p[4] / 8.0, "breath_v": p[5] / 8.0,
        "motion_count": motion_count, "sleep_state": sleep_state,
        "cv": cv_raw / 65536.0,
    }

def encrypt_nonce(nonce):
    return AES.new(AUTH_KEY, AES.MODE_ECB).encrypt(pad(nonce, 16))

async def on_notify(sender, data):
    received.append(bytes(data))

async def wr(client, data):
    await client.write_gatt_char(WRITE_CHAR, data, response=False)

def parse_event(data: bytes):
    if len(data) < 6:
        return None
    tag = data[0]
    length = data[1]
    ts_boot = struct.unpack("<I", data[2:6])[0]
    payload = data[6:]
    return {"tag": tag, "tag_name": EVENT_TAGS.get(tag, f"UNKNOWN (0x{tag:02x})"),
            "length": length, "boot_ts": ts_boot, "payload": payload}

async def main():
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Connecting to Gen3 ring...")
    async with BleakClient(ADDR, timeout=30) as client:
        print("Connected.")
        await client.start_notify(NOTIFY_CHAR, on_notify)
        await wr(client, b"\x08\x03\x00\x00\x00")
        await wr(client, b"\x2f\x02\x01\x00")
        await wr(client, b"\x2f\x02\x01\x01")
        await asyncio.sleep(0.5)
        received.clear()
        await wr(client, b"\x2f\x01\x2b")
        await asyncio.sleep(2)
        nonce = None
        for pkt in received:
            for i in range(min(4, len(pkt))):
                if pkt[i] == 0x2C and len(pkt) > i + 1:
                    nonce = pkt[i+1:i+16]
                    break
        if not nonce:
            print("FATAL: No nonce received.")
            sys.exit(1)
        proof = encrypt_nonce(nonce[:15])
        received.clear()
        await wr(client, b"\x2f\x11\x2d" + proof)
        await asyncio.sleep(1)
        if not any(p == bytes.fromhex("2f022e00") for p in received):
            print(f"FATAL: Auth failed: {[p.hex() for p in received]}")
            sys.exit(1)
        print("AUTH SUCCESS.")
        received.clear()
        await wr(client, b"\x16\x01\x02")
        await asyncio.sleep(0.5)
        await wr(client, b"\x1c\x01\xbf")
        await asyncio.sleep(0.3)
        for cat in [1, 2, 3, 4, 5]:
            await wr(client, bytes([0x18, 0x03, cat, 0xff, 0xff]))
            await asyncio.sleep(0.2)
        await wr(client, b"\x0c\x00")
        await asyncio.sleep(0.3)
        for param in [0x02, 0x04, 0x0b, 0x0d, 0x03, 0x0b, 0x10]:
            await wr(client, bytes([0x2f, 0x02, 0x20, param]))
            await asyncio.sleep(0.2)
        await wr(client, b"\x28\x01\x00")
        await asyncio.sleep(0.5)
        print(f"Setup complete. ({len(received)} packets)")
        received.clear()
        print("Requesting full available history (boot_ts=0)...")
        await wr(client, b"\x10\x09" + b"\x00\x00\x00\x00" + b"\xff\xff\xff\xff\xff")
        await asyncio.sleep(6)
        print(f"\n=== RAW: {len(received)} packets received ===\n")
        parsed = [parse_event(p) for p in received]
        parsed = [p for p in parsed if p]
        if not parsed:
            print("No events parsed.")
            return
        boot_tss = [p["boot_ts"] for p in parsed]
        print(f"Boot-relative timestamp range: {min(boot_tss)} - {max(boot_tss)}")
        print(f"Span: {(max(boot_tss) - min(boot_tss)):,} seconds (~{(max(boot_tss) - min(boot_tss)) / 3600:.1f} hours)\n")
        from collections import Counter
        tally = Counter(p["tag_name"] for p in parsed)
        print("Event type breakdown:")
        for name, count in tally.most_common():
            print(f"  {count:4d}  {name}")
        priority_events = [p for p in parsed if p["tag"] in PRIORITY_TAGS]
        print(f"\n=== PRIORITY EVENTS: {len(priority_events)} found ===")
        for p in priority_events:
            print(f"  [{p['tag_name']}] boot_ts={p['boot_ts']:>10}  payload={p['payload'].hex()}")

        sleep_states = []
        print(f"\n=== SLEEP STATE DECODE (0x6a) ===")
        for p in parsed:
            if p["tag"] == 0x6A:
                try:
                    decoded = decode_sleep_period_info_2(p["payload"])
                    sleep_states.append(decoded["sleep_state"])
                    print(f"  boot_ts={p['boot_ts']:>10}  state={decoded['sleep_state']}  "
                          f"hr={decoded['average_hr']:.1f}  breath={decoded['breath']:.1f}  "
                          f"motion={decoded['motion_count']}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if sleep_states:
            from collections import Counter
            sc = Counter(sleep_states)
            total = len(sleep_states)
            print(f"\nSleep state distribution ({total} samples):")
            for state in (0, 1, 2):
                pct = 100 * sc.get(state, 0) / total
                print(f"  state {state}: {pct:.1f}%  ({sc.get(state, 0)} samples)")
            print("  (state-to-label mapping not yet confirmed - see notes)")
        else:
            print("  No 0x6a sleep period events found in this pull.")

        outpath = f"gen3_pull_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(outpath, "w") as f:
            f.write(f"Pull timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for p in parsed:
                f.write(f"[{p['tag_name']}] boot_ts={p['boot_ts']} payload={p['payload'].hex()}\n")
        print(f"\nFull output saved to: {outpath}")

asyncio.run(main())
