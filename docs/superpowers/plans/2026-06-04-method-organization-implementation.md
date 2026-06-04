# Method Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move comparison algorithms under `src/methods/comparison_methods` and mirror method/script/common tests under the matching owner paths.

**Architecture:** Keep `src/methods/registry.py` as the stable policy-name boundary. Keep `proposed_methods` as the user's method space. Group all comparison methods by source type: `system_baselines`, `local_reproductions`, and `external_integrations`.

**Tech Stack:** Python package imports, `unittest`, Markdown documentation.

---

### Task 1: Source Layout Migration

**Files:**
- Move: `src/methods/system_baselines/`
- Move: existing local reproduction implementation directories
- Create: `src/methods/comparison_methods/__init__.py`
- Create: `src/methods/comparison_methods/README.md`
- Create: `src/methods/comparison_methods/external_integrations/__init__.py`
- Create: `src/methods/comparison_methods/external_integrations/README.md`

- [x] **Step 1: Move comparison method directories**

Run:

```bash
mkdir -p src/methods/comparison_methods
mv src/methods/system_baselines src/methods/comparison_methods/
mkdir -p src/methods/comparison_methods/local_reproductions
mv <local-reproduction-method-dir> src/methods/comparison_methods/local_reproductions/
mkdir -p src/methods/comparison_methods/external_integrations
```

- [x] **Step 2: Add comparison package docs and init files**

Create package init files and README files that explain the three comparison categories and external-method adapter boundary.

### Task 2: Test Layout Migration

**Method test files:**
- Move: `tests/system_baselines/`
- Move: `tests/everest/`
- Move: `tests/ali_2022/`
- Move: `tests/oracle_static/`
- Create: `tests/methods/__init__.py`
- Create: `tests/methods/comparison_methods/__init__.py`
- Create: `tests/methods/comparison_methods/local_reproductions/__init__.py`

**Non-method test files:**
- Move: `tests/experiment/`
- Move: `tests/telemetry/`
- Move: `tests/run/`
- Create: `tests/common/__init__.py`
- Create: `tests/scripts/__init__.py`

- [x] **Step 1: Move method test directories**

Run:

```bash
mkdir -p tests/methods/comparison_methods/local_reproductions
mv tests/system_baselines tests/methods/comparison_methods/
mv tests/everest tests/methods/comparison_methods/local_reproductions/everest_reimpl
mv tests/ali_2022 tests/methods/comparison_methods/local_reproductions/ali_2022_reimpl
mv tests/oracle_static tests/methods/comparison_methods/local_reproductions/oracle_static
```

- [x] **Step 2: Move common and script tests**

Run:

```bash
mkdir -p tests/common tests/scripts
mv tests/experiment tests/common/experiment
mv tests/telemetry tests/common/telemetry
mv tests/run tests/scripts/run
```

- [x] **Step 3: Add test package init files**

Create `__init__.py` files so `python3 -m unittest discover -s tests -t . -p "test_*.py"` discovers all tests with the repository root as the import top-level.

### Task 3: Import and Registry Updates

**Files:**
- Modify: `src/methods/registry.py`
- Modify: moved policy modules and tests with old import paths

- [x] **Step 1: Rewrite import paths**

Replace:

```text
src.methods.system_baselines
src.methods.reimplemented_methods
```

with:

```text
src.methods.comparison_methods.system_baselines
src.methods.comparison_methods.local_reproductions
```

- [x] **Step 2: Run targeted method tests**

Run:

```bash
python3 -m unittest discover -s tests/methods -p "test_*.py"
```

Expected: all method tests pass.

### Task 4: Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `docs/REPO_ARCHITECTURE.md`
- Modify: `src/README.md`
- Modify: `src/methods/README.md`
- Modify: moved method README files
- Modify: any tests/docs that mention old paths

- [x] **Step 1: Update source and test layout docs**

Update documentation to show:

```text
src/methods/
|-- registry.py
|-- proposed_methods/
`-- comparison_methods/
    |-- system_baselines/
    |-- local_reproductions/
    `-- external_integrations/
```

- [x] **Step 2: Scan for stale paths**

Run:

```bash
rg -n -g '!docs/superpowers/**' "reimplemented_methods|external_methods|src/methods/(system_baselines|local_reproductions|external_integrations)|src\\.methods\\.(system_baselines|reimplemented_methods|local_reproductions|external_integrations)|tests/(system_baselines|everest|ali_2022|oracle_static|experiment|telemetry|run)(/|$)" README.md docs src tests scripts
```

Expected: no source-code imports or user-facing docs bypass `comparison_methods`;
only implementation-plan/spec migration notes may mention legacy paths.

### Task 5: Final Verification

**Files:**
- All moved and edited files

- [x] **Step 1: Run full test suite**

Run:

```bash
python3 -m unittest discover -s tests -t . -p "test_*.py"
```

Expected: all tests pass.

- [x] **Step 2: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.
