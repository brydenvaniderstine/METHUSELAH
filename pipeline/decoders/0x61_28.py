"""0x61/0x28 — _dd_afe_statistics_values (debug data sub-type 0x28). PARTIAL.

CONFIRMED 2026-07-11 against all 114 real packets in the (then) 29-file
corpus. 14-byte payload, stateful: byte[1] distinguishes record kind
within a multi-record session (0=continuation, 1=header, confirmed --
these always fire as adjacent boot_ts pairs, continuation immediately
followed by its header).

PUSHED FURTHER 2026-07-12 against the full 34-file corpus (140 records,
70 continuation + 70 header) -- p[2:14] (the "stats_hex" blob) is
confirmed to be exactly 6x u16 LE fields, no leftover bytes. Real
structure found in both record kinds:

**Continuation records (kind=0) -- shape correlates with pfsm_state.**
Classified each record's 6-field pattern by which fields are nonzero and
whether they're equal, then cross-referenced against the nearest *real*
(non-echo) 0x61/0x09 pfsm_state in the same pull:

  - `[X,X,X,X,0,0]` (fields 0-3 all equal, 4-5 zero): fires almost only
    during pfsm 5/6 (TRANSITIONAL/SLEEP_REGIME) -- 36/37 occurrences (97%).
  - `[X,0,0,0,0,0]` (only field 0 nonzero): fires almost only during
    pfsm=3 (ACTIVE_REGIME) -- 16/18 (89%), 2/18 pfsm=4.
  - `[X,0,0,0,X,X]` (field 0 = field 4 = field 5, 1-3 zero): fires almost
    only during pfsm=5 -- 12/13 (92%).

  Reads as: the ring runs a reduced (1-field) AFE measurement scheme
  while active, and a fuller (4-field) scheme while asleep/transitional --
  consistent with lower-power PPG sampling when full biometric tracking
  isn't the priority. Field COUNT (not yet field IDENTITY) is
  state-dependent. This is a real, cross-validated correlation against
  an independently-decoded signal, not a guess.

**Header records (kind=1) -- field[0] is a drift-flag, not usually a
counter.** 67/70 (96%) have field[0]=0 and fields[2:6]=0, with only
field[1] varying (0-500, likely a running "records since last event"
count, exact semantics still unresolved). The 3 exceptions all have
field[0] nonzero (423, 424, 375) -- and in every one of those 3 cases,
the immediately-preceding continuation record's "4 fields equal" pattern
was actually a near-miss: 3 fields equal and a 4th field higher by almost
exactly that same amount (424, 424, 375 -- matching within 1 unit each
time). **The header's field[0], when nonzero, is reporting the magnitude
of a per-channel count drift in the paired continuation record.** A
genuine anomaly-flag mechanism, confirmed by exact cross-record
arithmetic, not inferred.

Ceiling: field IDENTITY (which physical channel/LED each of the 6
u16 slots represents, and what unit the counts are in -- samples? ADC
reads? something else?) is still unknown without a MAX86171 register
map. The structure and its state-dependence are now solid; the physical
meaning is not. Not promoted to DONE.

TESTED 2026-07-21 against pipeline/data/findings/max86171_register_reference.md
on the grown corpus (26,774 records: 13,387 continuation + 13,387
header). Checked the doc's plausible-range context (ADC full-scale
4/8/16/32 uA, dark-current noise 75-212 pA RMS, FIFO_DATA_COUNT[8:0]
saturating at 511, OVF_COUNTER[6:0] saturating at 127). Only the
FIFO/OVF saturation check is concretely falsifiable against a raw u16
field -- and it's FALSIFIED: continuation-record field values range
1-35,097 across the full corpus and never once equal exactly 127 or
511. A real saturating counter would be expected to hit and hold at its
ceiling repeatedly under sustained load; smooth climbs into the tens of
thousands with zero saturation events rules this identity out. The
ADC-uA and dark-current-pA figures aren't independently checkable
without a known scale factor (the reference doc itself flags this
section as firmware-computed aggregates, not raw register dumps, so
this negative result is expected, not surprising). Field identity
remains unresolved. See known_issues.md 2026-07-21 (session 3).
"""

import struct

STATE_NAMES = {3: "ACTIVE_REGIME", 4: "ACTIVE_REGIME", 5: "TRANSITIONAL", 6: "SLEEP_REGIME"}


def decode(payload: bytes) -> dict:
    if len(payload) < 14:
        raise ValueError(f"afe_statistics_values payload too short, got {len(payload)} bytes")
    if payload[0] != 0x28:
        raise ValueError(f"not an afe_statistics_values record (sub_byte={payload[0]:#x})")
    kind_byte = payload[1]
    fields = struct.unpack("<6H", payload[2:14])
    return {
        "record_kind": "header" if kind_byte == 1 else ("continuation" if kind_byte == 0 else f"unknown_{kind_byte}"),
        "kind_byte": kind_byte,
        "fields": list(fields),
        "stats_hex": payload[2:].hex(),
        "all_stats_zero": all(v == 0 for v in fields),
        "drift_flag": fields[0] if kind_byte == 1 and fields[0] != 0 else None,
    }
