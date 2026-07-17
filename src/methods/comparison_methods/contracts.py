"""Machine-readable admission contracts for comparison methods.

This module describes what a method needs before it may be exposed as a
runnable comparison.  It deliberately does not instantiate policies or launch
external programs.  The policy registry remains the source of truth for
methods that are actually runnable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class IntegrationRoute(str, Enum):
    """How a comparison method crosses the repository boundary."""

    IN_PROCESS_POLICY = "in_process_policy"
    LOCAL_REPRODUCTION = "local_reproduction"
    EXTERNAL_CONTROLLER = "external_controller"
    EXTERNAL_HARNESS = "external_harness"
    CHARACTERIZATION_TOOL = "characterization_tool"


class ImplementationStatus(str, Enum):
    """Current implementation state, separate from scientific importance."""

    REGISTERED = "registered"
    ALGORITHM_CORE = "algorithm_core"
    PLANNED = "planned"
    CONDITIONAL = "conditional"
    DEFERRED = "deferred"


class ActuationOwner(str, Enum):
    """Process that owns privileged hardware changes during a run."""

    LOCAL_CONTROLLER = "local_controller"
    UPSTREAM_CONTROLLER = "upstream_controller"
    NONE = "none"


@dataclass(slots=True, frozen=True)
class ComparisonMethodContract:
    """Requirements and routing metadata for one comparison method."""

    method_id: str
    display_name: str
    citation_key: str | None
    route: IntegrationRoute
    status: ImplementationStatus
    actuation_owner: ActuationOwner
    required_telemetry: frozenset[str] = field(default_factory=frozenset)
    required_control_knobs: frozenset[str] = field(default_factory=frozenset)
    required_artifacts: frozenset[str] = field(default_factory=frozenset)
    registry_name: str | None = None

    def __post_init__(self) -> None:
        if not self.method_id:
            raise ValueError("method_id must be non-empty.")
        if self.status == ImplementationStatus.REGISTERED and self.registry_name is None:
            raise ValueError("A registered method must declare registry_name.")
        if self.status != ImplementationStatus.REGISTERED and self.registry_name is not None:
            raise ValueError("Only a registered method may declare registry_name.")
        if (
            self.route == IntegrationRoute.EXTERNAL_CONTROLLER
            and self.actuation_owner != ActuationOwner.UPSTREAM_CONTROLLER
        ):
            raise ValueError(
                "An external-controller method must declare upstream actuation ownership."
            )


@dataclass(slots=True, frozen=True)
class RuntimeCapabilities:
    """Capabilities available to a candidate comparison run."""

    telemetry_fields: frozenset[str] = field(default_factory=frozenset)
    control_knobs: frozenset[str] = field(default_factory=frozenset)
    artifacts: frozenset[str] = field(default_factory=frozenset)
    external_controller_mode: bool = False


@dataclass(slots=True, frozen=True)
class AdmissionReport:
    """Deterministic preflight result for one method contract."""

    method_id: str
    missing_telemetry: tuple[str, ...]
    missing_control_knobs: tuple[str, ...]
    missing_artifacts: tuple[str, ...]
    external_controller_mode_missing: bool
    implementation_incomplete: bool

    @property
    def ready(self) -> bool:
        """Whether the method is both implemented and capability-compatible."""

        return not (
            self.missing_telemetry
            or self.missing_control_knobs
            or self.missing_artifacts
            or self.external_controller_mode_missing
            or self.implementation_incomplete
        )


def assess_admission(
    contract: ComparisonMethodContract,
    capabilities: RuntimeCapabilities,
) -> AdmissionReport:
    """Checks a method's declared requirements against runtime capabilities."""

    return AdmissionReport(
        method_id=contract.method_id,
        missing_telemetry=tuple(
            sorted(contract.required_telemetry - capabilities.telemetry_fields)
        ),
        missing_control_knobs=tuple(
            sorted(contract.required_control_knobs - capabilities.control_knobs)
        ),
        missing_artifacts=tuple(
            sorted(contract.required_artifacts - capabilities.artifacts)
        ),
        external_controller_mode_missing=(
            contract.route == IntegrationRoute.EXTERNAL_CONTROLLER
            and not capabilities.external_controller_mode
        ),
        implementation_incomplete=contract.status != ImplementationStatus.REGISTERED,
    )


