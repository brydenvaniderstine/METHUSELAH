#!/usr/bin/env python3
import asyncio, struct, time, sys, re
from pathlib import Path
from bleak import BleakClient
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..'))
from gen3_ble_connection import scan_for_ring
from decoders import (
    decode_sleep_period_info_2,
    decode_hrv_event,
    decode_sleep_phase_data,
    summarize_sleep_phase_data,
    decode_debug_data_sleep_statistics,
    decode_debug_data_battery_level,
    decode_debug_data_fuel_gauge,
    decode_spo2_event,
    decode_sleep_temp_event,
    decode_motion_event,
    decode_sleep_summary_1,
    decode_sleep_summary_2,
    decode_sleep_summary_3,
    decode_sleep_summary_4,
    decode_bedtime_period,
    decode_spo2_ibi_amplitude,
    decode_spo2_dc_event,
    decode_motion_period,
    decode_real_step_feature_1,
    decode_real_step_feature_2,
    decode_debug_data_alt_text,
    decode_debug_data_flash_usage,
    decode_debug_data_period_info,
    decode_debug_data_ble_usage,
    decode_debug_data_finger_detection,
    decode_debug_data_afe_statistics,
    decode_debug_data_acm_configuration,
    decode_debug_data_ppg_settings,
    decode_wear_event,
    calculate_rmssd,
)

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

PRIORITY_TAGS = {0x44, 0x47, 0x49, 0x4B, 0x4C, 0x4E, 0x4F, 0x53, 0x55, 0x58, 0x5A, 0x5D, 0x60, 0x69, 0x6A, 0x6B, 0x6E, 0x6F, 0x71, 0x72, 0x75, 0x76, 0x77, 0x7E, 0x7F}

