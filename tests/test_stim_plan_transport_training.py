from __future__ import annotations

import unittest

import cl
from cl_sim.training import CL1TrainingSession, ReadoutConfig
from cl_sim.transport import FeedbackPacket, pack_feedback_packet, pack_spike_packet, pack_stim_packet, unpack_feedback_packet, unpack_spike_packet, unpack_stim_packet


class SummingReadout:
    def predict(self, observation) -> float:
        return float(sum(sum(round_values) for round_values in observation.spike_rounds))


class StimPlanTransportTrainingTests(unittest.TestCase):
    def test_stim_plan_freezes_after_first_execution(self) -> None:
        with cl.open(project_conventions=cl.ProjectConventionProfile.repo_default()) as neurons:
            plan = neurons.create_stim_plan()
            plan.add_stim(1, 1.0)
            queued = plan.execute()
            self.assertTrue(queued)
            with self.assertRaises(RuntimeError):
                plan.add_stim(2, 1.0)

    def test_project_transport_packets_round_trip(self) -> None:
        stim_packet = pack_stim_packet(123, [1.0] * 64, [0.5] * 64)
        timestamp_us, frequencies, amplitudes = unpack_stim_packet(stim_packet)
        self.assertEqual(timestamp_us, 123)
        self.assertEqual(frequencies[0], 1.0)
        self.assertEqual(amplitudes[-1], 0.5)

        spike_packet = pack_spike_packet(456, [2.0] * 64)
        spike_timestamp_us, spike_counts = unpack_spike_packet(spike_packet)
        self.assertEqual(spike_timestamp_us, 456)
        self.assertEqual(spike_counts[10], 2.0)

        feedback = FeedbackPacket(
            timestamp_us=789,
            feedback_type="reward",
            channels=(1, 2, 3),
            frequency_hz=20,
            amplitude_ua=1.0,
            pulses=2,
            unpredictable=False,
            event_name="bonus",
        )
        unpacked_feedback = unpack_feedback_packet(pack_feedback_packet(feedback))
        self.assertEqual(unpacked_feedback.feedback_type, "reward")
        self.assertEqual(unpacked_feedback.channels, (1, 2, 3))

    def test_training_session_supports_zero_ablation(self) -> None:
        with cl.open() as neurons:
            session = CL1TrainingSession(neurons, readout=SummingReadout(), config=ReadoutConfig())
            result = session.run_sample(sample_id="sample-1", rounds=2, ablation="zero")
            self.assertEqual(result.prediction, 0.0)
            self.assertTrue(all(all(value == 0.0 for value in round_values) for round_values in result.spike_rounds))


if __name__ == "__main__":
    unittest.main()
