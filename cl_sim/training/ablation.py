from __future__ import annotations

import random
from typing import Iterable


def zero_ablation(spike_rounds: Iterable[tuple[float, ...]]) -> tuple[tuple[float, ...], ...]:
    return tuple(tuple(0.0 for _ in round_values) for round_values in spike_rounds)


def noise_ablation(
    spike_rounds: Iterable[tuple[float, ...]],
    *,
    seed: int = 17,
) -> tuple[tuple[float, ...], ...]:
    rng = random.Random(seed)
    return tuple(
        tuple(rng.random() for _ in round_values)
        for round_values in spike_rounds
    )


def shuffled_ablation(
    spike_rounds: Iterable[tuple[float, ...]],
    *,
    seed: int = 23,
) -> tuple[tuple[float, ...], ...]:
    rng = random.Random(seed)
    flattened = [value for round_values in spike_rounds for value in round_values]
    rng.shuffle(flattened)
    iterator = iter(flattened)
    return tuple(
        tuple(next(iterator) for _ in round_values)
        for round_values in spike_rounds
    )
