from __future__ import annotations

from dataclasses import dataclass

from cl_sim.api.stim import StimOperation
from cl_sim.api.types import StimEvent


@dataclass(frozen=True, slots=True)
class QueuedStim:
    operation: StimOperation
    scheduled_timestamp_us: int
    burst_index: int


class StimQueue:
    def __init__(self) -> None:
        self._items: list[QueuedStim] = []

    def has_pending(self) -> bool:
        return bool(self._items)

    def clear(self) -> int:
        count = len(self._items)
        self._items.clear()
        return count

    def enqueue(self, operation: StimOperation, *, current_timestamp_us: int) -> tuple[QueuedStim, ...]:
        burst_interval_us = (
            int(round(1_000_000 / operation.burst.burst_hz))
            if operation.burst.burst_count > 1 and operation.burst.burst_hz > 0
            else 0
        )
        queued: list[QueuedStim] = []
        for burst_index in range(operation.burst.burst_count):
            queued.append(
                QueuedStim(
                    operation=operation,
                    scheduled_timestamp_us=(
                        current_timestamp_us + operation.lead_time_us + burst_index * burst_interval_us
                    ),
                    burst_index=burst_index,
                )
            )
        self._items.extend(queued)
        self._items.sort(key=lambda item: (item.scheduled_timestamp_us, item.burst_index))
        return tuple(queued)

    def pop_ready(self, *, end_timestamp_us: int) -> tuple[StimEvent, ...]:
        ready: list[QueuedStim] = []
        pending: list[QueuedStim] = []
        for item in self._items:
            if item.scheduled_timestamp_us <= end_timestamp_us:
                ready.append(item)
            else:
                pending.append(item)
        self._items = pending

        events: list[StimEvent] = []
        for item in ready:
            for channel in item.operation.channels:
                events.append(
                    StimEvent(
                        channel=channel,
                        timestamp_us=item.scheduled_timestamp_us,
                        lead_time_us=item.operation.lead_time_us,
                        burst_index=item.burst_index,
                        source="scheduled",
                        phases=item.operation.design.phases,
                    )
                )
        events.sort(key=lambda event: (event.timestamp_us, event.channel, event.burst_index))
        return tuple(events)
