# DQBench

The standard benchmark for data quality and validation tools — five categories: Detect, Transform, ER, Pipeline, OCR Company.

## Commands

```bash
pip install -e ".[dev]"          # Dev install
pytest --tb=short -v             # Run tests (194 passing)
ruff check .                     # Lint
dqbench run <adapter>            # Run benchmark (records result on the leaderboard)
dqbench run all                  # Head-to-head comparison
dqbench leaderboard              # Ranked board across categories (--category, --json, --clear)
dqbench generate                 # Generate/cache detection datasets
dqbench generate --er            # Generate ER datasets (T1-T4)
dqbench generate --all           # Generate datasets for every category
dqbench generate --force         # Regenerate from scratch
```

## Architecture

```
dqbench/
├── cli.py                       # Typer CLI (run, generate, results, leaderboard)
├── leaderboard.py               # Persist run results to ~/.dqbench/results/, load + rank for the board
├── runner.py                    # Orchestrate adapter against tiers (Detect / Transform / ER / Pipeline / OCR Company)
├── scorer.py                    # Detect scoring: recall, precision, F1, DQBench Score
├── er_scorer.py                 # ER pair-level P/R/F1
├── transform_scorer.py          # Transform per-column accuracy
├── pipeline_scorer.py           # Pipeline composite (transform × dedup)
├── ocr_company_scorer.py        # OCR Company composite metrics
├── report.py                    # Rich console + JSON scorecards (all 5 categories)
├── models.py                    # DQBenchFinding, TierResult, Scorecard + per-category result/scorecard dataclasses
├── ground_truth.py              # Detect GroundTruth Pydantic model + loader
├── er_ground_truth.py           # ER duplicate-pair ground truth
├── pipeline_ground_truth.py     # Pipeline ground truth
├── generator/                   # Per-category dataset generators (tier1-3 detect, er_tier1-4, pipeline_tier1-3, ocr_company)
└── adapters/                    # Tool adapters (base ABC + built-ins for GoldenCheck, GX, Pandera, Soda, GoldenMatch, GoldenPipe, GoldenFlow)
```

## Categories & Tiers

| Category | Tiers | Notes |
|----------|-------|-------|
| Detect | 3 | Planted issues; column- and issue-level F1 |
| Transform | 3 | Per-column cell-level accuracy against a clean reference |
| ER | 3 scored + T4 diagnostic | Pair-level P/R/F1 against duplicate-pair ground truth |
| Pipeline | 3 | Combined transform + dedup composite |
| OCR Company | 3 | Confidence separation, review/correction quality |

### ER tier shapes

| Tier | Rows | Dupes | Difficulty |
|------|------|-------|------------|
| 1 | 1,000 | 100 | easy (case, typo, name swap) |
| 2 | 5,000 | 750 | fuzzy (nicknames, missing fields, format changes) |
| 3 | 10,000 | 2,000 | adversarial (phonetic, unicode, multi-field) |
| 4 | 800 | 80 | **mistyped** — diagnostic; `first_name`=hex, `last_name`=numeric ID, `address`=note, `industry`=person name |

T4 has `weights.get(tier, 0) == 0` in `ERScorecard.dqbench_er_score` — reported but excluded from the composite.

## Scoring

### Detect

- **Column Recall**: any finding on planted column (any severity) = detected
- **Column FPR**: WARNING/ERROR on clean column = false positive (INFO is NOT FP)
- **Issue Recall**: finding must match planted issue TYPE (via keyword matching)
- **Issue Precision**: matched findings / total findings on planted columns + FPs
- **DQBench Score**: `T1_issue_F1 × 20% + T2_issue_F1 × 40% + T3_issue_F1 × 40%` (0-100)

### ER

- **Pair-level P/R/F1** against `ERGroundTruth.duplicate_pairs` (pairs normalised to `(min, max)`)
- **DQBench ER Score**: `T1_F1 × 20% + T2_F1 × 40% + T3_F1 × 40%` — T4 weight is 0
- A perfect adapter on `tiers=[1, 2, 3]` scores 100; on `tiers=[4]` it scores 1.0 F1 but 0.0 composite

## Key Patterns

- **Datasets are deterministic**: per-tier `random.Random(42)` (stdlib only, no numpy)
- **Datasets cached**: `~/.dqbench/datasets/` — regenerate with `--force`
- **ER cache is per-tier idempotent**: adding a new ER tier doesn't require existing users to wipe their cache; missing tier dirs are generated on next run
- **Issue matching uses keywords**: `ISSUE_KEYWORDS` dict in `scorer.py`
- **Adapter interface**: one class, one method per category (`validate`, `transform`, `deduplicate`, `run_pipeline`, `score_companies`)
- **Three modes per Detect tool**: zero-config, auto-profiled, best-effort

## Gotchas

- Ground truth versions are immutable once published — bump `version` on `GroundTruth` / `ERGroundTruth` for any structural change
- `ISSUE_KEYWORDS` must not be changed after benchmark is locked — tools tune to it
- Tier generators use `random.Random(42)` instance, not global `random.seed(42)`
- T4 column **names** match T1 (`first_name`, `last_name`, `address`, etc.) but the **content** is intentionally wrong — tests in `tests/test_er_generator.py::TestERTier4` assert the mistypings hold
- GitHub auth: `gh auth switch --user benzsevern` before pushing
