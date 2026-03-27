from __future__ import annotations

from dataclasses import dataclass

from cl_sim.backends.base import BackendBatch, ReplayBackendConfig
from cl_sim.storage.jsonl_reader import ReplayDataset, load_recording


@dataclass
class ReplayBackend:
    dataset: ReplayDataset
    metadata_overrides: dict[str, object]

    @classmethod
    def from_path(cls, config: ReplayBackendConfig) -> "ReplayBackend":
        dataset = load_recording(config.path)
        return cls(dataset=dataset, metadata_overrides=dict(config.metadata_overrides))

    def __post_init__(self) -> None:
        self.backend_name = "replay"
        self.channel_count = self.dataset.channel_count
        self.frame_interval_us = self.dataset.frame_interval_us
        self.metadata = {
            **dict(self.dataset.metadata),
            **self.metadata_overrides,
            "compatibility_note": (
                "Replay timing and events come from a recording file. Live stim scheduled during "
                "replay is surfaced in loop analysis, but it does not rewrite recorded frames."
            ),
        }

    def advance_interval(
        self,
        *,
        start_timestamp_us: int,
        end_timestamp_us: int,
        delivered_stims,
    ) -> BackendBatch:
        return BackendBatch(
            frames=tuple(
                frame
                for frame in self.dataset.frames
                if start_timestamp_us < frame.timestamp_us <= end_timestamp_us
            ),
            spikes=tuple(
                spike
                for spike in self.dataset.spikes
                if start_timestamp_us < spike.timestamp_us <= end_timestamp_us
            ),
            stims=tuple(
                stim
                for stim in self.dataset.stims
                if start_timestamp_us < stim.timestamp_us <= end_timestamp_us
            ),
            data_streams=tuple(
                record
                for record in self.dataset.data_streams
                if start_timestamp_us < record.timestamp_us <= end_timestamp_us
            ),
        )

    def is_exhausted(self, current_timestamp_us: int) -> bool:
        if not self.dataset.frames and not self.dataset.spikes and not self.dataset.stims:
            return True
        latest_timestamp_us = max(
            [0]
            + [frame.timestamp_us for frame in self.dataset.frames]
            + [spike.timestamp_us for spike in self.dataset.spikes]
            + [stim.timestamp_us for stim in self.dataset.stims]
        )
        return current_timestamp_us >= latest_timestamp_us
