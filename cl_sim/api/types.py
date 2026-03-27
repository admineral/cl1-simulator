from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping


@dataclass(frozen=True, slots=True)
class RawFrame:
    timestamp_us: int
    samples: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class FrameChunk:
    timestamps_us: tuple[int, ...]
    samples: tuple[tuple[float, ...], ...]

    @classmethod
    def from_frames(cls, frames: tuple[RawFrame, ...]) -> "FrameChunk":
        return cls(
            timestamps_us=tuple(frame.timestamp_us for frame in frames),
            samples=tuple(frame.samples for frame in frames),
        )

    @classmethod
    def empty(cls) -> "FrameChunk":
        return cls(timestamps_us=(), samples=())

    @property
    def frame_count(self) -> int:
        return len(self.timestamps_us)

    @property
    def channel_count(self) -> int:
        if not self.samples:
            return 0
        return len(self.samples[0])


@dataclass(frozen=True, slots=True)
class Spike:
    channel: int
    timestamp_us: int
    samples: tuple[float, ...]
    source: Literal["synthetic", "stim", "replay"]


@dataclass(frozen=True, slots=True)
class StimEvent:
    channel: int
    timestamp_us: int
    lead_time_us: int
    burst_index: int
    source: Literal["scheduled", "replay"]
    phases: tuple["StimPhase", ...]


@dataclass(frozen=True, slots=True)
class DataStreamRecord:
    name: str
    timestamp_us: int
    payload: str
    attributes: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LoopAnalysis:
    spikes: tuple[Spike, ...]
    stims: tuple[StimEvent, ...]
    data_streams: tuple[DataStreamRecord, ...]


@dataclass(frozen=True, slots=True)
class LoopControllerMeta:
    iteration: int
    mode: Literal["wall", "simulated", "replay"]
    backend: str
    expected_interval_us: int
    actual_interval_us: int
    sleep_us: int
    jitter_us: int
    buffer_frame_count: int


@dataclass(frozen=True, slots=True)
class LoopTick:
    iteration: int
    timestamp_us: int
    frames: FrameChunk
    analysis: LoopAnalysis
    controller: LoopControllerMeta


@dataclass(frozen=True, slots=True)
class ProjectConventionProfile:
    """Project-specific bridge conventions, not official Cortical Labs API semantics."""

    name: str = "repo-cl1-bridge"
    channel_count: int = 64
    dead_channels: tuple[int, ...] = (0, 4, 7, 56, 63)
    artifact_window_us: int = 50_000
    transport_schema: str = "udp:uint64-ts|float32[64]-freq|float32[64]-amp"

    @classmethod
    def repo_default(cls) -> "ProjectConventionProfile":
        return cls()

    @property
    def stimmable_channels(self) -> tuple[int, ...]:
        dead = set(self.dead_channels)
        return tuple(channel for channel in range(self.channel_count) if channel not in dead)


@dataclass(frozen=True, slots=True)
class OpenMetadata:
    official_api_compatible: bool
    project_conventions: ProjectConventionProfile | None
    notes: tuple[str, ...] = ()


from .stim import StimPhase  # noqa: E402
