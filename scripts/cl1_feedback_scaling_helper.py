#!/usr/bin/env python3
"""Reusable reward and surprise scaling helpers for CL1 feedback policies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple


@dataclass
class SurpriseScaler:
    beta: float = 0.99
    base_gain: float = 0.25
    base_max_scale: float = 2.0
    freq_gain: float = 0.65
    amp_gain: float = 0.35
    freq_max_scale: float = 2.0
    amp_max_scale: float = 1.5
    compression_k: float = 1.0
    ema: float = 0.0

    def update(self, magnitude: float) -> float:
        self.ema = self.beta * self.ema + (1.0 - self.beta) * magnitude
        return self.ema

    def scales(self, magnitude: float) -> Tuple[float, float]:
        baseline = max(self.ema, 1e-3)
        ratio = min(magnitude / baseline, self.base_max_scale)
        freq_delta = self.freq_gain * (1.0 - math.exp(-self.compression_k * ratio))
        amp_delta = self.amp_gain * (1.0 - math.exp(-self.compression_k * ratio))
        freq_scale = max(0.5, min(self.freq_max_scale, 1.0 + freq_delta))
        amp_scale = min(self.amp_max_scale, 1.0 + amp_delta)
        return freq_scale, amp_scale


def direct_reward_scales(
    reward: float,
    positive_threshold: float,
    negative_threshold: float,
) -> Tuple[float, float, str]:
    if reward >= positive_threshold:
        return (
            1.0 + max(0.0, reward - positive_threshold),
            1.0 + max(0.0, reward - positive_threshold),
            "positive",
        )
    if reward <= negative_threshold:
        magnitude = abs(reward - negative_threshold)
        return 1.0 + magnitude, 1.0 + magnitude, "negative"
    return 1.0, 1.0, "neutral"


def value_surprise_magnitude(observed_reward: float, predicted_value: float) -> float:
    return abs(observed_reward - predicted_value)


if __name__ == "__main__":
    scaler = SurpriseScaler()
    magnitude = value_surprise_magnitude(2.5, 1.0)
    scaler.update(magnitude)
    print("surprise scales:", scaler.scales(magnitude))
    print("reward scales:", direct_reward_scales(2.0, positive_threshold=1.0, negative_threshold=-1.0))
