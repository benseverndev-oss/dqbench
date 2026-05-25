---
layout: default
title: GoldenMatch native-kernel ER validation
nav_order: 7
---

# GoldenMatch native kernels — DQBench ER validation (2026-05-25)

GoldenMatch ships optional Rust acceleration kernels (the PyO3 extension
`goldenmatch._native`) for two hot paths — **clustering** (`core/cluster.py`) and
**block-scoring** (`backends/score_buckets.py::score_block_pairs`) — behind a gate
(`core/_native_loader._GATED_ON`, default pure-Python). Before flipping the default to
native, the kernels must be proven against the DQBench ER composite:

1. the composite stays **≥ 91.04** (the v1.12 ship number), and
2. it is **identical** to the pure-Python baseline (the kernels are unit-tested as
   bit-exact, so any nonzero delta is a real finding, not noise).

## Result

| Mode | Composite | T1 F1 | T2 F1 | T3 F1 | T4 F1 (diagnostic, weight 0) |
|------|-----------|-------|-------|-------|------------------------------|
| Pure Python (`GOLDENMATCH_NATIVE=0`) | **92.03** | 0.8929 | 0.9836 | 0.8707 | 0.9195 |
| Native kernels (`GOLDENMATCH_NATIVE=1`) | **92.03** | 0.8929 | 0.9836 | 0.8707 | 0.9195 |
| **Delta** | **0.00** | 0 | 0 | 0 | 0 |

- **Criterion 1 (≥ 91.04): PASS** — 92.03. (Higher than 91.04 because this run uses
  goldenmatch `1.19.0`, not the v1.12 build the ship number was measured on.)
- **Criterion 2 (exact equality): PASS** — bit-identical at every tier, including
  precision, recall, TP/FP/FN, and the B³ cluster metrics. Only wall-time and peak
  memory differ between the two runs (expected).

Per-tier run JSON for both modes is committed under
[`evidence/`](evidence/): `dq_python.json` (`NATIVE=0`) and `dq_native.json`
(`NATIVE=1`).

## Coverage caveat — which kernel actually ran

`GOLDENMATCH_NATIVE=1` forces both gated components on, but only the kernels the
selected backend reaches actually execute. The zero-config controller chose the
**`polars-direct`** backend on every DQBench tier (T1=1k, T2=5k, T3=10k, T4=800 rows —
too small to trip the bucket backend). Instrumenting the native module to count calls:

| Tier | Backend | `connected_components` | `cluster_confidence` | `severe_bridge_count` | `score_block_pairs` |
|------|---------|------------------------|----------------------|-----------------------|---------------------|
| 1 | polars-direct | 5 | 4420 | 436 | **0** |
| 2 | polars-direct | 5 | 11541 | 637 | **0** |
| 3 | polars-direct | 5 | 15098 | 566 | **0** |
| 4 | polars-direct | 5 | 3545 | 352 | **0** |

- The **clustering** kernel is exercised heavily on every tier — its bit-exact parity is
  validated by this run.
- The **block-scoring** kernel (`score_block_pairs`) **never fires** on DQBench, because
  the bucket backend is never selected. Its parity therefore rests on the GoldenMatch
  unit tests only, and must be validated separately with a bucket-backend workload
  before its default is flipped.

## Environment

| Component | Version |
|-----------|---------|
| goldenmatch | 1.19.0 (`main`) |
| goldenmatch._native | 0.1.0 |
| Rust toolchain | 1.94.1 (pinned by `rust-toolchain.toml`) |
| dqbench | 1.1.0 |
| Python | 3.11 |

DQBench ER datasets are deterministic (`random.Random(42)`); the same cached datasets
were used for both runs.

## Runbook executed

From a clean `goldenmatch` `main` checkout, with dqbench installed into the same env:

```bash
uv sync --all-packages
uv run python scripts/build_native.py          # builds goldenmatch._native (Rust 1.94.1)
uv pip install -e <dqbench>                     # puts the dqbench CLI on PATH

# Gate sanity check
GOLDENMATCH_NATIVE=1 uv run python -c "import goldenmatch._native as n; \
  from goldenmatch.core._native_loader import native_enabled; \
  print(n.__version__, native_enabled('block_scoring'), native_enabled('clustering'))"
# -> 0.1.0 True True

# Same env, same datasets, autoconfig memory cache OFF
GOLDENMATCH_AUTOCONFIG_MEMORY=0 GOLDENMATCH_NATIVE=0 \
  uv run dqbench run goldenmatch-zeroconfig \
    --adapter scripts/dqbench_adapters/goldenmatch_zeroconfig.py --json
GOLDENMATCH_AUTOCONFIG_MEMORY=0 GOLDENMATCH_NATIVE=1 \
  uv run dqbench run goldenmatch-zeroconfig \
    --adapter scripts/dqbench_adapters/goldenmatch_zeroconfig.py --json
```

## Why this entry is on the reference (ungated) board

The published leaderboard's reproducibility gate re-runs each entry from pinned pip
packages on a clean runner. This result cannot pass that gate: it requires building the
`goldenmatch._native` Rust extension from the goldenmatch repo (via
`scripts/build_native.py`), which dqbench's pip-only CI cannot do. The entry is
therefore recorded on the **reference (not gate-verified)** board
(`leaderboard/reference/er.json`, manifest `gated: false`). Note this is *not* because
the run is non-deterministic — it is provably bit-exact against the pure-Python path, as
shown above.
