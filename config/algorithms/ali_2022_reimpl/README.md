# Ali HPEC 2022 Config

`ali_2022_reimpl` is an offline, whole-workload selector. It requires fitted
model coefficients plus one max-frequency profile for the target workload.
Pass this config through `POLICY_CONFIG_PATH` or `POLICY_CONFIG_JSON` when
running `POLICY_NAME=ali_2022_reimpl`.

## Minimal Schema

```json
{
  "objective": "edp",
  "frequencies_mhz": [510, 525, 540, 555],
  "f_max_mhz": 1380,
  "fp_activity": 0.25,
  "dram_activity": 0.40,
  "t_fmax_s": 12.34,
  "power_coefficients": {
    "alpha": 0.0,
    "beta": 0.0,
    "gamma": 0.0,
    "constant": 0.0
  },
  "performance_coefficients": {
    "beta1": 0.0,
    "beta2": 0.0,
    "beta3": 0.0,
    "beta4": 0.0,
    "beta5": 0.0
  }
}
```

## Notes

1. `objective` must be `energy`, `edp`, or `ed2p`; default is `edp`.
2. `frequencies_mhz` should match the calibrated platform frequency list.
3. `fp_activity`, `dram_activity`, and `t_fmax_s` are target-workload
   max-frequency profile values.
4. Coefficients come from offline calibration; do not fit them inside the
   runtime policy.
5. See
   `src/methods/comparison_methods/local_reproductions/ali_2022_reimpl/README.md`
   for the reproduction workflow and source notes.
