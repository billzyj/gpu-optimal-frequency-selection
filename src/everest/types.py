from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PhaseSignature:
    """Coarse-grained signature used to identify repeating phases."""

    gpu_bucket: int
    mem_bucket: int
    is_idle_like: bool

    def to_phase_id(self) -> str:
        mode = "idle" if self.is_idle_like else "active"
        return f"{mode}-g{self.gpu_bucket}-m{self.mem_bucket}"


@dataclass(slots=True, frozen=True)
class PhaseObservation:
    """Result emitted by Phase Identification for one input window."""

    phase_id: str | None
    is_stable: bool
    is_new_phase: bool
    gpu_util_avg_pct: float
    mem_util_avg_pct: float
    is_idle_like: bool


@dataclass(slots=True, frozen=True)
class CharacterizationRecord:
    """Cached Phase Characterization result for one phase."""

    phase_id: str
    fs: float
    mem_high: float
    mem_low: float
    freq_high_mhz: int
    freq_low_mhz: int


@dataclass(slots=True, frozen=True)
class CharacterizationResult:
    """Return value for a characterization event."""

    record: CharacterizationRecord
    cache_hit: bool


@dataclass(slots=True, frozen=True)
class ScalerOutput:
    """Frequency Scaling output with intermediate values for debugging."""

    target_frequency_mhz: int
    raw_frequency_mhz: float
    clamped_frequency_mhz: float
    fs_used: float
    pd_used: float
    min_allowed_mhz: int
    max_allowed_mhz: int
