#!/usr/bin/env python3
"""
One-time merge script: fills n/a Gen4 fields in the comparison CSV
using the Oura export CSV as the authoritative source.
Never overwrites a field that already has a real value.
"""
import csv

OURA_CSV = "/Users/brydenvaniderstine/Desktop/oura_2025-06-01_2026-08-01_trends.csv"
COMP_CSV = "pipeline/data/findings/gen3_vs_gen4_comparison.csv"


def secs_to_hm(secs):
    try:
        s = int(float(secs))
        return f"{s // 3600}h {(s % 3600) // 60}min"
    except Exception:
        return "n/a"


def secs_to_min(secs):
    try:
        return str(int(float(secs)) // 60)
    except Exception:
        return "n/a"


def pct(part, total):
    try:
        return str(round(int(float(part)) / int(float(total)) * 100))
    except Exception:
        return "n/a"


# Load Oura export — keyed by date string YYYY-MM-DD
oura = {}
with open(OURA_CSV, newline="") as f:
    for row in csv.DictReader(f):
        oura[row["date"]] = row

# Load comparison CSV
with open(COMP_CSV, newline="") as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    rows = list(reader)

# Add gen4_hrv_avg column if missing
if "gen4_hrv_avg" not in fieldnames:
    idx = fieldnames.index("gen4_awake_min") + 1
    fieldnames.insert(idx, "gen4_hrv_avg")
    for row in rows:
        row["gen4_hrv_avg"] = "n/a"

filled = 0
rows_updated = 0

for row in rows:
    raw_date = row["date"].strip()

    # Derive the Oura wake date (always the later calendar date)
    # Handles: "2026-06-28/29", "2026-07-01 (evening)", "2026-07-03 evening", "2026-07-01/02"
    if "/" in raw_date:
        # e.g. "2026-06-28/29" -> "2026-06-29" or "2026-07-01/02" -> "2026-07-02"
        base, tail = raw_date.split("/", 1)
        day = tail.split()[0].zfill(2)
        oura_date = base[:8] + day  # "YYYY-MM-" + DD
    else:
        oura_date = raw_date.split()[0]

    if oura_date not in oura:
        print(f"  No Oura data for date: {oura_date} (from '{raw_date}')")
        continue

    o = oura[oura_date]
    total_sleep = o.get("Total Sleep Duration", "")
    updated = False

    def fill(field, value):
        global filled, updated
        if row.get(field, "n/a").strip() in ("n/a", "", "N/A"):
            row[field] = value
            filled += 1
            updated = True

    fill("gen4_hr_lowest",        o.get("Lowest Resting Heart Rate", "n/a"))
    fill("gen4_hr_avg",           o.get("Average Resting Heart Rate", "n/a"))
    fill("gen4_total_sleep",      secs_to_hm(total_sleep))
    fill("gen4_sleep_efficiency", o.get("Sleep Efficiency", "n/a"))
    fill("gen4_rem_pct",          pct(o.get("REM Sleep Duration", ""), total_sleep))
    fill("gen4_light_pct",        pct(o.get("Light Sleep Duration", ""), total_sleep))
    fill("gen4_deep_pct",         pct(o.get("Deep Sleep Duration", ""), total_sleep))
    fill("gen4_awake_min",        secs_to_min(o.get("Awake Time", "")))
    fill("gen4_hrv_avg",          o.get("Average HRV", "n/a"))
    fill("gen4_respiratory_rate", o.get("Respiratory Rate", "n/a"))

    if updated:
        rows_updated += 1

# Write updated CSV
with open(COMP_CSV, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\nDone. {rows_updated} rows updated, {filled} fields filled.")
if "gen4_hrv_avg" in fieldnames:
    print("gen4_hrv_avg column added.")
