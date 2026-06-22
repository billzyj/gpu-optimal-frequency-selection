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
from src.methods.comparison_methods.local_reproductions.ali_2022_reimpl import (
    AliFrequencyEstimate,
    AliFrequencySelectionPolicy,
    PerformanceModelCoefficients,
    PowerModelCoefficients,
    build_frequency_estimates,
    estimate_power_w,
    estimate_runtime_s,
    select_frequency_by_objective,
)


def make_context() -> ExperimentContext:
    return ExperimentContext(
        platform=PlatformSpec(
            vendor="nvidia",
            gpu_model="A100",
            gpu_count=1,
            min_graphics_clock_mhz=900,
            max_graphics_clock_mhz=1500,
            graphics_clock_step_mhz=300,
        ),
        metadata=ExperimentMetadata(
            run_id="ali-test-run",
            experiment_id="ali-test",
            policy_name="ali_2022_reimpl",
            workload_name="synthetic",
            started_at_utc="2026-06-02T00:00:00Z",
        ),
        pd_target=0.0,
        window_seconds=5.0,
        sampling_interval_ms=1000,
    )


def make_window(sequence_id: int, clock_mhz: float) -> MetricWindow:
    return MetricWindow(
        sequence_id=sequence_id,
        start_unix_s=float(sequence_id),
        end_unix_s=float(sequence_id) + 1.0,
        duration_s=1.0,
        sample_count=1,
        gpu_util_avg_pct=50.0,
        mem_util_avg_pct=30.0,
        graphics_clock_avg_mhz=clock_mhz,
    )


def ali_config(objective: str = "edp", **overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "objective": objective,
        "reproduction_mode": "algorithmic_proxy",
        "frequencies_mhz": [900, 1200, 1500],
        "fp_activity": 1.0,
        "dram_activity": 1.0,
        "t_fmax_s": 1.0,
        "f_max_mhz": 1500,
        "profiling_run_count": 3,
        "sampling_interval_ms": 20,
        "profiler_source": "dcgmi",
        "profile_source": "max-frequency-profile-log",
        "calibration_source": "offline-calibration-fit",
        "power_coefficients": {
            "alpha": 0.0,
            "beta": 0.0,
            "gamma": 0.01,
            "constant": 0.0,
        },
        "performance_coefficients": {
            "beta1": 0.0,
            "beta2": 0.0002,
            "beta3": 0.0,
            "beta4": 0.0,
            "beta5": 0.0,
        },
    }
    config.update(overrides)
    return config


class AliModelEquationTests(unittest.TestCase):
    def test_power_equation_uses_fp_dram_frequency_and_constant_terms(self) -> None:
        coefficients = PowerModelCoefficients(
            alpha=2.0,
            beta=3.0,
            gamma=0.5,
            constant=10.0,
        )

        power_w = estimate_power_w(
            frequency_mhz=100,
            fp_activity=4.0,
            dram_activity=5.0,
            coefficients=coefficients,
        )

        self.assertAlmostEqual(power_w, 83.0, places=6)

    def test_runtime_equation_uses_delta_from_max_frequency(self) -> None:
        coefficients = PerformanceModelCoefficients(
            beta1=0.1,
            beta2=0.01,
            beta3=0.001,
            beta4=0.0001,
            beta5=0.00001,
        )

        runtime_s = estimate_runtime_s(
            frequency_mhz=900,
            f_max_mhz=1000,
            fp_activity=10.0,
            t_fmax_s=2.0,
            coefficients=coefficients,
        )

        self.assertAlmostEqual(runtime_s, 4.3, places=6)

    def test_frequency_estimate_includes_energy_edp_and_ed2p(self) -> None:
        estimates = build_frequency_estimates(
            frequencies_mhz=[1000],
            f_max_mhz=1000,
            fp_activity=10.0,
            dram_activity=5.0,
            t_fmax_s=2.0,
            power_coefficients=PowerModelCoefficients(
                alpha=1.0,
                beta=2.0,
                gamma=0.1,
                constant=10.0,
            ),
            performance_coefficients=PerformanceModelCoefficients(
                beta1=0.0,
                beta2=0.0,
                beta3=0.0,
                beta4=0.0,
                beta5=0.0,
            ),
        )

        self.assertEqual(len(estimates), 1)
        estimate = estimates[0]
        self.assertEqual(estimate.frequency_mhz, 1000)
        self.assertAlmostEqual(estimate.power_w, 130.0, places=6)
        self.assertAlmostEqual(estimate.runtime_s, 2.0, places=6)
        self.assertAlmostEqual(estimate.energy_j, 260.0, places=6)
        self.assertAlmostEqual(estimate.edp, 520.0, places=6)
        self.assertAlmostEqual(estimate.ed2p, 1040.0, places=6)


