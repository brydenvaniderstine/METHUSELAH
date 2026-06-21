#!/usr/bin/env python3
"""
METHUSELAH // Gen3 auto-repeating pull loop
Runs the full connect/auth/pull/decode cycle every INTERVAL_MINUTES, to stay
ahead of the ring's circular flash-buffer eviction (confirmed storage-size-
limited, not time-limited - see open_ring/PROTOCOL.md line 405, 591).

Appends results to a running log file rather than overwriting each time, so
sleep_state observations accumulate across the whole night/day instead of
only ever showing the same narrow recent window.

Usage:
    python3 tools/oura_gen3_auto_loop.py [interval_minutes] [duration_hours]

Defaults: interval=15 min, duration=8 hours (one overnight session).
Stop early any time with Ctrl+C - already-logged data is preserved.
"""
import asyncio, struct, time, sys
from bleak import BleakClient
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

ADDR        = "71E77907-1EE9-4949-801C-02979071309C"
AUTH_KEY    = bytes.fromhex("bdc2c37e63ce24c445b7de1eba6e1a65")
WRITE_CHAR  = "98ed0002-a541-11e4-b6a0-0002a5d5c51b"
NOTIFY_CHAR = "98ed0003-a541-11e4-b6a0-0002a5d5c51b"

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

def parse_event(data: bytes):
    if len(data) < 6:
        return None
    tag = data[0]
    ts_boot = struct.unpack("<I", data[2:6])[0]
    payload = data[6:]
    return {"tag": tag, "tag_name": EVENT_TAGS.get(tag, f"UNKNOWN (0x{tag:02x})"),
            "boot_ts": ts_boot, "payload": payload}

async def single_pull():
    received = []

    async def on_notify(sender, data):
        received.append(bytes(data))

    async def wr(client, data):
        await client.write_gatt_char(WRITE_CHAR, data, response=False)

    try:
        async with BleakClient(ADDR, timeout=30) as client:
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
                return None
            proof = encrypt_nonce(nonce[:15])
            received.clear()
            await wr(client, b"\x2f\x11\x2d" + proof)
            await asyncio.sleep(1)
            if not any(p == bytes.fromhex("2f022e00") for p in received):
                return None
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
            received.clear()
            await wr(client, b"\x10\x09" + b"\x00\x00\x00\x00" + b"\xff\xff\xff\xff\xff")
            await asyncio.sleep(6)
            parsed = [parse_event(p) for p in received]
            return [p for p in parsed if p]
    except Exception as e:
        print(f"  [pull failed: {e}]")
        return None


async def main():
    interval_min = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    duration_hr = float(sys.argv[2]) if len(sys.argv) > 2 else 8
    n_pulls = max(1, int((duration_hr * 60) / interval_min))

    logpath = f"gen3_autoloop_{time.strftime('%Y%m%d_%H%M%S')}.txt"
    seen_boot_ts = set()
    all_sleep_states = []

    print(f"Starting auto-loop: every {interval_min} min, for {duration_hr} hours "
          f"({n_pulls} pulls). Ctrl+C to stop early.")
    print(f"Logging to: {logpath}")

    with open(logpath, "a") as logf:
        logf.write(f"=== Auto-loop started {time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(interval={interval_min}min, duration={duration_hr}h) ===\n")

        for i in range(n_pulls):
            now = time.strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n[{now}] Pull {i+1}/{n_pulls}...")
            events = await single_pull()

            if events is None:
                print("  FAILED (connection/auth error) - will retry next cycle.")
                logf.write(f"[{now}] PULL FAILED\n")
                logf.flush()
            else:
                new_count = 0
                new_states = []
                for ev in events:
                    if ev["boot_ts"] not in seen_boot_ts:
                        seen_boot_ts.add(ev["boot_ts"])
                        new_count += 1
                        logf.write(f"[{now}] [{ev['tag_name']}] boot_ts={ev['boot_ts']} "
                                    f"payload={ev['payload'].hex()}\n")
                        if ev["tag"] == 0x6A:
                            try:
                                decoded = decode_sleep_period_info_2(ev["payload"])
                                new_states.append(decoded["sleep_state"])
                                all_sleep_states.append((ev["boot_ts"], decoded["sleep_state"]))
                            except ValueError:
                                pass
                logf.flush()
                print(f"  OK: {len(events)} events received, {new_count} new "
                      f"(not seen in prior pulls)")
                if new_states:
                    print(f"  New sleep_state values this pull: {new_states}")

            if i < n_pulls - 1:
                print(f"  Sleeping {interval_min} min until next pull...")
                await asyncio.sleep(interval_min * 60)

    print(f"\n=== Auto-loop complete. Total unique events logged: {len(seen_boot_ts)} ===")
    if all_sleep_states:
        from collections import Counter
        states_only = [s for _, s in all_sleep_states]
        tally = Counter(states_only)
        print(f"Sleep state distribution across all pulls ({len(all_sleep_states)} samples):")
        for state in (0, 1, 2):
            print(f"  state {state}: {tally.get(state, 0)} samples")
    print(f"Full log: {logpath}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped early by user. Already-logged data is preserved in the log file.")
