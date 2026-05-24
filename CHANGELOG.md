# Changelog

## Unreleased

### Added
- **Published leaderboard with a reproducibility gate** — a version-controlled, community-submittable board where **results are only accepted if a GitHub Action can reproduce them**. Each entry is backed by a manifest under `leaderboard/submissions/` (tool, category, adapter, pinned packages). New commands: `dqbench reproduce <manifest> [--write]` (run the manifest, optionally record it), `dqbench verify <manifest>` (reproduce and confirm the committed numbers match), `dqbench publish [--check]` (regenerate/verify `LEADERBOARD.md`), and `dqbench leaderboard --source repo`. `dqbench run --adapter` now also accepts a `module:Class` reference.
- CI: `.github/workflows/leaderboard.yml` gates PRs with `dqbench publish --check` (structural) and `dqbench verify` on each changed manifest (reproduction); `.github/workflows/leaderboard-refresh.yml` audits all manifests on a schedule.
- Seeded the published Detect board with reproduced, version-pinned runs for **Pandera** and **Soda** (zero-config / auto-profiled / best-effort). Great Expectations was excluded — its auto-profiling is non-deterministic and fails the reproducibility gate.
- `dqbench/submission.py` (manifests, reproduce/verify, repo store, validation, Markdown rendering) and `tests/test_submission.py`.
- **Local leaderboard** — `dqbench run` records each result under `~/.dqbench/results/<category>.json` (latest run per tool per category wins), and `dqbench leaderboard` renders a ranked board across all five categories. Supports `--category/-c` to filter, `--json` for machine-readable output, and `--clear` to reset. Use `dqbench run <adapter> --no-save` to benchmark without recording.
- `dqbench/leaderboard.py` with persistence/loading/ranking helpers and `tests/test_leaderboard.py`.
- **ER Tier 4 (Mistyped)** — diagnostic ER tier (800 rows, 80 duplicate pairs) where four column names deliberately disagree with their content: `first_name` holds 12-char hex tokens, `last_name` holds 6-8 digit numeric IDs, `address` holds free-form notes, `industry` holds person names. The duplicate signal lives in `email`/`phone`, so dedupers that gate per-column refinements on profiled `col_type` should score near T1; tools that trust the column name fire the wrong scorers on noise and pay a precision tax. T4 has weight 0 in `dqbench_er_score` (diagnostic, not headline).
- `dqbench/generator/er_tier4.py` with `generate_er_tier4()` returning `(pl.DataFrame, ERGroundTruth(tier=4, difficulty="mistyped"))`.
- 11 new tests in `tests/test_er_generator.py::TestERTier4` covering shape, dupe count, valid indices, determinism, and per-column-type assertions for each mistyping.

### Changed
- `ensure_er_datasets()` in `dqbench/runner.py` is now per-tier idempotent — users with an existing T1-T3 cache pick up T4 without needing `dqbench generate --force`.
- Default ER tier list extended to `[1, 2, 3, 4]`; existing callers passing explicit `tiers=` are unaffected.
- Full test suite: 233 passing (was 161).

## v1.1.0 — 2026-03-29

### Added
- **ER (Entity Resolution) benchmark category** — deduplicate and link records across three difficulty tiers
- **Pipeline benchmark category** — end-to-end pipeline orchestration and quality gate benchmarks
- GoldenMatch ER benchmark results (95.30 with LLM, 77.21 without)
- `EntityResolutionAdapter` interface for custom ER tool benchmarking
- CLI commands: `dqbench run goldenmatch`, `dqbench run goldenpipe`
- Dataset generation flags: `--er`, `--pipeline`, `--all`
- Built-in adapters for GoldenMatch (ER) and GoldenPipe (Pipeline)

### Changed
- Expanded from 2 categories (Detect, Transform) to 4 (Detect, Transform, ER, Pipeline)
- Total test count: 161 across 12 tiers
- Updated PyPI keywords to include entity-resolution, deduplication, record-linkage, pipeline
- Updated GitHub topics and repository description

## v1.0.0

- Initial release
- Detect benchmark: 3 tiers, 83 tests
- Transform benchmark category (experimental)
- Built-in adapters for GoldenCheck, Great Expectations, Pandera, Soda Core
- DQBench Score: weighted F1 across tiers
