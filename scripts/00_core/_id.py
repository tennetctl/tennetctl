"""UUID v7 generator per RFC 9562 §5.7.

48-bit ms timestamp | 4-bit version (7) | 12-bit random | 2-bit variant | 62-bit random.
Strictly monotonic within the same millisecond via a sequence counter.
"""

from __future__ import annotations

import secrets
import threading
import time

_lock = threading.Lock()
_last_ms: int = 0
_seq: int = 0


def uuid7() -> str:
    """Return a new UUID v7 string (lowercase, hyphenated, 36 chars)."""
    global _last_ms, _seq

    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms == _last_ms:
            _seq += 1
        else:
            _last_ms = ms
            _seq = 0
        seq = _seq

    # 48-bit timestamp
    ts = ms & 0xFFFFFFFFFFFF

    # 12-bit sequence (top 12 bits after version nibble)
    seq12 = seq & 0xFFF

    # 62 bits of random for the low 64 bits
    rand_bytes = secrets.token_bytes(8)
    rand_lo = int.from_bytes(rand_bytes, "big") & 0x3FFFFFFFFFFFFFFF

    # Assemble 128 bits
    hi = (ts << 16) | (0x7 << 12) | seq12
    lo = (0b10 << 62) | rand_lo

    # Format as UUID string
    b = (hi << 64) | lo
    hex_str = f"{b:032x}"
    return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:32]}"
