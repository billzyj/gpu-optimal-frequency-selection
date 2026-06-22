from __future__ import annotations

import unittest

from src.common.experiment import StaticPolicy
from src.common.experiment.types import (
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    MetricWindow,
    PlatformSpec,
)
from src.methods.comparison_methods.local_reproductions.oracle_static import (
    StaticOraclePolicy,
    SweepPoint,
    choose_static_oracle_clock,
)


def make_context(
    workload_name: str = "lammps-reaxff",
    pd_target: float = 0.1,
) -> ExperimentContext:
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


def make_window(
    sequence_id: int,
    clock_mhz: float,
    perf_ratio: float | None = None,
) -> MetricWindow:
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
    def test_on_window_is_monitor_only(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(),
            config={
                "workload_profiles": {
                    "lammps-reaxff": [
                        {"frequency_mhz": 1410, "performance_ratio": 1.0},
                        {"frequency_mhz": 1260, "performance_ratio": 0.93},
                        {"frequency_mhz": 1110, "performance_ratio": 0.85},
                    ]
                }
            },
        )

        self.assertEqual(state.get("pre_run_target_graphics_clock_mhz"), 1260)
        self.assertEqual(state.get("profile_mode"), "faithful")
        self.assertEqual(state.get("profile_provenance"), "workload_profiles[lammps-reaxff]")

        # on_window is monitor-only: the fixed clock is applied by
        # initial_decision before window 0, so every window holds.
        first = policy.on_window(make_window(sequence_id=1, clock_mhz=1410.0), state)
        self.assertEqual(first.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(first.target_graphics_clock_mhz)
        self.assertEqual(first.reason_code, "oracle_static_monitor_hold")
        self.assertEqual(first.debug_fields["pre_run_target_graphics_clock_mhz"], 1260)

        second = policy.on_window(make_window(sequence_id=2, clock_mhz=1260.0), state)
        self.assertEqual(second.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(second.target_graphics_clock_mhz)

        summary = policy.finalize(state)
        self.assertEqual(summary.total_windows, 2)
        self.assertEqual(summary.custom_summary["selected_clock_mhz"], 1260)
        self.assertTrue(summary.custom_summary["selection_meets_target"])
        self.assertEqual(summary.custom_summary["profile_mode"], "faithful")
        self.assertEqual(
            summary.custom_summary["profile_provenance"],
            "workload_profiles[lammps-reaxff]",
        )
        self.assertEqual(summary.custom_summary["pre_run_target_graphics_clock_mhz"], 1260)

    def test_initial_decision_applies_selected_clock_before_window_zero(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(),
            config={
                "workload_profiles": {
                    "lammps-reaxff": [
                        {"frequency_mhz": 1410, "performance_ratio": 1.0},
                        {"frequency_mhz": 1260, "performance_ratio": 0.93},
                    ]
                }
            },
        )

        self.assertIsInstance(policy, StaticPolicy)
        decision = policy.initial_decision(make_context(), state)

        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 1260)
        self.assertEqual(decision.reason_code, "oracle_static_pre_run_apply_selected_clock")
        self.assertEqual(decision.debug_fields["profile_mode"], "faithful")
        self.assertEqual(decision.debug_fields["profile_provenance"], "workload_profiles[lammps-reaxff]")
        self.assertEqual(state.get("total_windows"), 0)

    def test_policy_requires_exact_workload_profile_by_default(self) -> None:
        policy = StaticOraclePolicy()
        with self.assertRaisesRegex(ValueError, "exact workload profile"):
            policy.initialize(
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

    def test_policy_allows_default_profile_only_in_proxy_mode(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(workload_name="unknown-workload"),
            config={
                "allow_proxy_profile": True,
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
        # The proxy-mode selection is applied through the pre-run decision.
        decision = policy.initial_decision(make_context(), state)
        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 1200)
        self.assertEqual(decision.debug_fields["profile_mode"], "proxy")

        summary = policy.finalize(state)
        self.assertEqual(summary.custom_summary["profile_mode"], "proxy")
        self.assertEqual(summary.custom_summary["profile_provenance"], "workload_profiles.default")
        self.assertFalse(summary.custom_summary["profile_is_exact_workload"])

    def test_policy_tracks_pd_violations_when_perf_ratio_present(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(pd_target=0.1),
            config={
                "workload_profiles": {
                    "lammps-reaxff": [
                        {"frequency_mhz": 1410, "performance_ratio": 1.0},
                        {"frequency_mhz": 1260, "performance_ratio": 0.92},
                    ]
                }
            },
        )

        policy.on_window(make_window(sequence_id=1, clock_mhz=1410.0, perf_ratio=0.89), state)
        policy.on_window(make_window(sequence_id=2, clock_mhz=1260.0, perf_ratio=0.85), state)
        summary = policy.finalize(state)

        self.assertEqual(summary.pd_violation_count, 2)
        self.assertAlmostEqual(summary.max_pd_violation, 0.05, places=6)

    def test_initialize_rejects_profile_that_misses_target_in_faithful_mode(self) -> None:
        policy = StaticOraclePolicy()
        with self.assertRaisesRegex(ValueError, "does not contain any point meeting"):
            policy.initialize(
                context=make_context(pd_target=0.1),
                config={
                    "workload_profiles": {
                        "lammps-reaxff": [
                            {"frequency_mhz": 1410, "performance_ratio": 0.86},
                            {"frequency_mhz": 1260, "performance_ratio": 0.82},
                        ]
                    }
                },
            )

    def test_proxy_profile_summary_includes_target_audit_fields_when_target_missing(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(pd_target=0.1),
            config={
                "allow_proxy_profile": True,
                "profile": [
                    {"frequency_mhz": 1410, "performance_ratio": 0.86},
                    {"frequency_mhz": 1260, "performance_ratio": 0.82},
                ]
            },
        )

        policy.on_window(make_window(sequence_id=1, clock_mhz=1410.0), state)
        summary = policy.finalize(state)

        self.assertEqual(summary.custom_summary["selected_clock_mhz"], 1410)
        self.assertFalse(summary.custom_summary["selection_meets_target"])
        self.assertIn("target_ratio", summary.custom_summary)
        self.assertIn("selected_profile_performance_ratio", summary.custom_summary)
        self.assertAlmostEqual(summary.custom_summary["target_ratio"], 0.9, places=6)
        self.assertAlmostEqual(
            summary.custom_summary["selected_profile_performance_ratio"],
            0.86,
            places=6,
        )
        self.assertEqual(summary.custom_summary["profile_mode"], "proxy")
        self.assertEqual(summary.custom_summary["profile_provenance"], "profile")

    def test_policy_ignores_points_below_paper_frequency_floor_by_default(self) -> None:
        policy = StaticOraclePolicy()
        state = policy.initialize(
            context=make_context(pd_target=0.1),
            config={
                "workload_profiles": {
                    "lammps-reaxff": [
                        {"frequency_mhz": 1410, "performance_ratio": 1.0},
                        {"frequency_mhz": 930, "performance_ratio": 0.91},
                        {"frequency_mhz": 750, "performance_ratio": 0.96},
                    ]
                }
            },
        )

        summary = policy.finalize(state)
        self.assertEqual(summary.custom_summary["selected_clock_mhz"], 930)
        self.assertEqual(summary.custom_summary["effective_min_frequency_mhz"], 900)
        self.assertEqual(summary.custom_summary["ignored_profile_points_below_floor"], 1)

    def test_initialize_requires_profile(self) -> None:
        policy = StaticOraclePolicy()
        with self.assertRaisesRegex(ValueError, "exact workload profile"):
            policy.initialize(context=make_context(), config={})


if __name__ == "__main__":
    unittest.main()
