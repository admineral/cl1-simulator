from __future__ import annotations

import unittest

import cl


class LoopAndReadTests(unittest.TestCase):
    def test_loop_exposes_stims_and_spikes_on_same_timeline(self) -> None:
        with cl.open(project_conventions=cl.ProjectConventionProfile.repo_default()) as neurons:
            neurons.stim(1, 1.0)
            tick = next(neurons.loop(max_ticks=1))
            self.assertEqual(tick.timestamp_us, 10_000)
            self.assertGreater(tick.frames.frame_count, 0)
            self.assertTrue(any(stim.channel == 1 for stim in tick.analysis.stims))
            self.assertTrue(any(spike.source == "stim" for spike in tick.analysis.spikes))

    def test_read_blocks_by_advancing_simulated_timeline(self) -> None:
        with cl.open() as neurons:
            chunk = neurons.read(5)
            self.assertEqual(chunk.frame_count, 5)
            self.assertEqual(chunk.channel_count, 64)
            self.assertEqual(chunk.timestamps_us[0], 1_000)
            self.assertEqual(chunk.timestamps_us[-1], 5_000)


if __name__ == "__main__":
    unittest.main()
