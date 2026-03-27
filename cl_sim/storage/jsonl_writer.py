from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from cl_sim.api.types import DataStreamRecord, RawFrame, Spike, StimEvent


class JsonlRecordingWriter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")

    def write_header(self, *, metadata: Mapping[str, object]) -> None:
        self._write({"record_type": "header", "metadata": dict(metadata)})

    def write_frames(self, frames: tuple[RawFrame, ...]) -> None:
        for frame in frames:
            self._write(
                {
                    "record_type": "frame",
                    "timestamp_us": frame.timestamp_us,
                    "samples": list(frame.samples),
                }
            )

    def write_spikes(self, spikes: tuple[Spike, ...]) -> None:
        for spike in spikes:
            self._write(
                {
                    "record_type": "spike",
                    "channel": spike.channel,
                    "timestamp_us": spike.timestamp_us,
                    "samples": list(spike.samples),
                    "source": spike.source,
                }
            )

    def write_stims(self, stims: tuple[StimEvent, ...]) -> None:
        for stim in stims:
            self._write(
                {
                    "record_type": "stim",
                    "channel": stim.channel,
                    "timestamp_us": stim.timestamp_us,
                    "lead_time_us": stim.lead_time_us,
                    "burst_index": stim.burst_index,
                    "source": stim.source,
                    "phases": [
                        {"duration_us": phase.duration_us, "current_ua": phase.current_ua}
                        for phase in stim.phases
                    ],
                }
            )

    def write_data_streams(self, records: tuple[DataStreamRecord, ...]) -> None:
        for record in records:
            self._write(
                {
                    "record_type": "data_stream",
                    "name": record.name,
                    "timestamp_us": record.timestamp_us,
                    "payload": record.payload,
                    "attributes": dict(record.attributes),
                }
            )

    def write_event(self, *, event_type: str, payload: Mapping[str, object]) -> None:
        self._write({"record_type": "event", "event_type": event_type, "payload": dict(payload)})

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def _write(self, record: Mapping[str, object]) -> None:
        self._handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._handle.flush()
