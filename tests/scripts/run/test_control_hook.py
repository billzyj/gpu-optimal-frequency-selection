"""Regression tests for the legacy single-window control hook."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.run import control_hook


class ControlHookStaticPolicyTests(unittest.TestCase):
    def test_window_zero_applies_static_policy_initial_decision(self) -> None:
        profile_config = {
            "workload_profiles": {
                "lammps-reaxff": [
                    {"frequency_mhz": 1410, "performance_ratio": 1.0},
                    {"frequency_mhz": 1260, "performance_ratio": 0.93},
                ]
            }
        }

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            env = {
                "RUN_DIR": str(run_dir),
                "BENCH_ID": "lammps-reaxff",
                "POLICY_NAME": "oracle_static",
                "WINDOW_INDEX": "0",
                "PD_TARGET": "0.1",
                "POLICY_CONFIG_JSON": json.dumps(profile_config),
                "PLATFORM_MIN_CLOCK_MHZ": "210",
                "PLATFORM_MAX_CLOCK_MHZ": "1410",
                "PLATFORM_CLOCK_STEP_MHZ": "15",
                "METRIC_GPU_UTIL_PCT": "50",
                "METRIC_MEM_UTIL_PCT": "30",
                "METRIC_GRAPHICS_CLOCK_MHZ": "1410",
            }
            with mock.patch.dict(os.environ, env, clear=True):
                rc = control_hook.main()

            self.assertEqual(rc, 0)
            last_decision = json.loads(
                (run_dir / "control" / "last_decision.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(last_decision["window_index"], -1)
            self.assertEqual(last_decision["action"], "set_clock")
            self.assertEqual(last_decision["target_graphics_clock_mhz"], 1260)
            self.assertEqual(
                last_decision["reason_code"],
                "oracle_static_pre_run_apply_selected_clock",
            )


if __name__ == "__main__":
    unittest.main()
