# Changelog

## Unreleased

### Added
- **GoldenMatch auto-config on the leaderboard (ER, 92.36)** — `auto_configure_df` with zero hand-tuning, now the top ER entry (vs Splink 87.14, recordlinkage 80.28, GoldenMatch tuned 76.91). Its run-to-run drift turned out to be GoldenMatch's persisted cross-run learning store (`~/.goldenmatch/autoconfig_memory.db`), not randomness — the profiling sample is already seeded. The new `GoldenMatchAutoConfigAdapter` (`goldenmatch-auto`) disables that store (`GOLDENMATCH_AUTOCONFIG_MEMORY=0`, set before import since the flag is read once at import time), so it reproduces exactly and passes `dqbench verify`.
- **Ungated "reference" board** — for genuinely non-reproducible auto-config runs that can't pass the gate. Manifests marked `"gated": false` route to `leaderboard/reference/` (no manifest-linkage required, skipped by the CI verify matrix and the refresh audit) and render in a separate "Reference — auto-config (not gate-verified)" section of `LEADERBOARD.md`. Seeded with **GoldenSuite (zero-config)** (Pipeline, ~33.85).
- **ER B³ (BCubed) metrics + confusion matrix** — `score_er_tier` now also reports cluster-level B-Cubed precision/recall/F1 (built from the pair graph via connected components over all rows) and the full pair-level confusion matrix (TP/FP/FN/TN), surfaced in the ER report (rich + JSON). These are **diagnostic only** — the headline DQBench ER Score stays pair-F1-weighted and unchanged, so published entries don't move.
- **Third-party OSS tools on the leaderboard** — new adapters and reproducible, version-pinned entries: **Splink** (ER, 87.14 — probabilistic Fellegi-Sunter, seeded), **recordlinkage** (ER, 80.28 — blocking + Jaro-Winkler), **cuallee** (Detect, 30.56 — rule-based DQ checks), **frictionless** (Detect, 2.22 — inferred-schema validation), and a **pandas cleaning baseline** (Transform, 100.0). **Great Expectations** is now included too (Detect: best-effort 21.68, auto-profiled 21.29, zero-config 0.0) — its earlier non-determinism turned out to be dev-environment contamination; in an isolated env with pinned deps it reproduces exactly. Each entry runs in its own isolated CI job and passes `dqbench verify`.
- **Published leaderboard with a reproducibility gate** — a version-controlled, community-submittable board where **results are only accepted if a GitHub Action can reproduce them**. Each entry is backed by a manifest under `leaderboard/submissions/` (tool, category, adapter, pinned packages). New commands: `dqbench reproduce <manifest> [--write]` (run the manifest, optionally record it), `dqbench verify <manifest>` (reproduce and confirm the committed numbers match), `dqbench publish [--check]` (regenerate/verify `LEADERBOARD.md`), and `dqbench leaderboard --source repo`. `dqbench run --adapter` now also accepts a `module:Class` reference.
- CI: `.github/workflows/leaderboard.yml` gates PRs with `dqbench publish --check` (structural) and `dqbench verify` on each changed manifest (reproduction); `.github/workflows/leaderboard-refresh.yml` audits all manifests on a schedule.
- Seeded the published board across four categories with reproduced, version-pinned runs: **Detect** (GoldenCheck 88.40, plus Pandera/Soda baselines), **Transform** (GoldenFlow 100.0), **ER** (GoldenMatch 76.91), **Pipeline** (GoldenPipe 71.38). OCR Company is left open for submissions (no installable third-party tool; the example adapter peeks at ground truth).
- Each manifest is verified in its **own isolated CI job** with only its pinned packages, so an entry's numbers can't be perturbed by other tools in the environment (GoldenMatch in particular changes behaviour when unrelated packages are present). Transitive deps that affect results (e.g. `jellyfish`, `RapidFuzz`) are pinned in the manifest.
- **Full Golden suite pipeline** — a new Pipeline entry that runs the whole suite end-to-end (GoldenCheck → GoldenFlow → GoldenMatch): **GoldenSuite (tuned)** at 75.59 (GoldenCheck's safe auto-fix added to the tuned Flow+Match chain — beats the partial GoldenPipe at 71.38). New built-in adapters `goldensuite-tuned` and `goldensuite-zero`; the shared tuned Flow+Match logic is factored into `_tuned_flow_match`. The zero-config engine adapter (`goldensuite-zero`) runs but is **not published** — GoldenPipe's auto-config is non-deterministic run-to-run (T3 dedup varies by a row), so it fails the reproducibility gate, like Great Expectations.
- `dqbench/submission.py` (manifests, reproduce/verify, repo store, validation, Markdown rendering) and `tests/test_submission.py`.
- **Local leaderboard** — `dqbench run` records each result under `~/.dqbench/results/<category>.json` (latest run per tool per category wins), and `dqbench leaderboard` renders a ranked board across all five categories. Supports `--category/-c` to filter, `--json` for machine-readable output, and `--clear` to reset. Use `dqbench run <adapter> --no-save` to benchmark without recording.
- `dqbench/leaderboard.py` with persistence/loading/ranking helpers and `tests/test_leaderboard.py`.
- **ER Tier 4 (Mistyped)** — diagnostic ER tier (800 rows, 80 duplicate pairs) where four column names deliberately disagree with their content: `first_name` holds 12-char hex tokens, `last_name` holds 6-8 digit numeric IDs, `address` holds free-form notes, `industry` holds person names. The duplicate signal lives in `email`/`phone`, so dedupers that gate per-column refinements on profiled `col_type` should score near T1; tools that trust the column name fire the wrong scorers on noise and pay a precision tax. T4 has weight 0 in `dqbench_er_score` (diagnostic, not headline).
- `dqbench/generator/er_tier4.py` with `generate_er_tier4()` returning `(pl.DataFrame, ERGroundTruth(tier=4, difficulty="mistyped"))`.
- 11 new tests in `tests/test_er_generator.py::TestERTier4` covering shape, dupe count, valid indices, determinism, and per-column-type assertions for each mistyping.

### Changed
- `ensure_er_datasets()` in `dqbench/runner.py` is now per-tier idempotent — users with an existing T1-T3 cache pick up T4 without needing `dqbench generate --force`.
- Default ER tier list extended to `[1, 2, 3, 4]`; existing callers passing explicit `tiers=` are unaffected.
- Full test suite: 251 passing (was 161).

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
