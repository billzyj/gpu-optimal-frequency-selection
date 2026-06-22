#!/usr/bin/env python3
"""Long-lived GPU DVFS control loop runner.

This module is the preferred replacement for the per-window
``control_hook.py`` approach.  A single process starts the policy with
``initialize()``, drives the ``on_window()`` loop for the entire run, calls
``finalize()`` when done, and writes the resulting :class:`FinalSummary` to
``<run_dir>/control/final_summary.json``.

Key improvements over the legacy hook:
- Policy state lives in memory for the whole run (no JSON round-trip per window).
- ``finalize()`` is guaranteed to be called and its output is persisted.
- A single failing window is caught, logged, and skipped; the run continues.
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping

# Ensure repository root is importable when invoked directly from Slurm or CLI.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.experiment import (
    AlgorithmInterface,
    AlgorithmState,
    Decision,
    ExperimentContext,
    FinalSummary,
    MetricWindow,
    StaticPolicy,
    validate_decision,
)
from src.methods.registry import resolve_policy

from scripts.run.control_runtime import (
    append_decision_row,
    append_log,
    apply_decision,
    build_context,
    build_window,
    load_policy_config,
    parse_int_env,
    parse_float_env,
    persist_state,
    utc_now,
    write_last_decision,
    write_run_manifest,
)


class ControlLoopAbortError(RuntimeError):
    """Raised after finalization when the control loop aborts early."""


# Supported values for the ``CONTROL_PHASE`` environment variable:
#   all    - apply the pre-run decision (StaticPolicy only) then run the loop.
#   prerun - apply the pre-run decision only, then exit (set clock before the
#            benchmark process starts).
#   loop   - run the windowed loop only; the pre-run decision was already
#            applied by an earlier ``prerun`` phase in the same job.
_CONTROL_PHASES = frozenset({"all", "prerun", "loop"})


# ---------------------------------------------------------------------------
# Internal stop-condition helper
# ---------------------------------------------------------------------------


def _should_stop(
    window_index: int,
    *,
    max_windows: int | None,
    bench_pid: int | None,
    stop_file: Path | None,
) -> bool:
    """Returns ``True`` when the loop should exit before processing *window_index*."""
    if stop_file is not None and stop_file.exists():
        return True
    if max_windows is not None and window_index >= max_windows:
        return True
    if bench_pid is not None:
        try:
            os.kill(bench_pid, 0)
        except ProcessLookupError:
            # Process is gone — benchmark finished.
            return True
        except PermissionError:
            # Process exists but we cannot signal it — treat as alive.
            pass
    return False


def _get_initial_decision(
    policy: AlgorithmInterface,
    context: ExperimentContext,
    state: AlgorithmState,
) -> Decision | None:
    """Returns a pre-window decision for :class:`StaticPolicy` policies, else ``None``.

    Support is detected structurally: online policies that do not implement
    ``initial_decision`` are not :class:`StaticPolicy` instances and are skipped.
    """
    if not isinstance(policy, StaticPolicy):
        return None
    return policy.initial_decision(context, state)


def _apply_initial_decision_if_present(
    *,
    policy: AlgorithmInterface,
    context: ExperimentContext,
    state: AlgorithmState,
    control_log: Path,
    decisions_csv: Path,
    state_path: Path,
    decision_path: Path,
) -> None:
    """Applies a policy's optional run-level decision before window 0."""
    decision = _get_initial_decision(policy, context, state)
    if decision is None:
        return

    policy_name = context.metadata.policy_name
    validate_decision(decision, context.platform)
    apply_decision(decision, control_log)
    persist_state(state_path, state)
    append_decision_row(decisions_csv, policy_name, decision, window_index=-1)
    write_last_decision(decision_path, policy_name, window_index=-1, decision=decision)
    append_log(
        control_log,
        (
            f"initial_decision policy={policy_name} "
            f"decision={decision.action.value} "
            f"target={decision.target_graphics_clock_mhz} "
            f"reason={decision.reason_code}"
        ),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_control_loop(
    *,
    policy: AlgorithmInterface,
    context: ExperimentContext,
    policy_config: Mapping[str, object],
    run_dir: Path,
    control_log: Path,
    decisions_csv: Path,
    state_path: Path,
    decision_path: Path,
    window_seconds: float,
    max_windows: int | None = None,
    bench_pid: int | None = None,
    stop_file: Path | None = None,
    max_consecutive_failures: int = 5,
    window_builder: Callable[[ExperimentContext, int], MetricWindow] = build_window,
    sleep_fn: Callable[[float], Any] = time.sleep,
    raise_on_abort: bool = False,
    apply_initial_decision: bool = True,
) -> FinalSummary:
    """Runs the DVFS control loop until a stop condition is met.

    Parameters
    ----------
    policy:
        An :class:`AlgorithmInterface` instance.  ``initialize`` is called once
        here; the returned state is kept in memory for the entire run.
    context:
        Experiment context built from environment variables.
    policy_config:
        Policy configuration dict forwarded to ``initialize``.
    run_dir:
        Root directory for all run artifacts.
    control_log:
        Path to the append-only control log file.
    decisions_csv:
        Path to the decisions CSV.
    state_path:
        Path for periodic state snapshots (observability only, not the source
        of truth).
    decision_path:
        Path for the ``last_decision.json`` file (overwritten each window).
    window_seconds:
        Nominal duration of each control window in seconds.
    max_windows:
        Stop after this many windows.  ``None`` means no window limit.
    bench_pid:
        PID of the benchmark process.  Loop exits when the process dies.
        ``None`` means no PID check.
    stop_file:
        If this file exists at the top of any iteration, the loop exits.
    max_consecutive_failures:
        Abort the loop after this many consecutive per-window exceptions.
    window_builder:
        Callable that produces a :class:`MetricWindow` given ``(context,
        window_index)``.  Injectable so tests can supply deterministic data.
    sleep_fn:
        Callable used to wait between windows.  Injectable so tests skip
        sleeping.
    raise_on_abort:
        When true, raise :class:`ControlLoopAbortError` after writing
        ``final_summary.json`` if the loop aborted because of repeated
        per-window failures.  CLI callers use this to return a non-zero exit
        code without losing final artifacts.
    apply_initial_decision:
        When true, apply a :class:`StaticPolicy`'s
        ``initial_decision(context, state)`` before building telemetry window 0.
        Driven by ``CONTROL_PHASE``: true for ``all``, false for ``loop`` (where
        an earlier ``prerun`` phase already applied the prelaunch decision).

    Returns
    -------
    FinalSummary
        The summary returned by ``policy.finalize(state)``.
    """
    policy_name = context.metadata.policy_name

    # Initialise once; keep state in memory for the entire run.
    state: AlgorithmState = policy.initialize(context, policy_config)
    persist_state(state_path, state)
    write_run_manifest(run_dir / "control" / "run_manifest.json", context, policy_config)
    append_log(control_log, f"control_loop started: policy={policy_name}")
    if apply_initial_decision:
        _apply_initial_decision_if_present(
            policy=policy,
            context=context,
            state=state,
            control_log=control_log,
            decisions_csv=decisions_csv,
            state_path=state_path,
            decision_path=decision_path,
        )

    window_index: int = 0
    consecutive_failures: int = 0
    failed_window_count: int = 0
    max_consecutive_failures_observed: int = 0
    abort_reason: str | None = None

    while not _should_stop(
        window_index,
        max_windows=max_windows,
        bench_pid=bench_pid,
        stop_file=stop_file,
    ):
        try:
            metrics = window_builder(context, window_index)
            decision = policy.on_window(metrics, state)
            validate_decision(decision, context.platform)
            apply_decision(decision, control_log)
            persist_state(state_path, state)
            append_decision_row(decisions_csv, policy_name, decision, window_index)
            write_last_decision(decision_path, policy_name, window_index, decision)
            append_log(
                control_log,
                (
                    f"window={window_index} policy={policy_name} "
                    f"decision={decision.action.value} "
                    f"target={decision.target_graphics_clock_mhz} "
                    f"reason={decision.reason_code}"
                ),
            )
            consecutive_failures = 0

        except Exception as exc:  # noqa: BLE001
            consecutive_failures += 1
            failed_window_count += 1
            max_consecutive_failures_observed = max(
                max_consecutive_failures_observed,
                consecutive_failures,
            )
            append_log(
                control_log,
                (
                    f"window {window_index} failed: "
                    f"{type(exc).__name__}: {exc}; continuing"
                ),
            )
            if consecutive_failures >= max_consecutive_failures:
                append_log(
                    control_log,
                    (
                        f"aborting: too many consecutive failures "
                        f"({consecutive_failures})"
                    ),
                )
                abort_reason = (
                    "max_consecutive_failures_reached:"
                    f"{consecutive_failures}/{max_consecutive_failures}"
                )
                break

        window_index += 1
        sleep_fn(window_seconds)

    # Finalise: always called, even if we aborted early.
    summary: FinalSummary = policy.finalize(state)

    summary_dir = run_dir / "control"
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summary_dir / "final_summary.json"

    summary_dict: dict[str, Any] = dataclasses.asdict(summary)
    summary_dict["generated_at_utc"] = utc_now()
    summary_dict["control_status"] = "aborted" if abort_reason else "completed"
    summary_dict["abort_reason"] = abort_reason
    summary_dict["window_failure_count"] = failed_window_count
    summary_dict["max_consecutive_failures_observed"] = max_consecutive_failures_observed
    summary_dict["consecutive_failure_limit"] = max_consecutive_failures
    summary_path.write_text(
        json.dumps(summary_dict, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    append_log(
        control_log,
        (
            f"control_loop finished: policy={policy_name} "
            f"status={summary_dict['control_status']} "
            f"total_windows={summary.total_windows} "
            f"final_summary={summary_path}"
        ),
    )
    if abort_reason and raise_on_abort:
        raise ControlLoopAbortError(abort_reason)
    return summary


def run_initial_decision_only(
    *,
    policy: AlgorithmInterface,
    context: ExperimentContext,
    policy_config: Mapping[str, object],
    run_dir: Path,
    control_log: Path,
    decisions_csv: Path,
    state_path: Path,
    decision_path: Path,
) -> None:
    """Initializes a policy and applies only its optional pre-window decision."""
    state: AlgorithmState = policy.initialize(context, policy_config)
    persist_state(state_path, state)
    write_run_manifest(run_dir / "control" / "run_manifest.json", context, policy_config)
    append_log(
        control_log,
        f"initial_decision_only started: policy={context.metadata.policy_name}",
    )
    _apply_initial_decision_if_present(
        policy=policy,
        context=context,
        state=state,
        control_log=control_log,
        decisions_csv=decisions_csv,
        state_path=state_path,
        decision_path=decision_path,
    )
    append_log(
        control_log,
        f"initial_decision_only finished: policy={context.metadata.policy_name}",
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001 (argv reserved for future use)
    """CLI entry point that reads configuration from environment variables.

    Required env vars
    -----------------
    RUN_DIR
        Root directory for all run artifacts.
    BENCH_ID
        Benchmark identifier (e.g. ``ior``, ``lammps``).

    Optional env vars
    -----------------
    POLICY_NAME (default: ``max_freq``)
        Policy / algorithm identifier.
    RUN_ID (default: ``local-control``)
        Unique identifier for this run.
    BENCH_PID (optional int)
        PID of the benchmark process.  Loop exits when the process dies.
    MAX_WINDOWS (optional int)
        Maximum number of windows to run.  Either ``BENCH_PID`` or
        ``MAX_WINDOWS`` (or both) must be set; the loop refuses to run
        unbounded.
    MAX_CONSECUTIVE_FAILURES (default: ``5``)
        Abort after this many consecutive per-window exceptions.
    CONTROL_LOG (default: ``<run_dir>/control_loop.log``)
        Path to the append-only control log.
    CONTROL_WINDOW_SECONDS (default: ``5.0``)
        Nominal window duration in seconds.
    CONTROL_PHASE (default: ``all``)
        Run phase. ``all`` applies the pre-run decision (for static policies)
        then runs the windowed loop. ``prerun`` applies only the pre-run
        decision and exits, so the clock is set before the benchmark starts;
        it does not require ``BENCH_PID``/``MAX_WINDOWS``. ``loop`` runs only
        the windowed loop and skips the pre-run decision because an earlier
        ``prerun`` phase already applied it.

    Policy config is loaded from ``POLICY_CONFIG_PATH`` or
    ``POLICY_CONFIG_JSON`` (same as ``control_hook.py``).
    Platform / metrics telemetry env vars are identical to those read by
    ``control_hook.py``.

    Returns
    -------
    int
        0 on success, 1 on fatal setup error, 2 on bad arguments.
    """
    run_dir_raw = os.getenv("RUN_DIR", "")
    if not run_dir_raw:
        print("RUN_DIR is required for control loop.", file=sys.stderr)
        return 2
    run_dir = Path(run_dir_raw)

    bench_id = os.getenv("BENCH_ID", "")
    if not bench_id:
        print("BENCH_ID is required for control loop.", file=sys.stderr)
        return 2

    phase = os.getenv("CONTROL_PHASE", "all").strip().lower()
    if phase not in _CONTROL_PHASES:
        supported = ", ".join(sorted(_CONTROL_PHASES))
        print(
            f"Unsupported CONTROL_PHASE={phase!r}. Supported values: {supported}.",
            file=sys.stderr,
        )
        return 2

    # Resolve optional bounds — at least one must be provided for the windowed loop.
    bench_pid_raw = os.getenv("BENCH_PID", "")
    max_windows_raw = os.getenv("MAX_WINDOWS", "")

    bench_pid: int | None = int(bench_pid_raw) if bench_pid_raw else None
    max_windows: int | None = int(max_windows_raw) if max_windows_raw else None

    if phase != "prerun" and bench_pid is None and max_windows is None:
        print(
            "Either BENCH_PID or MAX_WINDOWS must be set to bound the control loop.",
            file=sys.stderr,
        )
        return 2

    policy_name = os.getenv("POLICY_NAME", "max_freq")
    run_id = os.getenv("RUN_ID", "local-control")
    max_consecutive_failures = parse_int_env("MAX_CONSECUTIVE_FAILURES", 5)

    control_log = Path(os.getenv("CONTROL_LOG", str(run_dir / "control_loop.log")))
    decisions_csv = Path(
        os.getenv("CONTROL_DECISIONS_CSV", str(run_dir / "control" / "decisions.csv"))
    )
    state_path = run_dir / "control" / "policy_state.json"
    decision_path = run_dir / "control" / "last_decision.json"
    stop_file = run_dir / "control" / "STOP"

    started_at_utc = os.getenv("CONTROL_STARTED_AT_UTC", utc_now())
    os.environ["CONTROL_STARTED_AT_UTC"] = started_at_utc

    try:
        policy_config = load_policy_config()
        policy = resolve_policy(policy_name)
        context = build_context(policy_name, bench_id, run_id, started_at_utc)
        window_seconds = parse_float_env("CONTROL_WINDOW_SECONDS", 5.0)

        if phase == "prerun":
            run_initial_decision_only(
                policy=policy,
                context=context,
                policy_config=policy_config,
                run_dir=run_dir,
                control_log=control_log,
                decisions_csv=decisions_csv,
                state_path=state_path,
                decision_path=decision_path,
            )
            return 0

        run_control_loop(
            policy=policy,
            context=context,
            policy_config=policy_config,
            run_dir=run_dir,
            control_log=control_log,
            decisions_csv=decisions_csv,
            state_path=state_path,
            decision_path=decision_path,
            window_seconds=window_seconds,
            max_windows=max_windows,
            bench_pid=bench_pid,
            stop_file=stop_file,
            max_consecutive_failures=max_consecutive_failures,
            raise_on_abort=True,
            apply_initial_decision=phase == "all",
        )
        return 0

    except ControlLoopAbortError as exc:
        try:
            append_log(control_log, f"control loop aborted: {exc}")
        except Exception:  # noqa: BLE001
            pass
        print(f"control loop aborted: {exc}", file=sys.stderr)
        return 1

    except Exception as exc:  # noqa: BLE001
        try:
            append_log(control_log, f"fatal setup error: {type(exc).__name__}: {exc}")
        except Exception:  # noqa: BLE001
            pass
        print(f"control loop fatal error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
