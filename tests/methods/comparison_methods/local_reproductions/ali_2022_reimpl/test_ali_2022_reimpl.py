from __future__ import annotations

import unittest

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


def ali_config(objective: str = "edp") -> dict[str, object]:
    return {
        "objective": objective,
        "frequencies_mhz": [900, 1200, 1500],
        "fp_activity": 1.0,
        "dram_activity": 1.0,
        "t_fmax_s": 1.0,
        "f_max_mhz": 1500,
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
    def test_policy_applies_selected_clock_once_then_holds(self) -> None:
        policy = AliFrequencySelectionPolicy()
        state = policy.initialize(make_context(), ali_config())

        first = policy.on_window(make_window(sequence_id=1, clock_mhz=1500.0), state)
        self.assertEqual(first.action, DecisionAction.SET_CLOCK)
        self.assertEqual(first.target_graphics_clock_mhz, 900)
        self.assertEqual(first.reason_code, "ali_apply_selected_clock")

        second = policy.on_window(make_window(sequence_id=2, clock_mhz=900.0), state)
        self.assertEqual(second.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(second.target_graphics_clock_mhz)
        self.assertEqual(second.reason_code, "ali_hold_selected_clock")

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


if __name__ == "__main__":
    unittest.main()
