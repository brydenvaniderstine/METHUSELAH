#!/usr/bin/env python3
"""Recompute bridge JSON from a daemon log and push to live site.

Use this when the daemon's final bridge push was overwritten by an
ACTIVE WINDOW morning pull. Reads the daemon log, computes:
  - sleep_duration_hrs from state=1 0x6A spans × tick rate
  - hrv_ms (RMSSD) from ALL 0x6E IBI events across the full night
  - rhr_bpm, spo2_avg_pct, sleep_temp_c, battery_pct (averaged)
  - sleep_stages from 0x4C if the cluster fired

Usage:
  cd ~/Desktop/METHUSELAH/pipeline
  python3 tools/recompute_bridge_from_daemon.py [daemon_log_path]
  python3 tools/recompute_bridge_from_daemon.py --push  # also push to live site
"""

import os, sys, re, struct, math
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from decoders import (
    decode_sleep_period_info_2, decode_spo2_ibi_amplitude,
    decode_spo2_event, decode_sleep_temp_event,
    decode_debug_data_fuel_gauge, decode_sleep_summary_2,
)
from decoders.hrv_rmssd import calculate_rmssd
from gen3_bridge import build_bridge_data, write_local_bridge_file, push_bridge_json

DAEMON_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw_pulls', 'gen3_daemon')
REPO_ROOT  = os.path.join(os.path.dirname(__file__), '..', '..')

# Tick rate: empirically derived from gen3_daemon_20260717_224745 (first boot_ts 67564124,
# last meaningful boot_ts 67975382, daemon duration=8h=28800s → 14.28 ticks/sec).
# This is an approximation; 0x4C sleep summary is authoritative when available.
TICKS_PER_SEC = 14.279


def parse_daemon_log(path):
    entries = []
    line_re = re.compile(r'^\[(.+?)\] boot_ts=(\d+) payload=([0-9a-f]+)$')
    header_re = re.compile(r'=== Daemon started (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \(poll=(\d+)s, duration=(\d+)h\)')

    header = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            hm = header_re.match(line)
            if hm:
                header = {'start': hm.group(1), 'poll': int(hm.group(2)), 'duration_h': int(hm.group(3))}
                continue
            m = line_re.match(line)
            if m:
                entries.append({
                    'tag_name': m.group(1),
                    'boot_ts': int(m.group(2)),
                    'payload': bytes.fromhex(m.group(3)),
                })
    return header, entries


# Tag name → numeric tag (subset needed for decode dispatch)
TAG_NAMES = {
    'Sleep period info (2)': 0x6A,
    'SPO2 IBI+amplitude':    0x6E,
    'SPO2 event':            0x6F,
    'Sleep temp event':      0x75,
    'Debug data':            0x61,
    'Sleep summary (2)':     0x4C,
}


