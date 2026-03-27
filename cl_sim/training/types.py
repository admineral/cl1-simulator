from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class ReadoutConfig:
    batch_size: int = 1
    group_norm_recommended: bool = True
    same_frame_encoding: bool = False
    max_readout_width: int = 64

    def __post_init__(self) -> None:
        if self.batch_size != 1:
            raise ValueError("CL1 live interaction should keep batch_size=1.")


@dataclass(frozen=True, slots=True)
class TrainingObservation:
    sample_id: str
    spike_rounds: tuple[tuple[float, ...], ...]
    metadata: Mapping[str, str] = field(default_factory=dict)


class StimPolicy(Protocol):
    def build_round(self, *, sample_id: str, round_index: int) -> object:
        ...


class Readout(Protocol):
    def predict(self, observation: TrainingObservation) -> object:
        ...
