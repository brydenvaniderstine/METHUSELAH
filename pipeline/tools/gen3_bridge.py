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

# Vector fields carrying a biometric reading whose *age* the user reads to make
# a same-day decision (the primary tiles plus the log-line vitals) -- as opposed
# to operational fields (battery/steps/cadence) whose staleness nobody acts on.
# merge_with_existing_bridge() uses this to decide freshness: a narrow pull that
# measured none of these but preserves them from the existing bridge inherits
# that bridge's (older) timestamp, so preserved data can never be displayed as
# freshly measured. See merge_with_existing_bridge().
BIOMETRIC_VECTOR_FIELDS = (
    "hrv_ms", "rhr_bpm", "ibi_hr_bpm", "sleep_duration_hrs",
    "spo2_avg_pct", "sleep_temp_c", "sleep_stages", "deep_sleep_pct",
)


def build_bridge_data(pull_class, pull_file, priority_event_count,
                       hr_avgs=None, ibi_hr_bpm=None, temps=None,
                       spo2_avgs=None, fuel_gauge_pct=None,
                       step_count=None, cadence_spm=None,
                       deep_sleep_pct=None, hrv_ms=None,
                       sleep_duration_hrs=None, sleep_stages=None,
                       sleep_duration_estimate_hrs=None,
                       sleep_duration_estimate_info=None):
    """Build the bridge JSON dict in the exact shape api/gen3-bridge.js
    and App.js expect. All vector args are optional accumulator lists
    (averaged here) or precomputed scalars -- caller decides what it has.

    sleep_stages: dict from 0x4C decode, shape:
      { wake_min, light_min, rem_min, deep_min, source_tag }
    Populated only when the 0x76/0x5A cluster fires. None otherwise.

    sleep_duration_estimate_hrs / sleep_duration_estimate_info: PROVISIONAL
    companion to sleep_duration_hrs, from pipeline/tools/
    sleep_duration_estimate.py (final 0x4C bout + uncovered tail). This is
    NOT a replacement for sleep_duration_hrs, which stays None until this
    estimate is validated across several more real nights -- do not read
    one as backfilling the other. sleep_duration_estimate_info carries the
    decline reason (when the estimate is None) or the confidence/inputs
    behind the number (when it isn't), so it's inspectable rather than a
    black box. Backend/bridge-only for now -- not surfaced on the
    dashboard.
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
            "sleep_duration_estimate_hrs": sleep_duration_estimate_hrs,
            "sleep_duration_estimate_info": sleep_duration_estimate_info,
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
    """Preserve prior real vector values a fresh pull has no data for.

    Never nulls a field: any vector that is None in the new push is backfilled
    from the existing local bridge's non-null value, regardless of how old the
    existing bridge is. Destroying a real prior reading is never acceptable --
    that is the recurring bridge-overwrite failure class (2026-07-19 SLEEP-
    window narrow pull; 2026-07-25 ACTIVE-window pull over a >18h-old bridge) --
    whereas a freshness *downgrade* is fine. So the age bound is no longer a
    hard cut that abandons backfill (which nulled the field); instead, when a
    narrow pull carries no biometric of its own and shows only values preserved
    from the existing bridge, the merged snapshot inherits that bridge's (older)
    timestamp. The preserved reading then renders as stale (App.js isStale,
    STALE_HRS) rather than masquerading as freshly measured -- staleness stays
    visually self-evident, and a stalled pipeline can never republish an old
    value as if it were live. A fresh pull's own value always wins; merge only
    fills the gaps it left.
    """
    existing_path = os.path.join(repo_root, "pipeline", "data", "bridge", "gen3_latest.json")
    if not os.path.exists(existing_path):
        return bridge_data
    try:
        with open(existing_path) as f:
            existing = json.load(f)
        existing_vectors = existing.get("vectors", {})
        existing_ts = existing.get("timestamp")
    except Exception:
        return bridge_data

    new_vectors = bridge_data["vectors"]
    # Did this pull measure any biometric of its own, or will every biometric it
    # shows be inherited from the existing bridge?
    pull_has_fresh_biometric = any(
        new_vectors.get(k) is not None for k in BIOMETRIC_VECTOR_FIELDS
    )

    backfilled_any = False
    for key, value in new_vectors.items():
        if value is None and existing_vectors.get(key) is not None:
            new_vectors[key] = existing_vectors[key]
            backfilled_any = True

    # Freshness honesty: a pull that preserved biometrics but measured none of
    # its own is only as fresh as the bridge it preserved them from. Carry the
    # older timestamp forward so a stale reading can never be displayed as live.
    # (Guarded by min() so a fresh pull is never falsely aged, and tolerant of a
    # malformed/tz-mismatched existing timestamp -- data is preserved either way.)
    if backfilled_any and not pull_has_fresh_biometric and existing_ts:
        try:
            if datetime.fromisoformat(existing_ts) < datetime.fromisoformat(bridge_data["timestamp"]):
                bridge_data["timestamp"] = existing_ts
        except Exception:
            pass
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
