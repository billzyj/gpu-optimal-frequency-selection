#!/usr/bin/env bash
#SBATCH --job-name=gpu-dvfs-controlled
#SBATCH --output=artifacts/raw/slurm-controlled-%j.out
#SBATCH --error=artifacts/raw/slurm-controlled-%j.err
#SBATCH --time=02:00:00

set -euo pipefail

# Controlled-mode orchestration template.
#
# This script is submitted from this repository and owns the job lifecycle.
# It starts an external benchmark adapter command as a child process,
# then runs a long-lived control loop runner in the same allocation.
# The runner owns the per-window loop, sleeping, state, and finalization
# internally and exits when the benchmark process dies.
#
# Required environment variables:
# - BENCH_ID: benchmark id used by external contract path (e.g., ior, lammps, hpl, osu)
# - BENCH_RUN_SCRIPT: path relative to external repo root
#   (e.g., benchmarks/ior/adapters/repacss/run.sh)
#
# Optional environment variables:
# - POLICY_NAME: algorithm/policy label (default: max_freq)
# - PD_TARGET: performance-degradation target (default: 0.0)
# - CONTROL_WINDOW_SECONDS: per-window sleep interval used by the runner (default: 5)
# - SITE_PROFILE: external site profile (default: repacss_zen4)
# - EXPERIMENT_ID: experiment id in run artifacts (default: controlled)
# - RUN_ROOT: external run root directory (default: <repo>/artifacts/raw/external_runs)
# - RUN_ID: external run id (default: job-<slurm_job_id>-<policy>)
# - BENCH_ARGS: benchmark run arguments passed to BENCH_RUN_SCRIPT
# - BENCH_PID: set automatically by this orchestrator from the benchmark child process;
#   exported to the runner so it can loop while that pid is alive
# - CONTROL_LOOP_CMD: command for the long-lived runner process
#   (default: python3 scripts/run/control_loop.py)
# - MAX_CONSECUTIVE_FAILURES: max consecutive window failures before the runner aborts
#   (default: 5, passed through to control_loop.py via env)
# - POLICY_CONFIG_PATH / POLICY_CONFIG_JSON: optional policy config for control_loop.py
# - APPLY_CLOCK_CMD_TEMPLATE: optional apply command template for control_loop.py
# - APPLY_CLOCK_RESET_CMD: optional reset command run during cleanup/trap
# - CONTROL_DECISIONS_CSV: optional control decision CSV path
#
# Example:
# sbatch --export=ALL,\
# BENCH_ID=ior,\
# BENCH_RUN_SCRIPT=benchmarks/ior/adapters/repacss/run.sh,\
# POLICY_NAME=max_freq,\
# PD_TARGET=0.1,\
# CONTROL_WINDOW_SECONDS=10 \
# scripts/run/controlled_mode.sbatch

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXTERNAL_REPO_ROOT="${EXTERNAL_REPO_ROOT:-${REPO_ROOT}/external/repacss-benchmarking}"

BENCH_ID="${BENCH_ID:-}"
BENCH_RUN_SCRIPT="${BENCH_RUN_SCRIPT:-}"
POLICY_NAME="${POLICY_NAME:-max_freq}"
PD_TARGET="${PD_TARGET:-0.0}"
CONTROL_WINDOW_SECONDS="${CONTROL_WINDOW_SECONDS:-5}"
SITE_PROFILE="${SITE_PROFILE:-repacss_zen4}"
EXPERIMENT_ID="${EXPERIMENT_ID:-controlled}"
RUN_ROOT="${RUN_ROOT:-${REPO_ROOT}/artifacts/raw/external_runs}"
RUN_ID="${RUN_ID:-job-${SLURM_JOB_ID:-local}-${POLICY_NAME}}"
BENCH_ARGS="${BENCH_ARGS:-}"
CONTROL_LOOP_CMD="${CONTROL_LOOP_CMD:-}"
APPLY_CLOCK_RESET_CMD="${APPLY_CLOCK_RESET_CMD:-}"

if [[ -z "$BENCH_ID" || -z "$BENCH_RUN_SCRIPT" ]]; then
  echo "Error: BENCH_ID and BENCH_RUN_SCRIPT are required."
  exit 2
fi

