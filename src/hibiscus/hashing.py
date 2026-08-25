"""Content hashing used for cache keys and comparison logs."""

from __future__ import annotations

import hashlib


def sha256_hex(text: str) -> str:
    """Return the hex-encoded SHA-256 digest of ``text``, encoded as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
