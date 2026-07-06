# pipeline/decoders package — re-exports each tag's decode() with the original function names
# used by pipeline/tools/ scripts. Module filenames start with digits (e.g. 0x6a.py) so
# we use importlib to load them rather than dotted from-imports.

import importlib.util, os

_HERE = os.path.dirname(__file__)

# Load utils first and inject it so decoder files can find it via relative import
_utils_spec = importlib.util.spec_from_file_location("pipeline.decoders.utils", os.path.join(_HERE, "utils.py"))
_utils_mod = importlib.util.module_from_spec(_utils_spec)
import sys as _sys
_sys.modules["pipeline.decoders.utils"] = _utils_mod
_utils_spec.loader.exec_module(_utils_mod)

def _load(filename, alias):
    full_alias = f"pipeline.decoders.{alias}"
    spec = importlib.util.spec_from_file_location(
        full_alias,
        os.path.join(_HERE, filename)
    )
    mod = importlib.util.module_from_spec(spec)
    _sys.modules[full_alias] = mod
    spec.loader.exec_module(mod)
    return mod.decode

decode_sleep_period_info_2      = _load("0x6a.py",    "decoder_0x6a")
decode_hrv_event                = _load("0x5d.py",    "decoder_0x5d")
decode_debug_data_sleep_statistics = _load("0x61_09.py", "decoder_0x61_09")
decode_debug_data_battery_level = _load("0x61_24.py", "decoder_0x61_24")
decode_debug_data_fuel_gauge    = _load("0x61_14.py", "decoder_0x61_14")
decode_spo2_event               = _load("0x6f.py",    "decoder_0x6f")
decode_sleep_temp_event         = _load("0x75.py",    "decoder_0x75")
decode_motion_event             = _load("0x47.py",    "decoder_0x47")
decode_bedtime_period           = _load("0x76.py",    "decoder_0x76")
decode_spo2_ibi_amplitude       = _load("0x6e.py",    "decoder_0x6e")
