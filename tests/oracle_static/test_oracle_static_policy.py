from __future__ import annotations

import unittest

from src.common.experiment.types import (
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    MetricWindow,
    PlatformSpec,
)
from src.methods.reimplemented_methods.oracle_static import StaticOraclePolicy, SweepPoint, choose_static_oracle_clock


def make_context(workload_name: str = "lammps-reaxff", pd_target: float = 0.1) -> ExperimentContext:
    return ExperimentContext(
        platform=PlatformSpec(
            vendor="nvidia",
            gpu_model="A100",
            gpu_count=1,
            min_graphics_clock_mhz=210,
            max_graphics_clock_mhz=1410,
            graphics_clock_step_mhz=15,
        ),
        metadata=ExperimentMetadata(
            run_id="run-001",
            experiment_id="exp-001",
            policy_name="oracle_static",
            workload_name=workload_name,
            started_at_utc="2026-02-23T00:00:00Z",
        ),
        pd_target=pd_target,
        window_seconds=5.0,
        sampling_interval_ms=1000,
    )


def make_window(sequence_id: int, clock_mhz: float, perf_ratio: float | None = None) -> MetricWindow:
    custom_metrics: dict[str, float] = {}
    if perf_ratio is not None:
        custom_metrics["relative_performance"] = perf_ratio
    return MetricWindow(
        sequence_id=sequence_id,
        start_unix_s=float(sequence_id),
        end_unix_s=float(sequence_id) + 1.0,
        duration_s=1.0,
        sample_count=1,
        gpu_util_avg_pct=50.0,
        mem_util_avg_pct=30.0,
        graphics_clock_avg_mhz=clock_mhz,
        custom_metrics=custom_metrics,
    )


class StaticOracleSelectorTests(unittest.TestCase):
    def test_choose_lowest_frequency_meeting_target(self) -> None:
        selected_clock, meets_target = choose_static_oracle_clock(
            sweep_points=[
                SweepPoint(frequency_mhz=1410, performance_ratio=1.0),
                SweepPoint(frequency_mhz=1260, performance_ratio=0.95),
                SweepPoint(frequency_mhz=1110, performance_ratio=0.88),
            ],
            pd_target=0.1,
        )

        self.assertTrue(meets_target)
        self.assertEqual(selected_clock, 1260)

    def test_fallback_when_target_not_reachable(self) -> None:
        selected_clock, meets_target = choose_static_oracle_clock(
            sweep_points=[
                SweepPoint(frequency_mhz=1410, performance_ratio=0.85),
                SweepPoint(frequency_mhz=1260, performance_ratio=0.81),
                SweepPoint(frequency_mhz=1110, performance_ratio=0.74),
            ],
            pd_target=0.1,
        )

        self.assertFalse(meets_target)
        self.assertEqual(selected_clock, 1410)


class StaticOraclePolicyTests(unittest.TestCase):
    def test_policy_sets_once_then_holds(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(),
            config={
                "profile": [
                    {"frequency_mhz": 1410, "performance_ratio": 1.0},
                    {"frequency_mhz": 1260, "performance_ratio": 0.93},
                    {"frequency_mhz": 1110, "performance_ratio": 0.85},
                ]
            },
        )

        first = policy.on_window(make_window(sequence_id=1, clock_mhz=1410.0), state)
        self.assertEqual(first.action, DecisionAction.SET_CLOCK)
        self.assertEqual(first.target_graphics_clock_mhz, 1260)

        second = policy.on_window(make_window(sequence_id=2, clock_mhz=1260.0), state)
        self.assertEqual(second.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(second.target_graphics_clock_mhz)

        summary = policy.finalize(state)
        self.assertEqual(summary.total_windows, 2)
        self.assertEqual(summary.custom_summary["selected_clock_mhz"], 1260)
        self.assertTrue(summary.custom_summary["selection_meets_target"])

    def test_policy_uses_workload_specific_profile_with_default_fallback(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(workload_name="unknown-workload"),
            config={
                "workload_profiles": {
                    "lammps-reaxff": [
                        {"frequency_mhz": 1410, "performance_ratio": 1.0},
                        {"frequency_mhz": 1260, "performance_ratio": 0.92},
                    ],
                    "default": [
                        {"frequency_mhz": 1410, "performance_ratio": 1.0},
                        {"frequency_mhz": 1200, "performance_ratio": 0.91},
                    ],
                }
            },
        )
        decision = policy.on_window(make_window(sequence_id=1, clock_mhz=1410.0), state)
        self.assertEqual(decision.target_graphics_clock_mhz, 1200)

    def test_policy_tracks_pd_violations_when_perf_ratio_present(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(pd_target=0.1),
            config={
                "profile": [
                    {"frequency_mhz": 1410, "performance_ratio": 1.0},
                    {"frequency_mhz": 1260, "performance_ratio": 0.92},
                ]
            },
        )

        policy.on_window(make_window(sequence_id=1, clock_mhz=1410.0, perf_ratio=0.89), state)
        policy.on_window(make_window(sequence_id=2, clock_mhz=1260.0, perf_ratio=0.85), state)
        summary = policy.finalize(state)

        self.assertEqual(summary.pd_violation_count, 2)
        self.assertAlmostEqual(summary.max_pd_violation, 0.05, places=6)

    def test_initialize_requires_profile(self) -> None:
        policy = StaticOraclePolicy()
        with self.assertRaises(ValueError):
            policy.initialize(context=make_context(), config={})


if __name__ == "__main__":
    unittest.main()
