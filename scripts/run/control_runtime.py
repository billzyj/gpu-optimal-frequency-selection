#!/usr/bin/env python3
"""Shared runtime helpers for the GPU DVFS control loop.

Both ``control_hook.py`` (legacy single-window variant) and
``control_loop.py`` (long-lived runner) import from this module so that
all helper logic lives in exactly one place.
"""
from __future__ import annotations

import csv
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

# Ensure the repository root is importable when invoked from Slurm hooks or
# directly via ``python3 scripts/run/<module>.py``.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.control import ClockController, ShellTemplateController
from src.common.experiment import (
    AlgorithmState,
    Decision,
    ExperimentContext,
    ExperimentMetadata,
    MetricWindow,
    PlatformSpec,
)
from src.common.telemetry import EnvTelemetryProvider


_MANIFEST_ENV_KEYS = (
    "RUN_DIR",
    "BENCH_ID",
    "BENCH_PID",
    "MAX_WINDOWS",
    "POLICY_NAME",
    "PD_TARGET",
    "CONTROL_WINDOW_SECONDS",
    "CONTROL_DECISIONS_CSV",
    "METRIC_SAMPLING_INTERVAL_MS",
    "PLATFORM_VENDOR",
    "PLATFORM_GPU_MODEL",
    "PLATFORM_GPU_COUNT",
    "PLATFORM_MIN_CLOCK_MHZ",
    "PLATFORM_MAX_CLOCK_MHZ",
    "PLATFORM_CLOCK_STEP_MHZ",
    "PLATFORM_NODE_NAME",
    "PLATFORM_DRIVER_VERSION",
    "PLATFORM_RUNTIME_VERSION",
    "POLICY_CONFIG_PATH",
    "APPLY_CLOCK_CMD_TEMPLATE",
    "APPLY_CLOCK_RESET_CMD",
)


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------


def utc_now() -> str:
    """Returns the current UTC time formatted as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Environment-variable parsers
# ---------------------------------------------------------------------------


def parse_int_env(name: str, default: int) -> int:
    """Returns the integer value of an environment variable, or *default*."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def parse_float_env(name: str, default: float) -> float:
    """Returns the float value of an environment variable, or *default*."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


# ---------------------------------------------------------------------------
# Log helpers
# ---------------------------------------------------------------------------


def append_log(control_log: Path, message: str) -> None:
    """Appends a single timestamped line to *control_log*."""
    control_log.parent.mkdir(parents=True, exist_ok=True)
    with control_log.open("a", encoding="utf-8") as fp:
        fp.write(f"[{utc_now()}] {message}\n")


# ---------------------------------------------------------------------------
# Decisions CSV helpers
# ---------------------------------------------------------------------------


def ensure_decisions_csv(path: Path) -> None:
    """Creates the decisions CSV with a header row if it does not yet exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["timestamp_utc", "component", "decision", "reason"])


def append_decision_row(
    path: Path,
    policy_name: str,
    decision: Decision,
    window_index: int,
) -> None:
    """Appends one decision row to the decisions CSV."""
    ensure_decisions_csv(path)
    decision_value = decision.action.value
    if decision.target_graphics_clock_mhz is not None:
        decision_value = f"{decision_value}:{decision.target_graphics_clock_mhz}"

    with path.open("a", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                utc_now(),
                f"policy:{policy_name}",
                decision_value,
                f"{decision.reason_code};window={window_index}",
            ]
        )


# ---------------------------------------------------------------------------
# Policy config loader
# ---------------------------------------------------------------------------


def load_policy_config() -> dict[str, Any]:
    """Loads policy config from ``POLICY_CONFIG_PATH`` or ``POLICY_CONFIG_JSON``.

    Returns an empty dict when neither variable is set.
    """
    config_path = os.getenv("POLICY_CONFIG_PATH", "")
    config_json = os.getenv("POLICY_CONFIG_JSON", "")

    if config_path:
        return json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config_json:
        return json.loads(config_json)
    return {}


# ---------------------------------------------------------------------------
# Run manifest helpers
# ---------------------------------------------------------------------------


