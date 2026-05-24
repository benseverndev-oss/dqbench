"""GoldenPipe / Golden suite adapters for DQBench Pipeline benchmarks.

- GoldenPipeAdapter:          tuned GoldenFlow transform -> GoldenMatch dedupe.
- GoldenSuiteZeroConfigAdapter: the full suite via GoldenPipe's own engine,
  zero-config (load -> GoldenCheck -> GoldenFlow -> GoldenMatch).
- GoldenSuiteTunedAdapter:    the full suite hand-tuned — GoldenCheck safe
  auto-fix prepended to the same tuned GoldenFlow/GoldenMatch chain.
"""
from __future__ import annotations
from pathlib import Path
import polars as pl
from dqbench.adapters.base import PipelineAdapter


def _assemble_dedup_output(
    unique: pl.DataFrame | None,
    dupes: pl.DataFrame | None,
    golden: pl.DataFrame | None,
    clusters: dict | None,
) -> pl.DataFrame:
    """Rebuild a deduplicated frame: unique records + one representative per cluster.

    Keeps `_row_id` (needed by the scorer) and drops GoldenMatch/GoldenFlow
    internal columns (those prefixed with `__`).
    """
    def _drop_internal(df: pl.DataFrame) -> pl.DataFrame:
        drop = [c for c in df.columns if c.startswith("__")]
        return df.drop(drop) if drop else df

    parts: list[pl.DataFrame] = []
    if unique is not None and unique.shape[0] > 0:
        parts.append(_drop_internal(unique))

    if clusters and dupes is not None:
        cluster_records = dupes
        if golden is not None:
            cluster_records = pl.concat(
                [
                    dupes.select(dupes.columns),
                    golden.select([c for c in dupes.columns if c in golden.columns]),
                ],
                how="diagonal",
            )
        if "_row_id" in cluster_records.columns and "__row_id__" in cluster_records.columns:
            representatives = []
            for cluster in clusters.values():
                members = cluster["members"]
                member_rows = cluster_records.filter(pl.col("__row_id__").is_in(members))
                if member_rows.shape[0] > 0:
                    representatives.append(member_rows.sort("_row_id").head(1))
            if representatives:
                parts.append(_drop_internal(pl.concat(representatives)))

    if not parts:
        return unique if unique is not None else pl.DataFrame()

    all_cols = parts[0].columns
    aligned = []
    for p in parts:
        missing = [c for c in all_cols if c not in p.columns]
        if missing:
            p = p.with_columns([pl.lit(None).alias(c) for c in missing])
        aligned.append(p.select(all_cols))
    return pl.concat(aligned)