def main(log_path, do_push=False):
    print(f"=== RECOMPUTE BRIDGE FROM DAEMON LOG ===")
    print(f"Source: {os.path.basename(log_path)}")
    print()

    header, entries = parse_daemon_log(log_path)
    if header:
        print(f"Daemon started: {header['start']}, duration={header['duration_h']}h, poll={header['poll']}s")
    print(f"Total entries: {len(entries)}")

    # Compute tick rate from first/last boot_ts and daemon duration
    meaningful = [e['boot_ts'] for e in entries if e['boot_ts'] < 100_000_000]  # exclude glitch values
    if meaningful and header.get('duration_h'):
        span_ticks = max(meaningful) - min(meaningful)
        span_secs = header['duration_h'] * 3600
        tick_rate = span_ticks / span_secs if span_secs > 0 else TICKS_PER_SEC
        print(f"Tick rate: {tick_rate:.3f} ticks/sec (derived from log span + header duration)")
    else:
        tick_rate = TICKS_PER_SEC
        print(f"Tick rate: {tick_rate:.3f} ticks/sec (fallback constant)")
    print()

    # Decode everything
    hr_avgs, spo2_avgs, temps, ibi_packets_all = [], [], [], []
    fuel_gauge_pct = None
    state_runs = []   # (state, boot_ts_start, boot_ts_end)
    sleep_stages_bridge = None

    prev_state = None
    prev_ts = None
    last_6a_ts = None

    for e in entries:
        tag = TAG_NAMES.get(e['tag_name'])
        if tag is None:
            continue
        try:
            if tag == 0x6A:
                d = decode_sleep_period_info_2(e['payload'])
                hr_avgs.append(d['average_hr'])
                s = d['sleep_state']
                bt = e['boot_ts']
                last_6a_ts = bt
                if s != prev_state:
                    if prev_state is not None:
                        state_runs.append((prev_state, prev_ts, bt))
                    prev_state = s
                    prev_ts = bt
            elif tag == 0x6E:
                d = decode_spo2_ibi_amplitude(e['payload'])
                ibi_packets_all.append(d['ibi_ms'])
            elif tag == 0x6F:
                d = decode_spo2_event(e['payload'])
                if d['spo2_percent']:
                    spo2_avgs.append(sum(d['spo2_percent']) / len(d['spo2_percent']))
            elif tag == 0x75:
                d = decode_sleep_temp_event(e['payload'])
                temps.extend(d['temps_c'])
            elif tag == 0x61:
                if len(e['payload']) > 0 and e['payload'][0] == 0x14:
                    from decoders import decode_debug_data_fuel_gauge
                    d = decode_debug_data_fuel_gauge(e['payload'])
                    fuel_gauge_pct = round(d['battery_percentage'], 1)
            elif tag == 0x4C:
                d = decode_sleep_summary_2(e['payload'])
                durs = d['stage_durations_min']
                sleep_stages_bridge = {
                    'wake_min':  durs[0], 'light_min': durs[1],
                    'rem_min':   durs[2], 'deep_min':  durs[3],
                    'source_tag': '0x4C',
                }
                print(f"0x4C cluster found! Stages: {sleep_stages_bridge}")
        except Exception as ex:
            pass

    # Close the last run at the last 0x6A timestamp (not max of all entries —
    # non-0x6A events continue after sleep ends and would inflate the duration).
    if prev_state is not None and prev_ts is not None and last_6a_ts is not None:
        state_runs.append((prev_state, prev_ts, last_6a_ts))

    # Sleep duration: only from 0x4C firmware summary (authoritative).
    # 0x6A state=1 tick spans are NOT used — the ring stops emitting 0x6A
    # before the sleep session ends, so tick-derived duration systematically
    # undercounts. The 0x4C cluster fires during the morning pull after the
    # daemon ends; recompute_bridge is called before that pull completes.
    sleep_duration_hrs = None  # populated by morning pull via 0x4C, not here

    # HRV from all night's IBI
    hrv_ms = calculate_rmssd(ibi_packets_all) if ibi_packets_all else None

    # HR average
    rhr_bpm = round(sum(hr_avgs) / len(hr_avgs), 1) if hr_avgs else None
    spo2 = round(sum(spo2_avgs) / len(spo2_avgs), 1) if spo2_avgs else None
    temp = round(sum(temps) / len(temps), 2) if temps else None
    ibi_hr = round(60000 / (sum(v for pkt in ibi_packets_all for v in pkt if 300 <= v <= 2000) /
                             len([v for pkt in ibi_packets_all for v in pkt if 300 <= v <= 2000])), 1) \
             if any(ibi_packets_all) else None

    print(f"Results:")
    print(f"  sleep_duration_hrs: {sleep_duration_hrs}  (from 0x4C only — not derived from 0x6A)")
    print(f"  hrv_ms (RMSSD):     {hrv_ms}  (from {sum(len(p) for p in ibi_packets_all)} IBI values)")
    print(f"  rhr_bpm:            {rhr_bpm}")
    print(f"  spo2_avg_pct:       {spo2}")
    print(f"  sleep_temp_c:       {temp}")
    print(f"  battery_pct:        {fuel_gauge_pct}")
    print(f"  sleep_stages:       {sleep_stages_bridge}")
    print()

    bridge_data = build_bridge_data(
        pull_class='SLEEP WINDOW',
        pull_file=os.path.basename(log_path),
        priority_event_count=len(entries),
        hr_avgs=hr_avgs,
        ibi_hr_bpm=ibi_hr,
        temps=temps,
        spo2_avgs=spo2_avgs,
        fuel_gauge_pct=fuel_gauge_pct,
        hrv_ms=hrv_ms,
        sleep_duration_hrs=sleep_duration_hrs,
        sleep_stages=sleep_stages_bridge,
    )

    # Not merge-protected: sleep_duration_hrs is intentionally None here (see
    # above) pending the more authoritative morning-pull 0x4C read, and must
    # not be silently resurrected from a prior 0x6A-derived value.
    bridge_path = write_local_bridge_file(bridge_data, REPO_ROOT)
    print(f"[BRIDGE] Written → {bridge_path}")

    if do_push:
        result = push_bridge_json(bridge_data)
        print(f"[BRIDGE PUSH] {result}")
    else:
        print("[BRIDGE PUSH] Skipped (pass --push to push to live site)")


if __name__ == '__main__':
    args = sys.argv[1:]
    do_push = '--push' in args
    args = [a for a in args if a != '--push']

    if args:
        log_path = args[0]
    else:
        logs = sorted(f for f in os.listdir(DAEMON_DIR) if f.endswith('.txt'))
        if not logs:
            print("No daemon logs found.")
            sys.exit(1)
        log_path = os.path.join(DAEMON_DIR, logs[-1])
        print(f"(No file specified — using latest: {logs[-1]})")
        print()

    main(log_path, do_push=do_push)
