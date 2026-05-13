# Generator

Produces deterministic benchmark datasets for each category and tier.

## Layout

```
generator/
├── tier1.py             # Detect T1
├── tier2.py             # Detect T2
├── tier3.py             # Detect T3
├── clean.py             # Clean (transform-target) variants of Detect tiers
├── er_tier1.py          # ER T1 (easy)
├── er_tier2.py          # ER T2 (fuzzy)
├── er_tier3.py          # ER T3 (adversarial)
├── er_tier4.py          # ER T4 (mistyped — diagnostic)
├── pipeline_tier1.py    # Pipeline T1
├── pipeline_tier2.py    # Pipeline T2
├── pipeline_tier3.py    # Pipeline T3
├── ocr_company.py       # OCR Company tiers (single module)
└── utils.py             # Shared fake-data pools (names, cities, phone area codes, ...)
```

## Detect Tiers

| Tier | Rows | Cols | Theme |
|------|------|------|-------|
| 1 | 5,000 | 20 | Customer database — basics |
| 2 | 50,000 | 30 | Transactions — realistic noise |
| 3 | 100,000 | 50 | Healthcare/finance — adversarial |

Each tier has **planted columns** (with deliberate issues) and **clean columns**
(false-positive traps — well-formed data that must not be flagged).

## ER Tiers

| Tier | Rows | Dupes | Difficulty | Profile |
|------|------|-------|------------|---------|
| 1 | 1,000 | 100 | easy | Case change, single-char typo, name swap |
| 2 | 5,000 | 750 | fuzzy | Nicknames, missing fields, format changes, transposed fields |
| 3 | 10,000 | 2,000 | adversarial | Phonetic variants, address abbreviations, split records, unicode, merged records, multi-field corruption |
| 4 | 800 | 80 | mistyped | Person-shaped rows; `first_name`=hex, `last_name`=numeric ID, `address`=note, `industry`=person name |

**T4 is diagnostic, not headline.** Column names match T1 but the content is deliberately wrong, so a deduper that gates per-column refinements on profiled `col_type` should land near T1; one that trusts the column name will fire name/address scorers on noise. T4 has weight 0 in `ERScorecard.dqbench_er_score`.

## Return Type

| Category | Generator return |
|----------|------------------|
| Detect | `(pl.DataFrame, GroundTruth)` |
| ER | `(pl.DataFrame, ERGroundTruth)` |
| Pipeline | `(pl.DataFrame messy, pl.DataFrame clean, PipelineGroundTruth)` |
| OCR Company | `pl.DataFrame` (ground truth is embedded in the dataset columns) |

```python
df, gt = generate_tier1()
df.write_csv("data.csv")
gt.model_dump()  # serialise to JSON

df, gt = generate_er_tier4()
gt.tier, gt.difficulty, gt.total_duplicates  # → (4, "mistyped", 80)
```

## Determinism Rule

Use a local `rng = random.Random(42)` instance passed through all helpers.
Never call `random.seed(42)` globally — that mutates shared state and breaks
tests that run in the same process.

## Detect Ground Truth Format

`GroundTruth.planted_columns` is a `dict[str, PlantedColumn]`:

```python
PlantedColumn(
    issues=["null_values", "invalid_format"],  # issue type keys
    planted_count=50,                           # how many rows affected
    description="email col with nulls + bad formats",
    affected_rows=[3, 7, 12, ...],             # optional row indices
)
```

`GroundTruth.clean_columns` is a plain `list[str]` — columns with no planted issues.

## ER Ground Truth Format

```python
ERGroundTruth(
    tier=4,
    version="1.0.0",
    rows=800,
    duplicate_pairs=[(7, 412), (15, 681), ...],  # normalised (min, max) row indices
    total_duplicates=80,
    difficulty="mistyped",
)
```

Pairs are normalised to `(min, max)` and scoring matches symmetrically — adapters can return either order.

## Adding a New Detect Tier

1. Create `dqbench/generator/tier4.py` following the existing pattern.
2. Return `(pl.DataFrame, GroundTruth(tier=4, version="1.0", ...))`.
3. Register in `runner.py` `ensure_datasets()` loop.
4. Add a weight entry in `Scorecard.dqbench_score` if it should affect the composite.

## Adding a New ER Tier

1. Create `dqbench/generator/er_tier<N>.py` following `er_tier4.py`.
2. Return `(pl.DataFrame, ERGroundTruth(tier=N, version="1.0.0", ...))`.
3. Append `(N, generate_er_tier<N>)` to the `generators` list in `ensure_er_datasets()` in `runner.py`.
4. Extend the default tier list in `run_er_benchmark` (`tiers or [1, 2, 3, 4, ...]`).
5. Decide whether the tier should contribute to `ERScorecard.dqbench_er_score`. Diagnostic tiers (like T4) leave `weights.get(tier, 0)` returning 0; scored tiers need an explicit entry in `weights`.
6. Add a `TestERTier<N>` class in `tests/test_er_generator.py` (shape, dupe count, valid indices, determinism, ground-truth metadata).

## Modifying an Existing Tier

Ground truth versions are **immutable once published**. If you change planted
issues or duplicate pairs, bump `version` in the returned ground truth and
document the change. Old cached files at `~/.dqbench/datasets/` will not
auto-invalidate — users must run `dqbench generate --force`.