_CONTRACTS = (
    ComparisonMethodContract(
        method_id="max_freq",
        display_name="Maximum Frequency",
        citation_key=None,
        route=IntegrationRoute.IN_PROCESS_POLICY,
        status=ImplementationStatus.REGISTERED,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_control_knobs=frozenset({"graphics_clock"}),
        registry_name="max_freq",
    ),
    ComparisonMethodContract(
        method_id="min_freq",
        display_name="Minimum Frequency",
        citation_key=None,
        route=IntegrationRoute.IN_PROCESS_POLICY,
        status=ImplementationStatus.REGISTERED,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_control_knobs=frozenset({"graphics_clock"}),
        registry_name="min_freq",
    ),
    ComparisonMethodContract(
        method_id="oracle_static",
        display_name="Lowest-Feasible Clock Reference",
        citation_key=None,
        route=IntegrationRoute.LOCAL_REPRODUCTION,
        status=ImplementationStatus.REGISTERED,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_control_knobs=frozenset({"graphics_clock"}),
        required_artifacts=frozenset({"workload_frequency_profile"}),
        registry_name="oracle_static",
    ),
    ComparisonMethodContract(
        method_id="everest",
        display_name="EVeREST",
        citation_key="yue2025everest_gpu",
        route=IntegrationRoute.LOCAL_REPRODUCTION,
        status=ImplementationStatus.REGISTERED,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_telemetry=frozenset(
            {"gpu_util_pct", "mem_util_pct", "observed_graphics_clock_mhz"}
        ),
        required_control_knobs=frozenset({"graphics_clock"}),
        registry_name="everest",
    ),
    ComparisonMethodContract(
        method_id="ali_2022_reimpl",
        display_name="Ali-HPEC-2022",
        citation_key="ali2022multi_objective_gpu_frequency",
        route=IntegrationRoute.LOCAL_REPRODUCTION,
        status=ImplementationStatus.REGISTERED,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_control_knobs=frozenset({"graphics_clock"}),
        required_artifacts=frozenset(
            {"ali_model_coefficients", "max_frequency_profile"}
        ),
        registry_name="ali_2022_reimpl",
    ),
    ComparisonMethodContract(
        method_id="geepafs",
        display_name="GEEPAFS",
        citation_key="zhang2024geepafs",
        route=IntegrationRoute.EXTERNAL_CONTROLLER,
        status=ImplementationStatus.PLANNED,
        actuation_owner=ActuationOwner.UPSTREAM_CONTROLLER,
        required_telemetry=frozenset(
            {
                "gpu_util_pct",
                "memory_bandwidth_util_pct",
                "power_w",
                "observed_graphics_clock_mhz",
            }
        ),
        required_control_knobs=frozenset({"graphics_clock"}),
        required_artifacts=frozenset(
            {"pinned_upstream_checkout", "target_gpu_calibration"}
        ),
    ),
    ComparisonMethodContract(
        method_id="energyucb_reimpl",
        display_name="EnergyUCB",
        citation_key="xu2026energyucb",
        route=IntegrationRoute.LOCAL_REPRODUCTION,
        status=ImplementationStatus.ALGORITHM_CORE,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_telemetry=frozenset(
            {
                "core_utilization",
                "uncore_utilization",
                "energy_delta_j",
                "progress",
                "observed_graphics_clock_mhz",
            }
        ),
        required_control_knobs=frozenset({"graphics_clock"}),
    ),
    ComparisonMethodContract(
        method_id="drlcap_reimpl",
        display_name="DRLCap",
        citation_key="wang2024drlcap",
        route=IntegrationRoute.LOCAL_REPRODUCTION,
        status=ImplementationStatus.CONDITIONAL,
        actuation_owner=ActuationOwner.LOCAL_CONTROLLER,
        required_telemetry=frozenset(
            {
                "gpu_util_pct",
                "mem_util_pct",
                "power_w",
                "observed_graphics_clock_mhz",
                "temperature_c",
            }
        ),
        required_control_knobs=frozenset({"graphics_clock"}),
        required_artifacts=frozenset(
            {"approved_independent_training_plan", "training_provenance"}
        ),
    ),
    ComparisonMethodContract(
        method_id="synergy",
        display_name="SYnergy",
        citation_key="fan2023synergy",
        route=IntegrationRoute.EXTERNAL_HARNESS,
        status=ImplementationStatus.DEFERRED,
        actuation_owner=ActuationOwner.UPSTREAM_CONTROLLER,
        required_artifacts=frozenset(
            {"sycl_instrumented_workload", "device_specific_model"}
        ),
    ),
    ComparisonMethodContract(
        method_id="latest",
        display_name="LATEST",
        citation_key="velicka2026gpu_frequency_latency",
        route=IntegrationRoute.CHARACTERIZATION_TOOL,
        status=ImplementationStatus.DEFERRED,
        actuation_owner=ActuationOwner.UPSTREAM_CONTROLLER,
        required_control_knobs=frozenset({"graphics_clock"}),
        required_artifacts=frozenset({"user_supplied_latest_executable"}),
    ),
)


COMPARISON_METHOD_CONTRACTS: Mapping[str, ComparisonMethodContract] = {
    contract.method_id: contract for contract in _CONTRACTS
}


def comparison_method_contract(method_id: str) -> ComparisonMethodContract:
    """Returns one declared comparison contract by stable method id."""

    try:
        return COMPARISON_METHOD_CONTRACTS[method_id]
    except KeyError as exc:
        supported = ", ".join(COMPARISON_METHOD_CONTRACTS)
        raise KeyError(f"Unknown comparison method {method_id!r}. Known ids: {supported}") from exc


def registered_contract_policy_names() -> tuple[str, ...]:
    """Returns registry names declared by completed comparison contracts."""

    return tuple(
        contract.registry_name
        for contract in _CONTRACTS
        if contract.registry_name is not None
    )
