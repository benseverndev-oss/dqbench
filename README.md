# DQBench

The standard benchmark for data quality tools — detection, transformation, entity resolution, and pipeline orchestration.

[![PyPI](https://img.shields.io/pypi/v/dqbench?color=d4a017)](https://pypi.org/project/dqbench/)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![Tests](https://img.shields.io/badge/tests-178%20passing-brightgreen)
![Categories](https://img.shields.io/badge/categories-5-orange)
![OCR Company Benchmark](https://img.shields.io/badge/OCR%20company-benchmark-included-blue)
![ER Benchmark](https://img.shields.io/badge/ER%20benchmark-included-blueviolet)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

> The ImageNet of data quality — standardized benchmarks for validation, transformation, entity resolution, and pipeline tools.

## Why DQBench?

Every data quality tool claims to be the best. But there's no standard way to compare them. DQBench fixes that with:

- **Four benchmark categories** — Detect, Transform, ER, and Pipeline
- **Three difficulty tiers** — basics, realistic, and adversarial
- **Ground truth** — every planted issue is documented with affected rows
- **Fair scoring** — recall AND precision matter (no gaming by flagging everything)
- **One number** — DQBench Score (0-100) for easy comparison
- **20-line integration** — implement one method to benchmark any tool

## Install

The repo now also includes an `OCR Company` benchmark for post-OCR company-name confidence and correction quality.

```bash
pip install dqbench
```

## Quick Start

```bash
# Run detection benchmark with GoldenCheck
pip install goldencheck
dqbench run goldencheck

# Run ER benchmark with GoldenMatch
pip install goldenmatch
dqbench run goldenmatch

# Run pipeline benchmark with GoldenPipe
pip install goldenpipe
dqbench run goldenpipe

# Run with a custom adapter
dqbench run --adapter my_adapter.py
```

## Benchmark Categories

| Category | What it measures | Example tools |
|----------|-----------------|---------------|
| **Detect** | Find data quality issues in a dataset | GoldenCheck, Great Expectations, Pandera, Soda Core |
| **Transform** | Clean, normalize, and repair data | GoldenFlow, dbt, pandas |
| **ER** | Entity resolution — deduplicate and link records | GoldenMatch, Splink, Dedupe |
| **Pipeline** | End-to-end pipeline orchestration and quality gates | GoldenPipe, Airflow, Prefect |
| **OCR Company** | OCR company-name confidence, review, and correction quality | OCR confidence/correction tools |

## Head-to-Head Results — Detect (DQBench v1.0)

| Tool | Mode | T1 F1 | T2 F1 | T3 F1 | Score |
|------|------|-------|-------|-------|-------|
| **GoldenCheck** | **zero-config** | **84.9%** | **80.0%** | **57.6%** | **72.00** |
| Pandera | best-effort | 36.4% | 38.1% | 25.0% | 32.51 |
| Soda Core | best-effort | 38.1% | 23.5% | 13.3% | 22.36 |
| Great Expectations | best-effort | 36.4% | 23.5% | 12.5% | 21.68 |
| Great Expectations | auto-profiled | 22.2% | 42.1% | 0.0% | 21.29 |
| Soda Core | auto-profiled | 0.0% | 11.1% | 6.2% | 6.94 |
| All tools | zero-config | 0.0% | 0.0% | 0.0% | 0.00 |

> GoldenCheck's zero-config discovery outperforms every competitor's hand-written rules.

## Head-to-Head Results — ER (DQBench v1.1)

| Tool | Mode | T1 F1 | T2 F1 | T3 F1 | Score |
|------|------|-------|-------|-------|-------|
| **GoldenMatch** | **with LLM** | **92.6%** | **97.8%** | **94.1%** | **95.30** |
| GoldenMatch | without LLM | — | — | — | 77.21 |

> GoldenMatch with LLM achieves a 95.30 DQBench ER Score across all three scored tiers.
>
> **Cost estimate:** ~$0.15-0.30 per full run (3 tiers) with LLM scoring. Without LLM: free, ~23s total. With LLM: ~$0.25, ~670s total. LLM scoring is optional and activates automatically when `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` is set.
>
> **External validation:** GoldenMatch also scores **75.0% F1 on [BPID](https://aclanthology.org/2024.emnlp-industry.40/)** (Amazon's adversarial PII deduplication benchmark, EMNLP 2024), matching Ditto (75.2%) with zero training data. See the [benchmark writeup](https://bensevern.dev/blog/2026-04-02-goldenmatch-bpid-benchmark).
>
> **T4 — Mistyped (diagnostic):** since DQBench v1.2 the ER harness also ships a fourth tier where four column names deliberately disagree with their content (`first_name`=hex tokens, `last_name`=numeric IDs, `address`=free-form notes, `industry`=person names). The duplicate signal lives in `email`/`phone`, so a deduper that gates per-column refinements on profiled `col_type` should land near its T1 F1; one that trusts the column name will fire name/address scorers on noise and pay a precision tax. T4 has weight 0 in the composite ER score — it's reported but doesn't move the headline.

Run the comparisons yourself:
```bash
# Detect benchmark
pip install dqbench goldencheck great_expectations pandera soda-core
dqbench run all

# ER benchmark
pip install dqbench goldenmatch
dqbench run goldenmatch
```

### Leaderboard

Every `dqbench run` records its result under `~/.dqbench/results/` (latest run per
tool per category wins). View your local board at any time:

```bash
dqbench run all              # populate Detect results
dqbench run goldenmatch      # add an ER result
dqbench leaderboard          # ranked tables for every category
dqbench leaderboard -c er    # just one category
dqbench leaderboard --json   # machine-readable
```

Use `dqbench run <adapter> --no-save` to benchmark without recording, and
`dqbench leaderboard --clear` to reset the local board.

### Published leaderboard

The repository ships a public, version-controlled board in
[`LEADERBOARD.md`](LEADERBOARD.md), generated from `leaderboard/results/`.

**Results must reproduce.** Every entry is backed by a manifest under
`leaderboard/submissions/` that declares how to run the benchmark (tool, adapter,
pinned packages). CI re-runs each changed manifest on a clean runner and rejects any
entry whose numbers don't reproduce — so scores can't be hand-edited onto the board.

To submit your tool, add a manifest and reproduce it:

```bash
# leaderboard/submissions/detect-mytool.json describes how to run your tool
dqbench reproduce leaderboard/submissions/detect-mytool.json --write
dqbench verify    leaderboard/submissions/detect-mytool.json
# commit the manifest + leaderboard/results/*.json + LEADERBOARD.md, then open a PR
```

CI gates the PR with `dqbench publish --check` (every entry has a manifest, board in
sync) and `dqbench verify` (the numbers reproduce). View the published board with
`dqbench leaderboard --source repo`. Full guide: [docs/leaderboard.md](docs/leaderboard.md).

## Tiers

### Detect

| Tier | Rows | Columns | Domain | Difficulty |
|------|------|---------|--------|------------|
| **1 — Basics** | 5,000 | 20 | Customer DB | Obvious errors, baseline |
| **2 — Realistic** | 50,000 | 30 | E-commerce | Subtle issues + false positive traps |
| **3 — Adversarial** | 100,000 | 50 | Healthcare | Encoding traps, semantic errors, cross-column logic |

Each tier has columns WITH planted issues and columns WITHOUT (false positive traps). Tools that flag clean columns lose precision points.

### ER (Entity Resolution)

| Tier | Rows | Dupes | Profile | In composite score |
|------|------|-------|---------|--------------------|
| **1 — Easy** | 1,000 | 100 | Case-change, single-char typo, name swap | ✓ (20%) |
| **2 — Fuzzy** | 5,000 | 750 | Nicknames, missing fields, format change, transposed fields | ✓ (40%) |
| **3 — Adversarial** | 10,000 | 2,000 | Phonetic variants, address abbrev, split records, unicode, merged records, multi-field corruption | ✓ (40%) |
| **4 — Mistyped** *(diagnostic)* | 800 | 80 | Person-shaped rows where four column names deliberately disagree with their content | weight 0 |

T4 is a diagnostic tier — same row shape as T1 but with `first_name`=hex, `last_name`=numeric ID, `address`=free-form notes, `industry`=person names. It exists to expose dedupers that fire per-column refinements (name scorers, address normalisation) on noise when the column name doesn't match the data. Reported alongside T1-T3 but excluded from the composite ER score so it doesn't move headline numbers for tools that don't opt in.

## Scoring

| Metric | Description |
|--------|-------------|
| **Recall** | % of planted-issue columns detected |
| **Precision** | % of flagged columns that actually have issues |
| **F1** | Harmonic mean of recall and precision |
| **FPR** | Clean columns incorrectly flagged (WARNING/ERROR only) |
| **DQBench Score** | Tier1_F1 x 20% + Tier2_F1 x 40% + Tier3_F1 x 40% |

## Write Your Own Adapter

Implement one class to benchmark any tool:

```python
from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding
from pathlib import Path

class MyToolAdapter(DQBenchAdapter):
    @property
    def name(self) -> str:
        return "MyTool"

    @property
    def version(self) -> str:
        return "1.0.0"

    def validate(self, csv_path: Path) -> list[DQBenchFinding]:
        # Run your tool on the CSV
        # Return a list of DQBenchFinding objects
        return [
            DQBenchFinding(
                column="email",
                severity="error",      # "error", "warning", or "info"
                check="format",         # what kind of issue
                message="Invalid email format",
                confidence=0.9,         # optional, 0.0-1.0
            )
        ]
```

Then run:
```bash
dqbench run --adapter my_adapter.py
```

## Writing a Custom ER Adapter

To benchmark an entity resolution tool, implement the `EntityResolutionAdapter` interface:

```python
from dqbench.adapters.er_base import EntityResolutionAdapter
from dqbench.models import ERPrediction
from pathlib import Path
import polars as pl

class MyERAdapter(EntityResolutionAdapter):
    @property
    def name(self) -> str:
        return "MyERTool"

    @property
    def version(self) -> str:
        return "1.0.0"

    def resolve(self, df: pl.DataFrame) -> list[ERPrediction]:
        # Given a DataFrame with potential duplicates,
        # return predicted duplicate pairs
        return [
            ERPrediction(
                record_id_a="row_001",
                record_id_b="row_042",
                confidence=0.95,        # 0.0-1.0
                match=True,             # True = predicted duplicate
            )
        ]
```

Then run:
```bash
dqbench run --adapter my_er_adapter.py
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `dqbench run <adapter>` | Run benchmark |
| `dqbench run --adapter <path>` | Run with custom adapter file |
| `dqbench run <adapter> --tier 2` | Run specific tier only |
| `dqbench run <adapter> --json` | JSON output |
| `dqbench run goldenmatch` | Run ER benchmark with GoldenMatch |
| `dqbench run goldenpipe` | Run Pipeline benchmark with GoldenPipe (tuned Flow+Match) |
| `dqbench run goldensuite-tuned` | Full Golden suite pipeline, tuned (Check+Flow+Match) |
| `dqbench run goldensuite-zero` | Full Golden suite pipeline, zero-config engine |
| `dqbench run placeholder --adapter <path>` | Run a custom OCR Company adapter |
| `dqbench run goldenmatch --tier 4` | Run only the ER T4 (Mistyped) diagnostic tier |
| `dqbench run <adapter> --no-save` | Run without recording the result on the leaderboard |
| `dqbench leaderboard` | Show your local ranked leaderboard across all categories |
| `dqbench leaderboard --category er` | Show the leaderboard for one category |
| `dqbench leaderboard --json` | Leaderboard as JSON |
| `dqbench leaderboard --source repo` | Show the published (committed) board |
| `dqbench leaderboard --clear` | Delete all locally recorded results |
| `dqbench reproduce <manifest> --write` | Run a submission manifest and record it on the board |
| `dqbench verify <manifest>` | Reproduce a manifest and confirm its committed entry matches |
| `dqbench publish` | Regenerate `LEADERBOARD.md` from the store |
| `dqbench publish --check` | Validate store + manifests and verify `LEADERBOARD.md` (CI) |
| `dqbench generate` | Generate/cache detection datasets |
| `dqbench generate --er` | Generate ER benchmark datasets (T1-T4) |
| `dqbench generate --pipeline` | Generate Pipeline benchmark datasets |
| `dqbench generate --ocr-company` | Generate OCR Company benchmark datasets |
| `dqbench generate --all` | Generate datasets for all categories |
| `dqbench generate --force` | Regenerate datasets |

## Supported Categories

| Category | Tiers | Description |
|----------|-------|-------------|
| **Detect** | 3 | Data quality issue detection |
| **Transform** | 3 | Data cleaning and normalization |
| **ER** | 3 scored + 1 diagnostic (T4 Mistyped) | Entity resolution and deduplication |
| **Pipeline** | 3 | End-to-end pipeline orchestration |
| **OCR Company** | 3 | OCR company-name confidence and correction |

Full suite: 241 tests passing across all five categories.

## OCR Company Benchmark

This benchmark measures company-name OCR scoring quality rather than generic data validation.

It ships with deterministic synthetic company OCR tiers and scores:

- confidence separation between clean and corrupted names
- false review rate on clean names
- review recall on corrupted names
- weakest-token hit rate
- correction exact-hit rate
- correction improvement rate

Generate OCR Company datasets:

```bash
dqbench generate --ocr-company
```

Run with a custom OCR Company adapter:

```bash
dqbench run placeholder --adapter examples/ocr_company_adapter.py
```

5 categories, 16 tiers (15 scored + T4 Mistyped diagnostic), 178 tests passing.

## Built-in Adapters

| Adapter | Tool | Category | Modes | Install |
|---------|------|----------|-------|---------|
| `goldencheck` | GoldenCheck | Detect | zero-config | `pip install goldencheck` |
| `gx-zero`, `gx-auto`, `gx-best` | Great Expectations | Detect | zero / auto / best-effort | `pip install great_expectations` |
| `pandera-zero`, `pandera-auto`, `pandera-best` | Pandera | Detect | zero / auto / best-effort | `pip install pandera` |
| `soda-zero`, `soda-auto`, `soda-best` | Soda Core | Detect | zero / auto / best-effort | `pip install soda-core` |
| `goldenmatch` | GoldenMatch | ER | with-LLM / without-LLM | `pip install goldenmatch` |
| `goldenpipe` | GoldenPipe | Pipeline | default | `pip install goldenpipe` |

Want to add your tool? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Reproducibility

- Datasets are generated deterministically with a per-tier `random.Random(42)` instance (stdlib only, no numpy)
- Canonical datasets committed as release artifacts
- Version-locked: published benchmark versions are immutable
- Cached datasets live under `~/.dqbench/datasets/`; regenerate with `dqbench generate --force`

## License

MIT

---

**From the maker of [GoldenCheck](https://github.com/benzsevern/goldencheck), [GoldenMatch](https://github.com/benzsevern/goldenmatch), [GoldenFlow](https://github.com/benzsevern/goldenflow), and [GoldenPipe](https://github.com/benzsevern/goldenpipe).**
