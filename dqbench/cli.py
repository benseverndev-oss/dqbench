"""DQBench CLI."""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(name="dqbench", help="The standard benchmark for data quality tools.")

# ---------------------------------------------------------------------------
# Built-in adapter registry
# ---------------------------------------------------------------------------
BUILTIN_ADAPTERS: dict[str, str] = {
    # GoldenCheck
    "goldencheck": "dqbench.adapters.goldencheck:GoldenCheckAdapter",
    # GoldenFlow
    "goldenflow": "dqbench.adapters.goldenflow:GoldenFlowAdapter",
    # pandas cleaning baseline (Transform)
    "pandas-transform": "dqbench.adapters.pandas_transform_adapter:PandasTransformAdapter",
    # Great Expectations
    "gx-zero":     "dqbench.adapters.great_expectations_adapter:GXZeroConfigAdapter",
    "gx-auto":     "dqbench.adapters.great_expectations_adapter:GXAutoProfileAdapter",
    "gx-best":     "dqbench.adapters.great_expectations_adapter:GXBestEffortAdapter",
    # Pandera
    "pandera-zero": "dqbench.adapters.pandera_adapter:PanderaZeroConfigAdapter",
    "pandera-auto": "dqbench.adapters.pandera_adapter:PanderaAutoProfileAdapter",
    "pandera-best": "dqbench.adapters.pandera_adapter:PanderaBestEffortAdapter",
    # Soda
    "soda-zero":   "dqbench.adapters.soda_adapter:SodaZeroConfigAdapter",
    "soda-auto":   "dqbench.adapters.soda_adapter:SodaAutoProfileAdapter",
    "soda-best":   "dqbench.adapters.soda_adapter:SodaBestEffortAdapter",
    # cuallee (Detect, third-party)
    "cuallee":     "dqbench.adapters.cuallee_adapter:CualleeAdapter",
    # frictionless (Detect, third-party)
    "frictionless": "dqbench.adapters.frictionless_adapter:FrictionlessAdapter",
    # GoldenMatch (ER)
    "goldenmatch": "dqbench.adapters.goldenmatch_adapter:GoldenMatchAdapter",
    # recordlinkage (ER, third-party)
    "recordlinkage": "dqbench.adapters.recordlinkage_adapter:RecordLinkageAdapter",
    # GoldenPipe (Pipeline)
    "goldenpipe":  "dqbench.adapters.goldenpipe_adapter:GoldenPipeAdapter",
    # Full Golden suite (Pipeline): zero-config engine vs hand-tuned chain
    "goldensuite-zero":  "dqbench.adapters.goldenpipe_adapter:GoldenSuiteZeroConfigAdapter",
    "goldensuite-tuned": "dqbench.adapters.goldenpipe_adapter:GoldenSuiteTunedAdapter",
}

# Order for comparison tables (by category)
ALL_ADAPTER_NAMES = [
    "goldencheck",
    "goldenflow",
    "gx-zero",
    "gx-auto",
    "gx-best",
    "pandera-zero",
    "pandera-auto",
    "pandera-best",
    "soda-zero",
    "soda-auto",
    "soda-best",
    "cuallee",
    "frictionless",
]

ER_ADAPTER_NAMES = ["goldenmatch", "recordlinkage"]
PIPELINE_ADAPTER_NAMES = ["goldenpipe", "goldensuite-zero", "goldensuite-tuned"]
OCR_COMPANY_ADAPTER_NAMES: list[str] = []


def _detect_category(adapter) -> str:
    """Detect which benchmark category an adapter belongs to."""
    from dqbench.adapters.base import PipelineAdapter, EntityResolutionAdapter, TransformAdapter, OCRCompanyAdapter
    if isinstance(adapter, PipelineAdapter):
        return "pipeline"
    if isinstance(adapter, EntityResolutionAdapter):
        return "er"
    if isinstance(adapter, TransformAdapter):
        return "transform"
    if isinstance(adapter, OCRCompanyAdapter):
        return "ocr-company"
    return "detect"


