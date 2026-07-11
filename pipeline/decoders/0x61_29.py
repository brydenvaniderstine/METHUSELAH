"""0x61/0x29 — _dd_acm_configuration_changed (debug data sub-type 0x29). VALIDATED.

CONFIRMED 2026-07-11 against all 37 real packets in the current 29-file
corpus. Layout matches open_ring's documented wire format exactly (8
bytes: sub:1 + 5x u8 + u16 LE):

  p[1]:   accelerometer_mode (u8)   -- observed {2, 3, 4}
  p[2]:   accelerometer_odr (u8)    -- observed {5, 7, 10}
  p[3]:   accelerometer_range (u8)  -- observed {2, 3}
  p[4]:   gyroscope_odr (u8)        -- always 0 in this corpus
  p[5]:   gyroscope_range (u8)      -- always 0 in this corpus
  p[6:8]: event_mask_and_fifo (u16 LE)

Clean, discrete config-state values with mode/odr/range moving together
consistently (mode=2 -> odr=5/range=2; mode=3 -> odr=7/range=2; mode=4 ->
odr=10/range=3) -- exactly the pattern you'd expect from a small set of
named accelerometer power/sampling profiles, not noise.

Gyroscope fields are 0 in every sample -- the ring's gyro appears disabled
across all observed configs (plausible power-saving choice; not confirmed
whether it's ever enabled under some other condition not captured here).

Ceiling: what mode=2/3/4 concretely mean (e.g. sleep vs. active sampling
profiles) is inferred from clustering, not firmware-confirmed. The
event_mask_and_fifo u16 is surfaced raw per open_ring — bit-level meaning
not decoded.
"""


def decode(payload: bytes) -> dict:
    if len(payload) < 8:
        raise ValueError(f"acm_configuration_changed payload too short, got {len(payload)} bytes")
    if payload[0] != 0x29:
        raise ValueError(f"not an acm_configuration_changed record (sub_byte={payload[0]:#x})")
    return {
        "accelerometer_mode": payload[1],
        "accelerometer_odr": payload[2],
        "accelerometer_range": payload[3],
        "gyroscope_odr": payload[4],
        "gyroscope_range": payload[5],
        "event_mask_and_fifo_u16": payload[6] | (payload[7] << 8),
    }
