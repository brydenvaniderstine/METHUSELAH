"""0x53 -- wear_event (WearEvent). Shares the StateChange enum with 0x45
(state_change_ind) -- see open_ring enums.py STATE_CHANGE.

Format: state:u8 + text:ascii. For most states, text is the duration (in
seconds, as a decimal ASCII string) of the *previous* state before this
transition. Confirmed real exception: state 8 (STATE_CHARGING_PHASE) carries
a fixed status string "chg. detected" instead of a numeric duration --
observed identically across 3 separate real occurrences (2026-07-02,
2026-07-10, 2026-07-18 evening pulls; also present in the 2026-07-19/20 and
2026-07-20/21 overnight daemon logs).

Real states observed so far (3 full overnight daemon logs, 2026-07-18
through 2026-07-21): only 1 (NOT_IN_FINGER), 3 (FINGER_USER_ACTIVE), and
8 (CHARGING_PHASE) ever appear. NOT_IN_FINGER/FINGER_USER_ACTIVE alternate
33-44 times per 8h night even during confirmed real sleep (a wear-confidence
oscillation, not literal on/off wrist removal) -- do NOT treat NOT_IN_FINGER
presence/absence as a sleep/non-sleep signal on its own. CHARGING_PHASE is
the one state value confirmed unambiguous: the ring cannot be worn while
reporting itself on the charging dock.
"""

STATE_NOT_IN_FINGER = 1
STATE_FINGER_USER_ACTIVE = 3
STATE_CHARGING_PHASE = 8


def decode(p: bytes) -> dict:
    if len(p) < 1:
        raise ValueError("WearEvent payload must have at least a state byte")
    state = p[0]
    text_bytes = bytes(p[1:])
    try:
        text = text_bytes.decode("ascii")
    except UnicodeDecodeError:
        text = None
    prev_state_secs = int(text) if text and text.isdigit() else None
    return {"state": state, "text": text, "prev_state_secs": prev_state_secs}
