"""Tests for the DQBench CLI."""
from __future__ import annotations

from typer.testing import CliRunner

from dqbench.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "dqbench" in result.stdout.lower()


def test_generate():
    result = runner.invoke(app, ["generate"])
    assert result.exit_code == 0


def test_results_command():
    result = runner.invoke(app, ["results"])
    assert result.exit_code == 0
    assert "dqbench run" in result.stdout


def test_run_help():
    result = runner.invoke(app, ["run", "--help"])
    assert result.exit_code == 0
    assert "adapter" in result.stdout.lower()


def test_generate_help():
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    assert "force" in result.stdout.lower()


def test_generate_ocr_company():
    result = runner.invoke(app, ["generate", "--ocr-company"])
    assert result.exit_code == 0


def test_leaderboard_help():
    result = runner.invoke(app, ["leaderboard", "--help"])
    assert result.exit_code == 0
    assert "leaderboard" in result.stdout.lower()


def test_leaderboard_empty(monkeypatch, tmp_path):
    import dqbench.leaderboard as lb
    monkeypatch.setattr(lb, "RESULTS_DIR", tmp_path)
    result = runner.invoke(app, ["leaderboard"])
    assert result.exit_code == 0
    assert "No results yet" in result.stdout


def test_leaderboard_unknown_category():
    result = runner.invoke(app, ["leaderboard", "--category", "bogus"])
    assert result.exit_code != 0


CUSTOM_ADAPTER = '''
from pathlib import Path
from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding


class MiniAdapter(DQBenchAdapter):
    @property
    def name(self) -> str:
        return "MiniTool"

    @property
    def version(self) -> str:
        return "9.9"

    def validate(self, csv_path: Path) -> list[DQBenchFinding]:
        return []
'''


def test_leaderboard_populated_after_run(monkeypatch, tmp_path):
    import json as _json

    import dqbench.leaderboard as lb
    monkeypatch.setattr(lb, "RESULTS_DIR", tmp_path / "results")

    adapter_file = tmp_path / "mini_adapter.py"
    adapter_file.write_text(CUSTOM_ADAPTER)

    run_result = runner.invoke(app, ["run", "mini", "--adapter", str(adapter_file), "--tier", "1"])
    assert run_result.exit_code == 0, run_result.output

    board = runner.invoke(app, ["leaderboard", "--json"])
    assert board.exit_code == 0
    data = _json.loads(board.stdout)
    assert data["detect"][0]["tool_name"] == "MiniTool"
    assert data["detect"][0]["rank"] == 1


def test_run_no_save_skips_leaderboard(monkeypatch, tmp_path):
    import dqbench.leaderboard as lb
    monkeypatch.setattr(lb, "RESULTS_DIR", tmp_path / "results")

    adapter_file = tmp_path / "mini_adapter.py"
    adapter_file.write_text(CUSTOM_ADAPTER)

    run_result = runner.invoke(
        app, ["run", "mini", "--adapter", str(adapter_file), "--tier", "1", "--no-save"]
    )
    assert run_result.exit_code == 0
    assert lb.load_entries(results_dir=tmp_path / "results") == []


DETECT_RUN_JSON = """{
  "tool_name": "MiniTool",
  "tool_version": "9.9",
  "dqbench_score": 42.0,
  "tiers": [
    {"tier": 1, "issue_f1": 0.4},
    {"tier": 2, "issue_f1": 0.45},
    {"tier": 3, "issue_f1": 0.4}
  ]
}"""


def test_submit_publish_flow(tmp_path):
    run_file = tmp_path / "run.json"
    run_file.write_text(DETECT_RUN_JSON)

    result = runner.invoke(app, [
        "submit", str(run_file), "--submitter", "Tester",
        "--adapter-ref", "pkg:MiniAdapter", "--repo", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "leaderboard" / "results" / "detect.json").exists()
    assert (tmp_path / "LEADERBOARD.md").exists()
    assert "MiniTool" in (tmp_path / "LEADERBOARD.md").read_text()

    check = runner.invoke(app, ["publish", "--check", "--repo", str(tmp_path)])
    assert check.exit_code == 0, check.output


def test_submit_requires_submitter(tmp_path):
    run_file = tmp_path / "run.json"
    run_file.write_text(DETECT_RUN_JSON)
    result = runner.invoke(app, ["submit", str(run_file), "--repo", str(tmp_path)])
    assert result.exit_code != 0


def test_publish_check_fails_on_stale(tmp_path):
    run_file = tmp_path / "run.json"
    run_file.write_text(DETECT_RUN_JSON)
    runner.invoke(app, [
        "submit", str(run_file), "--submitter", "Tester",
        "--repo", str(tmp_path), "--no-publish",
    ])
    # store exists but LEADERBOARD.md was never written
    result = runner.invoke(app, ["publish", "--check", "--repo", str(tmp_path)])
    assert result.exit_code == 1


def test_leaderboard_source_repo(tmp_path):
    run_file = tmp_path / "run.json"
    run_file.write_text(DETECT_RUN_JSON)
    runner.invoke(app, [
        "submit", str(run_file), "--submitter", "Tester", "--repo", str(tmp_path),
    ])
    import json as _json
    import os
    cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        result = runner.invoke(app, ["leaderboard", "--source", "repo", "--json"])
    finally:
        os.chdir(cwd)
    assert result.exit_code == 0
    data = _json.loads(result.stdout)
    assert data["detect"][0]["tool_name"] == "MiniTool"


def test_leaderboard_clear(monkeypatch, tmp_path):
    import dqbench.leaderboard as lb
    from dqbench.models import Scorecard, TierResult

    monkeypatch.setattr(lb, "RESULTS_DIR", tmp_path)
    t = TierResult(
        tier=1, recall=0.0, precision=0.0, f1=0.0, false_positive_rate=0.0,
        time_seconds=0.1, memory_mb=1.0, findings_count=0,
        issue_recall=0.5, issue_precision=0.5, issue_f1=0.5,
    )
    lb.save_scorecard(Scorecard("ToolA", "1.0", [t]), "detect", results_dir=tmp_path)

    result = runner.invoke(app, ["leaderboard", "--clear"])
    assert result.exit_code == 0
    assert "cleared" in result.stdout.lower()
    assert lb.load_entries(results_dir=tmp_path) == []
