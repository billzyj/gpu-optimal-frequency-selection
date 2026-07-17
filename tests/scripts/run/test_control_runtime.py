from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run.control_runtime import build_context, write_run_manifest
from src.common.experiment import PerformanceTargetType


def _build_context():
    return build_context(
        policy_name="max_freq",
        bench_id="synthetic",
        run_id="target-run",
        started_at_utc="2026-07-17T00:00:00Z",
    )


class BuildContextPerformanceTargetTests(unittest.TestCase):
    def test_runner_defaults_to_runtime_slowdown_semantics(self) -> None:
        with mock.patch.dict(os.environ, {"PD_TARGET": "0.1"}, clear=True):
            context = _build_context()

        self.assertEqual(context.performance_target_type, PerformanceTargetType.RUNTIME_SLOWDOWN)
        self.assertAlmostEqual(context.pd_target, 0.1, places=12)
        self.assertAlmostEqual(context.relative_performance_loss or 0.0, 1.0 / 11.0, places=12)
        self.assertAlmostEqual(context.minimum_performance_ratio or 0.0, 10.0 / 11.0, places=12)

    def test_runner_parses_explicit_relative_loss_semantics(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "PD_TARGET": "0.1",
                "PERFORMANCE_TARGET_TYPE": "relative_performance_loss",
            },
            clear=True,
        ):
            context = _build_context()

        self.assertEqual(
            context.performance_target_type,
            PerformanceTargetType.RELATIVE_PERFORMANCE_LOSS,
        )
        self.assertAlmostEqual(context.relative_performance_loss or 0.0, 0.1, places=12)
        self.assertAlmostEqual(context.minimum_performance_ratio or 0.0, 0.9, places=12)

    def test_runner_rejects_unknown_target_type(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"PERFORMANCE_TARGET_TYPE": "ambiguous"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported performance target type"):
                _build_context()

    def test_manifest_records_raw_and_all_normalized_target_values(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "PD_TARGET": "0.1",
                "PERFORMANCE_TARGET_TYPE": "runtime_slowdown",
            },
            clear=True,
        ):
            context = _build_context()
            with tempfile.TemporaryDirectory() as tmp:
                manifest_path = Path(tmp) / "run_manifest.json"
                write_run_manifest(manifest_path, context, {})
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertAlmostEqual(manifest["run"]["pd_target"], 0.1, places=12)
        target = manifest["run"]["performance_target"]
        self.assertEqual(target["type"], "runtime_slowdown")
        self.assertAlmostEqual(target["raw_value"], 0.1, places=12)
        self.assertAlmostEqual(target["runtime_slowdown"], 0.1, places=12)
        self.assertAlmostEqual(target["relative_performance_loss"], 1.0 / 11.0, places=12)
        self.assertAlmostEqual(target["minimum_performance_ratio"], 10.0 / 11.0, places=12)
        self.assertEqual(manifest["environment"]["PERFORMANCE_TARGET_TYPE"], "runtime_slowdown")


if __name__ == "__main__":
    unittest.main()
