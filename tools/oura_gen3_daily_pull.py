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

def encrypt_nonce(nonce):
    return AES.new(AUTH_KEY, AES.MODE_ECB).encrypt(pad(nonce, 16))

async def on_notify(sender, data):
    pkt = bytes(data)
    received.append(pkt)
    print(f"  RX: {pkt.hex()}")

async def wr(client, data):
    await client.write_gatt_char(WRITE_CHAR, data, response=False)

async def main():
    print(f"Connecting to {ADDR} ...")
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
            print("FATAL: No nonce received during handshake.")
            sys.exit(1)
        proof = encrypt_nonce(nonce[:15])
        received.clear()
        await wr(client, b"\x2f\x11\x2d" + proof)
        await asyncio.sleep(1)
        auth_ok = any(p == bytes.fromhex("2f022e00") for p in received)
        if not auth_ok:
            print(f"FATAL: Auth failed. Response: {[p.hex() for p in received]}")
            sys.exit(1)
        print("AUTH SUCCESS.")
        received.clear()
        await wr(client, b"\x16\x01\x02")
        await asyncio.sleep(0.5)
        ts = struct.pack("<I", int(time.time()))
        await wr(client, b"\x12\x07" + ts + b"\x00\x00\x00")
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
        print(f"Setup complete. Packets so far: {len(received)}")
        received.clear()
        hours_ago = int(sys.argv[1]) if len(sys.argv) > 1 else 24
        offset = 1777324215 - 274484781
        target_time = int(time.time()) - (hours_ago * 3600)
        ring_ts = target_time - offset
        ts_bytes = struct.pack("<I", ring_ts & 0xFFFFFFFF)
        print(f"Requesting history from ~{hours_ago}h ago...")
        await wr(client, b"\x10\x09" + ts_bytes + b"\xff\xff\xff\xff\xff")
        await asyncio.sleep(5)
        print(f"\n=== HISTORY FETCH RESULT ===")
        print(f"Packets received: {len(received)}")
        for p in received:
            print(f"  {p.hex()}")
        if not received:
            print("No data returned.")

asyncio.run(main())
