"""0x61/0x09 — _dd_sleep_statistics (debug data sub-type 0x09).

Partial decode confirmed 2026-06-26/27. See pipeline/data/findings/known_issues.md.
Layout: 6xU16 LE + 1xU8 pfsm_state. open_ring's u32 layout is wrong for this data.
"""


def decode(p: bytes) -> dict:
    if len(p) < 14:
        raise ValueError("sleep_statistics payload too short")
    if p[0] != 0x09:
        raise ValueError(f"not a sleep_statistics record (sub_byte={p[0]:#x})")
    return {
        # offset-3 u16 LE confirmed 2026-06-26: seconds in current pfsm state
        "seconds_in_pfsm_state": p[3] | (p[4] << 8),
        "pfsm_state": p[13],
        # remaining fields (offsets 1-2, 4-12) not yet decoded correctly —
        # open_ring's u32 layout produces nonsense; excluded until resolved
    }
