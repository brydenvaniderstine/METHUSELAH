#!/usr/bin/env python3
import asyncio, struct, time
from bleak import BleakClient, BleakScanner
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

AUTH_KEY    = bytes.fromhex("cddfdb6abad6840a2304ee892751e976")
WRITE_CHAR  = "98ed0002-a541-11e4-b6a0-0002a5d5c51b"
NOTIFY_CHAR = "98ed0003-a541-11e4-b6a0-0002a5d5c51b"
received = []

def encrypt_nonce(nonce):
    return AES.new(AUTH_KEY, AES.MODE_ECB).encrypt(pad(nonce, 16))

def make_time_sync():
    return bytes([0x12, 0x07]) + struct.pack("<I", int(time.time())) + bytes([0x00, 0x00, 0x00])

async def on_notify(sender, data):
    received.append(bytes(data))
    print(f"  RX: {data.hex()}")

async def wr(client, data):
    await client.write_gatt_char(WRITE_CHAR, data, response=False)

async def main():
    print("Scanning...")
    device = await BleakScanner.find_device_by_filter(
        lambda d, _: d.name and "Oura Ring 4" in d.name, timeout=15)
    if not device:
        print("Not found."); return
    print(f"Found: {device.name}")
    async with BleakClient(device, timeout=30) as client:
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
                if pkt[i] == 0x2C and len(pkt) > i+1:
                    nonce = pkt[i+1:i+16]; break
        if not nonce:
            print("No nonce."); return
        proof = encrypt_nonce(nonce[:15])
        await wr(client, b"\x2f\x11\x2d" + proof)
        await asyncio.sleep(2)
        auth_ok = any(len(p)>=4 and p[0]==0x2F and p[1]==0x02 and p[3]==0x00 for p in received)
        if not auth_ok:
            print("Auth failed."); return
        print("AUTH SUCCESS")
        await wr(client, b"\x16\x01\x02")
        await asyncio.sleep(0.3)
        await wr(client, make_time_sync())
        await asyncio.sleep(0.3)
        await wr(client, b"\x1c\x01\xbf")
        await asyncio.sleep(0.2)
        for cat in [0x01,0x02,0x03,0x04,0x05]:
            await wr(client, bytes([0x18,0x03,cat,0xFF,0xFF]))
        await asyncio.sleep(0.3)
        await wr(client, b"\x0c\x00")
        await asyncio.sleep(0.2)
        for param in [0x02,0x04,0x0b,0x0d,0x03,0x0b,0x10]:
            await wr(client, bytes([0x2f,0x02,0x20,param]))
        await asyncio.sleep(0.3)
        await wr(client, b"\x28\x01\x00")
        await asyncio.sleep(0.5)
        received.clear()

        # Request from yesterday 9pm ring timestamp
        START_TS = 278570166
        print(f"Fetching from ring_ts={START_TS} (yesterday 9pm)...")
        fetch = bytes([0x10,0x09]) + struct.pack("<I", START_TS) + bytes([0xFF,0xFF,0xFF,0xFF,0xFF])
        await wr(client, fetch)
        for _ in range(120):
            await asyncio.sleep(0.5)
            if any(p and p[0]==0x11 for p in received):
                print("Stream complete."); break

        print(f"Total packets: {len(received)}")
        for p in received:
            print(f"  {p.hex()}")

asyncio.run(main())
