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
    # GoldenMatch (ER)
    "goldenmatch": "dqbench.adapters.goldenmatch_adapter:GoldenMatchAdapter",
    # GoldenPipe (Pipeline)
    "goldenpipe":  "dqbench.adapters.goldenpipe_adapter:GoldenPipeAdapter",
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
]

ER_ADAPTER_NAMES = ["goldenmatch"]
PIPELINE_ADAPTER_NAMES = ["goldenpipe"]
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
def submit(
    run_json: Path = typer.Argument(..., help="A 'dqbench run --json' output file"),
    submitter: str = typer.Option(..., "--submitter", help="Who is submitting (name or handle)"),
    tool: Optional[str] = typer.Option(None, "--tool", help="Override the tool display name"),
    adapter: str = typer.Option("", "--adapter-ref", help="Adapter reference, e.g. module:Class or a URL"),
    source: str = typer.Option("reproduced", "--result-source", help="reproduced | vendor-reported | third-party"),
    notes: str = typer.Option("", "--notes", help="Optional notes (config, hardware, caveats)"),
    repo: Optional[Path] = typer.Option(None, "--repo", help="Repository root containing leaderboard/ (default: cwd)"),
    publish_md: bool = typer.Option(True, "--publish/--no-publish", help="Regenerate LEADERBOARD.md after adding"),
) -> None:
    """Add a benchmark run to the published leaderboard store (for a PR submission)."""
    import json as _json
    from dqbench.submission import add_submission, publish as publish_board, submission_from_run

    repo = repo or Path.cwd()
    if not run_json.exists():
        raise typer.Exit(f"Run file not found: {run_json}")

    run_data = _json.loads(run_json.read_text())
    try:
        submission = submission_from_run(
            run_data, submitter=submitter, tool=tool,
            adapter=adapter, source=source, notes=notes,
        )
        path = add_submission(submission, root=repo)
    except ValueError as e:
        raise typer.Exit(str(e))

    typer.echo(f"Added '{submission.tool}' ({submission.category}) -> {path}")
    if publish_md:
        md_path = publish_board(repo)
        typer.echo(f"Regenerated {md_path}")
    typer.echo("Commit the changed files and open a pull request to publish.")


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

    all_names = ALL_ADAPTER_NAMES + ER_ADAPTER_NAMES + PIPELINE_ADAPTER_NAMES + OCR_COMPANY_ADAPTER_NAMES
    raise typer.Exit(
        f"Unknown adapter: '{name}'. "
        f"Available: {', '.join(all_names + ['all'])} or use --adapter for a custom file."
    )
