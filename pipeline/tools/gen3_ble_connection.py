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
import os
import struct
import time
from bleak import BleakClient, BleakScanner
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

ADDR = "71E77907-1EE9-4949-801C-02979071309C"
# 2026-08-13: was hardcoded here (and duplicated in oura_gen3_daily_pull.py /
# oura_gen3_morning_pull.py) and committed in plaintext to this public repo --
# same class of exposure as GEN3_BRIDGE_WRITE_SECRET, caught and fixed 07-18.
AUTH_KEY = bytes.fromhex(os.environ["GEN3_RING_AUTH_KEY"])
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
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    while asyncio.get_event_loop().time() < deadline:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break
        found_event = asyncio.Event()

        def detection_callback(device, _advertisement_data):
            if device.address.upper() == ADDR.upper():
                found_event.set()

        scanner = BleakScanner(detection_callback)
        try:
            await scanner.start()
        except Exception as e:
            # CoreBluetooth can throw if BT state is changing (lid open/close,
            # BT toggle). Wait and retry rather than crashing the daemon.
            print(f"[scan_for_ring] Scanner start failed ({e}) — retrying in 10s.")
            await asyncio.sleep(10)
            continue
        try:
            await asyncio.wait_for(found_event.wait(), timeout=min(30, remaining))
            return True
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            print(f"[scan_for_ring] Scanner wait failed ({e}) — retrying in 10s.")
            await asyncio.sleep(10)
        finally:
            try:
                await scanner.stop()
            except Exception:
                pass
    return False


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
    # Brief pause: on macOS a fast reconnect (bonded peripheral, seconds after
    # a drop) can leave the GATT service table not yet populated even though
    # connect() returned. Without this, the first write_gatt_char raises
    # "Service Discovery has not been performed yet" (confirmed 2026-07-15).
    await asyncio.sleep(1)
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

    # 2026-08-04: sync-time write, opcode 0x12 -- ring clock (UTC unix secs +
    # timezone-half-hours byte). This project's own logs have NEVER once
    # shown a "Time sync" (0x42) event across every daemon night on record,
    # and this handshake never sent one -- meaning the ring has likely never
    # been told the current time by this pipeline. Reverse-engineered from
    # the official Android app's connect state machine (open_oura project,
    # verified live against a real Ring 3 Horizon -- same generation as
    # ours): SYNC_TIMESTAMPS fires on every connection, immediately after
    # auth and before anything else, including before enabling
    # notifications. Wire format and byte order confirmed against that
    # project's actual Packet::encode() (`[tag, len, payload..]`), not just
    # its prose docs. Timezone byte hardcoded to 0 to match their own real,
    # working client call (oura-link/src/client.rs) rather than inventing a
    # signed-offset convention neither project has tested.
    #
    # Hypothesis under test: the ring's sleep-summary (0x4C) finalization
    # may depend on having an accurate internal clock to know when to close
    # out and finalize a night's bout -- which would explain why 0x4C has
    # behaved as a stale, never-cleanly-finalized backlog across this
    # project's entire history. Unconfirmed -- needs a real night to judge,
    # not assumed correct just because the write succeeds.
    received.clear()
    sync_time_payload = struct.pack("<Q", int(time.time())) + b"\x00"
    await wr(client, bytes([0x12, len(sync_time_payload)]) + sync_time_payload)
    await asyncio.sleep(0.3)

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
    # 2026-08-04: force=1, not force=0. Per open_oura's reverse-engineering
    # of the official app (verified against real Ring 3 Horizon hardware,
    # same generation as ours): opcode 0x28 is not a passive status check --
    # it's a REQUEST asking the ring to actively run sleep analysis now,
    # after which sleep_phase/sleep_summary events (0x4b/0x4e/0x5a,
    # 0x49/0x4c/0x4f/0x58 -- our own exact tag numbers, independently
    # confirmed) appear in history. Their own cheatsheet notes force=1 was
    # tested successfully on real hardware; we'd only ever sent force=0.
    # Response tag 0x29 -- not currently in EVENT_TAGS/parsed, so its
    # content isn't visible yet; worth adding if this doesn't move the
    # needle and more diagnosis is needed. Bundled with the same night's
    # sync-time change (see commit bff19e7) at Bryden's explicit choice,
    # accepting that a fix tonight won't tell us which of the two did it.
    await wr(client, b"\x28\x01\x01")
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