@app.command()
def run(
    adapter_name: str = typer.Argument(..., help=(
        "Adapter name: goldencheck | gx-zero | gx-auto | gx-best | "
        "pandera-zero | pandera-auto | pandera-best | "
        "soda-zero | soda-auto | soda-best | "
        "goldenmatch | goldenpipe | all"
    )),
    tier: Optional[int] = typer.Option(None, "--tier", "-t", help="Run specific tier only (1, 2, or 3)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    adapter_path: Optional[Path] = typer.Option(None, "--adapter", help="Path to custom adapter file"),
    real: bool = typer.Option(False, "--real", help="Include real-world datasets (ER only)"),
    er: bool = typer.Option(False, "--er", help="Run only ER adapters (with 'all')"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Run only Pipeline adapters (with 'all')"),
    ocr_company: bool = typer.Option(False, "--ocr-company", help="Run only OCR Company adapters (with 'all')"),
    save: bool = typer.Option(True, "--save/--no-save", help="Record the result on the leaderboard"),
) -> None:
    """Run benchmark against a validation tool."""
    if adapter_name == "all":
        if er:
            _run_all(tier=tier, category="er", save=save)
        elif pipeline:
            _run_all(tier=tier, category="pipeline", save=save)
        elif ocr_company:
            _run_all(tier=tier, category="ocr-company", save=save)
        else:
            _run_all(tier=tier, save=save)
        return

    adapter = _load_adapter(adapter_name, adapter_path)
    tiers = [tier] if tier else None
    category = _detect_category(adapter)

    if category == "er":
        from dqbench.runner import run_er_benchmark
        from dqbench.report import report_er_rich, report_er_json
        scorecard = run_er_benchmark(adapter, tiers=tiers, real=real)
        if json_output:
            report_er_json(scorecard, sys.stdout)
        else:
            report_er_rich(scorecard)
    elif category == "pipeline":
        from dqbench.runner import run_pipeline_benchmark
        from dqbench.report import report_pipeline_rich, report_pipeline_json
        scorecard = run_pipeline_benchmark(adapter, tiers=tiers)
        if json_output:
            report_pipeline_json(scorecard, sys.stdout)
        else:
            report_pipeline_rich(scorecard)
    elif category == "ocr-company":
        from dqbench.runner import run_ocr_company_benchmark
        from dqbench.report import report_ocr_company_rich, report_ocr_company_json
        scorecard = run_ocr_company_benchmark(adapter, tiers=tiers)
        if json_output:
            report_ocr_company_json(scorecard, sys.stdout)
        else:
            report_ocr_company_rich(scorecard)
    elif category == "transform":
        from dqbench.runner import run_transform_benchmark
        from dqbench.report import report_transform_rich, report_transform_json
        scorecard = run_transform_benchmark(adapter, tiers=tiers)
        if json_output:
            report_transform_json(scorecard, sys.stdout)
        else:
            report_transform_rich(scorecard)
    else:
        from dqbench.runner import run_benchmark
        scorecard = run_benchmark(adapter, tiers=tiers)
        if json_output:
            from dqbench.report import report_json
            report_json(scorecard, sys.stdout)
        else:
            from dqbench.report import report_rich
            report_rich(scorecard)

    if save:
        from dqbench.leaderboard import save_scorecard
        save_scorecard(scorecard, category)


def _run_all(tier: Optional[int] = None, category: str | None = None, save: bool = True) -> None:
    """Run all registered adapters and print a comparison table."""
    tiers = [tier] if tier else None

    if category == "er":
        from dqbench.runner import run_er_benchmark
        from dqbench.report import report_er_comparison
        scorecards = []
        for name in ER_ADAPTER_NAMES:
            typer.echo(f"\nRunning: {name} ...", err=True)
            try:
                adapter = _load_adapter(name)
                sc = run_er_benchmark(adapter, tiers=tiers)
                scorecards.append(sc)
                _save_result(sc, "er", save)
                typer.echo(f"  Done — score: {sc.dqbench_er_score:.2f}", err=True)
            except Exception as e:
                typer.echo(f"  FAILED: {e}", err=True)
        report_er_comparison(scorecards)
        return

    if category == "pipeline":
        from dqbench.runner import run_pipeline_benchmark
        from dqbench.report import report_pipeline_comparison
        scorecards = []
        for name in PIPELINE_ADAPTER_NAMES:
            typer.echo(f"\nRunning: {name} ...", err=True)
            try:
                adapter = _load_adapter(name)
                sc = run_pipeline_benchmark(adapter, tiers=tiers)
                scorecards.append(sc)
                _save_result(sc, "pipeline", save)
                typer.echo(f"  Done — score: {sc.dqbench_pipeline_score:.2f}", err=True)
            except Exception as e:
                typer.echo(f"  FAILED: {e}", err=True)
        report_pipeline_comparison(scorecards)
        return

    if category == "ocr-company":
        typer.echo("No built-in OCR Company adapters registered yet. Use --adapter with a custom adapter file.", err=True)
        return

    # Default: run detect-category adapters
    from dqbench.runner import run_benchmark
    from dqbench.report import report_comparison

    scorecards = []
    for name in ALL_ADAPTER_NAMES:
        typer.echo(f"\nRunning: {name} ...", err=True)
        try:
            adapter = _load_adapter(name)
            sc = run_benchmark(adapter, tiers=tiers)
            scorecards.append(sc)
            _save_result(sc, "detect", save)
            typer.echo(f"  Done — score: {sc.dqbench_score:.2f}", err=True)
        except Exception as e:
            typer.echo(f"  FAILED: {e}", err=True)

    report_comparison(scorecards)


def _save_result(scorecard, category: str, save: bool) -> None:
    """Record a scorecard on the leaderboard, ignoring persistence errors."""
    if not save:
        return
    from dqbench.leaderboard import save_scorecard
    save_scorecard(scorecard, category)


@app.command()
def generate(
    force: bool = typer.Option(False, "--force", help="Regenerate even if cached"),
    er: bool = typer.Option(False, "--er", help="Generate ER datasets"),
    pipeline: bool = typer.Option(False, "--pipeline", help="Generate Pipeline datasets"),
    ocr_company: bool = typer.Option(False, "--ocr-company", help="Generate OCR Company datasets"),
    all_categories: bool = typer.Option(False, "--all", help="Generate datasets for all categories"),
) -> None:
    """Generate benchmark datasets."""
    from dqbench.runner import CACHE_DIR, ensure_datasets

    if force:
        import shutil
        if CACHE_DIR.exists():
            shutil.rmtree(CACHE_DIR)

    # Default: generate detect datasets (backwards compatible)
    if not er and not pipeline and not ocr_company and not all_categories:
        ensure_datasets()
        typer.echo(f"Datasets generated at {CACHE_DIR}")
        return

    if er or all_categories:
        from dqbench.runner import ensure_er_datasets
        ensure_er_datasets()
        typer.echo(f"ER datasets generated at {CACHE_DIR}")

    if pipeline or all_categories:
        from dqbench.runner import ensure_pipeline_datasets
        ensure_pipeline_datasets()
        typer.echo(f"Pipeline datasets generated at {CACHE_DIR}")

    if ocr_company or all_categories:
        from dqbench.runner import ensure_ocr_company_datasets
        ensure_ocr_company_datasets()
        typer.echo(f"OCR Company datasets generated at {CACHE_DIR}")

    if all_categories:
        ensure_datasets()
        typer.echo(f"Detect datasets generated at {CACHE_DIR}")


@app.command()
def results() -> None:
    """Show results from last run."""
    typer.echo("No cached results. Run 'dqbench run <adapter>' first.")


@app.command()
def leaderboard(
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Filter to one category: detect | transform | er | pipeline | ocr-company",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    clear: bool = typer.Option(False, "--clear", help="Delete all locally recorded results"),
    source: str = typer.Option(
        "local", "--source",
        help="'local' for your own cached runs, 'repo' for the published board",
    ),
) -> None:
    """Show the ranked leaderboard of benchmarked tools across categories."""
    from dqbench.leaderboard import CATEGORY_META, clear_results, entries_to_json, load_entries

    if category is not None and category not in CATEGORY_META:
        raise typer.Exit(
            f"Unknown category: '{category}'. Choose from: {', '.join(CATEGORY_META)}"
        )

    if source == "repo":
        from dqbench.leaderboard import LeaderboardEntry
        from dqbench.submission import load_store
        subs = load_store(Path.cwd(), category=category)
        entries = [
            LeaderboardEntry(
                category=s.category, tool_name=s.tool, tool_version=s.tool_version,
                score=s.score, tier_scores=s.tier_scores, timestamp=s.date,
            )
            for s in subs
        ]
    elif source == "local":
        if clear:
            clear_results()
            typer.echo("Leaderboard cleared.")
            return
        entries = load_entries(category=category)
    else:
        raise typer.Exit(f"Unknown source: '{source}'. Choose 'local' or 'repo'.")

    if json_output:
        entries_to_json(entries, sys.stdout)
    else:
        from dqbench.report import report_leaderboard_rich
        report_leaderboard_rich(entries, category=category)


@app.command()
def reproduce(
    manifest: Path = typer.Argument(..., help="A submission manifest JSON (see docs/leaderboard.md)"),
    write: bool = typer.Option(False, "--write", help="Merge the reproduced result into leaderboard/results/ and republish"),
    out: Optional[Path] = typer.Option(None, "--out", help="Write the raw run JSON to this file"),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repository root containing leaderboard/ (default: cwd)"),
) -> None:
    """Reproduce a submission manifest by running its benchmark, and optionally record it."""
    import json as _json
    from dqbench.submission import reproduce as run_manifest, reproduce_and_write

    repo = repo or Path.cwd()
    if not manifest.exists():
        raise typer.Exit(f"Manifest not found: {manifest}")
    manifest_data = _json.loads(manifest.read_text())

    try:
        if write:
            submission = reproduce_and_write(manifest_data, root=repo)
            typer.echo(
                f"Recorded '{submission.tool}' ({submission.category}) "
                f"score={submission.score} and republished LEADERBOARD.md"
            )
            typer.echo("Commit the manifest, leaderboard/results/*.json, and LEADERBOARD.md, then open a PR.")
        else:
            run_data = run_manifest(manifest_data, root=repo)
            if out:
                out.write_text(_json.dumps(run_data, indent=2) + "\n")
                typer.echo(f"Wrote {out}")
            else:
                _json.dump(run_data, sys.stdout, indent=2)
                sys.stdout.write("\n")
    except ValueError as e:
        raise typer.Exit(str(e))


@app.command()
def verify(
    manifest: Path = typer.Argument(..., help="A submission manifest JSON to reproduce and check"),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repository root containing leaderboard/ (default: cwd)"),
) -> None:
    """Reproduce a manifest and confirm its committed leaderboard entry matches (CI gate)."""
    import json as _json
    from dqbench.submission import verify as verify_manifest

    repo = repo or Path.cwd()
    if not manifest.exists():
        raise typer.Exit(f"Manifest not found: {manifest}")
    manifest_data = _json.loads(manifest.read_text())

    errors = verify_manifest(manifest_data, root=repo)
    if errors:
        typer.echo(f"Verification failed for {manifest}:", err=True)
        for e in errors:
            typer.echo(f"  - {e}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Verified: {manifest_data.get('tool')} reproduces its committed result.")


@app.command()
def publish(
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repository root containing leaderboard/ (default: cwd)"),
    check: bool = typer.Option(False, "--check", help="Validate the store and verify LEADERBOARD.md is current (CI mode)"),
) -> None:
    """Regenerate LEADERBOARD.md from the published results store."""
    from dqbench.submission import check_published, publish as publish_board

    repo = repo or Path.cwd()
    if check:
        errors = check_published(repo)
        if errors:
            typer.echo("Leaderboard check failed:", err=True)
            for e in errors:
                typer.echo(f"  - {e}", err=True)
            raise typer.Exit(code=1)
        typer.echo("Leaderboard store is valid and LEADERBOARD.md is up to date.")
        return

    path = publish_board(repo)
    typer.echo(f"Wrote {path}")


def _load_adapter(name: str, path: Path | None = None):
    """Load a built-in or custom adapter by name or file path."""
    if path:
        import importlib.util
        from dqbench.adapters.base import BenchmarkAdapter

        spec = importlib.util.spec_from_file_location("custom_adapter", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if (
                isinstance(obj, type)
                and issubclass(obj, BenchmarkAdapter)
                and obj is not BenchmarkAdapter
                and obj.__module__ == mod.__name__
            ):
                return obj()
        raise typer.Exit("No BenchmarkAdapter subclass found in adapter file.")

    if name in BUILTIN_ADAPTERS:
        module_path, class_name = BUILTIN_ADAPTERS[name].split(":")
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)()

    # Dotted reference to an installed adapter class, e.g. "mypkg.adapters:MyAdapter"
    if ":" in name:
        import importlib
        module_path, class_name = name.split(":", 1)
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)()

    all_names = ALL_ADAPTER_NAMES + ER_ADAPTER_NAMES + PIPELINE_ADAPTER_NAMES + OCR_COMPANY_ADAPTER_NAMES
    raise typer.Exit(
        f"Unknown adapter: '{name}'. "
        f"Available: {', '.join(all_names + ['all'])} or use --adapter for a custom file."
    )
