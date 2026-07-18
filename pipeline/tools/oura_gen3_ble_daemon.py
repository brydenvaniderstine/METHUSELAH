#!/usr/bin/env python3
"""
METHUSELAH // Gen3 persistent-connection BLE daemon

Holds ONE BLE connection to the ring open continuously and polls it every
POLL_SECONDS (default 60s) using an incremental "history since boot_ts=X"
request, instead of reconnecting/re-authenticating every cycle the way
oura_gen3_auto_loop.py does. Comfortably ahead of the ring's ~1.8-minute
worst-case circular-buffer eviction window (confirmed in known_issues.md),
so no event should ever be silently overwritten while this is running.

Built 2026-07-12 after the owner confirmed the official Oura app's BLE
connection to the ring is no longer worth protecting -- it was only ever a
data pipe to Oura's cloud API, and that pipe is being cut off by the Gen4
token expiry (2026-07-13) regardless. See known_issues.md and
SESSION_HANDOFF.md for the full context/decision.

Reuses (does not duplicate):
  - pipeline/decoders/* for every decode (same imports as
    oura_gen3_morning_pull.py)
  - gen3_ble_connection.py for connect/auth/setup and the incremental
    history-request primitive (confirmed supported by
    oura_gen3_daily_pull.py's hours-ago request)
  - gen3_bridge.py for the bridge JSON shape and live-site push, so this
    can't drift out of sync with oura_gen3_morning_pull.py or
    api/gen3-bridge.js

Usage:
    python3 pipeline/tools/oura_gen3_ble_daemon.py [poll_seconds] [duration_hours]

Defaults: poll_seconds=5, duration_hours=8 (one overnight/workday session).
Revised twice on 2026-07-12 from real live-hardware observations, each one
finding a faster real event rate than the last:
  1. First run at 60s: buffer filled (256 events) in ~66s just sitting at
     a desk -- already faster than the "~1.8 min worst-case while walking"
     figure this project was previously built around.
  2. Tightened to 30s: EVERY cycle still returned exactly 256 events with
     zero gaps in the continuity check (confirmed no data loss, but no
     margin either) -- measured sustained rate ~14 events/sec, meaning
     the 256-event buffer could fill in ~18 seconds during active daytime
     use. 30s was already too close to that ceiling.
5s leaves real margin under an ~18s fill time. This may still need
revisiting once there's daytime-activity and overnight-sleep data to
compare -- the true rate likely varies a lot by context.
Stop any time with Ctrl+C -- already-logged data and the last bridge push
are preserved.
"""
import asyncio
import os as _os
import sys as _sys
import time
from collections import Counter

_sys.path.insert(0, _os.path.dirname(__file__))
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))

from gen3_ble_connection import open_connection, request_history, scan_for_ring, ConnectError
from gen3_bridge import build_bridge_data, write_local_bridge_file, push_bridge_json
from decoders import (
    decode_sleep_period_info_2,
    decode_spo2_event,
    decode_spo2_ibi_amplitude,
    decode_sleep_temp_event,
    decode_debug_data_fuel_gauge,
    decode_motion_period,
    calculate_rmssd,
)

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
SLEEP_TAGS = {0x6A, 0x5D, 0x6F, 0x75}
ACTIVITY_TAGS = {0x7E, 0x7F}


def parse_event(data: bytes):
    if len(data) < 6:
        return None
    tag = data[0]
    boot_ts = int.from_bytes(data[2:6], "little")
    payload = data[6:]
    return {"tag": tag, "tag_name": EVENT_TAGS.get(tag, f"UNKNOWN (0x{tag:02x})"),
            "boot_ts": boot_ts, "payload": payload}


def classify(tags_seen, motion_count):
    has_sleep = bool(tags_seen & SLEEP_TAGS)
    has_activity = bool((tags_seen & ACTIVITY_TAGS) or motion_count >= 3)
    if has_sleep and has_activity:
        return "MIXED WINDOW"
    if has_sleep:
        return "SLEEP WINDOW"
    if has_activity:
        return "ACTIVE WINDOW"
    return "UNCLEAR"


