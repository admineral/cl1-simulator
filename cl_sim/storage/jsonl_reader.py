from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from cl_sim.api.stim import StimPhase
from cl_sim.api.types import DataStreamRecord, RawFrame, Spike, StimEvent


@dataclass(frozen=True, slots=True)
class ReplayDataset:
    frames: tuple[RawFrame, ...]
    spikes: tuple[Spike, ...]
    stims: tuple[StimEvent, ...]
    data_streams: tuple[DataStreamRecord, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def channel_count(self) -> int:
        if self.frames:
            return len(self.frames[0].samples)
        metadata_count = self.metadata.get("channel_count")
        if isinstance(metadata_count, int):
            return metadata_count
        return 0

    @property
    def frame_interval_us(self) -> int:
        if len(self.frames) < 2:
            return 1_000
        deltas = [
            self.frames[index].timestamp_us - self.frames[index - 1].timestamp_us
            for index in range(1, len(self.frames))
        ]
        return int(median(deltas))


def load_recording(path: str | Path) -> ReplayDataset:
    frames: list[RawFrame] = []
    spikes: list[Spike] = []
    stims: list[StimEvent] = []
    data_streams: list[DataStreamRecord] = []
    metadata: Mapping[str, object] = {}

    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            record: Mapping[str, Any] = json.loads(line)
            record_type = record.get("record_type")
            if record_type == "header":
                metadata = dict(record.get("metadata", {}))
            elif record_type == "frame":
                frames.append(
                    RawFrame(
                        timestamp_us=int(record["timestamp_us"]),
                        samples=tuple(float(value) for value in record["samples"]),
                    )
                )
            elif record_type == "spike":
                spikes.append(
                    Spike(
                        channel=int(record["channel"]),
                        timestamp_us=int(record["timestamp_us"]),
                        samples=tuple(float(value) for value in record["samples"]),
                        source=str(record["source"]),
                    )
                )
            elif record_type == "stim":
                stims.append(
                    StimEvent(
                        channel=int(record["channel"]),
                        timestamp_us=int(record["timestamp_us"]),
                        lead_time_us=int(record["lead_time_us"]),
                        burst_index=int(record["burst_index"]),
                        source=str(record["source"]),
                        phases=tuple(
                            StimPhase(
                                duration_us=int(phase["duration_us"]),
                                current_ua=float(phase["current_ua"]),
                            )
                            for phase in record["phases"]
                        ),
                    )
                )
            elif record_type == "data_stream":
                data_streams.append(
                    DataStreamRecord(
                        name=str(record["name"]),
                        timestamp_us=int(record["timestamp_us"]),
                        payload=str(record["payload"]),
                        attributes={
                            str(key): str(value) for key, value in dict(record["attributes"]).items()
                        },
                    )
                )

    frames.sort(key=lambda frame: frame.timestamp_us)
    spikes.sort(key=lambda spike: (spike.timestamp_us, spike.channel))
    stims.sort(key=lambda stim: (stim.timestamp_us, stim.channel))
    data_streams.sort(key=lambda record: (record.timestamp_us, record.name))
    return ReplayDataset(
        frames=tuple(frames),
        spikes=tuple(spikes),
        stims=tuple(stims),
        data_streams=tuple(data_streams),
        metadata=metadata,
    )
