from __future__ import annotations

import unittest

import cl
from cl_sim.api.stim import BurstDesign, ChannelSet, StimDesign, StimValidationError, StimOperation, validate_stim_operation


class StimValidationTests(unittest.TestCase):
    def test_scalar_shorthand_matches_documented_biphasic_form(self) -> None:
        design = StimDesign.from_scalar_current(1.25)
        self.assertEqual(len(design.phases), 2)
        self.assertEqual(design.phases[0].duration_us, 160)
        self.assertEqual(design.phases[0].current_ua, -1.25)
        self.assertEqual(design.phases[1].current_ua, 1.25)

    def test_dead_channel_is_blocked_by_project_profile(self) -> None:
        with cl.open(project_conventions=cl.ProjectConventionProfile.repo_default()) as neurons:
            with self.assertRaises(StimValidationError):
                neurons.stim(4, 1.0)

    def test_near_limit_values_warn_but_validate(self) -> None:
        warnings = validate_stim_operation(
            StimOperation(
                channels=ChannelSet(1),
                design=StimDesign(1000, -2.8, 1000, 2.8),
                burst=BurstDesign(burst_count=1, burst_hz=0),
                lead_time_us=80,
            ),
            channel_count=64,
        )
        self.assertTrue(any("near the documented limit" in warning for warning in warnings))

    def test_charge_limit_is_enforced(self) -> None:
        with self.assertRaises(StimValidationError):
            validate_stim_operation(
                StimOperation(
                    channels=ChannelSet(1),
                    design=StimDesign(2000, -2.0, 2000, 2.0),
                    burst=BurstDesign(),
                    lead_time_us=80,
                ),
                channel_count=64,
            )


if __name__ == "__main__":
    unittest.main()
