#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# Ensure repository root is importable when this script is invoked from Slurm hooks.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.experiment import (
    AlgorithmState,
    Decision,
    DecisionAction,
    ExperimentContext,
    ExperimentMetadata,
    FinalSummary,
    MetricWindow,
    PlatformSpec,
    validate_decision,
)
from src.methods.reimplemented_methods.oracle_static.policy import StaticOraclePolicy


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return int(raw)


def parse_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return float(raw)


def parse_optional_float_env(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return None
    return float(raw)


def append_log(control_log: Path, message: str) -> None:
    control_log.parent.mkdir(parents=True, exist_ok=True)
    with control_log.open("a", encoding="utf-8") as fp:
        fp.write(f"[{utc_now()}] {message}\n")


def ensure_decisions_csv(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["timestamp_utc", "component", "decision", "reason"])


def append_decision_row(path: Path, policy_name: str, decision: Decision, window_index: int) -> None:
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


def load_policy_config() -> dict[str, Any]:
    config_path = os.getenv("POLICY_CONFIG_PATH", "")
    config_json = os.getenv("POLICY_CONFIG_JSON", "")

    if config_path:
        return json.loads(Path(config_path).read_text(encoding="utf-8"))
    if config_json:
        return json.loads(config_json)
    return {}


def build_context(policy_name: str, bench_id: str, run_id: str, started_at_utc: str) -> ExperimentContext:
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
    end_unix_s = time.time()
    duration_s = context.window_seconds
    start_unix_s = end_unix_s - duration_s

    perf_ratio = parse_optional_float_env("METRIC_PERFORMANCE_RATIO")
    custom_metrics: dict[str, float] = {}
    if perf_ratio is not None:
        custom_metrics["performance_ratio"] = perf_ratio

    current_clock = parse_float_env(
        "METRIC_GRAPHICS_CLOCK_MHZ",
        float(context.platform.max_graphics_clock_mhz),
    )

    return MetricWindow(
        sequence_id=window_index,
        start_unix_s=start_unix_s,
        end_unix_s=end_unix_s,
        duration_s=duration_s,
        sample_count=max(1, int((duration_s * 1000.0) / max(1, context.sampling_interval_ms))),
        gpu_util_avg_pct=parse_float_env("METRIC_GPU_UTIL_PCT", 0.0),
        mem_util_avg_pct=parse_float_env("METRIC_MEM_UTIL_PCT", 0.0),
        graphics_clock_avg_mhz=current_clock,
        power_avg_w=parse_optional_float_env("METRIC_POWER_W"),
        energy_delta_j=parse_optional_float_env("METRIC_ENERGY_DELTA_J"),
        custom_metrics=custom_metrics,
    )


class MaxFreqPolicy:
    policy_name = "max_freq"

    def initialize(self, context: ExperimentContext, config: Mapping[str, object]) -> AlgorithmState:
        _ = config
        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("selected_clock_mhz", context.platform.max_graphics_clock_mhz)
        state.set("decision_emitted", False)
        state.set("total_windows", 0)
        return state

    def on_window(self, metrics: MetricWindow, state: AlgorithmState) -> Decision:
        state.set("total_windows", int(state.get("total_windows", 0)) + 1)
        target = int(state.get("selected_clock_mhz"))
        if not bool(state.get("decision_emitted", False)):
            state.set("decision_emitted", True)
            if abs(metrics.graphics_clock_avg_mhz - float(target)) < 0.5:
                return Decision(DecisionAction.HOLD_CLOCK, None, "max_freq_already_at_target")
            return Decision(DecisionAction.SET_CLOCK, target, "max_freq_apply")
        return Decision(DecisionAction.HOLD_CLOCK, None, "max_freq_hold")

    def finalize(self, state: AlgorithmState) -> FinalSummary:
        return FinalSummary(
            policy_name=self.policy_name,
            run_id=str(state.get("run_id")),
            total_windows=int(state.get("total_windows", 0)),
            pd_target=parse_float_env("PD_TARGET", 0.0),
            pd_violation_count=0,
            max_pd_violation=0.0,
            custom_summary={"selected_clock_mhz": int(state.get("selected_clock_mhz", 0))},
        )


class MinFreqPolicy:
    policy_name = "min_freq"

    def initialize(self, context: ExperimentContext, config: Mapping[str, object]) -> AlgorithmState:
        _ = config
        state = AlgorithmState()
        state.set("run_id", context.metadata.run_id)
        state.set("selected_clock_mhz", context.platform.min_graphics_clock_mhz)
        state.set("decision_emitted", False)
        state.set("total_windows", 0)
        return state

    def on_window(self, metrics: MetricWindow, state: AlgorithmState) -> Decision:
        state.set("total_windows", int(state.get("total_windows", 0)) + 1)
        target = int(state.get("selected_clock_mhz"))
        if not bool(state.get("decision_emitted", False)):
            state.set("decision_emitted", True)
            if abs(metrics.graphics_clock_avg_mhz - float(target)) < 0.5:
                return Decision(DecisionAction.HOLD_CLOCK, None, "min_freq_already_at_target")
            return Decision(DecisionAction.SET_CLOCK, target, "min_freq_apply")
        return Decision(DecisionAction.HOLD_CLOCK, None, "min_freq_hold")

    def finalize(self, state: AlgorithmState) -> FinalSummary:
        return FinalSummary(
            policy_name=self.policy_name,
            run_id=str(state.get("run_id")),
            total_windows=int(state.get("total_windows", 0)),
            pd_target=parse_float_env("PD_TARGET", 0.0),
            pd_violation_count=0,
            max_pd_violation=0.0,
            custom_summary={"selected_clock_mhz": int(state.get("selected_clock_mhz", 0))},
        )


def resolve_policy(policy_name: str):
    if policy_name == "max_freq":
        return MaxFreqPolicy()
    if policy_name == "min_freq":
        return MinFreqPolicy()
    if policy_name == "oracle_static":
        return StaticOraclePolicy()
    raise ValueError(
        "Unsupported POLICY_NAME. Supported values: max_freq, min_freq, oracle_static"
    )


def load_or_initialize_state(
    state_path: Path,
    policy,
    context: ExperimentContext,
    policy_config: Mapping[str, object],
) -> AlgorithmState:
    if state_path.exists():
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        return AlgorithmState(data=dict(payload.get("policy_state", {})))

    state = policy.initialize(context, policy_config)
    persist_state(state_path, state)
    return state


def persist_state(state_path: Path, state: AlgorithmState) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"policy_state": state.data}
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def apply_decision(decision: Decision, control_log: Path) -> None:
    if not decision.requires_clock_change or decision.target_graphics_clock_mhz is None:
        return

    template = os.getenv("APPLY_CLOCK_CMD_TEMPLATE", "")
    if not template:
        append_log(
            control_log,
            f"dry-run control action: set_clock target={decision.target_graphics_clock_mhz} MHz",
        )
        return

    cmd = template.format(
        target_mhz=decision.target_graphics_clock_mhz,
        action=decision.action.value,
        reason=decision.reason_code,
    )
    append_log(control_log, f"applying control command: {cmd}")
    subprocess.run(cmd, shell=True, check=True)


