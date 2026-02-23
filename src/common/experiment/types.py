from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


JSONPrimitive = str | int | float | bool | None
JSONValue = JSONPrimitive | list["JSONValue"] | dict[str, "JSONValue"]


class DecisionAction(str, Enum):
    """Control intent emitted by an algorithm."""

    SET_CLOCK = "set_clock"
    HOLD_CLOCK = "hold_clock"
    RESET_TO_MAX = "reset_to_max"
    NO_OP = "no_op"


@dataclass(slots=True, frozen=True)
class PlatformSpec:
    """Hardware and runtime characteristics of the target platform."""

    vendor: str
    gpu_model: str
    gpu_count: int
    min_graphics_clock_mhz: int
    max_graphics_clock_mhz: int
    graphics_clock_step_mhz: int
    node_name: str | None = None
    driver_version: str | None = None
    runtime_version: str | None = None


@dataclass(slots=True, frozen=True)
class ExperimentMetadata:
    """Stable identity and metadata for one experiment run."""

    run_id: str
    experiment_id: str
    policy_name: str
    workload_name: str
    started_at_utc: str
    tags: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ExperimentContext:
    """Inputs visible to all algorithms at initialization time."""

    platform: PlatformSpec
    metadata: ExperimentMetadata
    pd_target: float
    window_seconds: float
    sampling_interval_ms: int
    user_config: dict[str, JSONValue] = field(default_factory=dict)

    @property
    def performance_target_ratio(self) -> float:
        """Returns expected minimum relative performance, 1 - PD."""
        return 1.0 - self.pd_target


@dataclass(slots=True, frozen=True)
class TelemetrySample:
    """Raw per-sample telemetry read from hardware APIs."""

    timestamp_unix_s: float
    gpu_util_pct: float
    mem_util_pct: float
    graphics_clock_mhz: int
    power_w: float | None = None
    energy_j: float | None = None
    temperature_c: float | None = None
    raw_counters: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class MetricWindow:
    """Window-aggregated metrics passed to on_window()."""

    sequence_id: int
    start_unix_s: float
    end_unix_s: float
    duration_s: float
    sample_count: int
    gpu_util_avg_pct: float
    mem_util_avg_pct: float
    graphics_clock_avg_mhz: float
    power_avg_w: float | None = None
    energy_delta_j: float | None = None
    custom_metrics: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(slots=True)
class AlgorithmState:
    """
    Mutable state bag owned by one algorithm instance.

    The shared runner should treat this object as opaque.
    """

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value


@dataclass(slots=True, frozen=True)
class Decision:
    """Control decision produced for the next window."""

    action: DecisionAction
    target_graphics_clock_mhz: int | None
    reason_code: str
    debug_fields: dict[str, JSONValue] = field(default_factory=dict)

    @property
    def requires_clock_change(self) -> bool:
        return self.action in {DecisionAction.SET_CLOCK, DecisionAction.RESET_TO_MAX}


@dataclass(slots=True, frozen=True)
class FinalSummary:
    """End-of-run summary returned by finalize()."""

    policy_name: str
    run_id: str
    total_windows: int
    pd_target: float
    pd_violation_count: int
    max_pd_violation: float
    custom_summary: dict[str, JSONValue] = field(default_factory=dict)
