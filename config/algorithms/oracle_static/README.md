# Oracle Static Config

`oracle_static` selects one fixed graphics clock from offline sweep results.
Pass this config through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON` when
running `POLICY_NAME=oracle_static`.

## Minimal schema

```yaml
profile:
  - frequency_mhz: 1410
    performance_ratio: 1.00
    power_w: 490
  - frequency_mhz: 1260
    performance_ratio: 0.93
    power_w: 430
  - frequency_mhz: 1110
    performance_ratio: 0.86
    power_w: 390
```

## Per-workload schema

```yaml
workload_profiles:
  lammps-reaxff:
    - frequency_mhz: 1410
      performance_ratio: 1.00
    - frequency_mhz: 1260
      performance_ratio: 0.94
  default:
    - frequency_mhz: 1410
      performance_ratio: 1.00
    - frequency_mhz: 1200
      performance_ratio: 0.91
```

## Notes

1. `performance_ratio` is relative to max-frequency runtime (`1.0` means max-frequency performance).
2. For a target `PD`, the policy picks the lowest frequency with `performance_ratio >= (1 - PD)`.
3. If no point meets target, it falls back to the best available `performance_ratio`.
4. Profile points must come from the same workload input, GPU, driver stack, and
   measurement protocol used for the comparison run.
5. The selected clock is still clamped to platform min/max bounds by the policy.