def _tuned_flow_match(df: pl.DataFrame) -> pl.DataFrame:
    """Tuned GoldenFlow transform + GoldenMatch dedupe; returns a deduped frame."""
    try:
        import goldenflow
        import goldenmatch
        from goldenmatch.config.schemas import (
            GoldenMatchConfig,
            MatchkeyConfig,
            MatchkeyField,
            BlockingConfig,
            BlockingKeyConfig,
            StandardizationConfig,
            LLMScorerConfig,
            BudgetConfig,
        )
    except ImportError:
        raise RuntimeError(
            "goldenpipe[golden-suite] is not installed. "
            "Run: pip install goldenflow goldenmatch"
        )

    # Stage 1: Transform with GoldenFlow (configured, not zero-config)
    from goldenflow.config.schema import GoldenFlowConfig, TransformSpec

    flow_config = GoldenFlowConfig(
        transforms=[
            TransformSpec(column="first_name", ops=["strip", "title_case"]),
            TransformSpec(column="last_name", ops=["strip", "title_case"]),
            TransformSpec(column="email", ops=["strip", "lowercase"]),
            TransformSpec(column="phone", ops=["strip", "phone_national"]),
            TransformSpec(column="address", ops=["strip", "collapse_whitespace"]),
            TransformSpec(column="city", ops=["strip", "title_case"]),
            TransformSpec(column="company", ops=["strip", "collapse_whitespace"]),
        ],
    )
    transform_result = goldenflow.transform_df(df, config=flow_config)
    cleaned = transform_result.df

    # Stage 2: Deduplicate with GoldenMatch (same config as the ER adapter)
    config = GoldenMatchConfig(
        standardization=StandardizationConfig(
            email=["email"],
            phone=["phone"],
            first_name=["strip", "name_proper"],
            last_name=["strip", "name_proper"],
            address=["address"],
            zip=["zip5"] if "zip" in cleaned.columns else [],
            state=["state"] if "state" in cleaned.columns else [],
        ),
        blocking=BlockingConfig(
            strategy="multi_pass",
            keys=[
                BlockingKeyConfig(fields=["email"], transforms=["lowercase", "strip"]),
            ],
            passes=[
                BlockingKeyConfig(fields=["email"], transforms=["lowercase", "strip"]),
                BlockingKeyConfig(fields=["last_name"], transforms=["soundex"]),
                BlockingKeyConfig(fields=["last_name"], transforms=["substring:0:3"]),
            ],
        ),
        matchkeys=[
            MatchkeyConfig(
                name="identity",
                type="weighted",
                threshold=0.75,
                fields=[
                    MatchkeyField(field="first_name", scorer="ensemble", weight=1.0, transforms=["lowercase", "strip"]),
                    MatchkeyField(field="last_name", scorer="ensemble", weight=1.0, transforms=["lowercase", "strip"]),
                    MatchkeyField(field="email", scorer="jaro_winkler", weight=0.8, transforms=["lowercase", "strip"]),
                    MatchkeyField(field="phone", scorer="exact", weight=0.5, transforms=["digits_only"]),
                    MatchkeyField(field="address", scorer="token_sort", weight=0.6, transforms=["lowercase", "strip"]),
                    MatchkeyField(field="city", scorer="exact", weight=0.3, transforms=["lowercase", "strip"]),
                ],
            ),
        ],
    )

    # Enable LLM scorer if API key available (off in CI — deterministic).
    import os
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        config.llm_scorer = LLMScorerConfig(
            enabled=True,
            candidate_lo=0.60,
            candidate_hi=0.90,
            auto_threshold=0.90,
            budget=BudgetConfig(max_calls=500, max_cost_usd=1.0),
        )

    dedupe_result = goldenmatch.dedupe_df(cleaned, config=config)
    out = _assemble_dedup_output(
        dedupe_result.unique, dedupe_result.dupes, dedupe_result.golden, dedupe_result.clusters
    )
    return out if out.shape[0] > 0 else cleaned


def _goldenpipe_version() -> str:
    try:
        import goldenpipe
        return goldenpipe.__version__
    except ImportError:
        return "not-installed"


class GoldenPipeAdapter(PipelineAdapter):
    @property
    def name(self) -> str:
        return "goldenpipe"

    @property
    def version(self) -> str:
        return _goldenpipe_version()

    def run_pipeline(self, csv_path: Path) -> pl.DataFrame:
        """Tuned Flow + Match (no detect stage)."""
        return _tuned_flow_match(pl.read_csv(csv_path))


class GoldenSuiteZeroConfigAdapter(PipelineAdapter):
    """Full suite via GoldenPipe's engine, zero-config: load -> check -> flow -> dedupe."""

    @property
    def name(self) -> str:
        return "GoldenSuite (zero-config)"

    @property
    def version(self) -> str:
        return _goldenpipe_version()

    def run_pipeline(self, csv_path: Path) -> pl.DataFrame:
        try:
            import goldenpipe
        except ImportError:
            raise RuntimeError(
                "The full Golden suite is not installed. "
                "Run: pip install goldenpipe goldenflow goldenmatch goldencheck"
            )
        # Run from the file so the GoldenCheck stage can read and scan/fix it.
        result = goldenpipe.run(source=str(csv_path))
        artifacts = result.artifacts or {}
        return _assemble_dedup_output(
            artifacts.get("unique"),
            artifacts.get("dupes"),
            artifacts.get("golden"),
            artifacts.get("clusters"),
        )


class GoldenSuiteTunedAdapter(PipelineAdapter):
    """Full suite, hand-tuned: GoldenCheck safe auto-fix -> tuned Flow + Match."""

    @property
    def name(self) -> str:
        return "GoldenSuite (tuned)"

    @property
    def version(self) -> str:
        return _goldenpipe_version()

    def run_pipeline(self, csv_path: Path) -> pl.DataFrame:
        try:
            import goldencheck
        except ImportError:
            raise RuntimeError(
                "The full Golden suite is not installed. "
                "Run: pip install goldencheck goldenflow goldenmatch goldenpipe"
            )
        df = pl.read_csv(csv_path)
        # Stage 0: GoldenCheck safe auto-fixes (trim, invisible chars, unicode, quotes).
        findings, _profile = goldencheck.scan_file(csv_path)
        fixed_df, _report = goldencheck.apply_fixes(df, findings, mode="safe")
        # Stages 1-2: the same tuned Flow + Match chain as GoldenPipe.
        return _tuned_flow_match(fixed_df)
