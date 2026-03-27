from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal


ClockMode = Literal["wall", "simulated", "replay"]


@dataclass(frozen=True, slots=True)
class ClockConfig:
    mode: ClockMode = "simulated"
    accelerated_factor: float = 1.0


@dataclass(frozen=True, slots=True)
class LoopTiming:
    actual_interval_us: int
    sleep_us: int
    jitter_us: int


class LoopPacer:
    def __init__(self, config: ClockConfig) -> None:
        self._config = config
        self._anchor_wall_ns: int | None = None
        self._anchor_device_us: int | None = None
        self._last_wall_ns: int | None = None
        self._last_device_us: int | None = None

    def pace(self, *, target_device_us: int) -> LoopTiming:
        if self._config.mode != "wall":
            previous_device = self._last_device_us
            self._last_device_us = target_device_us
            interval = 0 if previous_device is None else target_device_us - previous_device
            return LoopTiming(actual_interval_us=interval, sleep_us=0, jitter_us=0)

        factor = self._config.accelerated_factor if self._config.accelerated_factor > 0 else 1.0
        now_ns = time.monotonic_ns()
        if self._anchor_wall_ns is None or self._anchor_device_us is None:
            self._anchor_wall_ns = now_ns
            self._anchor_device_us = target_device_us
            self._last_wall_ns = now_ns
            self._last_device_us = target_device_us
            return LoopTiming(actual_interval_us=0, sleep_us=0, jitter_us=0)

        expected_wall_elapsed_ns = int(
            ((target_device_us - self._anchor_device_us) / factor) * 1000
        )
        target_wall_ns = self._anchor_wall_ns + expected_wall_elapsed_ns
        requested_sleep_ns = max(0, target_wall_ns - now_ns)
        if requested_sleep_ns > 0:
            time.sleep(requested_sleep_ns / 1_000_000_000)
        after_ns = time.monotonic_ns()

        previous_wall_ns = self._last_wall_ns or after_ns
        previous_device_us = self._last_device_us or target_device_us
        actual_interval_us = int(((after_ns - previous_wall_ns) / 1000.0) * factor)
        expected_interval_us = target_device_us - previous_device_us
        self._last_wall_ns = after_ns
        self._last_device_us = target_device_us
        return LoopTiming(
            actual_interval_us=actual_interval_us,
            sleep_us=int(requested_sleep_ns / 1000),
            jitter_us=actual_interval_us - expected_interval_us,
        )
