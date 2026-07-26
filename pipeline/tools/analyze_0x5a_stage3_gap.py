#!/usr/bin/env python3
"""METHUSELAH // 0x5A stage-3 gap corpus analysis (PARALLEL ANALYSIS ONLY)

Does not modify pipeline/decoders/0x5a.py or any live pipeline file. Scans
the full raw_pulls corpus (not a hand-picked subset), reuses the real
decode_sleep_phase_data/decode_sleep_summary_2 decoders, and tests one
literature-informed hypothesis about the still-unresolved 0x5A stage-3 gap:

  H: if 0xFF ("NO_DATA sentinel") bytes are actually masking real stage-3
     data at the edges of deep-sleep bouts (consistent with deep sleep being
     the hardest-bounded/most-reclassified stage in the wearable-sleep-staging
     literature — see output/sleep-stage-science-ppg-hrv.md in the agent
     workspace), then 0xFF bytes should disproportionately sit ADJACENT to
     decoded stage-3 runs, not just correlate with total 0xFF count (already
     falsified 2026-07-21 at n=6).

Built 2026-07-24. Findings (see known_issues.md 2026-07-24 entry for full
writeup): corpus contains extensive byte-identical retransmitted duplicate
bouts (dedup by boot_ts handled below — always rerun through this script,
don't hand-count bursts); a real complete-flag bug in 0x5a.py was found and
fixed while building this; stage 0/1/2 exact-match holds 100% at n=31 (2+
chunk bouts) but not for 1-chunk bouts; the adjacency hypothesis above is
NOT supported (weaker correlation than the already-falsified total-count
measure). Stage 3 stays PARTIAL/unresolved.

Run from repo root:
  cd ~/methuselah && python3 pipeline/tools/analyze_0x5a_stage3_gap.py
"""
import glob
import os
import re
import sys

REPO = os.path.expanduser("~/methuselah")
sys.path.insert(0, REPO)

from pipeline.decoders import decode_sleep_phase_data, decode_sleep_summary_2  # noqa: E402

RAW_DIR = os.path.join(REPO, "pipeline", "data", "raw_pulls")
LINE_RE = re.compile(r"\[(?P<tag>[^\]]+)\] boot_ts=(?P<ts>\d+) payload=(?P<payload>[0-9a-f]+)")
BURST_GAP_THRESH = 40   # ticks; observed intra-burst spacing is 1-3, inter-burst gaps are 100s-1000000s
MATCH_THRESH = 300      # max |boot_ts diff| to accept a 0x5A cycle <-> 0x4C record as same cluster firing


def parse_file(path):
    phase_pkts = []    # (ts, idx, 13 bytes)
    summary_pkts = []  # (ts, 14 bytes)
    with open(path, "r", errors="replace") as f:
        for line in f:
            m = LINE_RE.search(line)
            if not m:
                continue
            tag = m.group("tag")
            ts = int(m.group("ts"))
            payload = bytes.fromhex(m.group("payload"))
            if tag == "Sleep phase data" and len(payload) == 14:
                phase_pkts.append((ts, payload[0], payload[1:]))
            elif tag == "Sleep summary (2)" and len(payload) == 14:
                summary_pkts.append((ts, payload))
    return phase_pkts, summary_pkts


def segment_bursts(phase_pkts):
    """Group chunk packets into cluster-firing bursts. New burst starts when
    boot_ts jumps > BURST_GAP_THRESH since the last chunk, or when the next
    idx is already present in the current burst (a new firing restarting at
    0 with no timestamp gap detected). Returns list of (packets_dict, last_ts)."""
    bursts = []
    cur = {}
    cur_last_ts = None
    for ts, idx, data in phase_pkts:
        starts_new = cur and (
            (cur_last_ts is not None and ts - cur_last_ts > BURST_GAP_THRESH)
            or idx in cur
        )
        if starts_new:
            bursts.append((cur, cur_last_ts))
            cur = {}
        cur[idx] = data
        cur_last_ts = ts
    if cur:
        bursts.append((cur, cur_last_ts))
    return bursts