# 0x6A/0x5D/0x6F/0x75 are continuous background-sensor tags -- they fire
# whenever the ring has skin contact, not only during sleep (confirmed
# 2026-07-21: an afternoon dishes episode where the ring sat motionless on a
# counter between wears produced an identical SLEEP_TAGS/motion signature to
# a real overnight sleep pull -- see known_issues.md). Real 0x53 (wear event)
# data shows NOT_IN_FINGER/FINGER_USER_ACTIVE alternate 33-44x per night even
# during confirmed sleep, so that pair can't gate SLEEP WINDOW without
# misclassifying real sleep too. The one unambiguous real signal is
# CHARGING_PHASE (state 8): the ring cannot be worn while charging. Combined
# with a wide local-hour plausibility band (grounded in the actual daemon
# schedule: 22:00 start, ~06:00 end, plus safety-net morning pulls through
# ~08:30) as the practical defense against daytime stillness being read as
# sleep by a single short manual pull, where 0x53 essentially never survives
# the ring's flash-buffer eviction (0/29 real historical morning pulls ever
# captured one).
PLAUSIBLE_SLEEP_HOURS = set(range(20, 24)) | set(range(0, 9))  # 20:00-08:59 local

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
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Scanning for ring...")
    found = await scan_for_ring(timeout_seconds=120)
    if not found:
        print("Ring not found in scan window — is it nearby and charged?")
        return
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ring detected — connecting...")
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

        # --- PULL CLASSIFIER ---
        SLEEP_TAGS = {0x6A, 0x5D, 0x6F, 0x75}
        ACTIVITY_TAGS = {0x7E, 0x7F}
        tag_set = set(p["tag"] for p in parsed)
        tag_counts_all = Counter(p["tag"] for p in parsed)
        has_sleep = bool(tag_set & SLEEP_TAGS)
        has_activity = bool((tag_set & ACTIVITY_TAGS) or tag_counts_all.get(0x47, 0) >= 3)
        charging_seen = False
        for p in parsed:
            if p["tag"] == 0x53:
                try:
                    if decode_wear_event(p["payload"])["state"] == 8:  # STATE_CHARGING_PHASE
                        charging_seen = True
                except ValueError:
                    pass
        local_hour = time.localtime().tm_hour
        if has_sleep and has_activity:
            pull_class, pull_note = "MIXED WINDOW", "sleep and activity tags both present"
        elif has_sleep and charging_seen:
            pull_class, pull_note = "UNCLEAR", "sleep tags present but ring reported charging (0x53 state 8)"
        elif has_sleep and local_hour not in PLAUSIBLE_SLEEP_HOURS:
            pull_class, pull_note = "UNCLEAR", f"sleep tags present but pull hour ({local_hour}:00) is outside plausible sleep hours"
        elif has_sleep:
            pull_class, pull_note = "SLEEP WINDOW", "sleep tags present"
        elif has_activity:
            pull_class, pull_note = "ACTIVE WINDOW", "no sleep tags present"
        else:
            pull_class, pull_note = "UNCLEAR", "neither sleep nor activity tags"
        print(f"\n=== PULL CLASSIFICATION: {pull_class} ({pull_note}) ===")

        pull_dir = Path(__file__).parent.parent / "data" / "raw_pulls" / "gen3_morning"
        prior_files = sorted(pull_dir.glob("gen3_pull_*.txt"))
        if prior_files:
            last_file = prior_files[-1]
            last_boot_ts = None
            with open(last_file) as _fh:
                for _line in _fh:
                    _m = re.search(r"boot_ts=(\d+)", _line)
                    if _m:
                        last_boot_ts = int(_m.group(1))
            if last_boot_ts is not None:
                gap = min(boot_tss) - last_boot_ts
                if gap > 1800:
                    print(f"  WARNING: boot_ts gap from {last_file.name} is {gap:,} ticks "
                          f"(~{gap/60:.0f} min) — possible buffer rollover")

        print(f"\n=== SLEEP STATE DECODE (0x6a) ===")
        sleep_states = []
        hr_avgs = []  # bridge accumulator
        for p in parsed:
            if p["tag"] == 0x6A:
                try:
                    decoded = decode_sleep_period_info_2(p["payload"])
                    sleep_states.append(decoded["sleep_state"])
                    hr_avgs.append(decoded["average_hr"])
                    print(f"  boot_ts={p['boot_ts']:>10}  state={decoded['sleep_state']}  "
                          f"hr={decoded['average_hr']:.1f}  breath={decoded['breath']:.1f}  "
                          f"motion={decoded['motion_count']}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if sleep_states:
            sc = Counter(sleep_states)
            total = len(sleep_states)
            print(f"\nSleep state distribution ({total} samples):")
            for state in (0, 1, 2):
                pct = 100 * sc.get(state, 0) / total
                print(f"  state {state}: {pct:.1f}%  ({sc.get(state, 0)} samples)")
        else:
            print("  No 0x6a sleep period events found in this pull.")

        print(f"\n=== HRV DECODE (0x5d) - verified RMSSD per 5-min window ===")
        hrv_found = False
        for p in parsed:
            if p["tag"] == 0x5D:
                hrv_found = True
                try:
                    decoded = decode_hrv_event(p["payload"])
                    print(f"  boot_ts={p['boot_ts']:>10}  payload={p['payload'].hex()}")
                    for i, sample in enumerate(decoded["samples_5min"]):
                        print(f"    window -{(len(decoded['samples_5min'])-1-i)*5}min: "
                              f"hr={sample['hr_bpm']} bpm  rmssd={sample['rmssd_ms']} ms")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if not hrv_found:
            print("  No 0x5d HRV events found in this pull.")

        print(f"\n=== SPO2 DECODE (0x6f) ===")
        spo2_found = False
        spo2_avgs = []  # bridge accumulator
        for p in parsed:
            if p["tag"] == 0x6F:
                spo2_found = True
                try:
                    d = decode_spo2_event(p["payload"])
                    avg = sum(d["spo2_percent"])/len(d["spo2_percent"]) if d["spo2_percent"] else 0
                    spo2_avgs.append(avg)
                    print(f"  boot_ts={p['boot_ts']:>10}  samples={d['spo2_percent']}  avg={avg:.1f}%")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if not spo2_found:
            print("  No 0x6f SpO2 events found in this pull.")

        print(f"\n=== SLEEP TEMP DECODE (0x75) ===")
        temp_found = False
        temps = []  # bridge accumulator
        for p in parsed:
            if p["tag"] == 0x75:
                temp_found = True
                try:
                    d = decode_sleep_temp_event(p["payload"])
                    temps.extend(d["temps_c"])
                    print(f"  boot_ts={p['boot_ts']:>10}  temps_c={d['temps_c']}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if not temp_found:
            print("  No 0x75 sleep temp events found in this pull.")

        print(f"\n=== MOTION DECODE (0x47) ===")
        motion_found = False
        for p in parsed:
            if p["tag"] == 0x47:
                motion_found = True
                try:
                    d = decode_motion_event(p["payload"])
                    print(f"  boot_ts={p['boot_ts']:>10}  acm_x={d['acm_x']}  acm_y={d['acm_y']}  acm_z={d['acm_z']}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if not motion_found:
            print("  No 0x47 motion events found in this pull.")

        print(f"\n=== MOTION PERIOD DECODE (0x6B) — per-window step count ===")
        motion_period_found = False
        total_steps = 0           # bridge accumulator
        cadence_samples = []      # bridge accumulator
        for p in parsed:
            if p["tag"] == 0x6B:
                motion_period_found = True
                try:
                    d = decode_motion_period(p["payload"])
                    total_steps += d["step_count"]
                    if d["cadence_spm"] and d["cadence_spm"] > 0:
                        cadence_samples.append(d["cadence_spm"])
                    overflow = f"  OVERFLOW b4={d['b4_overflow_flag']}" if d.get("b4_overflow_flag") else ""
                    print(f"  boot_ts={p['boot_ts']:>10}  steps={d['step_count']}  cadence={d['cadence_spm']} spm"
                          f"  b2={d['b2_unknown']}  b3={d['b3_unknown']}{overflow}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if motion_period_found:
            print(f"  TOTAL STEPS THIS WINDOW: {total_steps}")
        else:
            print("  No 0x6B motion period events found in this pull.")
        step_count_bridge = total_steps if motion_period_found else None
        cadence_spm_bridge = round(sum(cadence_samples) / len(cadence_samples), 1) if cadence_samples else None

        print(f"\n=== BEDTIME PERIOD DECODE (0x76) ===")
        bedtime_found = False
        for p in parsed:
            if p["tag"] == 0x76:
                bedtime_found = True
                try:
                    d = decode_bedtime_period(p["payload"])
                    print(f"  boot_ts={p['boot_ts']:>10}  start_rt={d['start_ring_time']}  end_rt={d['end_ring_time']}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if not bedtime_found:
            print("  No 0x76 bedtime period events found in this pull.")

        print(f"\n=== SLEEP SUMMARY DECODE (0x49 / 0x4C / 0x4F / 0x58) ===")
        print("  Fire alongside 0x76/0x5A only when a completed sleep session is in the buffer.")
        ss_tags = {0x49: decode_sleep_summary_1, 0x4C: decode_sleep_summary_2,
                   0x4F: decode_sleep_summary_3, 0x58: decode_sleep_summary_4}
        ss_found = False
        sleep_stages_bridge = None   # populated from 0x4C when cluster fires
        sleep_duration_bridge = None  # computed from 0x4C non-wake epochs × 30s ÷ 3600
        for p in parsed:
            if p["tag"] in ss_tags:
                ss_found = True
                tag_hex = f"0x{p['tag']:02X}"
                try:
                    d = ss_tags[p["tag"]](p["payload"])
                    if p["tag"] == 0x49:
                        print(f"  [{tag_hex}] boot_ts={p['boot_ts']:>10}  "
                              f"score_candidate={d['score_candidate']}  "
                              f"b1={d['b1']} b2={d['b2']} b3={d['b3']}")
                    elif p["tag"] == 0x4C:
                        durs = d["stage_durations_min"]
                        # Total sleep = non-wake epochs × 30s ÷ 3600.
                        # stage0=WAKE excluded; stage1/2/3 are sleep stages.
                        # Epoch duration confirmed 30s (matches 0x5A, cross-validated 2026-07-12).
                        _sleep_epochs = d["stage1_epochs"] + d["stage2_epochs"] + d["stage3_epochs"]
                        sleep_duration_bridge = round(_sleep_epochs * 30 / 3600, 2)
                        print(f"  [{tag_hex}] boot_ts={p['boot_ts']:>10}  "
                              f"STAGE COUNTS: "
                              f"s0(WAKE?)={d['stage0_epochs']}ep/{durs[0]}min  "
                              f"s1(LIGHT)={d['stage1_epochs']}ep/{durs[1]}min  "
                              f"s2(REM?)={d['stage2_epochs']}ep/{durs[2]}min  "
                              f"s3(DEEP?)={d['stage3_epochs']}ep/{durs[3]}min  "
                              f"u16_4={d['u16_4']} u16_5={d['u16_5']} u16_6={d['u16_6']}  "
                              f"→ sleep_duration={sleep_duration_bridge}h")
                        sleep_stages_bridge = {
                            "wake_min":  durs[0],
                            "light_min": durs[1],
                            "rem_min":   durs[2],
                            "deep_min":  durs[3],
                            "source_tag": "0x4C",
                        }
                    elif p["tag"] == 0x4F:
                        print(f"  [{tag_hex}] boot_ts={p['boot_ts']:>10}  "
                              f"u16=[{d['u16_0']},{d['u16_1']},{d['u16_2']},{d['u16_3']},{d['u16_4']}]  "
                              f"b10={d['b10']}  (field meanings UNKNOWN n=1)")
                    elif p["tag"] == 0x58:
                        print(f"  [{tag_hex}] boot_ts={p['boot_ts']:>10}  "
                              f"scores(field order UNCONFIRMED)={d['scores_u8']}")
                except ValueError as e:
                    print(f"  [{tag_hex}] boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if not ss_found:
            print("  No sleep summary events found in this pull.")

        print(f"\n=== SLEEP PHASE DATA DECODE (0x5A) — 2-bit per epoch, stage 1=LIGHT confirmed ===")
        phase_packets = {}
        for p in parsed:
            if p["tag"] == 0x5A:
                raw_p = p["payload"]
                if len(raw_p) == 14:
                    idx = raw_p[0]
                    phase_packets[idx] = bytes(raw_p[1:])
                else:
                    print(f"  boot_ts={p['boot_ts']:>10}  UNEXPECTED LENGTH {len(raw_p)}")
        if phase_packets:
            try:
                result = decode_sleep_phase_data(phase_packets)
                print(f"  {summarize_sleep_phase_data(result)}")
                counts = result["stage_counts"]
                labels = result["stage_labels"]
                durs = result["stage_durations_min"]
                for s in sorted(counts):
                    print(f"    stage {s} [{labels[s]:8s}]: {counts[s]:4d} epochs "
                          f"= {durs.get(s,0):5.1f} min")
                if result["no_data_epochs"]:
                    print(f"    NO DATA (0xFF):     {result['no_data_epochs']:4d} epochs (empty buffer slots)")
                if not result["complete"]:
                    print(f"  WARNING: partial capture — missing chunks {result['missing_chunks']}")
            except Exception as e:
                print(f"  DECODE FAIL: {e}")
        else:
            print("  No 0x5A sleep phase data packets found in this pull.")
            print("  (0x5A only fires when a completed sleep session is in the buffer — rare)")

        print(f"\n=== REAL STEP FEATURE DECODE (0x7E/0x7F) — FFT spectral features, NOT step counters ===")
        print("  Only b[9] (0x7E) / b[10] (0x7F) have a confirmed interpretation (walk vs. other-")
        print("  activity, not pace-sensitive — see pipeline/decoders/0x7e.py, 0x7f.py). Step count")
        print("  is 0x6B b[0], printed above.")
        step_feature_found = False
        for p in parsed:
            if p["tag"] == 0x7E:
                step_feature_found = True
                try:
                    d = decode_real_step_feature_1(p["payload"])
                    print(f"  boot_ts={p['boot_ts']:>10}  [0x7E] b9(walk-responsive)={d['b9']:>3}  "
                          f"all_bytes={[d[f'b{i}'] for i in range(14)]}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  [0x7E]  DECODE FAIL: {e}")
            elif p["tag"] == 0x7F:
                step_feature_found = True
                try:
                    d = decode_real_step_feature_2(p["payload"])
                    print(f"  boot_ts={p['boot_ts']:>10}  [0x7F] b10(walk-responsive)={d['b10']:>3}  "
                          f"all_bytes={[d[f'b{i}'] for i in range(14)]}")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  [0x7F]  DECODE FAIL: {e}")
        if not step_feature_found:
            print("  No 0x7E/0x7F real step feature events found in this pull.")

        print(f"\n=== SPO2 IBI+AMPLITUDE DECODE (0x6E) ===")
        ibi6e_found = False
        ibi6e_all = []
        ibi_packets = []  # list of per-packet IBI lists, for HRV RMSSD (needs packet boundaries preserved)
        for p in parsed:
            if p["tag"] == 0x6E:
                ibi6e_found = True
                try:
                    d = decode_spo2_ibi_amplitude(p["payload"])
                    ibi6e_all.extend(v for v in d["ibi_ms"] if 300 <= v <= 2000)
                    ibi_packets.append(d["ibi_ms"])
                    hr_str = " ".join(f"{v:.0f}" for v in d["hr_bpm"] if v is not None)
                    print(f"  boot_ts={p['boot_ts']:>10}  ch={d['channel']}  "
                          f"ibi_ms={d['ibi_ms']}  hr=[{hr_str}]bpm")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        ibi6e_hr_mean = None
        if ibi6e_all:
            import statistics as _stats
            ibi6e_hr_mean = round(60000 / _stats.mean(ibi6e_all), 1)
            print(f"  → {len(ibi6e_all)} valid IBI samples  HR mean={ibi6e_hr_mean:.1f}bpm")
        hrv_rmssd_ms = calculate_rmssd(ibi_packets)
        if hrv_rmssd_ms is not None:
            print(f"  → HRV (RMSSD from IBI, Gen3 fallback): {hrv_rmssd_ms}ms "
                  f"(approximation -- see pipeline/decoders/hrv_rmssd.py for validated error margin)")
        if not ibi6e_found:
            print("  No 0x6E SPO2 IBI+amplitude events found in this pull.")

        print(f"\n=== SPO2 DC EVENT DECODE (0x77) [PARTIAL — DC samples confirmed, field sub-structure uncertain] ===")
        dc77_found = False
        dc77_sentinels = 0
        dc77_real = 0
        for p in parsed:
            if p["tag"] == 0x77:
                dc77_found = True
                try:
                    d = decode_spo2_dc_event(p["payload"])
                    if d["is_sentinel"]:
                        dc77_sentinels += 1
                    else:
                        dc77_real += 1
                        samp_str = " ".join(str(v) for v in d["dc_samples"][:5])
                        print(f"  boot_ts={p['boot_ts']:>10}  ch={d['channel']}({d['beat_counter']:3d})"
                              f"  n={d['n_samples']:2d}  samples=[{samp_str}{'...' if d['n_samples']>5 else ''}]")
                except ValueError as e:
                    print(f"  boot_ts={p['boot_ts']:>10}  DECODE FAIL: {e}")
        if dc77_found:
            print(f"  → {dc77_real} real packets  {dc77_sentinels} sentinels")
        else:
            print("  No 0x77 SPO2 DC events found in this pull.")

        # pfsm_state labels derived from corpus context segregation analysis (2026-07-06)
        # pfsm=6 → sleep-only; pfsm=3/4 → activity-only; pfsm=5 → both; pfsm=128 → echo
        # NOT firmware-confirmed — behaviorally derived.
        PFSM_LABELS = {
            0: "AWAKE", 1: "ASLEEP",
            3: "ACTIVE_REGIME", 4: "ACTIVE_REGIME",
            5: "TRANSITIONAL", 6: "SLEEP_REGIME", 128: "ECHO_RECORD",
        }

        print(f"\n=== DEBUG DATA DECODE (0x61) - sleep stats / battery / flash / BLE / ACM / AFE / PPG chip / finger detect / debug text ===")
        debug_found = False
        fuel_gauge_pct = None  # bridge accumulator
        for p in parsed:
            if p["tag"] == 0x61 and len(p["payload"]) > 0:
                sub = p["payload"][0]
                if sub == 0x09:
                    debug_found = True
                    try:
                        d = decode_debug_data_sleep_statistics(p["payload"])
                        secs = d["seconds_in_pfsm_state"]
                        pfsm = d["pfsm_state"]
                        pfsm_label = PFSM_LABELS.get(pfsm, "UNKNOWN")
                        print(f"  boot_ts={p['boot_ts']:>10}  [SLEEP STATS] "
                              f"pfsm_state={pfsm} [{pfsm_label}]  "
                              f"seconds_in_pfsm_state={secs}  ({secs/60:.2f}min)")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  SLEEP STATS DECODE FAIL: {e}")
                elif sub == 0x24:
                    debug_found = True
                    try:
                        d = decode_debug_data_battery_level(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [BATTERY] "
                              f"{d['battery_percentage']}%  {d['battery_voltage_mv']}mV  reason={d['reason']}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  BATTERY DECODE FAIL: {e}")
                elif sub == 0x14:
                    debug_found = True
                    try:
                        d = decode_debug_data_fuel_gauge(p["payload"])
                        fuel_gauge_pct = round(d["battery_percentage"], 1)
                        print(f"  boot_ts={p['boot_ts']:>10}  [FUEL GAUGE] "
                              f"{d['battery_percentage']:.1f}%  {d['average_battery_voltage_mv']}mV  "
                              f"remaining_capacity={d['remaining_capacity']}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  FUEL GAUGE DECODE FAIL: {e}")
                elif sub == 0x04:
                    debug_found = True
                    try:
                        d = decode_debug_data_alt_text(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [DEBUG TEXT] \"{d['text']}\"")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  DEBUG TEXT DECODE FAIL: {e}")
                elif sub == 0x0A:
                    debug_found = True
                    try:
                        d = decode_debug_data_flash_usage(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [FLASH USAGE] "
                              f"read={d['ticks_reading_flash']}  write={d['ticks_writing_flash']}  "
                              f"erase={d['ticks_erasing_flash']}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  FLASH USAGE DECODE FAIL: {e}")
                elif sub == 0x0C:
                    debug_found = True
                    try:
                        d = decode_debug_data_period_info(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [PERIOD INFO] "
                              f"ticks_measuring={d['ticks_measuring_last_period']}  "
                              f"systime_s={d['systime_spent_in_last_state_s']:.1f}  "
                              f"pfsm_state={d['pfsm_state']}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  PERIOD INFO DECODE FAIL: {e}")
                elif sub == 0x0D:
                    debug_found = True
                    try:
                        d = decode_debug_data_ble_usage(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [BLE USAGE] "
                              f"fast={d['ticks_fast_mode']}  slow={d['ticks_slow_mode']}  "
                              f"advertising={d['ticks_advertising_mode']}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  BLE USAGE DECODE FAIL: {e}")
                elif sub == 0x15:
                    debug_found = True
                    try:
                        d = decode_debug_data_finger_detection(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [FINGER DETECTION] "
                              f"bytes={d['bytes']}  (fires every ~36000 ticks; "
                              f"byte[3]/[7] are slow state counters, rest unresolved)")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  FINGER DETECTION DECODE FAIL: {e}")
                elif sub == 0x28:
                    debug_found = True
                    try:
                        d = decode_debug_data_afe_statistics(p["payload"])
                        drift_note = f"  DRIFT_FLAG={d['drift_flag']}" if d['drift_flag'] else ""
                        print(f"  boot_ts={p['boot_ts']:>10}  [AFE STATS] "
                              f"kind={d['record_kind']}  fields={d['fields']}  "
                              f"all_zero={d['all_stats_zero']}{drift_note}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  AFE STATS DECODE FAIL: {e}")
                elif sub == 0x29:
                    debug_found = True
                    try:
                        d = decode_debug_data_acm_configuration(p["payload"])
                        print(f"  boot_ts={p['boot_ts']:>10}  [ACM CONFIG] "
                              f"mode={d['accelerometer_mode']}  acc_odr={d['accelerometer_odr']}  "
                              f"acc_range={d['accelerometer_range']}  gyro_odr={d['gyroscope_odr']}  "
                              f"gyro_range={d['gyroscope_range']}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  ACM CONFIG DECODE FAIL: {e}")
                elif sub == 0x33:
                    debug_found = True
                    try:
                        d = decode_debug_data_ppg_settings(p["payload"])
                        ch_note = f"  ch_a={d['channel_a']}  ch_b={d['channel_b']}" if not d['truncated'] else ""
                        print(f"  boot_ts={p['boot_ts']:>10}  [PPG SETTINGS] "
                              f"chip={d['chip_variant_name']}  truncated={d['truncated']}{ch_note}")
                    except ValueError as e:
                        print(f"  boot_ts={p['boot_ts']:>10}  PPG SETTINGS DECODE FAIL: {e}")
        if not debug_found:
            print("  No sleep-stats/battery debug records found in this pull.")

        outpath = f"gen3_pull_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(outpath, "w") as f:
            f.write(f"Pull timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for p in parsed:
                f.write(f"[{p['tag_name']}] boot_ts={p['boot_ts']} payload={p['payload'].hex()}\n")
        print(f"\nFull output saved to: {outpath}")

        # ── AUTO-FILE BY CLASSIFIER ────────────────────────────────────────────
        import shutil
        base_dir = _os.path.dirname(_os.path.abspath(__file__))
        repo_root = _os.path.join(base_dir, '..', '..')

        src = outpath  # original timestamped name — always exists on disk
        if pull_class == "SLEEP WINDOW":
            dest_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_morning')
            dest_name = _os.path.basename(outpath)
        elif pull_class == "ACTIVE WINDOW":
            dest_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_evening')
            dest_name = _os.path.basename(outpath)
        elif pull_class == "MIXED WINDOW":
            dest_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_morning')
            dest_name = _os.path.basename(outpath).replace('.txt', '_MIXED.txt')
        else:
            dest_dir = _os.path.join(repo_root, 'pipeline', 'data', 'raw_pulls', 'gen3_morning')
            dest_name = _os.path.basename(outpath).replace('.txt', '_UNCLEAR.txt')

        _os.makedirs(dest_dir, exist_ok=True)
        dest_path = _os.path.join(dest_dir, dest_name)
        shutil.move(src, dest_path)
        print(f"[AUTO-FILE] {pull_class} → {dest_path}")

        # ── BRIDGE WRITER — feeds Gen3 data to the web app ───────────────────
        # Shared with oura_gen3_ble_daemon.py via gen3_bridge.py so the
        # vectors-dict shape can't drift out of sync between the two tools.
        from gen3_bridge import build_bridge_data, merge_with_existing_bridge, write_local_bridge_file, push_bridge_json
        import json as _json
        from datetime import datetime as _dt, timezone as _tz

        # Guard: never downgrade the bridge from SLEEP WINDOW to ACTIVE WINDOW.
        # The daemon pushes SLEEP WINDOW with good HRV + sleep duration data; a
        # safety-net morning pull that catches the ring in ACTIVE state must not
        # erase that. If the existing bridge is SLEEP WINDOW and was pushed within
        # the last 18 hours, skip the push for ACTIVE WINDOW pulls.
        _should_push = True
        _existing_bridge_path = _os.path.join(repo_root, "pipeline", "data", "bridge", "gen3_latest.json")
        if pull_class == "ACTIVE WINDOW" and _os.path.exists(_existing_bridge_path):
            try:
                with open(_existing_bridge_path) as _bf:
                    _existing = _json.load(_bf)
                _existing_class = _existing.get("classifier", "")
                _existing_ts_str = _existing.get("timestamp", "")
                if _existing_class == "SLEEP WINDOW" and _existing_ts_str:
                    _existing_age_h = (_dt.now() - _dt.fromisoformat(_existing_ts_str)).total_seconds() / 3600
                    if _existing_age_h < 18:
                        print(f"[BRIDGE] Skipping push — existing SLEEP WINDOW bridge is only "
                              f"{_existing_age_h:.1f}h old; not downgrading to ACTIVE WINDOW.")
                        _should_push = False
            except Exception as _e:
                print(f"[BRIDGE] Could not read existing bridge for downgrade check: {_e}")

        bridge_data = build_bridge_data(
            pull_class=pull_class,
            pull_file=_os.path.basename(dest_path),
            priority_event_count=len(priority_events),
            hr_avgs=hr_avgs,
            ibi_hr_bpm=ibi6e_hr_mean,
            temps=temps,
            spo2_avgs=spo2_avgs,
            fuel_gauge_pct=fuel_gauge_pct,
            step_count=step_count_bridge,
            cadence_spm=cadence_spm_bridge,
            hrv_ms=hrv_rmssd_ms,
            sleep_duration_hrs=sleep_duration_bridge,
            sleep_stages=sleep_stages_bridge,
        )

        # Backfill any field this narrow pull found no data for (e.g. no 0x4C
        # in a ~42min post-daemon buffer) from the existing bridge, rather
        # than nulling out a value the daemon's own multi-hour session already
        # found. This covers SLEEP WINDOW-classified narrow pulls, which the
        # ACTIVE WINDOW downgrade guard above does not.
        bridge_data = merge_with_existing_bridge(bridge_data, repo_root)

        if _should_push:
            bridge_path = write_local_bridge_file(bridge_data, repo_root)
            print(f"[BRIDGE] Written → {bridge_path}")

            # ── PUSH TO LIVE SITE — the local file above never reaches production ──
            # (pipeline/data/bridge/ is gitignored for data sovereignty; Vercel only
            # builds from git). This is what actually feeds methuselah.ca now — see
            # api/gen3-bridge.js. Best-effort: never fail the pull over a push error.
            print(f"[BRIDGE PUSH] {push_bridge_json(bridge_data)}")
        else:
            print(f"[BRIDGE] Local data built but not pushed (downgrade protection active).")

asyncio.run(main())