class AliObjectiveSelectionTests(unittest.TestCase):
    def test_edp_and_ed2p_can_select_different_frequencies(self) -> None:
        estimates = [
            AliFrequencyEstimate(
                frequency_mhz=900,
                power_w=10.0,
                runtime_s=2.0,
                energy_j=20.0,
                edp=40.0,
                ed2p=80.0,
            ),
            AliFrequencyEstimate(
                frequency_mhz=1000,
                power_w=30.0,
                runtime_s=1.3,
                energy_j=39.0,
                edp=50.7,
                ed2p=65.91,
            ),
        ]

        edp_result = select_frequency_by_objective(estimates, objective="edp")
        ed2p_result = select_frequency_by_objective(estimates, objective="ed2p")

        self.assertEqual(edp_result.selected_frequency_mhz, 900)
        self.assertEqual(edp_result.objective, "edp")
        self.assertEqual(ed2p_result.selected_frequency_mhz, 1000)
        self.assertEqual(ed2p_result.objective, "ed2p")


class AliPolicyTests(unittest.TestCase):
    def test_policy_rejects_duplicate_or_unsorted_frequency_candidates(self) -> None:
        policy = AliFrequencySelectionPolicy()

        for frequencies_mhz in ([900, 1200, 1200], [1200, 900, 1500]):
            with self.subTest(frequencies_mhz=frequencies_mhz):
                with self.assertRaisesRegex(ValueError, "strictly increasing"):
                    policy.initialize(
                        make_context(),
                        ali_config(frequencies_mhz=frequencies_mhz),
                    )

    def test_policy_rejects_frequency_candidates_outside_platform_bounds(self) -> None:
        policy = AliFrequencySelectionPolicy()

        with self.assertRaisesRegex(ValueError, "platform graphics clock range"):
            policy.initialize(
                make_context(),
                ali_config(frequencies_mhz=[600, 900, 1500]),
            )

    def test_policy_rejects_frequency_candidates_above_fmax(self) -> None:
        policy = AliFrequencySelectionPolicy()

        with self.assertRaisesRegex(ValueError, "must not exceed f_max_mhz"):
            policy.initialize(
                make_context(),
                ali_config(frequencies_mhz=[900, 1200, 1500], f_max_mhz=1200),
            )

    def test_paper_faithful_mode_requires_fmax_to_match_max_candidate(self) -> None:
        policy = AliFrequencySelectionPolicy()

        with self.assertRaisesRegex(ValueError, "paper_faithful_gv100.*f_max_mhz"):
            policy.initialize(
                make_context(),
                ali_config(
                    reproduction_mode="paper_faithful_gv100",
                    frequencies_mhz=[900, 1200],
                    f_max_mhz=1500,
                ),
            )

    def test_algorithmic_proxy_mode_allows_fmax_above_candidate_max_with_label(self) -> None:
        policy = AliFrequencySelectionPolicy()
        state = policy.initialize(
            make_context(),
            ali_config(frequencies_mhz=[900, 1200], f_max_mhz=1500),
        )

        summary = policy.finalize(state)

        self.assertEqual(state.get("reproduction_mode"), "algorithmic_proxy")
        self.assertEqual(summary.custom_summary["reproduction_mode"], "algorithmic_proxy")
        self.assertEqual(summary.custom_summary["f_max_mhz"], 1500)
        self.assertEqual(summary.custom_summary["frequencies_mhz"], [900, 1200])

    def test_on_window_is_monitor_only(self) -> None:
        policy = AliFrequencySelectionPolicy()
        state = policy.initialize(make_context(), ali_config())

        self.assertEqual(state.get("pre_run_target_graphics_clock_mhz"), 900)
        self.assertTrue(state.get("requires_pre_run_clock"))

        # on_window is monitor-only: the selected whole-workload clock is applied
        # by initial_decision before window 0, so every window holds.
        first = policy.on_window(make_window(sequence_id=1, clock_mhz=1500.0), state)
        self.assertEqual(first.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(first.target_graphics_clock_mhz)
        self.assertEqual(first.reason_code, "ali_monitor_hold")
        self.assertEqual(first.debug_fields["pre_run_target_graphics_clock_mhz"], 900)
        self.assertTrue(first.debug_fields["requires_pre_run_clock"])

        second = policy.on_window(make_window(sequence_id=2, clock_mhz=900.0), state)
        self.assertEqual(second.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(second.target_graphics_clock_mhz)
        self.assertEqual(second.reason_code, "ali_monitor_hold")

    def test_initial_decision_applies_selected_clock_before_window_zero(self) -> None:
        policy = AliFrequencySelectionPolicy()
        state = policy.initialize(make_context(), ali_config())

        self.assertIsInstance(policy, StaticPolicy)
        decision = policy.initial_decision(make_context(), state)

        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 900)
        self.assertEqual(decision.reason_code, "ali_pre_run_apply_selected_clock")
        self.assertEqual(decision.debug_fields["selected_clock_mhz"], 900)
        self.assertEqual(decision.debug_fields["reproduction_mode"], "algorithmic_proxy")
        self.assertEqual(state.get("total_windows"), 0)

    def test_policy_exports_selected_clock_and_objective_in_final_summary(self) -> None:
        policy = AliFrequencySelectionPolicy()
        state = policy.initialize(make_context(), ali_config(objective="edp"))

        policy.on_window(make_window(sequence_id=1, clock_mhz=1500.0), state)
        summary = policy.finalize(state)

        self.assertEqual(summary.policy_name, "ali_2022_reimpl")
        self.assertEqual(summary.total_windows, 1)
        self.assertEqual(summary.custom_summary["selected_clock_mhz"], 900)
        self.assertEqual(summary.custom_summary["objective"], "edp")
        self.assertEqual(summary.custom_summary["model_scope"], "offline_application_level")
        self.assertEqual(summary.custom_summary["reproduction_mode"], "algorithmic_proxy")
        self.assertEqual(summary.custom_summary["profiling_run_count"], 3)
        self.assertEqual(summary.custom_summary["sampling_interval_ms"], 20)
        self.assertEqual(summary.custom_summary["profiler_source"], "dcgmi")
        self.assertEqual(summary.custom_summary["profile_source"], "max-frequency-profile-log")
        self.assertEqual(summary.custom_summary["calibration_source"], "offline-calibration-fit")
        self.assertEqual(summary.custom_summary["pre_run_target_graphics_clock_mhz"], 900)
        self.assertTrue(summary.custom_summary["requires_pre_run_clock"])

    def test_policy_rejects_energy_objective(self) -> None:
        policy = AliFrequencySelectionPolicy()

        with self.assertRaisesRegex(ValueError, "objective must be 'edp' or 'ed2p'"):
            policy.initialize(make_context(), ali_config(objective="energy"))


if __name__ == "__main__":
    unittest.main()