def true_complete(packets):
    """Real completeness check: every index 0..max(idx) present exactly once.
    NOTE: decode()'s own result['complete']/['missing_chunks'] hardcodes
    expected_chunks = set(range(23)) — NOT trustworthy post the 2026-07-21
    variable-length finding. Cross-checked separately below."""
    if not packets:
        return False
    return set(packets.keys()) == set(range(max(packets.keys()) + 1))


def stage3_runs_and_adjacency(epochs):
    """(num_stage3_runs, num_0xFF/None epochs adjacent to a stage-3 run, total_none)"""
    runs = 0
    for i, e in enumerate(epochs):
        if e == 3 and (i == 0 or epochs[i - 1] != 3):
            runs += 1
    adjacent_none = 0
    for i, e in enumerate(epochs):
        if e is None:
            left_is_3 = i > 0 and epochs[i - 1] == 3
            right_is_3 = i < len(epochs) - 1 and epochs[i + 1] == 3
            if left_is_3 or right_is_3:
                adjacent_none += 1
    total_none = sum(1 for e in epochs if e is None)
    return runs, adjacent_none, total_none


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, "**", "*.txt"), recursive=True))
    rows = []
    complete_flag_bug_seen = 0
    total_complete_bursts = 0

    for path in files:
        phase_pkts, summary_pkts = parse_file(path)
        if not phase_pkts or not summary_pkts:
            continue
        for packets, last_ts in segment_bursts(phase_pkts):
            if not true_complete(packets):
                continue
            total_complete_bursts += 1
            result = decode_sleep_phase_data(packets)

            if result["complete"] is not True or result["missing_chunks"] != []:
                complete_flag_bug_seen += 1

            # nearest 0x4C record by boot_ts
            nearest = min(summary_pkts, key=lambda sp: abs(sp[0] - last_ts))
            if abs(nearest[0] - last_ts) > MATCH_THRESH:
                continue
            summary = decode_sleep_summary_2(nearest[1])

            epochs = result["epochs"]
            runs, adj_none, total_none = stage3_runs_and_adjacency(epochs)
            stage3_5a = result["stage_counts"].get(3, 0)
            stage3_4c = summary["stage3_epochs"]
            gap = stage3_4c - stage3_5a

            rows.append({
                "file": os.path.basename(path),
                "boot_ts": last_ts,
                "n_chunks": max(packets.keys()) + 1,
                "s0_5a": result["stage_counts"].get(0, 0), "s0_4c": summary["stage0_epochs"],
                "s1_5a": result["stage_counts"].get(1, 0), "s1_4c": summary["stage1_epochs"],
                "s2_5a": result["stage_counts"].get(2, 0), "s2_4c": summary["stage2_epochs"],
                "gap": gap,
                "runs": runs,
                "adj_none": adj_none,
                "total_none": total_none,
                "u16_4": summary["u16_4"], "u16_5": summary["u16_5"], "u16_6": summary["u16_6"],
            })

    print(f"Total true-complete 0x5A bursts across corpus: {total_complete_bursts}")
    print(f"Matched to a nearby 0x4C record (<= {MATCH_THRESH} ticks): {len(rows)}")
    print(f"result['complete'] flag WRONG on {complete_flag_bug_seen}/{total_complete_bursts} "
          f"true-complete bursts (hardcoded range(23) bug)\n")

    # De-duplicate by boot_ts: the SAME underlying bout is re-transmitted (byte-identical)
    # across multiple later daemon sessions' backlog dumps -- confirmed by inspection
    # (identical boot_ts + identical gap/features recur verbatim across 20260718..20260722
    # daemon files). Treating each file's copy as an independent sample would silently
    # multiply-count the same bout up to 5x. Dedup by boot_ts, keep first occurrence.
    seen_ts = set()
    deduped = []
    dup_count = 0
    for r in sorted(rows, key=lambda r: r["file"]):
        if r["boot_ts"] in seen_ts:
            dup_count += 1
            continue
        seen_ts.add(r["boot_ts"])
        deduped.append(r)
    print(f"De-duplicated by boot_ts: {dup_count} re-transmitted duplicates removed, "
          f"{len(deduped)} truly distinct bouts remain.\n")
    rows = deduped

    print("stages 0/1/2 exact-match check (should be exact per 2026-07-21 finding):")
    mismatches = [r for r in rows if not (r["s0_5a"] == r["s0_4c"] and r["s1_5a"] == r["s1_4c"] and r["s2_5a"] == r["s2_4c"])]
    print(f"  {len(rows) - len(mismatches)}/{len(rows)} exact match; {len(mismatches)} mismatches")
    for r in mismatches:
        print(f"    MISMATCH {r['file']} ts={r['boot_ts']}: 5a(s0/1/2)={r['s0_5a']}/{r['s1_5a']}/{r['s2_5a']} "
              f"4c(s0/1/2)={r['s0_4c']}/{r['s1_4c']}/{r['s2_4c']}")

    print("\nstage-3 gap table (4c - 5a_nonFF), with run-count / adjacency features:")
    print(f"  {'file':<32} {'ts':<11} {'chunks':<7} {'gap':<6} {'runs':<5} {'adj_none':<9} {'total_none':<10} u16_4/5/6")
    for r in sorted(rows, key=lambda r: (r["file"], r["boot_ts"])):
        print(f"  {r['file']:<32} {r['boot_ts']:<11} {r['n_chunks']:<7} {r['gap']:<6} {r['runs']:<5} "
              f"{r['adj_none']:<9} {r['total_none']:<10} {r['u16_4']}/{r['u16_5']}/{r['u16_6']}")

    # crude correlation checks (n likely small; report honestly either way)
    def pearson(xs, ys):
        n = len(xs)
        if n < 3:
            return None
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        vx = sum((x - mx) ** 2 for x in xs)
        vy = sum((y - my) ** 2 for y in ys)
        if vx == 0 or vy == 0:
            return None
        return cov / (vx ** 0.5 * vy ** 0.5)

    gaps = [r["gap"] for r in rows]
    runs_l = [r["runs"] for r in rows]
    adj_l = [r["adj_none"] for r in rows]
    tot_none_l = [r["total_none"] for r in rows]
    chunks_l = [r["n_chunks"] for r in rows]
    abs_gaps = [abs(g) for g in gaps]
    print(f"\nn = {len(rows)}")
    print(f"corr(gap, runs)             = {pearson(gaps, runs_l)}")
    print(f"corr(gap, adj_none)         = {pearson(gaps, adj_l)}")
    print(f"corr(gap, total_none)       = {pearson(gaps, tot_none_l)}")
    print(f"corr(runs, adj_none)        = {pearson(runs_l, adj_l)}")
    print(f"corr(gap, n_chunks)         = {pearson(gaps, chunks_l)}  [confound check: bout length]")
    print(f"corr(total_none, n_chunks)  = {pearson(tot_none_l, chunks_l)}  [confound check]")
    print(f"corr(|gap|, n_chunks)       = {pearson(abs_gaps, chunks_l)}  [confound check, magnitude not signed]")
    print(f"corr(|gap|, total_none)     = {pearson(abs_gaps, tot_none_l)}")

    print("\n--- same correlations, excluding 1-chunk bursts (stage0/1/2 mismatch cluster; "
          "possible 0x00-as-padding artifact in freshly-started accumulators, see "
          "known_issues.md 2026-07-24 Finding 3 -- unconfirmed) ---")
    clean = [r for r in rows if r["n_chunks"] >= 2]
    cg = [r["gap"] for r in clean]
    cr = [r["runs"] for r in clean]
    ca = [r["adj_none"] for r in clean]
    ct = [r["total_none"] for r in clean]
    cc = [r["n_chunks"] for r in clean]
    cag = [abs(g) for g in cg]
    print(f"n = {len(clean)}")
    print(f"corr(gap, runs)        = {pearson(cg, cr)}")
    print(f"corr(gap, adj_none)    = {pearson(cg, ca)}")
    print(f"corr(gap, total_none)  = {pearson(cg, ct)}")
    print(f"corr(gap, n_chunks)    = {pearson(cg, cc)}")
    print(f"corr(|gap|, n_chunks)  = {pearson(cag, cc)}")
    print(f"corr(|gap|, total_none)= {pearson(cag, ct)}")


if __name__ == "__main__":
    main()
