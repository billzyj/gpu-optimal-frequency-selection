from __future__ import annotations

from src.methods.reimplemented_methods.everest_reimpl.types import CharacterizationRecord


class PhaseCharacterizer:
    """Implements EVeREST Phase Characterization and phase-wise FS cache."""

    def __init__(self) -> None:
        self._records: dict[str, CharacterizationRecord] = {}

    def estimate_frequency_sensitivity(
        self,
        mem_high: float,
        mem_low: float,
        freq_high_mhz: int,
        freq_low_mhz: int,
    ) -> float:
        """Estimates normalized frequency sensitivity (FS) and clamps it to [0, 1]."""
        self._validate_inputs(mem_high, mem_low, freq_high_mhz, freq_low_mhz)

        mem_ratio = mem_high / mem_low
        freq_ratio = freq_high_mhz / freq_low_mhz
        fs = (mem_ratio - 1.0) / (freq_ratio - 1.0)
        return _clamp(fs, 0.0, 1.0)

    def upsert_phase_characterization(
        self,
        phase_id: str,
        fs: float,
        mem_high: float,
        mem_low: float,
        freq_high_mhz: int,
        freq_low_mhz: int,
    ) -> CharacterizationRecord:
        """Stores or updates one phase characterization in cache."""
        if not phase_id:
            raise ValueError("phase_id must be non-empty.")
        self._validate_inputs(mem_high, mem_low, freq_high_mhz, freq_low_mhz)

        record = CharacterizationRecord(
            phase_id=phase_id,
            fs=_clamp(fs, 0.0, 1.0),
            mem_high=mem_high,
            mem_low=mem_low,
            freq_high_mhz=freq_high_mhz,
            freq_low_mhz=freq_low_mhz,
        )
        self._records[phase_id] = record
        return record

    def get_phase_characterization(self, phase_id: str) -> CharacterizationRecord | None:
        return self._records.get(phase_id)

    def has_phase_characterization(self, phase_id: str) -> bool:
        return phase_id in self._records

    @staticmethod
    def _validate_inputs(mem_high: float, mem_low: float, freq_high_mhz: int, freq_low_mhz: int) -> None:
        if mem_high <= 0 or mem_low <= 0:
            raise ValueError("mem_high and mem_low must both be > 0.")
        if freq_low_mhz <= 0:
            raise ValueError("freq_low_mhz must be > 0.")
        if freq_high_mhz <= freq_low_mhz:
            raise ValueError("freq_high_mhz must be > freq_low_mhz.")


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))
