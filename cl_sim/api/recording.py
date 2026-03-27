from __future__ import annotations

from dataclasses import dataclass

from cl_sim.storage.jsonl_writer import JsonlRecordingWriter


@dataclass
class RecordingSession:
    path: str
    writer: JsonlRecordingWriter
    active: bool = True

    def close(self) -> None:
        if self.active:
            self.writer.close()
            self.active = False

    def __enter__(self) -> "RecordingSession":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