def decode_cycle_events(events):
    """Decode this cycle's new events into the same accumulators
    oura_gen3_morning_pull.py builds the bridge JSON from. Returns
    (accumulators dict, pull_class, decode_fail_count).
    """
    hr_avgs, spo2_avgs, temps, ibi_ms_all = [], [], [], []
    ibi_packets = []  # per-packet IBI lists, for HRV RMSSD (needs packet boundaries preserved)
    fuel_gauge_pct = None
    total_steps, motion_period_found = 0, False
    cadence_samples = []
    tags_seen = set()
    motion_event_count = 0
    fails = 0

    asleep_6a_count = 0  # 0x6A packets with sleep_state != 0 — used for duration accumulation
    for ev in events:
        tags_seen.add(ev["tag"])
        if ev["tag"] == 0x47:
            motion_event_count += 1
        try:
            if ev["tag"] == 0x6A:
                d = decode_sleep_period_info_2(ev["payload"])
                hr_avgs.append(d["average_hr"])
                if d["sleep_state"] != 0:
                    asleep_6a_count += 1
            elif ev["tag"] == 0x6F:
                d = decode_spo2_event(ev["payload"])
                if d["spo2_percent"]:
                    spo2_avgs.append(sum(d["spo2_percent"]) / len(d["spo2_percent"]))
            elif ev["tag"] == 0x6E:
                d = decode_spo2_ibi_amplitude(ev["payload"])
                ibi_ms_all.extend(v for v in d["ibi_ms"] if 300 <= v <= 2000)
                ibi_packets.append(d["ibi_ms"])
            elif ev["tag"] == 0x75:
                d = decode_sleep_temp_event(ev["payload"])
                temps.extend(d["temps_c"])
            elif ev["tag"] == 0x6B:
                d = decode_motion_period(ev["payload"])
                motion_period_found = True
                total_steps += d["step_count"]
                if d["cadence_spm"] and d["cadence_spm"] > 0:
                    cadence_samples.append(d["cadence_spm"])
            elif ev["tag"] == 0x61 and len(ev["payload"]) > 0 and ev["payload"][0] == 0x14:
                d = decode_debug_data_fuel_gauge(ev["payload"])
                fuel_gauge_pct = round(d["battery_percentage"], 1)
        except ValueError:
            fails += 1

    ibi_hr_bpm = None
    if ibi_ms_all:
        ibi_hr_bpm = round(60000 / (sum(ibi_ms_all) / len(ibi_ms_all)), 1)
    hrv_ms = calculate_rmssd(ibi_packets)

    accum = {
        "hr_avgs": hr_avgs, "spo2_avgs": spo2_avgs, "temps": temps,
        "ibi_hr_bpm": ibi_hr_bpm, "fuel_gauge_pct": fuel_gauge_pct,
        "step_count": total_steps if motion_period_found else None,
        "cadence_spm": round(sum(cadence_samples) / len(cadence_samples), 1) if cadence_samples else None,
        "hrv_ms": hrv_ms,
        "asleep_6a_count": asleep_6a_count,  # asleep-state packets this cycle, ~60s each
        "ibi_packets": ibi_packets,  # raw IBI packet lists this cycle, for nightly accumulation
    }
    pull_class = classify(tags_seen, motion_event_count)
    return accum, pull_class, fails


