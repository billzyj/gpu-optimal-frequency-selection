"""Experiment-level interfaces and data models."""

from .interfaces import AlgorithmInterface
from .types import (
    AlgorithmState,
    Decision,
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    FinalSummary,
    MetricWindow,
    PlatformSpec,
    TelemetrySample,
)
from .validation import validate_decision

__all__ = [
    "AlgorithmInterface",
    "AlgorithmState",
    "Decision",
    "DecisionAction",
    "ExperimentContext",
    "ExperimentMetadata",
    "FinalSummary",
    "MetricWindow",
    "PlatformSpec",
    "TelemetrySample",
    "validate_decision",
]
