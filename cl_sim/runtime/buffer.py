from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from cl_sim.api.types import DataStreamRecord, RawFrame, Spike, StimEvent


@dataclass(frozen=True, slots=True)
class IntervalSlice:
    frames: tuple[RawFrame, ...]
    spikes: tuple[Spike, ...]
    stims: tuple[StimEvent, ...]
    data_streams: tuple[DataStreamRecord, ...]


class TimelineBuffer:
    def __init__(self, *, frame_limit: int = 16_384, event_limit: int = 32_768) -> None:
        self._frames: deque[RawFrame] = deque(maxlen=frame_limit)
        self._spikes: deque[Spike] = deque(maxlen=event_limit)
        self._stims: deque[StimEvent] = deque(maxlen=event_limit)
        self._data_streams: deque[DataStreamRecord] = deque(maxlen=event_limit)

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def append_interval(
        self,
        *,
        frames: tuple[RawFrame, ...],
        spikes: tuple[Spike, ...],
        stims: tuple[StimEvent, ...],
        data_streams: tuple[DataStreamRecord, ...],
    ) -> None:
        self._frames.extend(frames)
        self._spikes.extend(spikes)
        self._stims.extend(stims)
        self._data_streams.extend(data_streams)

    def append_data_stream(self, record: DataStreamRecord) -> None:
        self._data_streams.append(record)

    def select_interval(self, *, start_us: int, end_us: int) -> IntervalSlice:
        return IntervalSlice(
            frames=tuple(frame for frame in self._frames if start_us < frame.timestamp_us <= end_us),
            spikes=tuple(spike for spike in self._spikes if start_us < spike.timestamp_us <= end_us),
            stims=tuple(stim for stim in self._stims if start_us < stim.timestamp_us <= end_us),
            data_streams=tuple(
                record
                for record in self._data_streams
                if start_us < record.timestamp_us <= end_us
            ),
        )

    def read_frames(self, *, start_us: int, frame_count: int) -> tuple[RawFrame, ...]:
        frames = tuple(frame for frame in self._frames if frame.timestamp_us >= start_us)
        if len(frames) < frame_count:
            return ()
        return frames[:frame_count]
