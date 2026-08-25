"""Deterministic sampling: same seed, same reference set, every time."""

from __future__ import annotations

import random
from typing import Callable, Sequence, TypeVar

T = TypeVar("T")


def sample_deterministic(
    items: Sequence[T], k: int, seed: int, *, key: Callable[[T], object] = lambda x: x
) -> list[T]:
    """Sample ``k`` items from ``items`` deterministically for a given seed.

    ``items`` is sorted by ``key`` first so the sample does not depend on
    the iteration order of whatever collection produced it (e.g. dict
    insertion order in a Pool) — only on the seed and the item identities.
    """
    ordered = sorted(items, key=key)
    if k > len(ordered):
        raise ValueError(f"cannot sample {k} items from a population of {len(ordered)}")
    rng = random.Random(seed)
    return rng.sample(ordered, k)
