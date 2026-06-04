# Local Reproductions

This directory contains comparison algorithms implemented and maintained in this
repository. Use this category when no directly usable third-party
implementation exists, or when available code cannot be used unchanged through a
thin adapter. Each subdirectory should be traceable to explicit citation
metadata before it is used in experiments or manuscript claims.

## Citation Ledger

| Directory | Local reproduction target | Primary citation | DOI / URL | Source cache trace | Implementation status |
|---|---|---|---|---|---|
| `everest_reimpl/` | EVeREST runtime GPU energy-saving method: phase identification, phase characterization, and frequency scaling. | Anna Yue, Pen-Chung Yew, and Sanyam Mehta. 2025. "EVeREST: An Effective and Versatile Runtime Energy Saving Tool for GPUs." PPoPP '25. | <https://doi.org/10.1145/3710848.3710875> | `topics/power_management`, item_key `8AY5ISNG`; co-located source copy in `everest_reimpl/paper/`. | Core stages and online `EverestPolicy` implemented; hardware telemetry/control validation pending. |
| `ali_2022_reimpl/` | Ali HPEC 2022 analytical GPU frequency-selection baseline based on offline power/performance model calibration. | Ghazanfar Ali, Sridutt Bhalachandra, Nicholas J. Wright, Mert Side, and Yong Chen. 2022. "Optimal GPU Frequency Selection using Multi-Objective Approaches for HPC Systems." HPEC 2022. | <https://doi.org/10.1109/HPEC55821.2022.9926317> | `topics/power_management`, item_key `D9D98WW7`; co-located source copy in `ali_2022_reimpl/paper/`. | Implemented as `AliFrequencySelectionPolicy` with policy name `ali_2022_reimpl`; coefficients and DCGMI field mapping must be verified before numerical reproduction claims. |
| `oracle_static/` | Static oracle baseline: choose the lowest offline-swept frequency that satisfies a target performance-degradation bound. | Evaluation baseline used in EVeREST and related GPU DVFS comparisons; not a standalone published method. Cite the paper whose evaluation protocol is being reproduced, currently EVeREST. | <https://doi.org/10.1145/3710848.3710875> | `topics/power_management`, item_key `8AY5ISNG`; local ignored source cache may live in `oracle_static/paper/`, with EVeREST also cached under `everest_reimpl/paper/`. | Implemented as `StaticOraclePolicy`; baseline scope recorded in `oracle_static/docs/ORACLE_STATIC_REPRODUCTION_PLAN.md`. |

Runtime policy names are defined in `src/methods/registry.py`:

1. `everest`
2. `ali_2022_reimpl`
3. `oracle_static`

Do not use a local reproduction in experiments or manuscript claims unless the
ledger row, local README, reproduction plan, tests, and registry entry all agree
on the method scope.

## Companion Sources

The following papers are related to `ali_2022_reimpl/` and may become primary or secondary sources depending on which variant is implemented:

| Source role | Citation | DOI / URL | Source cache trace | Notes |
|---|---|---|---|---|
| DNN-based model variant | Ghazanfar Ali, Mert Side, Sridutt Bhalachandra, Nicholas J. Wright, and Yong Chen. 2023. "Performance-Aware Energy-Efficient GPU Frequency Selection using DNN-based Models." ICPP '23. | <https://doi.org/10.1145/3605573.3605600> | `topics/power_management`, item_key `EIVPISAU`. | Keep separate from `ali_2022_reimpl`; use only for a DNN/model-training reimplementation. |
| Journal-length portable selection source | Ghazanfar Ali, Mert Side, Sridutt Bhalachandra, Nicholas J. Wright, and Yong Chen. 2023. "An automated and portable method for selecting an optimal GPU frequency." Future Generation Computer Systems. | <https://doi.org/10.1016/j.future.2023.07.011> | `topics/power_management`, item_key `8W5J6Z7L`. | Useful for a broader portable-frequency-selection implementation and literature framing. |

## Rules for New Local Reproductions

Before adding a new subdirectory under
`src/methods/comparison_methods/local_reproductions/`, update this README
with:

1. The target method name and the exact paper/system being reproduced.
2. Full citation metadata: authors, year, title, venue if known, DOI or stable URL.
3. The repository source trace: topic cache name, `item_key`, and co-located PDF/text path when available.
4. Implementation scope: exact reproduction, best-effort approximation, proxy baseline, or evaluation-only baseline.
5. Known deviations from the paper, including unavailable counters, missing training artifacts, hardware differences, or benchmark substitutions.

Prefer a `paper/` directory inside each local reproduction when the method depends
on a specific publication. Keep method-specific reproduction plans in that same
method directory under `docs/`.

Do not use a local reproduction for paper claims until its citation metadata and implementation deviations are recorded here.

## Source Caching and Licensing

1. Co-located `paper/` folders are git-ignored (`/src/methods/comparison_methods/local_reproductions/*/paper/`). They are a local-only source cache and are never committed, so the provenance of record is this ledger and the tracked `docs/` reproduction plans, not the ignored `paper/` folders.
2. Do not commit or redistribute publisher PDFs or extracted full text. The tracked source of truth is the citation ledger and each method's reproduction plan; ignored `paper/` folders are local convenience caches only.
3. Before making this repository public, confirm no publisher PDF remains in the working tree or in git history. An earlier copy at `references/papers/EVEREST_ppopp25.pdf` exists in history (commit `129b78b`); fully purging it would require history rewriting (for example, `git filter-repo`).
