from __future__ import annotations

import unittest

from src.methods.reimplemented_methods.everest_reimpl.phase_characterization import PhaseCharacterizer


class PhaseCharacterizerTests(unittest.TestCase):
    def test_paper_example_fs_is_point_five(self) -> None:
        characterizer = PhaseCharacterizer()
        fs = characterizer.estimate_frequency_sensitivity(
            mem_high=1.25,
            mem_low=1.0,
            freq_high_mhz=1500,
            freq_low_mhz=1000,
        )
        self.assertAlmostEqual(fs, 0.5, places=6)

    def test_fs_clamped_to_zero_and_one(self) -> None:
        characterizer = PhaseCharacterizer()

        low = characterizer.estimate_frequency_sensitivity(
            mem_high=0.5,
            mem_low=1.0,
            freq_high_mhz=2000,
            freq_low_mhz=1000,
        )
        high = characterizer.estimate_frequency_sensitivity(
            mem_high=4.0,
            mem_low=1.0,
            freq_high_mhz=2000,
            freq_low_mhz=1000,
        )

        self.assertEqual(low, 0.0)
        self.assertEqual(high, 1.0)

    def test_invalid_input_raises(self) -> None:
        characterizer = PhaseCharacterizer()

        with self.assertRaises(ValueError):
            characterizer.estimate_frequency_sensitivity(1.0, 0.0, 1500, 1000)

        with self.assertRaises(ValueError):
            characterizer.estimate_frequency_sensitivity(1.0, 1.0, 1000, 1000)

        with self.assertRaises(ValueError):
            characterizer.upsert_phase_characterization("", 0.5, 1.0, 1.0, 1500, 1000)

    def test_cache_upsert_and_override(self) -> None:
        characterizer = PhaseCharacterizer()

        first = characterizer.upsert_phase_characterization(
            phase_id="active-g4-m2",
            fs=0.4,
            mem_high=1.2,
            mem_low=1.0,
            freq_high_mhz=1400,
            freq_low_mhz=1000,
        )
        self.assertTrue(characterizer.has_phase_characterization("active-g4-m2"))
        self.assertEqual(first.fs, 0.4)

        second = characterizer.upsert_phase_characterization(
            phase_id="active-g4-m2",
            fs=0.7,
            mem_high=1.3,
            mem_low=1.0,
            freq_high_mhz=1400,
            freq_low_mhz=1000,
        )
        self.assertEqual(second.fs, 0.7)
        cached = characterizer.get_phase_characterization("active-g4-m2")
        assert cached is not None
        self.assertEqual(cached.fs, 0.7)


if __name__ == "__main__":
    unittest.main()
