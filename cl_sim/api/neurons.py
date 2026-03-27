from __future__ import annotations

from typing import Mapping

from cl_sim.api.data_stream import DataStream
from cl_sim.api.recording import RecordingSession
from cl_sim.api.stim import BurstDesign, ChannelSet, MIN_LEAD_TIME_US, StimDesign
from cl_sim.api.types import FrameChunk, OpenMetadata
from cl_sim.runtime.scheduler import RuntimeEngine


class Neurons:
    def __init__(self, engine: RuntimeEngine) -> None:
        self._engine = engine

    def __enter__(self) -> "Neurons":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def metadata(self) -> OpenMetadata:
        return self._engine.metadata

    def close(self) -> None:
        self._engine.stop_recording()

    def timestamp(self) -> int:
        return self._engine.current_timestamp_us

    def loop(self, *, max_ticks: int | None = None, duration_us: int | None = None, interval_us: int | None = None):
        return self._engine.loop(max_ticks=max_ticks, duration_us=duration_us, interval_us=interval_us)

    def stim(
        self,
        channels: int | ChannelSet | tuple[int, ...] | list[int],
        design: StimDesign | float | int,
        burst: BurstDesign | None = None,
        *,
        lead_time_us: int = MIN_LEAD_TIME_US,
    ):
        return self._engine.queue_stim(
            channels=channels,
            design=design,
            burst=burst,
            lead_time_us=lead_time_us,
        )

    def interrupt(self) -> int:
        return self._engine.interrupt()

    def interrupt_then_stim(
        self,
        channels: int | ChannelSet | tuple[int, ...] | list[int],
        design: StimDesign | float | int,
        burst: BurstDesign | None = None,
        *,
        lead_time_us: int = MIN_LEAD_TIME_US,
    ):
        return self._engine.interrupt_then_stim(
            channels=channels,
            design=design,
            burst=burst,
            lead_time_us=lead_time_us,
        )

    def create_stim_plan(self):
        return self._engine.create_stim_plan()

    def read(
        self,
        frame_count: int,
        *,
        from_timestamp: int | None = None,
        timeout_s: float | None = None,
    ) -> FrameChunk:
        return self._engine.read(frame_count, from_timestamp=from_timestamp, timeout_s=timeout_s)

    def record(
        self,
        path: str | None = None,
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> RecordingSession:
        return self._engine.start_recording(path=path, metadata=metadata)

    def create_data_stream(
        self,
        name: str,
        *,
        attributes: Mapping[str, str] | None = None,
    ) -> DataStream:
        return DataStream(name=name, engine=self._engine, attributes=dict(attributes or {}))

    def sync(self, target_timestamp_us: int | None = None) -> int:
        return self._engine.sync(target_timestamp_us=target_timestamp_us)