async def main():
    poll_seconds = float(_sys.argv[1]) if len(_sys.argv) > 1 else 5
    duration_hr = float(_sys.argv[2]) if len(_sys.argv) > 2 else 8
    morning_pull_threshold_hrs = 4  # fire safety-net morning pull if less than this captured
    end_time = time.time() + duration_hr * 3600

    repo_root = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')
    log_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_daemon')
    _os.makedirs(log_dir, exist_ok=True)
    log_path = _os.path.join(log_dir, f"gen3_daemon_{time.strftime('%Y%m%d_%H%M%S')}.txt")

    digest_every = max(1, round(600 / poll_seconds))  # ~every 10 minutes
    tag_tally_since_digest = Counter()
    last_boot_ts = 0
    total_events_logged = 0
    sleep_secs_accumulated = 0  # rolling overnight total; each asleep 0x6A packet ≈ 60s
    ibi_packets_all: list = []  # all IBI packet lists across all cycles, for nightly RMSSD
    recent_tags: set = set()    # tags seen in the last two cycles; used to classify disconnects
    disconnected = asyncio.Event()

    def on_disconnect(_client):
        disconnected.set()

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting Gen3 BLE daemon: "
          f"poll every {poll_seconds}s, for up to {duration_hr}h. Ctrl+C to stop.")
    print(f"Logging to: {log_path}")

    with open(log_path, "a") as logf:
        logf.write(f"=== Daemon started {time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(poll={poll_seconds}s, duration={duration_hr}h) ===\n")
        logf.flush()

        client = None
        cycle = 0
        while time.time() < end_time:
            if client is None:
                # Scan first: BleakClient.connect() on macOS does not respect its
                # timeout= for bonded peripherals — CoreBluetooth queues the request
                # indefinitely instead of raising after 30s, producing ~2h gaps between
                # real reconnect attempts (confirmed 2026-07-14 overnight run).
                # BleakScanner.discover() uses a short-lived scan window so we know the
                # ring is actively advertising before calling open_connection().
                scan_timeout = max(0, min(1800, int(end_time - time.time())))
                print(f"[{time.strftime('%H:%M:%S')}] Scanning for ring (up to {scan_timeout}s)...")
                found = await scan_for_ring(timeout_seconds=scan_timeout)
                if not found:
                    print(f"[{time.strftime('%H:%M:%S')}] Ring not found in scan window — will retry.")
                    continue
                try:
                    print(f"[{time.strftime('%H:%M:%S')}] Ring detected — connecting...")
                    # 25s asyncio-level timeout: BleakClient.connect(timeout=30) does not
                    # reliably fire on macOS for bonded peripherals (CoreBluetooth queues
                    # connectPeripheral: indefinitely). The ring also stops advertising
                    # within seconds of a sleep-stage transition, so if we don't connect
                    # within ~25s the window has closed — confirmed 2026-07-17 overnight
                    # where connect() blocked from 04:31 until manually killed at 05:27.
                    client, received = await asyncio.wait_for(
                        open_connection(disconnected_callback=on_disconnect),
                        timeout=25,
                    )
                    disconnected.clear()
                    print(f"[{time.strftime('%H:%M:%S')}] Connected and authenticated.")
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
                # confirmed 2026-07-12 (real hardware run) that the ring's
                # since_boot_ts filter is inclusive, causing one duplicate event
                # per cycle boundary without this.
                since = last_boot_ts + 1 if last_boot_ts else 0
                raw = await request_history(client, received, since_boot_ts=since)
            except Exception as e:
                print(f"[{time.strftime('%H:%M:%S')}] Poll failed: {e} — will reconnect.")
                disconnected.set()
                raw = []

            if disconnected.is_set():
                # Task 3 instrumentation: 0x53 (Wear event) in the last two cycles
                # suggests the ring was removed before the drop; absence suggests pure
                # range-drop. This is the only way to resolve off-finger vs out-of-range
                # advertising behavior with real data over time.
                wear_tag_seen = 0x53 in recent_tags
                disconnect_type = "WEAR-EVENT (ring possibly removed)" if wear_tag_seen else "RANGE-DROP (no recent 0x53)"
                print(f"[{time.strftime('%H:%M:%S')}] Disconnected [{disconnect_type}] — will rescan.")
                try:
                    await client.disconnect()
                except Exception:
                    pass
                client = None
                recent_tags.clear()
                await asyncio.sleep(2)
                continue

            parsed = [p for p in (parse_event(pkt) for pkt in raw) if p]
            cycle += 1

            # Rolling two-cycle tag window for disconnect classification (Task 3).
            # 0x53 in this window means a wear-state change preceded the drop.
            if parsed:
                recent_tags = {p["tag"] for p in parsed}

            if parsed:
                # Some tags are protocol control/terminator packets, not real
                # historical telemetry -- confirmed 2026-07-12 (real hardware
                # run) for both 0x11 (end-of-transfer ack, garbage boot_ts
                # bytes) and 0x1f (empty payload, also garbage boot_ts). Both
                # are outside EVENT_TAGS' known 0x41-0x83 event range. Rather
                # than hardcode each one as discovered, exclude ANY tag not in
                # EVENT_TAGS from checkpoint calculation -- still logged for
                # visibility, just not trusted to advance the checkpoint.
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
                logf.flush()
                total_events_logged += len(parsed)

                accum, pull_class, fails = decode_cycle_events(parsed)
                print(f"[{time.strftime('%H:%M:%S')}] cycle {cycle}: {len(parsed)} new events "
                      f"({pull_class}), {fails} decode fails")

                # Accumulate sleep duration: each asleep-state 0x6A packet ≈ 60s of real sleep.
                # Only count during SLEEP WINDOW so activity-session packets don't inflate the total.
                if pull_class == "SLEEP WINDOW":
                    sleep_secs_accumulated += accum["asleep_6a_count"] * 60
                    # Accumulate IBI across all sleep cycles for nightly RMSSD.
                    # Per-cycle window (~5s) has too few pairs for calculate_rmssd's min_pairs=10.
                    ibi_packets_all.extend(accum["ibi_packets"])

                priority_data_present = any([
                    accum["hr_avgs"], accum["spo2_avgs"], accum["temps"],
                    accum["ibi_hr_bpm"], accum["fuel_gauge_pct"],
                    accum["step_count"] is not None,
                ])
                if priority_data_present:
                    # HRV: use nightly accumulated IBI (not per-cycle) so there are enough
                    # successive-difference pairs. Only push in sleep context.
                    nightly_hrv = calculate_rmssd(ibi_packets_all) if ibi_packets_all else None
                    hrv_for_bridge = nightly_hrv if pull_class == "SLEEP WINDOW" else None
                    sleep_hrs_for_bridge = round(sleep_secs_accumulated / 3600, 2) if sleep_secs_accumulated > 0 else None
                    bridge_data = build_bridge_data(
                        pull_class=pull_class,
                        pull_file=_os.path.basename(log_path),
                        priority_event_count=len(parsed),
                        hr_avgs=accum["hr_avgs"],
                        ibi_hr_bpm=accum["ibi_hr_bpm"],
                        temps=accum["temps"],
                        spo2_avgs=accum["spo2_avgs"],
                        fuel_gauge_pct=accum["fuel_gauge_pct"],
                        step_count=accum["step_count"],
                        cadence_spm=accum["cadence_spm"],
                        hrv_ms=hrv_for_bridge,
                        sleep_duration_hrs=sleep_hrs_for_bridge,
                    )
                    write_local_bridge_file(bridge_data, repo_root)
                    push_result = push_bridge_json(bridge_data)
                    print(f"[{time.strftime('%H:%M:%S')}] [BRIDGE PUSH] {push_result}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] cycle {cycle}: no new events")

            if cycle % digest_every == 0 and tag_tally_since_digest:
                print(f"\n=== DIGEST (last ~{digest_every * poll_seconds / 60:.0f} min) ===")
                for name, count in tag_tally_since_digest.most_common():
                    print(f"  {count:4d}  {name}")
                print(f"  Total events logged this session: {total_events_logged}\n")
                tag_tally_since_digest.clear()

            await asyncio.sleep(poll_seconds)

        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    print(f"\n=== Daemon session complete. Total events logged: {total_events_logged} ===")
    print(f"Full log: {log_path}")

    # Always recompute the final bridge from the complete daemon log.
    # This runs after the main loop so it has all IBI + sleep data for the
    # nightly RMSSD and sleep duration — more accurate than per-cycle pushes
    # which only see a 5-second slice.
    print(f"\n[POST-RUN] Recomputing bridge from full daemon log...")
    import subprocess as _subprocess
    recompute_script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                      "recompute_bridge_from_daemon.py")
    _rc = _subprocess.run([_sys.executable, recompute_script, log_path, "--push"],
                          capture_output=False)
    if _rc.returncode == 0:
        print("[POST-RUN] Bridge recomputed and pushed.")
    else:
        print(f"[POST-RUN] Recompute exited with code {_rc.returncode}.")

    # Safety net: if daemon captured less than the threshold of sleep data,
    # fire a one-shot morning pull to capture whatever the ring's buffer still holds.
    if sleep_secs_accumulated < morning_pull_threshold_hrs * 3600:
        captured_hrs = round(sleep_secs_accumulated / 3600, 2)
        print(f"\n[SAFETY NET] Only {captured_hrs}h of sleep data captured "
              f"(threshold: {morning_pull_threshold_hrs}h) — firing morning pull...")
        pull_script = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                     "oura_gen3_morning_pull.py")
        result = _subprocess.run([_sys.executable, pull_script], capture_output=False)
        if result.returncode == 0:
            print("[SAFETY NET] Morning pull completed.")
        else:
            print(f"[SAFETY NET] Morning pull exited with code {result.returncode}.")
    else:
        print(f"Sleep data OK ({round(sleep_secs_accumulated / 3600, 2)}h) — no safety-net pull needed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped by user. Already-logged data and the last bridge push are preserved.")
