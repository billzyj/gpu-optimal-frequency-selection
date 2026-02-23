from __future__ import annotations

import unittest

from src.common.experiment.types import MetricWindow
from src.everest.phase_identification import PhaseIdentifier


def make_window(sequence_id: int, gpu: float, mem: float, duration_s: float = 1.0) -> MetricWindow:
    return MetricWindow(
        sequence_id=sequence_id,
        start_unix_s=float(sequence_id),
        end_unix_s=float(sequence_id) + duration_s,
        duration_s=duration_s,
        sample_count=1,
        gpu_util_avg_pct=gpu,
        mem_util_avg_pct=mem,
        graphics_clock_avg_mhz=1410.0,
    )


class PhaseIdentifierTests(unittest.TestCase):
    def test_stable_window_identification(self) -> None:
        identifier = PhaseIdentifier(window_seconds=3.0, change_threshold_pct=10.0)

        self.assertFalse(identifier.observe(make_window(1, 60.0, 30.0)).is_stable)
        self.assertFalse(identifier.observe(make_window(2, 61.0, 29.0)).is_stable)

        stable = identifier.observe(make_window(3, 59.5, 30.5))
        self.assertTrue(stable.is_stable)
        self.assertTrue(stable.is_new_phase)
        self.assertIsNotNone(stable.phase_id)

        repeated = identifier.observe(make_window(4, 60.0, 30.0))
        self.assertTrue(repeated.is_stable)
        self.assertFalse(repeated.is_new_phase)
        self.assertEqual(stable.phase_id, repeated.phase_id)

    def test_phase_change_on_threshold_crossing(self) -> None:
        identifier = PhaseIdentifier(window_seconds=3.0, change_threshold_pct=10.0)

        for i in range(1, 4):
            first = identifier.observe(make_window(i, 40.0, 20.0))

        self.assertTrue(first.is_stable)
        old_phase_id = first.phase_id

        new_phase_seen = False
        for i in range(4, 9):
            obs = identifier.observe(make_window(i, 70.0, 45.0))
            if obs.is_stable and obs.is_new_phase:
                new_phase_seen = True
                self.assertNotEqual(old_phase_id, obs.phase_id)
                break

        self.assertTrue(new_phase_seen)

    def test_idle_like_and_busy_low_mem_are_distinct(self) -> None:
        identifier = PhaseIdentifier(window_seconds=2.0, change_threshold_pct=10.0)

        identifier.observe(make_window(1, 2.0, 1.0))
        idle_obs = identifier.observe(make_window(2, 2.5, 1.5))
        self.assertTrue(idle_obs.is_stable)
        self.assertTrue(idle_obs.is_idle_like)

        identifier.observe(make_window(3, 55.0, 1.5))
        busy_obs = identifier.observe(make_window(4, 58.0, 1.0))
        self.assertTrue(busy_obs.is_stable)
        self.assertFalse(busy_obs.is_idle_like)
        self.assertNotEqual(idle_obs.phase_id, busy_obs.phase_id)

    def test_small_noise_does_not_trigger_new_phase(self) -> None:
        identifier = PhaseIdentifier(window_seconds=3.0, change_threshold_pct=10.0)

        for i in range(1, 4):
            base_obs = identifier.observe(make_window(i, 50.0, 25.0))
        self.assertTrue(base_obs.is_stable)

        for i, (gpu, mem) in enumerate([(52.0, 24.0), (51.0, 26.0), (53.0, 25.5)], start=4):
            obs = identifier.observe(make_window(i, gpu, mem))
            if obs.is_stable:
                self.assertFalse(obs.is_new_phase)


if __name__ == "__main__":
    unittest.main()
