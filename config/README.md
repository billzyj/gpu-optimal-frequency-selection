# Configuration

Shared experiment configuration for all algorithms.

## Layout

1. `common`: global defaults (logging, sampling, output schema).
2. `platforms`: hardware and vendor-specific capabilities.
3. `workloads`: benchmark input sets and launch metadata.
4. `experiments`: run matrices and sweep definitions.
5. `algorithms`: per-algorithm parameters (`everest`, `my_algo`, etc.).
