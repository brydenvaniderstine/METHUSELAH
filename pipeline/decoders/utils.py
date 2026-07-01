"""Shared helpers for all pipeline/decoders/. Import from here only — never cross-import between decoder files."""


def _i8(b: int) -> int:
    """Reinterpret a uint8 as a signed int8."""
    return b - 0x100 if b & 0x80 else b


def _u32(p: bytes, off: int) -> int:
    """Little-endian uint32 from bytes p starting at offset off."""
    return p[off] | (p[off + 1] << 8) | (p[off + 2] << 16) | (p[off + 3] << 24)
