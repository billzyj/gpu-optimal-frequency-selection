#!/usr/bin/env bash
set -euo pipefail

SUBMODULE_PATH="external/repacss-benchmarking"
TARGET_BRANCH="main"
AUTO_STAGE=0

print_usage() {
  cat <<'USAGE'
Update external benchmark submodule to latest commit on target branch.

Usage:
  scripts/update_submodules.sh [options]

Options:
  --path <path>       Submodule path (default: external/repacss-benchmarking)
  --branch <branch>   Target branch to fast-forward (default: main)
  --stage             Run git add <submodule-path> after update
  -h, --help          Show this help message
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path)
      [[ $# -ge 2 ]] || { echo "Missing value for --path" >&2; exit 2; }
      SUBMODULE_PATH="$2"
      shift 2
      ;;
    --branch)
      [[ $# -ge 2 ]] || { echo "Missing value for --branch" >&2; exit 2; }
      TARGET_BRANCH="$2"
      shift 2
      ;;
    --stage)
      AUTO_STAGE=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      print_usage >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ ! -f .gitmodules ]]; then
  echo "No .gitmodules found in repository root: $REPO_ROOT" >&2
  exit 1
fi

if ! git config -f .gitmodules --get-regexp '^submodule\..*\.path$' | awk '{print $2}' | grep -Fxq "$SUBMODULE_PATH"; then
  echo "Configured submodule path not found in .gitmodules: $SUBMODULE_PATH" >&2
  exit 1
fi

if [[ ! -d "$SUBMODULE_PATH" ]]; then
  echo "Submodule directory not found. Initializing submodules first..."
fi

echo "[1/4] Initializing submodules..."
git submodule update --init --recursive

OLD_SHA="$(git -C "$SUBMODULE_PATH" rev-parse HEAD)"

echo "[2/4] Fetching latest refs for $SUBMODULE_PATH..."
git -C "$SUBMODULE_PATH" fetch origin

echo "[3/4] Fast-forwarding $SUBMODULE_PATH to origin/$TARGET_BRANCH..."
git -C "$SUBMODULE_PATH" checkout "$TARGET_BRANCH"
git -C "$SUBMODULE_PATH" pull --ff-only origin "$TARGET_BRANCH"

echo "[4/4] Syncing nested submodules under $SUBMODULE_PATH..."
git -C "$SUBMODULE_PATH" submodule update --init --recursive

NEW_SHA="$(git -C "$SUBMODULE_PATH" rev-parse HEAD)"

echo "Updated $SUBMODULE_PATH"
echo "  old: $OLD_SHA"
echo "  new: $NEW_SHA"

if [[ "$AUTO_STAGE" -eq 1 ]]; then
  git add "$SUBMODULE_PATH"
  echo "Staged submodule pointer update: $SUBMODULE_PATH"
else
  echo "Submodule pointer is not staged. Stage it with: git add $SUBMODULE_PATH"
fi