def main() -> int:
    run_dir_raw = os.getenv("RUN_DIR", "")
    if run_dir_raw == "":
        print("RUN_DIR is required for control hook.", file=sys.stderr)
        return 2
    run_dir = Path(run_dir_raw)

    bench_id = os.getenv("BENCH_ID", "")
    if not bench_id:
        print("BENCH_ID is required for control hook.", file=sys.stderr)
        return 2

    policy_name = os.getenv("POLICY_NAME", "max_freq")
    run_id = os.getenv("RUN_ID", "local-control")
    window_index = parse_int_env("WINDOW_INDEX", 0)

    control_log = Path(os.getenv("CONTROL_LOG", str(run_dir / "control_loop.log")))
    decisions_csv = run_dir / "normalized" / "decisions.csv"
    state_path = run_dir / "control" / "policy_state.json"
    decision_path = run_dir / "control" / "last_decision.json"

    started_at_utc = os.getenv("CONTROL_STARTED_AT_UTC", utc_now())
    os.environ["CONTROL_STARTED_AT_UTC"] = started_at_utc

    try:
        policy_config = load_policy_config()
        policy = resolve_policy(policy_name)
        context = build_context(policy_name, bench_id, run_id, started_at_utc)
        state = load_or_initialize_state(state_path, policy, context, policy_config)
        metrics = build_window(context, window_index)

        decision = policy.on_window(metrics, state)
        validate_decision(decision, context.platform)
        apply_decision(decision, control_log)

        persist_state(state_path, state)
        append_decision_row(decisions_csv, policy_name, decision, window_index)

        decision_path.parent.mkdir(parents=True, exist_ok=True)
        decision_path.write_text(
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

        append_log(
            control_log,
            (
                f"window={window_index} policy={policy_name} "
                f"decision={decision.action.value} target={decision.target_graphics_clock_mhz} "
                f"reason={decision.reason_code}"
            ),
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        append_log(control_log, f"control hook failed: {type(exc).__name__}: {exc}")
        print(f"control hook failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
