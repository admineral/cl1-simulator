from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from cl_sim.api.types import DataStreamRecord

if TYPE_CHECKING:
    from cl_sim.runtime.scheduler import RuntimeEngine


@dataclass
class DataStream:
    name: str
    engine: "RuntimeEngine"
    attributes: Mapping[str, str]

    def append(
        self,
        payload: str,
        *,
        timestamp_us: int | None = None,
        attributes: Mapping[str, str] | None = None,
    ) -> DataStreamRecord:
        merged_attributes = {**self.attributes, **(attributes or {})}
        return self.engine.append_data_stream(
            name=self.name,
            payload=payload,
            timestamp_us=timestamp_us,
            attributes=merged_attributes,
        )
