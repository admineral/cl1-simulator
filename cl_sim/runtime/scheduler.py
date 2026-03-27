from __future__ import annotations

import os
from pathlib import Path
from time import monotonic
from typing import Mapping

from cl_sim.api.recording import RecordingSession
from cl_sim.api.stim import (
    BurstDesign,
    ChannelSet,
    MIN_LEAD_TIME_US,
    StimDesign,
    StimOperation,
    StimPlan,
    coerce_stim_design,
    validate_stim_operation,
)
from cl_sim.api.types import (
    DataStreamRecord,
    FrameChunk,
    LoopAnalysis,
    LoopControllerMeta,
    LoopTick,
    OpenMetadata,
    ProjectConventionProfile,
)
from cl_sim.backends.base import Backend
from cl_sim.runtime.buffer import TimelineBuffer
from cl_sim.runtime.clock import ClockConfig, LoopPacer
from cl_sim.runtime.stim_queue import StimQueue
from cl_sim.storage.jsonl_writer import JsonlRecordingWriter


class RuntimeEngine:
    def __init__(
        self,
        *,
        backend: Backend,
        clock: ClockConfig,
        loop_interval_us: int,
        history_frame_limit: int = 16_384,
        project_conventions: ProjectConventionProfile | None = None,
    ) -> None:
        self.backend = backend
        self.clock = clock
        self.loop_interval_us = loop_interval_us
        self.project_conventions = project_conventions
        self.metadata = OpenMetadata(
            official_api_compatible=True,
            project_conventions=project_conventions,
            notes=(
                "The public API surface is intentionally aligned to the Cortical Labs Python mental model.",
                "Transport packet schemas, dead-channel masks, and artifact windows remain project-specific.",
            ),
        )
        self.current_timestamp_us = 0
        self._buffer = TimelineBuffer(frame_limit=history_frame_limit)
        self._stim_queue = StimQueue()
        self._pacer = LoopPacer(clock)
        self._read_cursor_us = 0
        self._recording: RecordingSession | None = None

    def create_stim_plan(self) -> StimPlan:
        return StimPlan(self._execute_stim_plan)

    def queue_stim(
        self,
        channels: int | ChannelSet | tuple[int, ...] | list[int],
        design: StimDesign | float | int,
        *,
        burst: BurstDesign | None = None,
        lead_time_us: int = MIN_LEAD_TIME_US,
    ):
        channel_set = channels if isinstance(channels, ChannelSet) else ChannelSet(channels)
        operation = StimOperation(
            channels=channel_set,
            design=coerce_stim_design(design),
            burst=burst or BurstDesign(),
            lead_time_us=lead_time_us,
        )
        warnings = validate_stim_operation(
            operation,
            channel_count=self.backend.channel_count,
            blocked_channels=set(self.project_conventions.dead_channels)
            if self.project_conventions is not None
            else None,
        )
        operation = StimOperation(
            channels=operation.channels,
            design=operation.design,
            burst=operation.burst,
            lead_time_us=operation.lead_time_us,
            warnings=warnings,
        )
        return self._stim_queue.enqueue(operation, current_timestamp_us=self.current_timestamp_us)

    def interrupt(self) -> int:
        cleared = self._stim_queue.clear()
        self.append_data_stream(
            name="control.interrupt",
            payload=f"cleared={cleared}",
            timestamp_us=self.current_timestamp_us,
            attributes={"source": "project-bridge-convention"},
        )
        return cleared

    def interrupt_then_stim(
        self,
        channels: int | ChannelSet | tuple[int, ...] | list[int],
        design: StimDesign | float | int,
        *,
        burst: BurstDesign | None = None,
        lead_time_us: int = MIN_LEAD_TIME_US,
    ):
        self.interrupt()
        return self.queue_stim(
            channels=channels,
            design=design,
            burst=burst,
            lead_time_us=lead_time_us,
        )

    def read(
        self,
        frame_count: int,
        *,
        from_timestamp: int | None = None,
        timeout_s: float | None = None,
    ) -> FrameChunk:
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        start_timestamp = from_timestamp if from_timestamp is not None else self._read_cursor_us + 1
        if start_timestamp < 0:
            raise ValueError("from_timestamp must be non-negative.")

        deadline = None if timeout_s is None else monotonic() + timeout_s
        while True:
            available = self._buffer.read_frames(start_us=start_timestamp, frame_count=frame_count)
            if available:
                self._read_cursor_us = available[-1].timestamp_us
                return FrameChunk.from_frames(available)

            if deadline is not None and monotonic() > deadline:
                raise TimeoutError("Timed out waiting for frames.")

            target_timestamp = max(
                self.current_timestamp_us + self.backend.frame_interval_us,
                start_timestamp + (frame_count - 1) * self.backend.frame_interval_us,
            )
            self._advance_to(target_timestamp)
            if self.backend.is_exhausted(self.current_timestamp_us):
                available = self._buffer.read_frames(start_us=start_timestamp, frame_count=frame_count)
                if not available:
                    raise TimeoutError("Replay backend exhausted before the requested frames were available.")

    def append_data_stream(
        self,
        *,
        name: str,
        payload: str,
        timestamp_us: int | None,
        attributes: Mapping[str, str],
    ) -> DataStreamRecord:
        record = DataStreamRecord(
            name=name,
            timestamp_us=self.current_timestamp_us if timestamp_us is None else timestamp_us,
            payload=payload,
            attributes=dict(attributes),
        )
        self._buffer.append_data_stream(record)
        if self._recording is not None and self._recording.active:
            self._recording.writer.write_data_streams((record,))
        return record

    def start_recording(
        self,
        *,
        path: str | None,
        metadata: Mapping[str, object] | None,
    ) -> RecordingSession:
        if self._recording is not None and self._recording.active:
            raise RuntimeError("A recording session is already active.")
        recording_path = path or str(
            Path(os.getcwd()) / "recordings" / f"cl-sim-{self.current_timestamp_us:012d}.jsonl"
        )
        writer = JsonlRecordingWriter(recording_path)
        writer.write_header(
            metadata={
                "backend": self.backend.backend_name,
                "channel_count": self.backend.channel_count,
                "loop_interval_us": self.loop_interval_us,
                "clock_mode": self.clock.mode,
                "project_conventions": (
                    {
                        "name": self.project_conventions.name,
                        "channel_count": self.project_conventions.channel_count,
                        "dead_channels": list(self.project_conventions.dead_channels),
                        "artifact_window_us": self.project_conventions.artifact_window_us,
                        "transport_schema": self.project_conventions.transport_schema,
                    }
                    if self.project_conventions is not None
                    else None
                ),
                **dict(self.backend.metadata),
                **dict(metadata or {}),
            }
        )
        self._recording = RecordingSession(path=recording_path, writer=writer)
        return self._recording

    def stop_recording(self) -> None:
        if self._recording is not None:
            self._recording.close()
            self._recording = None

    def sync(self, target_timestamp_us: int | None = None) -> int:
        if target_timestamp_us is None:
            target_timestamp_us = self.current_timestamp_us + self.backend.frame_interval_us
        if target_timestamp_us > self.current_timestamp_us:
            self._advance_to(target_timestamp_us)
        return self.current_timestamp_us

    def loop(
        self,
        *,
        max_ticks: int | None = None,
        duration_us: int | None = None,
        interval_us: int | None = None,
    ):
        interval = interval_us or self.loop_interval_us
        iteration = 0
        started_at = self.current_timestamp_us
        while True:
            if max_ticks is not None and iteration >= max_ticks:
                return
            if duration_us is not None and self.current_timestamp_us - started_at >= duration_us:
                return

            target_timestamp = self.current_timestamp_us + interval
            timing = self._pacer.pace(target_device_us=target_timestamp)
            previous_timestamp = self.current_timestamp_us
            self._advance_to(target_timestamp)
            interval_slice = self._buffer.select_interval(
                start_us=previous_timestamp,
                end_us=self.current_timestamp_us,
            )
            iteration += 1
            yield LoopTick(
                iteration=iteration,
                timestamp_us=self.current_timestamp_us,
                frames=FrameChunk.from_frames(interval_slice.frames),
                analysis=LoopAnalysis(
                    spikes=interval_slice.spikes,
                    stims=interval_slice.stims,
                    data_streams=interval_slice.data_streams,
                ),
                controller=LoopControllerMeta(
                    iteration=iteration,
                    mode=self.clock.mode,
                    backend=self.backend.backend_name,
                    expected_interval_us=interval,
                    actual_interval_us=timing.actual_interval_us or interval,
                    sleep_us=timing.sleep_us,
                    jitter_us=timing.jitter_us,
                    buffer_frame_count=self._buffer.frame_count,
                ),
            )
            if (
                self.clock.mode == "replay"
                and self.backend.is_exhausted(self.current_timestamp_us)
                and not self._stim_queue.has_pending()
            ):
                return

    def _advance_to(self, target_timestamp_us: int) -> None:
        if target_timestamp_us <= self.current_timestamp_us:
            return
        ready_stims = self._stim_queue.pop_ready(end_timestamp_us=target_timestamp_us)
        backend_batch = self.backend.advance_interval(
            start_timestamp_us=self.current_timestamp_us,
            end_timestamp_us=target_timestamp_us,
            delivered_stims=ready_stims,
        )
        merged_stims = tuple(sorted(ready_stims + backend_batch.stims, key=lambda item: (item.timestamp_us, item.channel)))
        self._buffer.append_interval(
            frames=backend_batch.frames,
            spikes=backend_batch.spikes,
            stims=merged_stims,
            data_streams=backend_batch.data_streams,
        )
        if self._recording is not None and self._recording.active:
            self._recording.writer.write_frames(backend_batch.frames)
            self._recording.writer.write_spikes(backend_batch.spikes)
            self._recording.writer.write_stims(merged_stims)
            self._recording.writer.write_data_streams(backend_batch.data_streams)
        self.current_timestamp_us = target_timestamp_us

    def _execute_stim_plan(self, operations: tuple[StimOperation, ...]) -> tuple[object, ...]:
        queued = []
        for operation in operations:
            queued.extend(
                self.queue_stim(
                    operation.channels,
                    operation.design,
                    burst=operation.burst,
                    lead_time_us=operation.lead_time_us,
                )
            )
        return tuple(queued)
