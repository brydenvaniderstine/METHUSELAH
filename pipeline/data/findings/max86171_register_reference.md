# MAX86171 Register Reference (external datasheet extract)

Source: Analog Devices official datasheet (19-100558 Rev 4, 6/22),
https://www.analog.com/media/en/technical-documentation/data-sheets/MAX86171.pdf
Pulled 2026-07-21 to unblock register/field-identity ceilings flagged in
`open_ring_roadmap.md` for `0x61/0x33`, `0x61/0x28`, `0x77`, `0x73`.

Chip confirmed as the Gen3 ring's PPG AFE via `0x61/0x33` (chip_variant=1,
see roadmap). This is the real ADI/Maxim datasheet, not Oura firmware —
it tells you what the chip CAN do and its generic register layout, not
which specific configuration Oura's firmware chose. Keep that distinction
when using this doc: it resolves register *shape*, not Oura-specific
*wavelength/channel assignment*.

## Direct match — `0x61/0x33 ppg_settings` (12-byte blob, 2×6-byte per-channel)

Roadmap finding: two structurally-identical 6-byte halves (A/B), each with
a channel-marker byte, a constant register-address byte, and a near-fixed
calibration offset. This maps closely to the MEASx per-channel config
registers below — each MEASn block repeats this same field set for
channel 1 and channel 2:

**MEASn Configuration 1** (e.g. 0x19 for MEAS1):
| Field | Bits | Meaning |
|---|---|---|
| `MEASn_PPG2_PDSEL` | 1 bit | which of 2 PDs feeds channel 2 |
| `MEASn_PPG1_PDSEL` | 1 bit | which of 2 PDs feeds channel 1 |
| `MEASn_TINT[1:0]` | 2 bits | ADC integration time: 14.6/29.2/58.6/117.1 µs |
| `MEASn_AVER[2:0]` | 3 bits | on-chip averaging factor (2^N) |

**MEASn Configuration 2** (e.g. 0x1A for MEAS1):
| Field | Bits | Meaning |
|---|---|---|
| `MEASn_SINC3_SEL` | 1 bit | decimation filter: SINC3 vs COI |
| `MEASn_FILT_SEL` | 1 bit | ambient rejection: CDM vs FDM |
| `MEASn_LED_RGE[1:0]` | 2 bits | LED full-scale: 32/64/96/128 mA |
| `MEASn_PPG2_ADC_RGE[1:0]` | 2 bits | ch2 ADC full-scale: 4/8/16/32 µA |
| `MEASn_PPG1_ADC_RGE[1:0]` | 2 bits | ch1 ADC full-scale: 4/8/16/32 µA |

**MEASn Configuration 3** (e.g. 0x1B for MEAS1):
| Field | Bits | Meaning |
|---|---|---|
| `MEASn_PD_SETLNG[1:0]` | 2 bits | photodiode settling time |
| `MEASn_LED_SETLNG[1:0]` | 2 bits | LED settling time |
| `MEASn_PPG2_DACOFF[1:0]` | 2 bits | ch2 offset DAC (extends dynamic range) |
| `MEASn_PPG1_DACOFF[1:0]` | 2 bits | ch1 offset DAC |

**Next step for the decoder:** test whether the 6-byte-per-channel split
in the captured blob lines up as `[PDSEL/TINT/AVER byte][SINC3/FILT/LED_RGE/ADC_RGE byte]
[SETLNG/DACOFF byte] + 3 more` — the "constant register-address byte"
you found is plausibly the register address itself (0x19/0x1A/0x1B-style,
or the equivalent for whichever MEASn Oura firmware uses), and the
"near-fixed calibration offset" is very likely `DACOFF[1:0]` or
`PPGx_ADC_RGE`, both of which are expected to stay constant across a
session once the ring's firmware picks a working configuration.

## Useful context — `0x61/0x28 afe_statistics`

Not a direct register match (statistics tags are firmware-computed
aggregates, not raw register dumps) but these give plausible ranges to
sanity-check the 6× u16 LE fields against:
- ADC is 19.5-bit, full-scale input current 4/8/16/32 µA depending on
  `ADC_RGE` setting
- Dark current input-referred noise: 75–212 pA RMS depending on
  integration time
- FIFO/status counters (`FIFO_DATA_COUNT[8:0]`, `OVF_COUNTER[6:0]`,
  saturates at 0x7F) are plausible candidates if any field maxes out
  at 255 or 511 repeatedly in the corpus

## Ceiling — band/channel identity (`0x77` DC samples, `0x73` DHR channels)

The chip supports up to 9 independently configured measurements per
frame, each mappable to any of 9 LED pins × 4 photodiode inputs
(Table 1/2 in datasheet, LED driver mux). **Which measurement slot
Oura's firmware assigned to red/IR/green is not in this datasheet** —
that's an Oura-firmware-specific choice, not a chip-generic fact. This
ceiling is NOT resolved by this document. Still needs Oura firmware
access or a controlled-wavelength experiment (e.g. covering specific
LEDs) to determine empirically.

## FIFO tag structure (context, not a current ceiling item)

FIFO words are 24 bits: 4-bit tag + 20-bit signed ADC value (2's
complement, left-justified). Tags 0x1–0x9 = MEASn data, 0xA = dark
data (raw mode only), 0xB = ALC overflow, 0xC = exposure overflow,
0xD = picket-fence-corrected sample, 0xE = invalid/empty-FIFO read.
Not yet cross-referenced against any Gen3 tag in the roadmap — flagging
in case it's useful context for future FIFO-adjacent decode work.
