"""The three-tier rating scale: love / okay / nope."""

from __future__ import annotations

from enum import Enum


class Tier(str, Enum):
    """A hand-assigned rating tier. Exactly three, ordered."""

    LOVE = "love"
    OKAY = "okay"
    NOPE = "nope"


TIER_ORDER: dict[Tier, int] = {Tier.NOPE: 0, Tier.OKAY: 1, Tier.LOVE: 2}


def parse_tier(value: "str | Tier") -> Tier:
    """Parse a tier from a string (case-insensitive) or pass through a Tier."""
    if isinstance(value, Tier):
        return value
    try:
        return Tier(value.strip().lower())
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"unknown tier {value!r}; expected one of love/okay/nope") from exc
