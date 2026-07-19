"""Shared Gen3 bridge JSON construction + live-site push.

Extracted from oura_gen3_morning_pull.py so oura_gen3_ble_daemon.py can push
periodic updates without duplicating the vectors-dict shape or the KV write
path a second time -- that format has to stay in sync with api/gen3-bridge.js
and web/src/App.js, and drift between two independent copies is exactly the
kind of bug this project has already had to debug once (the KV wire-format
work, 2026-07-12).
"""
import json
import os
import urllib.request
import urllib.error
from datetime import datetime

# How stale the existing bridge is allowed to be before we stop backfilling
# from it -- keeps a broken pipeline from silently repeating an old value
# under a fresh timestamp forever. Matches the existing SLEEP/ACTIVE
# downgrade guard's threshold in oura_gen3_morning_pull.py.
MERGE_MAX_AGE_HOURS = 18


def build_bridge_data(pull_class, pull_file, priority_event_count,
                       hr_avgs=None, ibi_hr_bpm=None, temps=None,
                       spo2_avgs=None, fuel_gauge_pct=None,
                       step_count=None, cadence_spm=None,
                       deep_sleep_pct=None, hrv_ms=None,
                       sleep_duration_hrs=None, sleep_stages=None):
    """Build the bridge JSON dict in the exact shape api/gen3-bridge.js
    and App.js expect. All vector args are optional accumulator lists
    (averaged here) or precomputed scalars -- caller decides what it has.

    sleep_stages: dict from 0x4C decode, shape:
      { wake_min, light_min, rem_min, deep_min, source_tag }
    Populated only when the 0x76/0x5A cluster fires. None otherwise.
    """
    return {
        "source": "gen3_ble",
        "timestamp": datetime.now().isoformat(),
        "pull_file": pull_file,
        "classifier": pull_class,
        "vectors": {
            "hrv_ms": hrv_ms,
            "rhr_bpm": round(sum(hr_avgs) / len(hr_avgs), 1) if hr_avgs else None,
            "ibi_hr_bpm": ibi_hr_bpm,
            "sleep_duration_hrs": sleep_duration_hrs,
            "deep_sleep_pct": deep_sleep_pct,
            "sleep_stages": sleep_stages,
            "sleep_temp_c": round(sum(temps) / len(temps), 2) if temps else None,
            "spo2_avg_pct": round(sum(spo2_avgs) / len(spo2_avgs), 1) if spo2_avgs else None,
            "battery_pct": fuel_gauge_pct,
            "step_count": step_count,
            "cadence_spm": cadence_spm,
        },
        "raw_sample_count": priority_event_count,
    }


def merge_with_existing_bridge(bridge_data, repo_root):
    """Backfill null vector fields from the existing local bridge file.

    A fresh pull that only sees a narrow buffer window (e.g. the automatic
    post-daemon morning pull catching ~42 minutes while the daemon's own
    multi-hour session already found real sleep_duration_hrs/sleep_stages)
    must not blank out fields it simply didn't see data for this round.
    Only backfills a field that is None in the new push -- a field the
    fresh pull actually has data for always wins. Bounded by
    MERGE_MAX_AGE_HOURS so this can't repeat a stale value indefinitely.
    """
    existing_path = os.path.join(repo_root, "pipeline", "data", "bridge", "gen3_latest.json")
    if not os.path.exists(existing_path):
        return bridge_data
    try:
        with open(existing_path) as f:
            existing = json.load(f)
        existing_ts = datetime.fromisoformat(existing["timestamp"])
        age_h = (datetime.now() - existing_ts).total_seconds() / 3600
        if age_h > MERGE_MAX_AGE_HOURS:
            return bridge_data
        existing_vectors = existing.get("vectors", {})
    except Exception:
        return bridge_data

    for key, value in bridge_data["vectors"].items():
        if value is None and existing_vectors.get(key) is not None:
            bridge_data["vectors"][key] = existing_vectors[key]
    return bridge_data


def write_local_bridge_file(bridge_data, repo_root):
    bridge_dir = os.path.join(repo_root, "pipeline", "data", "bridge")
    os.makedirs(bridge_dir, exist_ok=True)
    bridge_path = os.path.join(bridge_dir, "gen3_latest.json")
    with open(bridge_path, "w") as f:
        json.dump(bridge_data, f, indent=2)
    return bridge_path


def push_bridge_json(bridge_data, timeout=10):
    """Best-effort POST to the live site. Never raises -- returns a status
    string for the caller to print/log. Mirrors the exact behavior already
    verified working in oura_gen3_morning_pull.py on 2026-07-12.
    """
    write_secret = os.environ.get("GEN3_BRIDGE_WRITE_SECRET")
    if not write_secret:
        return "Skipped — GEN3_BRIDGE_WRITE_SECRET not set in this environment."
    try:
        req = urllib.request.Request(
            "https://www.methuselah.ca/api/gen3-bridge",
            data=json.dumps(bridge_data).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Write-Secret": write_secret},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return f"{resp.status} → live site updated."
    except urllib.error.HTTPError as e:
        return f"FAILED — HTTP {e.code}: {e.read().decode(errors='replace')}"
    except Exception as e:
        return f"FAILED — {e}"
