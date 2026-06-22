from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run.control_loop import run_control_loop
from src.common.experiment.types import (
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    MetricWindow,
    PlatformSpec,
)
from src.methods.registry import resolve_policy, supported_policy_names
from src.methods.comparison_methods.local_reproductions.everest_reimpl import EverestPolicy


_PLATFORM = PlatformSpec(
    vendor="nvidia",
    gpu_model="A100",
    gpu_count=1,
    min_graphics_clock_mhz=210,
    max_graphics_clock_mhz=1410,
    graphics_clock_step_mhz=15,
)


def _context(pd_target: float = 0.1) -> ExperimentContext:
    return ExperimentContext(
        platform=_PLATFORM,
        metadata=ExperimentMetadata(
            run_id="everest-test-run",
            experiment_id="everest-test",
            policy_name="everest",
            workload_name="synthetic",
            started_at_utc="2026-06-01T00:00:00Z",
        ),
        pd_target=pd_target,
        window_seconds=1.0,
        sampling_interval_ms=1000,
    )


def _window(
    sequence_id: int,
    *,
    gpu: float = 60.0,
    mem: float = 50.0,
    clock_mhz: float = 1410.0,
    perf_ratio: float | None = None,
) -> MetricWindow:
    custom_metrics = {}
    if perf_ratio is not None:
        custom_metrics["performance_ratio"] = perf_ratio
    return MetricWindow(
        sequence_id=sequence_id,
        start_unix_s=float(sequence_id),
        end_unix_s=float(sequence_id + 1),
        duration_s=1.0,
        sample_count=1,
        gpu_util_avg_pct=gpu,
        mem_util_avg_pct=mem,
        graphics_clock_avg_mhz=clock_mhz,
        custom_metrics=custom_metrics,
    )


