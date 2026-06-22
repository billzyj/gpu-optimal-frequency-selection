from __future__ import annotations

import unittest

from src.common.experiment.types import PlatformSpec
from src.methods.comparison_methods.local_reproductions.everest_reimpl.frequency_scaling import FrequencyScaler


class FrequencyScalerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.platform = PlatformSpec(
            vendor="nvidia",
            gpu_model="A100",
            gpu_count=1,
            min_graphics_clock_mhz=210,
            max_graphics_clock_mhz=1410,
            graphics_clock_step_mhz=15,
        )
        self.scaler = FrequencyScaler()

    def test_equation_four_computation(self) -> None:
        result = self.scaler.compute_target_frequency(
            freq_high_mhz=1410,
            fs=0.5,
            pd=0.1,
            platform=self.platform,
        )
        self.assertAlmostEqual(result.raw_frequency_mhz, 1153.6363636, places=4)
        self.assertEqual(result.target_frequency_mhz, 1155)

    def test_fs_zero_uses_paper_frequency_floor_when_platform_allows(self) -> None:
        result = self.scaler.compute_target_frequency(
            freq_high_mhz=1410,
            fs=0.0,
            pd=0.1,
            platform=self.platform,
        )
        self.assertEqual(result.min_allowed_mhz, 900)
        self.assertEqual(result.target_frequency_mhz, 900)

    def test_pd_zero_keeps_high_frequency(self) -> None:
        result = self.scaler.compute_target_frequency(
            freq_high_mhz=1200,
            fs=0.8,
            pd=0.0,
            platform=self.platform,
        )
        self.assertEqual(result.target_frequency_mhz, 1200)

    def test_result_stays_in_platform_range(self) -> None:
        result = self.scaler.compute_target_frequency(
            freq_high_mhz=5000,
            fs=1.2,
            pd=-1.0,
            platform=self.platform,
        )
        self.assertGreaterEqual(result.target_frequency_mhz, self.platform.min_graphics_clock_mhz)
        self.assertLessEqual(result.target_frequency_mhz, self.platform.max_graphics_clock_mhz)

    def test_high_floor_ratio_is_bounded_by_high_frequency(self) -> None:
        result = self.scaler.compute_target_frequency(
            freq_high_mhz=300,
            fs=0.2,
            pd=0.9,
            platform=self.platform,
            min_ratio_of_max=0.95,
        )
        self.assertEqual(result.max_allowed_mhz, 300)
        self.assertEqual(result.target_frequency_mhz, 300)

    def test_paper_frequency_floor_is_bounded_by_platform_maximum(self) -> None:
        small_platform = PlatformSpec(
            vendor="nvidia",
            gpu_model="small-test-gpu",
            gpu_count=1,
            min_graphics_clock_mhz=210,
            max_graphics_clock_mhz=810,
            graphics_clock_step_mhz=15,
        )

        result = self.scaler.compute_target_frequency(
            freq_high_mhz=810,
            fs=0.0,
            pd=0.1,
            platform=small_platform,
        )

        self.assertEqual(result.max_allowed_mhz, 810)
        self.assertEqual(result.target_frequency_mhz, 810)


if __name__ == "__main__":
    unittest.main()
