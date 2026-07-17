from __future__ import annotations

import unittest

from src.common.experiment import (
    ExperimentContext,
    ExperimentMetadata,
    PerformanceTarget,
    PerformanceTargetType,
    PlatformSpec,
    relative_performance_loss_to_runtime_slowdown,
    runtime_slowdown_to_relative_performance_loss,
)


def _context(**overrides: object) -> ExperimentContext:
    values = {
        "platform": PlatformSpec(
            vendor="nvidia",
            gpu_model="TestGPU",
            gpu_count=1,
            min_graphics_clock_mhz=210,
            max_graphics_clock_mhz=1410,
            graphics_clock_step_mhz=15,
        ),
        "metadata": ExperimentMetadata(
            run_id="target-test",
            experiment_id="target-test",
            policy_name="test",
            workload_name="synthetic",
            started_at_utc="2026-07-17T00:00:00Z",
        ),
        "pd_target": 0.1,
        "window_seconds": 5.0,
        "sampling_interval_ms": 1000,
    }
    values.update(overrides)
    return ExperimentContext(**values)  # type: ignore[arg-type]


class PerformanceTargetConversionTests(unittest.TestCase):
    def test_runtime_slowdown_converts_to_relative_loss_and_minimum_ratio(self) -> None:
        target = PerformanceTarget(PerformanceTargetType.RUNTIME_SLOWDOWN, 0.1)

        self.assertAlmostEqual(target.runtime_slowdown or 0.0, 0.1, places=12)
        self.assertAlmostEqual(target.relative_performance_loss or 0.0, 1.0 / 11.0, places=12)
        self.assertAlmostEqual(target.minimum_performance_ratio or 0.0, 10.0 / 11.0, places=12)

    def test_relative_loss_round_trips_through_runtime_slowdown(self) -> None:
        slowdown = relative_performance_loss_to_runtime_slowdown(0.1)

        self.assertAlmostEqual(slowdown, 1.0 / 9.0, places=12)
        self.assertAlmostEqual(
            runtime_slowdown_to_relative_performance_loss(slowdown),
            0.1,
            places=12,
        )

    def test_none_has_no_normalized_constraint(self) -> None:
        target = PerformanceTarget(PerformanceTargetType.NONE, 0.0)

        self.assertIsNone(target.runtime_slowdown)
        self.assertIsNone(target.relative_performance_loss)
        self.assertIsNone(target.minimum_performance_ratio)

    def test_invalid_values_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "runtime_slowdown"):
            PerformanceTarget(PerformanceTargetType.RUNTIME_SLOWDOWN, -0.1)
        with self.assertRaisesRegex(ValueError, "relative_performance_loss"):
            PerformanceTarget(PerformanceTargetType.RELATIVE_PERFORMANCE_LOSS, 1.0)
        with self.assertRaisesRegex(ValueError, "raw_value=0.0"):
            PerformanceTarget(PerformanceTargetType.NONE, 0.1)


class ExperimentContextCompatibilityTests(unittest.TestCase):
    def test_direct_construction_keeps_historical_relative_loss_default(self) -> None:
        context = _context(pd_target=0.1)

        self.assertEqual(
            context.performance_target_type,
            PerformanceTargetType.RELATIVE_PERFORMANCE_LOSS,
        )
        self.assertAlmostEqual(context.relative_performance_loss or 0.0, 0.1, places=12)
        self.assertAlmostEqual(context.minimum_performance_ratio or 0.0, 0.9, places=12)
        self.assertAlmostEqual(context.performance_target_ratio or 0.0, 0.9, places=12)

    def test_context_accepts_stable_string_spelling_and_normalizes_to_enum(self) -> None:
        context = _context(
            pd_target=0.1,
            performance_target_type="runtime_slowdown",
        )

        self.assertEqual(context.performance_target_type, PerformanceTargetType.RUNTIME_SLOWDOWN)
        self.assertAlmostEqual(context.require_relative_performance_loss(), 1.0 / 11.0, places=12)
        self.assertAlmostEqual(context.require_minimum_performance_ratio(), 10.0 / 11.0, places=12)

    def test_none_cannot_be_required_by_a_constrained_policy(self) -> None:
        context = _context(
            pd_target=0.0,
            performance_target_type=PerformanceTargetType.NONE,
        )

        with self.assertRaisesRegex(ValueError, "requires a performance target"):
            context.require_relative_performance_loss()
        with self.assertRaisesRegex(ValueError, "requires a performance target"):
            context.require_minimum_performance_ratio()


if __name__ == "__main__":
    unittest.main()
