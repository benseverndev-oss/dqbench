"""Tests for the persisted leaderboard."""
from __future__ import annotations

import io
import json

import pytest

from dqbench.leaderboard import (
    LeaderboardEntry,
    clear_results,
    entries_to_json,
    entry_from_scorecard,
    load_entries,
    ranked_by_category,
    save_scorecard,
)
from dqbench.models import (
    ERScorecard,
    ERTierResult,
    OCRCompanyScorecard,
    OCRCompanyTierResult,
    PipelineScorecard,
    PipelineTierResult,
    Scorecard,
    TierResult,
    TransformScorecard,
    TransformTierResult,
)


def _detect_scorecard(name: str, issue_f1: float) -> Scorecard:
    t = TierResult(
        tier=1, recall=0.0, precision=0.0, f1=0.0, false_positive_rate=0.0,
        time_seconds=0.1, memory_mb=1.0, findings_count=0,
        issue_recall=issue_f1, issue_precision=issue_f1, issue_f1=issue_f1,
    )
    return Scorecard(tool_name=name, tool_version="1.0", tiers=[t])


def test_entry_from_detect_scorecard():
    sc = _detect_scorecard("ToolA", 0.5)
    entry = entry_from_scorecard(sc, "detect")
    assert entry.tool_name == "ToolA"
    assert entry.category == "detect"
    # T1 weight is 0.20 -> 0.5 * 0.20 * 100 = 10.0
    assert entry.score == 10.0
    assert entry.tier_scores == {1: 0.5}
    assert entry.timestamp  # populated


def test_entry_from_scorecard_unknown_category():
    with pytest.raises(ValueError):
        entry_from_scorecard(_detect_scorecard("X", 0.1), "nope")


def test_save_and_load_roundtrip(tmp_path):
    save_scorecard(_detect_scorecard("ToolA", 0.5), "detect", results_dir=tmp_path)
    save_scorecard(_detect_scorecard("ToolB", 1.0), "detect", results_dir=tmp_path)

    entries = load_entries(results_dir=tmp_path)
    assert {e.tool_name for e in entries} == {"ToolA", "ToolB"}
    assert (tmp_path / "detect.json").exists()


def test_latest_run_wins(tmp_path):
    save_scorecard(_detect_scorecard("ToolA", 0.5), "detect", results_dir=tmp_path)
    save_scorecard(_detect_scorecard("ToolA", 1.0), "detect", results_dir=tmp_path)

    entries = load_entries(results_dir=tmp_path)
    assert len(entries) == 1
    assert entries[0].score == 20.0  # 1.0 * 0.20 * 100


def test_load_filtered_by_category(tmp_path):
    save_scorecard(_detect_scorecard("ToolA", 0.5), "detect", results_dir=tmp_path)
    er = ERScorecard(
        tool_name="ERTool", tool_version="2.0",
        tiers=[ERTierResult(tier=1, precision=1.0, recall=1.0, f1=1.0,
                            false_positives=0, false_negatives=0,
                            time_seconds=0.1, memory_mb=1.0)],
    )
    save_scorecard(er, "er", results_dir=tmp_path)

    detect_only = load_entries(results_dir=tmp_path, category="detect")
    assert [e.category for e in detect_only] == ["detect"]


def test_ranked_by_category_sorts_descending(tmp_path):
    save_scorecard(_detect_scorecard("Low", 0.2), "detect", results_dir=tmp_path)
    save_scorecard(_detect_scorecard("High", 0.9), "detect", results_dir=tmp_path)
    save_scorecard(_detect_scorecard("Mid", 0.5), "detect", results_dir=tmp_path)

    ranked = ranked_by_category(load_entries(results_dir=tmp_path))
    names = [e.tool_name for e in ranked["detect"]]
    assert names == ["High", "Mid", "Low"]


def test_clear_results(tmp_path):
    save_scorecard(_detect_scorecard("ToolA", 0.5), "detect", results_dir=tmp_path)
    clear_results(results_dir=tmp_path)
    assert load_entries(results_dir=tmp_path) == []


def test_load_missing_dir_returns_empty(tmp_path):
    assert load_entries(results_dir=tmp_path / "does-not-exist") == []


def test_entries_to_json_includes_rank():
    entries = [
        LeaderboardEntry("detect", "High", "1.0", 90.0, {1: 0.9}, "t"),
        LeaderboardEntry("detect", "Low", "1.0", 10.0, {1: 0.1}, "t"),
    ]
    buf = io.StringIO()
    entries_to_json(entries, buf)
    data = json.loads(buf.getvalue())
    assert data["detect"][0]["rank"] == 1
    assert data["detect"][0]["tool_name"] == "High"
    assert data["detect"][1]["rank"] == 2


def test_all_category_score_attrs_resolve(tmp_path):
    transform = TransformScorecard(
        tool_name="T", tool_version="1.0",
        tiers=[TransformTierResult(tier=1, accuracy=0.8, correct_cells=8, wrong_cells=2,
                                  skipped_cells=0, planted_cells=10, time_seconds=0.1,
                                  memory_mb=1.0, per_column=[])],
    )
    pipeline = PipelineScorecard(
        tool_name="P", tool_version="1.0",
        tiers=[PipelineTierResult(tier=1, transform_accuracy=0.8, dedup_accuracy=0.9,
                                 composite=0.85, output_rows=10, expected_rows=10,
                                 time_seconds=0.1, memory_mb=1.0)],
    )
    ocr = OCRCompanyScorecard(
        tool_name="O", tool_version="1.0",
        tiers=[OCRCompanyTierResult(tier=1, confidence_separation=0.5, clean_flag_rate=0.1,
                                   corrupted_flag_rate=0.9, weakest_token_hit_rate=0.8,
                                   suggestion_coverage_rate=0.6, suggestion_exact_hit_rate=0.7,
                                   suggestion_improvement_rate=0.75,
                                   avg_similarity_delta_on_suggestions=0.02, composite=0.78,
                                   rows=100, time_seconds=0.2, memory_mb=5.0)],
    )
    for sc, cat in [(transform, "transform"), (pipeline, "pipeline"), (ocr, "ocr-company")]:
        entry = save_scorecard(sc, cat, results_dir=tmp_path)
        assert entry.score > 0
        assert entry.tier_scores[1] > 0
