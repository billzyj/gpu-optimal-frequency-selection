"""Ali HPEC 2022 model-based frequency-selection baseline."""

from .policy import (
    AliFrequencyEstimate,
    AliFrequencySelectionPolicy,
    AliSelectionResult,
    PerformanceModelCoefficients,
    PowerModelCoefficients,
    build_frequency_estimates,
    estimate_power_w,
    estimate_runtime_s,
    select_frequency_by_objective,
)

__all__ = [
    "AliFrequencyEstimate",
    "AliFrequencySelectionPolicy",
    "AliSelectionResult",
    "PerformanceModelCoefficients",
    "PowerModelCoefficients",
    "build_frequency_estimates",
    "estimate_power_w",
    "estimate_runtime_s",
    "select_frequency_by_objective",
]
