from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cl
from cl_sim.storage import load_recording


class RecordingAndReplayTests(unittest.TestCase):
    def test_recording_writes_frames_stims_and_data_streams(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recording_path = Path(tmpdir) / "session.jsonl"
            with cl.open(project_conventions=cl.ProjectConventionProfile.repo_default()) as neurons:
                session = neurons.record(str(recording_path), metadata={"session": "unit-test"})
                stream = neurons.create_data_stream("task.state", attributes={"kind": "annotation"})
                neurons.stim(1, 1.0)
                stream.append("ready")
                next(neurons.loop(max_ticks=1))
                session.close()

            dataset = load_recording(recording_path)
            self.assertTrue(dataset.frames)
            self.assertTrue(any(stim.channel == 1 for stim in dataset.stims))
            self.assertTrue(any(record.name == "task.state" for record in dataset.data_streams))

    def test_replay_backend_preserves_recorded_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            recording_path = Path(tmpdir) / "replay-source.jsonl"
            with cl.open(project_conventions=cl.ProjectConventionProfile.repo_default()) as neurons:
                session = neurons.record(str(recording_path))
                neurons.stim(2, 1.0)
                next(neurons.loop(max_ticks=2))
                session.close()

            with cl.open(replay_path=str(recording_path)) as replay_neurons:
                tick = next(replay_neurons.loop(max_ticks=1))
                self.assertGreater(tick.frames.frame_count, 0)
                self.assertTrue(any(stim.channel == 2 for stim in tick.analysis.stims))
                chunk = replay_neurons.read(3, from_timestamp=1_000)
                self.assertEqual(chunk.frame_count, 3)


if __name__ == "__main__":
    unittest.main()
