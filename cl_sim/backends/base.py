from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from cl_sim.api.types import DataStreamRecord, RawFrame, Spike, StimEvent


@dataclass(frozen=True, slots=True)
class BackendBatch:
    frames: tuple[RawFrame, ...] = ()
    spikes: tuple[Spike, ...] = ()
    stims: tuple[StimEvent, ...] = ()
    data_streams: tuple[DataStreamRecord, ...] = ()


class Backend(Protocol):
    backend_name: str
    channel_count: int
    frame_interval_us: int
    metadata: Mapping[str, object]

    def advance_interval(
        self,
        *,
        start_timestamp_us: int,
        end_timestamp_us: int,
        delivered_stims: tuple[StimEvent, ...],
    ) -> BackendBatch:
        ...

    def is_exhausted(self, current_timestamp_us: int) -> bool:
        ...


@dataclass(frozen=True, slots=True)
class SyntheticBackendConfig:
    channel_count: int = 64
    sample_rate_hz: int = 1_000
    sample_mean: float = 0.0
    sample_noise_std: float = 0.05
    spontaneous_spike_rate_hz: float = 2.0
    seed: int = 7


@dataclass(frozen=True, slots=True)
class ReplayBackendConfig:
    path: str
    sample_rate_hz: int | None = None
    metadata_overrides: Mapping[str, object] = field(default_factory=dict)
