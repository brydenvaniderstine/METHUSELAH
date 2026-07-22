#!/usr/bin/env python3
"""
METHUSELAH // Walk-test BLE keep-warm tool

Standalone manual tool: connect to the ring and hold the connection open
continuously BEFORE a walk starts, instead of connecting only after motion
begins. Root cause this is built to route around (see
pipeline/data/findings/known_issues.md, 2026-07-19 entry, "0x7E/0x7F absent
again... ring-side buffer window confirmed as the cause"): the ring's
readable buffer window for step-feature events (0x7E/0x7F) is short
(~7-12 min) and reliably rolls over before a fresh connect-auth-setup
handshake completes if the connection is only opened after the walk has
already started. Pre-connecting and polling continuously avoids that race
entirely -- the handshake happens while stationary (no time pressure), and
by the time real walking motion starts, the connection is already warm and
draining the buffer every poll_seconds.

Reuses the same event-driven scan-then-connect pattern already validated
for overnight reconnects in oura_gen3_ble_daemon.py (scan_for_ring,
open_connection, request_history from gen3_ble_connection.py) --
connection handling is not reimplemented here.

This tool does NOT decode or classify anything, and does NOT touch the
sleep-side daemon, classifier, or bridge. It only holds the connection and
logs every raw event (tagged by name) in the same format
oura_gen3_ble_daemon.py's log uses, so existing analysis tools (e.g.
analyze_fft_walk.py) can read the output directly once a real walk has
been captured.

Usage:
    python3 pipeline/tools/walk_test_keepwarm.py [poll_seconds]

Start this BEFORE putting the ring on / before leaving for the walk. Leave
it running through the whole walk -- it reconnects automatically on a
drop, the same way the overnight daemon does. Stop any time with Ctrl+C;
already-logged data is preserved (log writes are flushed every cycle).

Default poll_seconds=5, matching the daemon's real-hardware-validated
default (60s and 30s were both found too slow during active use -- see
oura_gen3_ble_daemon.py's module docstring).

IMPORTANT: running this tool and confirming it connects/holds/logs cleanly
verifies connection mechanics ONLY. It says nothing about whether 0x7E/0x7F
actually fires during a real walk -- that requires an actual walk while
this is running, not just a stationary dry run.
"""
import asyncio
import os as _os
import sys as _sys
import time
from collections import Counter

_sys.path.insert(0, _os.path.dirname(__file__))
from gen3_ble_connection import open_connection, request_history, scan_for_ring, ConnectError

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


def parse_event(data: bytes):
    if len(data) < 6:
        return None
    tag = data[0]
    boot_ts = int.from_bytes(data[2:6], "little")
    payload = data[6:]
    return {"tag": tag, "tag_name": EVENT_TAGS.get(tag, f"UNKNOWN (0x{tag:02x})"),
            "boot_ts": boot_ts, "payload": payload}


