#!/usr/bin/env python3
"""Legacy single-window control hook.  Prefer ``control_loop.py`` for new deployments."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repository root is importable when invoked from Slurm hooks.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.common.experiment import StaticPolicy, validate_decision
from src.methods.registry import resolve_policy

from scripts.run.control_runtime import (
    append_decision_row,
    append_log,
    apply_decision,
    build_context,
    build_window,
    load_or_initialize_state,
    load_policy_config,
    parse_int_env,
    persist_state,
    utc_now,
    write_last_decision,
)


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
    decisions_csv = Path(
        os.getenv("CONTROL_DECISIONS_CSV", str(run_dir / "control" / "decisions.csv"))
    )
    state_path = run_dir / "control" / "policy_state.json"
    decision_path = run_dir / "control" / "last_decision.json"

    started_at_utc = os.getenv("CONTROL_STARTED_AT_UTC", utc_now())
    os.environ["CONTROL_STARTED_AT_UTC"] = started_at_utc

    try:
        policy_config = load_policy_config()
        policy = resolve_policy(policy_name)
        context = build_context(policy_name, bench_id, run_id, started_at_utc)
        state = load_or_initialize_state(state_path, policy, context, policy_config)

        decision_window_index = window_index
        decision = None
        if window_index == 0 and isinstance(policy, StaticPolicy):
            decision = policy.initial_decision(context, state)
            decision_window_index = -1

        if decision is None:
            metrics = build_window(context, window_index)
            decision = policy.on_window(metrics, state)

        validate_decision(decision, context.platform)
        apply_decision(decision, control_log)

        persist_state(state_path, state)
        append_decision_row(decisions_csv, policy_name, decision, decision_window_index)
        write_last_decision(decision_path, policy_name, decision_window_index, decision)

        append_log(
            control_log,
            (
                f"window={decision_window_index} policy={policy_name} "
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
