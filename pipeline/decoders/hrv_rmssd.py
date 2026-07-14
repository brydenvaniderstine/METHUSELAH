"""HRV (RMSSD) computed from IBI streams -- NOT a direct byte decoder.

The ring's own 0x5D HRV event is confirmed ACTIVITY-ONLY (0/21 sleep pulls,
re-verified twice -- see known_issues.md 2026-06-27/2026-07-10). Sleep HRV
is not accessible via 0x5D. The alternative identified in known_issues.md
(2026-07-07): "Compute RMSSD from 0x6E / 0x80 IBI data already captured in
sleep pulls (viable -- IBI confirmed working)." This module does that.

CALLER CONTRACT: pass a list of PACKETS, each packet itself a list of that
packet's IBI values in order (i.e. list[list[int]], not a flattened
list[int]). Diffs are only computed WITHIN a packet, never across packet
boundaries -- 0x6E interleaves channel A/B packets (5 IBI values each,
single channel per packet), and diffing across a packet boundary would
compare unrelated channel-A/channel-B beats. Tested naive cross-packet
flattening first (2026-07-13): gave 145-154ms RMSSD against a real 30ms
Gen4 value -- confirmed wrong, not used.

ARTIFACT REJECTION IS REQUIRED, not optional. Real within-packet diffs
from this pull's raw data have a median absolute value of ~15ms (a
reasonable, plausible HRV signal) but also contain a handful of extreme
outliers (a few >1000ms) from misdetected/noisy PPG beats -- RMS squaring
means a tiny number of these dominate the entire result if not excluded.
This is a well-known problem with PPG-derived (vs ECG-derived) IBI in HRV
literature, not unique to this decoder.

VALIDATED 2026-07-13 against two real, independent nights with known Gen4
HRV ground truth (retrospective check against gen3_vs_gen4_comparison.csv):
  - 2026-07-12/13: computed 31.0ms vs real 30ms (3% error, 13/384 diffs
    excluded as artifacts at the 300ms threshold)
  - 2026-07-11/12: computed 24.6ms vs real 29ms (15% error, 0 diffs
    excluded -- this night's data had no extreme outliers to reject)
Not clinical-grade precision, but real signal in the right range on two
independent nights, and far better than permanent AWAITING DATA. Honest
error margin: roughly 3-15% observed so far, n=2.
"""
import math

ARTIFACT_THRESHOLD_MS = 300  # validated against two real nights, see above


def calculate_rmssd(ibi_packets, min_pairs=10):
    """RMSSD = sqrt(mean(diff(IBI)^2)) over valid, sentinel-excluded,
    within-packet-only successive differences. `ibi_packets` is a list of
    packets, each a list of that packet's raw IBI values in order (NOT a
    pre-flattened list -- see module docstring for why). Returns None if
    there aren't enough valid pairs for a meaningful result -- mirrors how
    other decoders in this project return None/skip rather than emit a
    meaningless number from insufficient data.
    """
    sq_diffs = []
    for packet in ibi_packets:
        valid = [v for v in packet if 300 <= v < 2000]
        for i in range(len(valid) - 1):
            diff = valid[i + 1] - valid[i]
            if abs(diff) <= ARTIFACT_THRESHOLD_MS:
                sq_diffs.append(diff * diff)
    if len(sq_diffs) < min_pairs:
        return None
    return round(math.sqrt(sum(sq_diffs) / len(sq_diffs)), 1)
