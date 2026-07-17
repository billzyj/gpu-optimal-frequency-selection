"""Experiment-level interfaces and data models."""

from .interfaces import AlgorithmInterface, StaticPolicy
from .types import (
    AlgorithmState,
    Decision,
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    FinalSummary,
    MetricWindow,
    PerformanceTarget,
    PerformanceTargetType,
    PlatformSpec,
    TelemetrySample,
    relative_performance_loss_to_runtime_slowdown,
    runtime_slowdown_to_relative_performance_loss,
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
    "PerformanceTarget",
    "PerformanceTargetType",
    "PlatformSpec",
    "StaticPolicy",
    "TelemetrySample",
    "relative_performance_loss_to_runtime_slowdown",
    "runtime_slowdown_to_relative_performance_loss",
    "validate_decision",
]