if [[ ! -d "$EXTERNAL_REPO_ROOT" ]]; then
  echo "Error: external repo not found: $EXTERNAL_REPO_ROOT"
  exit 2
fi

BENCH_SCRIPT_ABS="${EXTERNAL_REPO_ROOT}/${BENCH_RUN_SCRIPT}"
if [[ ! -f "$BENCH_SCRIPT_ABS" ]]; then
  echo "Error: benchmark run script not found: $BENCH_SCRIPT_ABS"
  exit 2
fi

mkdir -p "$RUN_ROOT" "${REPO_ROOT}/artifacts/raw"

# Export external contract variables so the benchmark adapter writes run artifacts
# to a deterministic location known by the orchestration layer.
export SITE_PROFILE
export EXPERIMENT_ID
export RUN_ROOT
export RUN_ID

RUN_DIR="${RUN_ROOT%/}/${EXPERIMENT_ID}/${SITE_PROFILE}/${BENCH_ID}/${RUN_ID}"
CONTROL_LOG="${RUN_DIR}/control_loop.log"
mkdir -p "$RUN_DIR"

if [[ -z "$CONTROL_LOOP_CMD" ]]; then
  CONTROL_LOOP_CMD="python3 \"$REPO_ROOT/scripts/run/control_loop.py\""
fi

echo "[orchestrator] repo_root=$REPO_ROOT"
echo "[orchestrator] external_repo_root=$EXTERNAL_REPO_ROOT"
echo "[orchestrator] policy=$POLICY_NAME pd_target=$PD_TARGET"
echo "[orchestrator] bench_id=$BENCH_ID"
echo "[orchestrator] bench_script=$BENCH_SCRIPT_ABS"
echo "[orchestrator] run_dir=$RUN_DIR"

# Start benchmark workload as a child process inside this allocation.
# Do not submit a nested independent batch job from this layer.
set +e
bash -lc "\"$BENCH_SCRIPT_ABS\" $BENCH_ARGS" &
BENCH_PID=$!
set -e

cleanup() {
  if kill -0 "$BENCH_PID" >/dev/null 2>&1; then
    kill "$BENCH_PID" >/dev/null 2>&1 || true
  fi
  reset_clock
}

RESET_CLOCK_ATTEMPTED=0
reset_clock() {
  if [[ -z "$APPLY_CLOCK_RESET_CMD" || "$RESET_CLOCK_ATTEMPTED" -ne 0 ]]; then
    return
  fi
  RESET_CLOCK_ATTEMPTED=1
  echo "[orchestrator] resetting clock via APPLY_CLOCK_RESET_CMD"
  set +e
  bash -lc "$APPLY_CLOCK_RESET_CMD"
  RESET_RC=$?
  set -e
  if [[ "$RESET_RC" -ne 0 ]]; then
    echo "[orchestrator] warning: clock reset command failed: $RESET_RC"
  fi
}
trap cleanup EXIT INT TERM

# Export all env the runner needs; BENCH_PID tells the runner which process to
# watch — it will loop internally until that pid exits, then finalize and return.
export REPO_ROOT EXTERNAL_REPO_ROOT POLICY_NAME PD_TARGET CONTROL_WINDOW_SECONDS
export BENCH_ID BENCH_SCRIPT_ABS RUN_DIR CONTROL_LOG BENCH_PID

# Run the long-lived control loop runner once in the foreground.
# It blocks and loops internally (initialize -> on_window* -> finalize) until
# the benchmark pid dies, then writes control/final_summary.json and returns.
# Use set +e so a non-zero runner exit does not bypass the wait/cleanup below.
set +e
bash -lc "$CONTROL_LOOP_CMD"
CONTROL_RC=$?
set -e

echo "[orchestrator] control loop return code: $CONTROL_RC"
if [[ "$CONTROL_RC" -ne 0 ]]; then
  cleanup
fi

set +e
wait "$BENCH_PID"
BENCH_RC=$?
set -e

echo "[orchestrator] benchmark return code: $BENCH_RC"
if [[ "$CONTROL_RC" -ne 0 ]]; then
  exit "$CONTROL_RC"
fi
if [[ "$BENCH_RC" -ne 0 ]]; then
  exit "$BENCH_RC"
fi

echo "[orchestrator] completed successfully"
echo "[orchestrator] normalized summary (expected): ${RUN_DIR}/normalized/summary.json"