async def main():
    poll_seconds = float(_sys.argv[1]) if len(_sys.argv) > 1 else 5

    repo_root = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')
    log_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_walk')
    _os.makedirs(log_dir, exist_ok=True)
    log_path = _os.path.join(log_dir, f"gen3_walk_keepwarm_{time.strftime('%Y%m%d_%H%M%S')}.txt")

    digest_every = max(1, round(60 / poll_seconds))  # ~every 1 min -- short sessions, want fast visual confirmation
    tag_tally_since_digest = Counter()
    tag_tally_total = Counter()
    last_boot_ts = 0
    total_events_logged = 0
    disconnected = asyncio.Event()

    def on_disconnect(_client):
        disconnected.set()

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting walk-test keep-warm tool: "
          f"poll every {poll_seconds}s. Start this BEFORE the walk, leave it running "
          f"through the whole walk, Ctrl+C when done.")
    print(f"Logging to: {log_path}")
    print("NOTE: this tool only holds the connection and logs raw events -- it does "
          "NOT verify 0x7E/0x7F fires. That needs an actual walk while this runs.\n")

    with open(log_path, "a") as logf:
        logf.write(f"=== Walk-test keep-warm started {time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(poll={poll_seconds}s) ===\n")
        logf.flush()

        client = None
        cycle = 0
        while True:
            if client is None:
                # Scan first: BleakClient.connect() on macOS does not respect its
                # timeout= for bonded peripherals -- CoreBluetooth queues the request
                # indefinitely instead of raising. Same pattern already validated for
                # overnight reconnects in oura_gen3_ble_daemon.py.
                print(f"[{time.strftime('%H:%M:%S')}] Scanning for ring...")
                found = await scan_for_ring(timeout_seconds=1800)
                if not found:
                    print(f"[{time.strftime('%H:%M:%S')}] Ring not found in scan window — will retry.")
                    continue
                try:
                    print(f"[{time.strftime('%H:%M:%S')}] Ring detected — connecting...")
                    client, received = await asyncio.wait_for(
                        open_connection(disconnected_callback=on_disconnect),
                        timeout=25,
                    )
                    disconnected.clear()
                    print(f"[{time.strftime('%H:%M:%S')}] Connected and authenticated. Holding warm.")
                except asyncio.TimeoutError:
                    print(f"[{time.strftime('%H:%M:%S')}] Connect timed out (ring likely "
                          f"stopped advertising) — will rescan.")
                    client = None
                    continue
                except (ConnectError, Exception) as e:
                    print(f"[{time.strftime('%H:%M:%S')}] Connect failed: {e} — will rescan.")
                    client = None
                    await asyncio.sleep(5)
                    continue

            try:
                # +1 makes this exclusive of the last event already captured --
                # same off-by-one fix already validated in oura_gen3_ble_daemon.py.
                since = last_boot_ts + 1 if last_boot_ts else 0
                raw = await request_history(client, received, since_boot_ts=since)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Poll failed: {e} — will reconnect.")
                disconnected.set()
                raw = []

            if disconnected.is_set():
                print(f"[{time.strftime('%H:%M:%S')}] Disconnected — will rescan.")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                client = None
                await asyncio.sleep(2)
                continue

            parsed = [p for p in (parse_event(pkt) for pkt in raw) if p]
            cycle += 1

            if parsed:
                # Exclude tags outside the known EVENT_TAGS range from checkpoint
                # calculation -- same terminator/ack filtering already validated in
                # oura_gen3_ble_daemon.py (0x11, 0x1f are protocol control packets
                # with garbage boot_ts, not real telemetry).
                checkpoint_candidates = [p["boot_ts"] for p in parsed if p["tag"] in EVENT_TAGS]
                if checkpoint_candidates:
                    new_max = max(checkpoint_candidates)
                    if new_max < last_boot_ts:
                        print(f"[{time.strftime('%H:%M:%S')}] boot_ts regressed "
                              f"({new_max} < {last_boot_ts}) — ring likely rebooted, "
                              f"resetting checkpoint.")
                        last_boot_ts = 0
                    else:
                        last_boot_ts = new_max

                for p in parsed:
                    logf.write(f"[{p['tag_name']}] boot_ts={p['boot_ts']} payload={p['payload'].hex()}\n")
                    tag_tally_since_digest[p["tag_name"]] += 1
                    tag_tally_total[p["tag_name"]] += 1
                logf.flush()
                total_events_logged += len(parsed)
                print(f"[{time.strftime('%H:%M:%S')}] cycle {cycle}: {len(parsed)} new events "
                      f"(total {total_events_logged})")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] cycle {cycle}: no new events")

            if cycle % digest_every == 0 and tag_tally_since_digest:
                print(f"\n=== DIGEST (last ~{digest_every * poll_seconds / 60:.1f} min) ===")
                for name, count in tag_tally_since_digest.most_common():
                    print(f"  {count:4d}  {name}")
                print(f"  Total events logged this session: {total_events_logged}\n")
                tag_tally_since_digest.clear()

            await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n[{time.strftime('%H:%M:%S')}] Ctrl+C received — stopping. "
              f"Already-logged data is preserved.")