def write_run_manifest(
    path: Path,
    context: ExperimentContext,
    policy_config: Mapping[str, object],
) -> None:
    """Writes reproducibility metadata for one controlled run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    policy_config_dict = dict(policy_config)
    payload = {
        "generated_at_utc": utc_now(),
        "run": {
            "run_id": context.metadata.run_id,
            "experiment_id": context.metadata.experiment_id,
            "policy_name": context.metadata.policy_name,
            "workload_name": context.metadata.workload_name,
            "started_at_utc": context.metadata.started_at_utc,
            "pd_target": context.pd_target,
            "window_seconds": context.window_seconds,
            "sampling_interval_ms": context.sampling_interval_ms,
        },
        "platform": dataclasses.asdict(context.platform),
        "policy_config": policy_config_dict,
        "policy_config_sha256": _json_sha256(policy_config_dict),
        "environment": _manifest_environment(),
        "repository": _repository_manifest(),
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )


def _manifest_environment() -> dict[str, str]:
    env = {
        name: value
        for name in _MANIFEST_ENV_KEYS
        if (value := os.getenv(name)) not in (None, "")
    }
    if os.getenv("POLICY_CONFIG_JSON"):
        env["POLICY_CONFIG_JSON_SET"] = "true"
    return env


def _repository_manifest() -> dict[str, object]:
    status = _git_output(["status", "--short"])
    return {
        "root": str(REPO_ROOT),
        "commit": _git_output(["rev-parse", "HEAD"]),
        "dirty": None if status is None else bool(status.strip()),
        "dirty_status": [] if status is None else status.splitlines(),
        "submodules": _git_output(
            ["submodule", "status", "--recursive", "external/repacss-benchmarking"]
        ),
    }


def _git_output(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def _json_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ---------------------------------------------------------------------------
# Context and window builders
# ---------------------------------------------------------------------------


def build_context(
    policy_name: str,
    bench_id: str,
    run_id: str,
    started_at_utc: str,
) -> ExperimentContext:
    """Builds an :class:`ExperimentContext` from the current environment variables."""
    min_clock = parse_int_env("PLATFORM_MIN_CLOCK_MHZ", 210)
    max_clock = parse_int_env("PLATFORM_MAX_CLOCK_MHZ", 1980)

    platform = PlatformSpec(
        vendor=os.getenv("PLATFORM_VENDOR", "unknown"),
        gpu_model=os.getenv("PLATFORM_GPU_MODEL", "unknown"),
        gpu_count=parse_int_env("PLATFORM_GPU_COUNT", 1),
        min_graphics_clock_mhz=min_clock,
        max_graphics_clock_mhz=max_clock,
        graphics_clock_step_mhz=parse_int_env("PLATFORM_CLOCK_STEP_MHZ", 15),
        node_name=os.getenv("PLATFORM_NODE_NAME") or None,
        driver_version=os.getenv("PLATFORM_DRIVER_VERSION") or None,
        runtime_version=os.getenv("PLATFORM_RUNTIME_VERSION") or None,
    )

    metadata = ExperimentMetadata(
        run_id=run_id,
        experiment_id=os.getenv("EXPERIMENT_ID", "controlled"),
        policy_name=policy_name,
        workload_name=bench_id,
        started_at_utc=started_at_utc,
    )

    return ExperimentContext(
        platform=platform,
        metadata=metadata,
        pd_target=parse_float_env("PD_TARGET", 0.0),
        window_seconds=parse_float_env("CONTROL_WINDOW_SECONDS", 5.0),
        sampling_interval_ms=parse_int_env("METRIC_SAMPLING_INTERVAL_MS", 1000),
    )


def build_window(context: ExperimentContext, window_index: int) -> MetricWindow:
    """Builds a :class:`MetricWindow` by reading telemetry from environment variables."""
    return EnvTelemetryProvider().get_window(context, window_index)


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


def persist_state(state_path: Path, state: AlgorithmState) -> None:
    """Writes a JSON snapshot of *state* to *state_path* (observability only)."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"policy_state": state.data}
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------------------
# Decision application
# ---------------------------------------------------------------------------


def build_clock_controller(logger: Callable[[str], None]) -> ClockController:
    """Builds the default env-backed clock controller.

    Reads ``APPLY_CLOCK_CMD_TEMPLATE`` and ``APPLY_CLOCK_RESET_CMD`` and returns
    a :class:`ShellTemplateController`. This is the env-binding adapter for the
    typed actuation seam, mirroring how ``build_window`` binds telemetry.
    """
    return ShellTemplateController(
        apply_template=os.getenv("APPLY_CLOCK_CMD_TEMPLATE", "") or None,
        reset_cmd=os.getenv("APPLY_CLOCK_RESET_CMD", "") or None,
        logger=logger,
    )


def apply_decision(decision: Decision, control_log: Path) -> None:
    """Applies *decision* through the env-backed :class:`ClockController`."""
    controller = build_clock_controller(lambda message: append_log(control_log, message))
    controller.apply(decision)


# ---------------------------------------------------------------------------
# Last-decision writer
# ---------------------------------------------------------------------------


def write_last_decision(
    path: Path,
    policy_name: str,
    window_index: int,
    decision: Decision,
) -> None:
    """Writes the most-recent decision as JSON to *path* (replaces previous file)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "timestamp_utc": utc_now(),
                "policy_name": policy_name,
                "window_index": window_index,
                "action": decision.action.value,
                "target_graphics_clock_mhz": decision.target_graphics_clock_mhz,
                "reason_code": decision.reason_code,
                "debug_fields": decision.debug_fields,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# State initialiser (legacy helper kept for control_hook.py)
# ---------------------------------------------------------------------------


def load_or_initialize_state(
    state_path: Path,
    policy: Any,
    context: ExperimentContext,
    policy_config: Mapping[str, object],
) -> AlgorithmState:
    """Loads persisted state from disk, or calls ``policy.initialize`` if absent.

    This function exists for the legacy single-window ``control_hook.py`` path.
    The long-lived ``control_loop.py`` runner does **not** use it — it always
    calls ``policy.initialize`` once at startup and keeps state in memory.
    """
    if state_path.exists():
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        return AlgorithmState(data=dict(payload.get("policy_state", {})))

    state = policy.initialize(context, policy_config)
    persist_state(state_path, state)
    return state
