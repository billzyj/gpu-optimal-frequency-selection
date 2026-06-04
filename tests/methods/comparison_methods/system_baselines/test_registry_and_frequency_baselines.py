from __future__ import annotations

import unittest

from src.common.experiment.types import (
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    MetricWindow,
    PlatformSpec,
)
from src.methods.registry import resolve_policy, supported_policy_names
from src.methods.comparison_methods.local_reproductions.ali_2022_reimpl import AliFrequencySelectionPolicy
from src.methods.comparison_methods.local_reproductions.everest_reimpl import EverestPolicy
from src.methods.comparison_methods.system_baselines.max_freq import MaxFreqPolicy
from src.methods.comparison_methods.system_baselines.min_freq import MinFreqPolicy


def make_context(policy_name: str) -> ExperimentContext:
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
            policy_name=policy_name,
            workload_name="smoke",
            started_at_utc="2026-06-01T00:00:00Z",
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
        gpu_util_avg_pct=40.0,
        mem_util_avg_pct=20.0,
        graphics_clock_avg_mhz=clock_mhz,
    )


class PolicyRegistryTests(unittest.TestCase):
    def test_registry_resolves_system_baselines_and_oracle(self) -> None:
        self.assertEqual(
            supported_policy_names(),
            ("max_freq", "min_freq", "oracle_static", "everest", "ali_2022_reimpl"),
        )
        self.assertIsInstance(resolve_policy("max_freq"), MaxFreqPolicy)
        self.assertIsInstance(resolve_policy("min_freq"), MinFreqPolicy)
        self.assertIsInstance(resolve_policy("everest"), EverestPolicy)
        self.assertIsInstance(resolve_policy("ali_2022_reimpl"), AliFrequencySelectionPolicy)

    def test_registry_rejects_unknown_policy(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported POLICY_NAME"):
            resolve_policy("missing_policy")


class FrequencyBaselinePolicyTests(unittest.TestCase):
    def test_max_freq_sets_max_once_then_holds(self) -> None:
        policy = MaxFreqPolicy()
        context = make_context("max_freq")
        state = policy.initialize(context, {})

        first = policy.on_window(make_window(1, clock_mhz=900.0), state)
        self.assertEqual(first.action, DecisionAction.SET_CLOCK)
        self.assertEqual(first.target_graphics_clock_mhz, 1410)

        second = policy.on_window(make_window(2, clock_mhz=1410.0), state)
        self.assertEqual(second.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(second.target_graphics_clock_mhz)

        summary = policy.finalize(state)
        self.assertEqual(summary.policy_name, "max_freq")
        self.assertEqual(summary.total_windows, 2)

    def test_min_freq_sets_min_once_then_holds(self) -> None:
        policy = MinFreqPolicy()
        context = make_context("min_freq")
        state = policy.initialize(context, {})

        first = policy.on_window(make_window(1, clock_mhz=1410.0), state)
        self.assertEqual(first.action, DecisionAction.SET_CLOCK)
        self.assertEqual(first.target_graphics_clock_mhz, 210)

        second = policy.on_window(make_window(2, clock_mhz=210.0), state)
        self.assertEqual(second.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(second.target_graphics_clock_mhz)

        summary = policy.finalize(state)
        self.assertEqual(summary.policy_name, "min_freq")
        self.assertEqual(summary.total_windows, 2)


if __name__ == "__main__":
    unittest.main()
