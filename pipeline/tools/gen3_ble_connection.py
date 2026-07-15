"""Shared Gen3 ring BLE connect/auth primitives.

Extracted from oura_gen3_morning_pull.py's connect-auth-setup sequence so
oura_gen3_ble_daemon.py (which needs to hold a connection open across many
poll cycles instead of one-shot) doesn't duplicate the handshake a sixth
time. Existing one-shot scripts (oura_gen3_morning_pull.py,
oura_gen3_auto_loop.py, oura_gen3_daily_pull.py) are intentionally left
as-is, not migrated to this module -- that would be unrelated churn on
working code.
"""
import asyncio
import struct
from bleak import BleakClient, BleakScanner
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

ADDR = "71E77907-1EE9-4949-801C-02979071309C"
AUTH_KEY = bytes.fromhex("bdc2c37e63ce24c445b7de1eba6e1a65")
WRITE_CHAR = "98ed0002-a541-11e4-b6a0-0002a5d5c51b"
NOTIFY_CHAR = "98ed0003-a541-11e4-b6a0-0002a5d5c51b"


def encrypt_nonce(nonce):
    return AES.new(AUTH_KEY, AES.MODE_ECB).encrypt(pad(nonce, 16))


async def wr(client, data):
    await client.write_gatt_char(WRITE_CHAR, data, response=False)


class ConnectError(Exception):
    pass


async def scan_for_ring(timeout_seconds=1800):
    """Passively scan for the ring's BLE advertisement.

    On macOS, BleakClient.connect() for a known peripheral UUID does NOT
    reliably respect its timeout= parameter — CoreBluetooth queues
    connectPeripheral: indefinitely instead of returning after the timeout.
    Confirmed overnight 2026-07-14: only 5 "reconnect attempts" happened
    in 8h (one every ~2h) because each open_connection() call blocked until
    CoreBluetooth finally connected, rather than retrying every 10s.

    Uses the callback-based BleakScanner so scanning stops the instant the
    ring is detected — not after a fixed window — minimising reconnect latency
    during short out-of-range events like bathroom trips. Returns True when
    the ring is detected in advertisements, False on timeout.

    Caller should call open_connection() immediately on True return while
    the ring is still in advertising state.
    """
    if timeout_seconds <= 0:
        return False
    found_event = asyncio.Event()

    def detection_callback(device, _advertisement_data):
        if device.address.upper() == ADDR.upper():
            found_event.set()

    scanner = BleakScanner(detection_callback)
    await scanner.start()
    try:
        await asyncio.wait_for(found_event.wait(), timeout=timeout_seconds)
        return True
    except asyncio.TimeoutError:
        return False
    finally:
        await scanner.stop()


async def open_connection(disconnected_callback=None):
    """Connect, authenticate, and run the ring's setup sequence.

    Returns (client, received) where `received` is the list on_notify
    appends raw packets to -- caller owns clearing it between requests.
    Raises ConnectError on any handshake failure (nonce not received,
    auth rejected). Caller is responsible for calling client.disconnect()
    when done.
    """
    received = []

    async def on_notify(sender, data):
        received.append(bytes(data))

    client = BleakClient(ADDR, timeout=30, disconnected_callback=disconnected_callback)
    await client.connect()
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
                nonce = pkt[i + 1:i + 16]
                break
    if not nonce:
        await client.disconnect()
        raise ConnectError("No nonce received during handshake.")

    proof = encrypt_nonce(nonce[:15])
    received.clear()
    await wr(client, b"\x2f\x11\x2d" + proof)
    await asyncio.sleep(1)
    if not any(p == bytes.fromhex("2f022e00") for p in received):
        await client.disconnect()
        raise ConnectError(f"Auth failed: {[p.hex() for p in received]}")

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

    return client, received


async def request_history(client, received, since_boot_ts=0, wait_seconds=6):
    """Send the history-since-boot_ts request and wait for the response.

    since_boot_ts=0 requests the full buffer (what every existing one-shot
    script does). A nonzero value requests only events since that ring-
    relative tick -- confirmed supported by oura_gen3_daily_pull.py's
    hours-ago request. Clears `received` before sending so the caller gets
    exactly this request's response back.
    """
    received.clear()
    ts_bytes = struct.pack("<I", since_boot_ts & 0xFFFFFFFF)
    await wr(client, b"\x10\x09" + ts_bytes + b"\xff\xff\xff\xff\xff")
    await asyncio.sleep(wait_seconds)
    return list(received)
