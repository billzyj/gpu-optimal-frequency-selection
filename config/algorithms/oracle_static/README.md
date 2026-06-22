# Oracle Static Config

`oracle_static` selects one fixed graphics clock from offline sweep results.
Pass this config through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON` when
running `POLICY_NAME=oracle_static`.

## Minimal schema

Faithful oracle runs require an exact `workload_profiles[workload_name]` entry
for the workload being run. The profile must come from the same workload input,
GPU, driver/runtime stack, and measurement protocol used for the comparison.

```yaml
workload_profiles:
  lammps-reaxff:
    - frequency_mhz: 1410
      performance_ratio: 1.00
      power_w: 490
    - frequency_mhz: 1260
      performance_ratio: 0.94
      power_w: 430
    - frequency_mhz: 1110
      performance_ratio: 0.86
      power_w: 390
```

## Proxy profile schema

Fallback profiles are not paper-faithful oracle inputs. They are accepted only
when explicitly labeled with `allow_proxy_profile: true`; final summaries record
`profile_mode: proxy`, the profile provenance, and whether the selected profile
actually met the target.

```yaml
allow_proxy_profile: true
workload_profiles:
  default:
    - frequency_mhz: 1410
      performance_ratio: 1.00
    - frequency_mhz: 1200
      performance_ratio: 0.91
```

## Notes

1. `performance_ratio` is relative to max-frequency runtime (`1.0` means max-frequency performance).
2. For a target `PD`, the policy picks the lowest frequency with `performance_ratio >= (1 - PD)`.
3. In faithful mode, initialization fails if no in-domain profile point meets
   the target. Proxy mode may report a target-missing fallback, but it is marked
   with `selection_meets_target: false`.
4. By default, profile points below the EVeREST paper domain are ignored:
   `max(platform_min_clock, 900 MHz)` when the platform maximum is at least
   900 MHz, otherwise the platform minimum. Set
   `enforce_paper_frequency_floor: false` only for explicitly labeled broader
   oracle-domain studies.
5. The selected clock is still clamped to platform min/max bounds by the policy.
6. The policy satisfies the `StaticPolicy` protocol via
   `initial_decision(context, state)` and records
   `pre_run_target_graphics_clock_mhz` in state/debug/summary fields so the
   shared runner can apply the selected fixed clock once before the first
   measurement window. `on_window` is monitor-only.
