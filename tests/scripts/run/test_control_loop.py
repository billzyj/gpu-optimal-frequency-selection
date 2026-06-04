"""Integration tests for scripts/run/control_loop.py.

These tests call ``run_control_loop`` directly (no subprocess) and use
``sleep_fn=lambda _: None`` so they never actually sleep.
``APPLY_CLOCK_CMD_TEMPLATE`` is intentionally left unset, so ``apply_decision``
stays in dry-run mode and writes no real clock commands.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run.control_loop import ControlLoopAbortError, run_control_loop
from scripts.run.control_runtime import build_window
from src.common.experiment.types import (
    ExperimentContext,
    ExperimentMetadata,
    PlatformSpec,
)
from src.methods.registry import resolve_policy


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_PLATFORM = PlatformSpec(
    vendor="nvidia",
    gpu_model="TestGPU",
    gpu_count=1,
    min_graphics_clock_mhz=210,
    max_graphics_clock_mhz=1410,
    graphics_clock_step_mhz=15,
)

_METADATA = ExperimentMetadata(
    run_id="test-run-001",
    experiment_id="test-exp",
    policy_name="max_freq",
    workload_name="synthetic",
    started_at_utc="2026-01-01T00:00:00Z",
)


def _make_context() -> ExperimentContext:
    """Returns a deterministic ExperimentContext suitable for all test cases."""
    return ExperimentContext(
        platform=_PLATFORM,
        metadata=_METADATA,
        pd_target=0.05,
        window_seconds=5.0,
        sampling_interval_ms=1000,
    )


def _make_paths(run_dir: Path) -> dict[str, Path]:
    """Returns the four canonical artifact paths derived from *run_dir*.

    The layout matches what ``control_loop.main()`` uses.
    """
    return {
        "control_log": run_dir / "control_loop.log",
        "decisions_csv": run_dir / "control" / "decisions.csv",
        "state_path": run_dir / "control" / "policy_state.json",
        "decision_path": run_dir / "control" / "last_decision.json",
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestControlLoopStatePersistsAcrossWindows(unittest.TestCase):
    """State initialized once and kept in memory for the full run."""

    def test_state_persists_across_windows(self) -> None:
        context = _make_context()
        policy = resolve_policy("max_freq")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            paths = _make_paths(run_dir)

            summary = run_control_loop(
                policy=policy,
                context=context,
                policy_config={},
                run_dir=run_dir,
                control_log=paths["control_log"],
                decisions_csv=paths["decisions_csv"],
                state_path=paths["state_path"],
                decision_path=paths["decision_path"],
                window_seconds=5.0,
                max_windows=4,
                sleep_fn=lambda _seconds: None,
                window_builder=build_window,
            )

            # The returned summary must reflect all 4 windows.
            self.assertEqual(summary.total_windows, 4)

            # The final_summary.json must exist under <run_dir>/control/.
            summary_path = run_dir / "control" / "final_summary.json"
            self.assertTrue(summary_path.exists(), "final_summary.json was not written")

            data = json.loads(summary_path.read_text(encoding="utf-8"))

            # Core FinalSummary fields must be present and correct.
            self.assertEqual(data["total_windows"], 4)
            self.assertIn("generated_at_utc", data)
            self.assertIn("policy_name", data)
            self.assertIn("run_id", data)
            self.assertIn("pd_target", data)
            self.assertIn("pd_violation_count", data)
            self.assertIn("max_pd_violation", data)
            self.assertIn("custom_summary", data)
            self.assertTrue(paths["decisions_csv"].exists(), "control decisions CSV was not written")

            manifest_path = run_dir / "control" / "run_manifest.json"
            self.assertTrue(manifest_path.exists(), "run_manifest.json was not written")
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["run"]["run_id"], "test-run-001")
            self.assertEqual(manifest["run"]["policy_name"], "max_freq")
            self.assertIn("policy_config_sha256", manifest)
            self.assertIn("repository", manifest)


class TestControlLoopSingleWindowFailureIsTolerated(unittest.TestCase):
    """A single failing window is logged and the loop continues."""

    def test_single_window_failure_is_tolerated(self) -> None:
        context = _make_context()
        policy = resolve_policy("max_freq")

        def _window_builder(ctx: ExperimentContext, window_index: int):
            if window_index == 1:
                raise ValueError("injected")
            return build_window(ctx, window_index)

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            paths = _make_paths(run_dir)

            # Must not raise even though window 1 raises.
            summary = run_control_loop(
                policy=policy,
                context=context,
                policy_config={},
                run_dir=run_dir,
                control_log=paths["control_log"],
                decisions_csv=paths["decisions_csv"],
                state_path=paths["state_path"],
                decision_path=paths["decision_path"],
                window_seconds=5.0,
                max_windows=4,
                sleep_fn=lambda _seconds: None,
                window_builder=_window_builder,
            )

            # Windows 0, 2, 3 should have succeeded (window 1 failed and was
            # skipped, but window_index still advanced past it).
            self.assertEqual(summary.total_windows, 3)

            # final_summary.json must still be written.
            summary_path = run_dir / "control" / "final_summary.json"
            self.assertTrue(summary_path.exists(), "final_summary.json was not written")

            # The control log must record the failure.
            log_text = paths["control_log"].read_text(encoding="utf-8")
            self.assertIn("failed", log_text)
            # The failing window index (1) should appear in the log.
            self.assertIn("1", log_text)


class TestControlLoopAbortsAfterMaxConsecutiveFailures(unittest.TestCase):
    """The loop aborts early when consecutive failures reach the threshold."""

    def test_aborts_after_max_consecutive_failures(self) -> None:
        context = _make_context()
        policy = resolve_policy("max_freq")

        def _always_raise(ctx: ExperimentContext, window_index: int):
            raise RuntimeError("always failing")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            paths = _make_paths(run_dir)

            summary = run_control_loop(
                policy=policy,
                context=context,
                policy_config={},
                run_dir=run_dir,
                control_log=paths["control_log"],
                decisions_csv=paths["decisions_csv"],
                state_path=paths["state_path"],
                decision_path=paths["decision_path"],
                window_seconds=5.0,
                max_windows=100,
                max_consecutive_failures=3,
                sleep_fn=lambda _seconds: None,
                window_builder=_always_raise,
            )

            # on_window was never called (every window_builder call failed), so
            # total_windows stays at 0.
            self.assertEqual(summary.total_windows, 0)

            # finalize was still called and the summary file exists.
            summary_path = run_dir / "control" / "final_summary.json"
            self.assertTrue(summary_path.exists(), "final_summary.json was not written after abort")

            # The control log must mention that the loop is aborting.
            log_text = paths["control_log"].read_text(encoding="utf-8")
            self.assertIn("aborting", log_text)

            summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_data["control_status"], "aborted")
            self.assertEqual(summary_data["window_failure_count"], 3)
            self.assertEqual(summary_data["max_consecutive_failures_observed"], 3)
            self.assertEqual(summary_data["consecutive_failure_limit"], 3)
            self.assertIn("max_consecutive_failures_reached", summary_data["abort_reason"])

    def test_raise_on_abort_preserves_final_summary(self) -> None:
        context = _make_context()
        policy = resolve_policy("max_freq")

        def _always_raise(ctx: ExperimentContext, window_index: int):
            raise RuntimeError("always failing")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            paths = _make_paths(run_dir)

            with self.assertRaises(ControlLoopAbortError):
                run_control_loop(
                    policy=policy,
                    context=context,
                    policy_config={},
                    run_dir=run_dir,
                    control_log=paths["control_log"],
                    decisions_csv=paths["decisions_csv"],
                    state_path=paths["state_path"],
                    decision_path=paths["decision_path"],
                    window_seconds=5.0,
                    max_windows=100,
                    max_consecutive_failures=2,
                    raise_on_abort=True,
                    sleep_fn=lambda _seconds: None,
                    window_builder=_always_raise,
                )

            summary_path = run_dir / "control" / "final_summary.json"
            self.assertTrue(summary_path.exists(), "final_summary.json was not written before raising")
            summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary_data["control_status"], "aborted")
            self.assertEqual(summary_data["window_failure_count"], 2)


class TestControlLoopStopFileHaltsLoop(unittest.TestCase):
    """A pre-existing stop file causes the loop to exit before any window."""

    def test_stop_file_halts_loop_immediately(self) -> None:
        context = _make_context()
        policy = resolve_policy("max_freq")

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            paths = _make_paths(run_dir)

            # Create the stop file before calling run_control_loop.
            stop_file = run_dir / "control" / "STOP"
            stop_file.parent.mkdir(parents=True, exist_ok=True)
            stop_file.write_text("stop", encoding="utf-8")

            summary = run_control_loop(
                policy=policy,
                context=context,
                policy_config={},
                run_dir=run_dir,
                control_log=paths["control_log"],
                decisions_csv=paths["decisions_csv"],
                state_path=paths["state_path"],
                decision_path=paths["decision_path"],
                window_seconds=5.0,
                max_windows=10,
                stop_file=stop_file,
                sleep_fn=lambda _seconds: None,
                window_builder=build_window,
            )

            # The loop exited before processing any window.
            self.assertEqual(summary.total_windows, 0)

            # final_summary.json must still be written.
            summary_path = run_dir / "control" / "final_summary.json"
            self.assertTrue(summary_path.exists(), "final_summary.json was not written after stop-file exit")


if __name__ == "__main__":
    unittest.main()