class EverestPolicyTests(unittest.TestCase):
    def test_registry_resolves_everest_policy(self) -> None:
        self.assertIn("everest", supported_policy_names())
        self.assertIsInstance(resolve_policy("everest"), EverestPolicy)

    def test_unstable_window_holds_when_already_at_high_frequency(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(
            _context(),
            {"phase_window_seconds": 3.0},
        )

        decision = policy.on_window(_window(0, clock_mhz=1410.0), state)

        self.assertEqual(decision.action, DecisionAction.HOLD_CLOCK)
        self.assertEqual(decision.reason_code, "everest_wait_for_stable_phase")
        self.assertEqual(state.get("unstable_window_count"), 1)

    def test_new_phase_characterization_then_scaled_decision(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(
            _context(pd_target=0.1),
            {
                "phase_window_seconds": 1.0,
                "characterization_low_frequency_ratio": 0.70,
            },
        )

        first = policy.on_window(_window(0, mem=50.0, clock_mhz=1410.0), state)
        self.assertEqual(first.action, DecisionAction.SET_CLOCK)
        self.assertEqual(first.target_graphics_clock_mhz, 990)
        self.assertEqual(first.reason_code, "everest_characterize_low_frequency")
        self.assertIsNotNone(state.get("pending_characterization"))

        second = policy.on_window(_window(1, mem=40.0, clock_mhz=990.0), state)
        self.assertEqual(second.action, DecisionAction.SET_CLOCK)
        self.assertEqual(second.reason_code, "everest_apply_new_characterization")
        self.assertIsNone(state.get("pending_characterization"))
        self.assertEqual(state.get("characterization_count"), 1)
        self.assertEqual(len(state.get("phase_cache")), 1)
        self.assertLess(second.target_graphics_clock_mhz, 1410)
        self.assertGreaterEqual(second.target_graphics_clock_mhz, 900)
        self.assertEqual(second.target_graphics_clock_mhz % 15, 0)

        cached_phase_id = next(iter(state.get("phase_cache")))
        cached = state.get("phase_cache")[cached_phase_id]
        self.assertAlmostEqual(cached["fs"], 0.5892857142857142, places=6)

    def test_cached_phase_reuses_characterization(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(_context(), {"phase_window_seconds": 1.0})

        policy.on_window(_window(0, mem=50.0, clock_mhz=1410.0), state)
        policy.on_window(_window(1, mem=40.0, clock_mhz=990.0), state)
        before = int(state.get("characterization_count"))

        third = policy.on_window(_window(2, mem=50.0, clock_mhz=1155.0), state)

        self.assertEqual(third.reason_code, "everest_apply_cached_phase")
        self.assertEqual(state.get("characterization_count"), before)
        self.assertGreaterEqual(state.get("cache_hit_count"), 1)

    def test_pd_violation_tracking_uses_performance_ratio_metric(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(_context(pd_target=0.1), {"phase_window_seconds": 1.0})

        policy.on_window(_window(0, perf_ratio=0.80), state)
        summary = policy.finalize(state)

        self.assertEqual(summary.pd_violation_count, 1)
        self.assertAlmostEqual(summary.max_pd_violation, 0.10, places=6)


class EverestPaperFidelityTests(unittest.TestCase):
    """Guardrails for the paper-faithful EVeREST reimplementation."""

    def test_stable_phase_below_high_collects_high_window_before_low_probe(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(_context(pd_target=0.1), {"phase_window_seconds": 1.0})

        decision = policy.on_window(_window(0, mem=50.0, clock_mhz=1200.0), state)

        self.assertEqual(decision.reason_code, "everest_collect_high_frequency")
        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 1410)
        self.assertEqual(state.get("pending_characterization")["stage"], "capture_high")
        self.assertNotIn("characterization_deferred_count", state.data)

    def test_high_window_capture_then_starts_low_probe(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(
            _context(pd_target=0.1),
            {"phase_window_seconds": 1.0, "characterization_low_frequency_ratio": 0.70},
        )

        policy.on_window(_window(0, mem=50.0, clock_mhz=1200.0), state)
        decision = policy.on_window(_window(1, mem=55.0, clock_mhz=1410.0), state)

        self.assertEqual(decision.reason_code, "everest_characterize_low_frequency")
        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 990)
        pending = state.get("pending_characterization")
        self.assertEqual(pending["stage"], "capture_low")
        self.assertAlmostEqual(pending["mem_high"], 55.0, places=6)

    def test_probe_window_deferred_when_observed_clock_misses_low_target(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(
            _context(pd_target=0.1),
            {"phase_window_seconds": 1.0, "characterization_low_frequency_ratio": 0.70},
        )

        policy.on_window(_window(0, mem=50.0, clock_mhz=1410.0), state)
        decision = policy.on_window(_window(1, mem=45.0, clock_mhz=1200.0), state)

        self.assertEqual(decision.reason_code, "everest_defer_characterization_clock_mismatch")
        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 1410)
        self.assertIsNone(state.get("pending_characterization"))
        self.assertEqual(state.get("characterization_count"), 0)
        self.assertEqual(len(state.get("phase_cache")), 0)

    def test_probe_window_with_gpu_util_change_is_deferred_without_cache(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(
            _context(pd_target=0.1),
            {"phase_window_seconds": 1.0, "change_threshold_pct": 10.0},
        )

        policy.on_window(_window(0, gpu=60.0, mem=50.0, clock_mhz=1410.0), state)
        decision = policy.on_window(_window(1, gpu=80.0, mem=40.0, clock_mhz=990.0), state)

        self.assertEqual(decision.reason_code, "everest_defer_characterization_phase_drift")
        self.assertEqual(decision.action, DecisionAction.SET_CLOCK)
        self.assertEqual(decision.target_graphics_clock_mhz, 1410)
        self.assertEqual(state.get("characterization_count"), 0)
        self.assertEqual(len(state.get("phase_cache")), 0)

    def test_zero_memory_phase_stays_uncharacterized_at_high_frequency(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(_context(pd_target=0.1), {"phase_window_seconds": 1.0})

        decision = policy.on_window(_window(0, gpu=60.0, mem=0.0, clock_mhz=1410.0), state)

        self.assertEqual(decision.reason_code, "everest_wait_for_characterizable_phase")
        self.assertEqual(decision.action, DecisionAction.HOLD_CLOCK)
        self.assertIsNone(decision.target_graphics_clock_mhz)
        self.assertIsNone(state.get("pending_characterization"))
        self.assertEqual(state.get("characterization_count"), 0)
        self.assertEqual(len(state.get("phase_cache")), 0)

    def test_finalize_omits_non_paper_robustness_counters(self) -> None:
        policy = EverestPolicy()
        state = policy.initialize(_context(), {"phase_window_seconds": 1.0})

        summary = policy.finalize(state)

        self.assertNotIn("characterization_deferred_count", summary.custom_summary)
        self.assertNotIn("characterization_abandoned_count", summary.custom_summary)
        self.assertNotIn("characterization_settle_retry_count", summary.custom_summary)


class EverestRunnerIntegrationTests(unittest.TestCase):
    def test_runner_accepts_everest_policy_and_writes_summary(self) -> None:
        policy = resolve_policy("everest")
        context = _context()
        windows = [
            _window(0, mem=50.0, clock_mhz=1410.0),
            _window(1, mem=40.0, clock_mhz=990.0),
            _window(2, mem=50.0, clock_mhz=1155.0),
        ]

        def _window_builder(ctx: ExperimentContext, window_index: int) -> MetricWindow:
            _ = ctx
            return windows[window_index]

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            summary = run_control_loop(
                policy=policy,
                context=context,
                policy_config={"phase_window_seconds": 1.0},
                run_dir=run_dir,
                control_log=run_dir / "control_loop.log",
                decisions_csv=run_dir / "control" / "decisions.csv",
                state_path=run_dir / "control" / "policy_state.json",
                decision_path=run_dir / "control" / "last_decision.json",
                window_seconds=1.0,
                max_windows=len(windows),
                window_builder=_window_builder,
                sleep_fn=lambda _seconds: None,
            )

            self.assertEqual(summary.policy_name, "everest")
            self.assertEqual(summary.total_windows, 3)
            summary_path = run_dir / "control" / "final_summary.json"
            payload = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["policy_name"], "everest")
            self.assertEqual(payload["custom_summary"]["characterized_phase_count"], 1)


if __name__ == "__main__":
    unittest.main()
