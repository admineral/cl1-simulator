from __future__ import annotations

import math
import random
from dataclasses import dataclass

from cl_sim.api.types import RawFrame, Spike, StimEvent
from cl_sim.backends.base import BackendBatch, SyntheticBackendConfig


SPIKE_WAVEFORM = (-0.12, -0.38, 0.82, -0.27, -0.11, 0.03, 0.01)


@dataclass
class SyntheticBackend:
    config: SyntheticBackendConfig

    def __post_init__(self) -> None:
        self.backend_name = "synthetic"
        self.channel_count = self.config.channel_count
        self.frame_interval_us = int(1_000_000 / self.config.sample_rate_hz)
        self.metadata = {
            "sample_rate_hz": self.config.sample_rate_hz,
            "sample_mean": self.config.sample_mean,
            "sample_noise_std": self.config.sample_noise_std,
            "spontaneous_spike_rate_hz": self.config.spontaneous_spike_rate_hz,
            "seed": self.config.seed,
            "compatibility_note": (
                "Synthetic samples and stim-response effects are simulator behavior, not "
                "official Cortical Labs device guarantees."
            ),
        }
        self._rng = random.Random(self.config.seed)
        self._stim_memory_until: dict[int, int] = {}

    def advance_interval(
        self,
        *,
        start_timestamp_us: int,
        end_timestamp_us: int,
        delivered_stims: tuple[StimEvent, ...],
    ) -> BackendBatch:
        frames: list[RawFrame] = []
        spikes: list[Spike] = []

        for stim in delivered_stims:
            self._stim_memory_until[stim.channel] = max(
                self._stim_memory_until.get(stim.channel, 0),
                stim.timestamp_us + 3 * self.frame_interval_us,
            )
            evoked_ts = stim.timestamp_us + self.frame_interval_us
            if evoked_ts <= end_timestamp_us:
                spikes.append(
                    Spike(
                        channel=stim.channel,
                        timestamp_us=evoked_ts,
                        samples=SPIKE_WAVEFORM,
                        source="stim",
                    )
                )

        next_timestamp_us = (
            ((start_timestamp_us // self.frame_interval_us) + 1) * self.frame_interval_us
        )
        spontaneous_probability = (
            self.config.spontaneous_spike_rate_hz / self.config.sample_rate_hz
        )

        while next_timestamp_us <= end_timestamp_us:
            samples: list[float] = []
            phase = next_timestamp_us / 50_000.0
            for channel in range(self.channel_count):
                base = self.config.sample_mean + math.sin(phase + channel * 0.15) * 0.1
                noise = self._rng.gauss(0.0, self.config.sample_noise_std)
                stim_bump = 0.0
                if self._stim_memory_until.get(channel, 0) >= next_timestamp_us:
                    stim_bump = 0.15
                samples.append(base + noise + stim_bump)

                if self._rng.random() < spontaneous_probability:
                    spikes.append(
                        Spike(
                            channel=channel,
                            timestamp_us=next_timestamp_us,
                            samples=SPIKE_WAVEFORM,
                            source="synthetic",
                        )
                    )

            frames.append(RawFrame(timestamp_us=next_timestamp_us, samples=tuple(samples)))
            next_timestamp_us += self.frame_interval_us

        spikes.sort(key=lambda spike: (spike.timestamp_us, spike.channel))
        return BackendBatch(frames=tuple(frames), spikes=tuple(spikes))

    def is_exhausted(self, current_timestamp_us: int) -> bool:
        return False
