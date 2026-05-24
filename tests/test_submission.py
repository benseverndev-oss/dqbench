"""Tests for the published, submittable leaderboard."""
from __future__ import annotations

import json

import pytest

from dqbench.submission import (
    Submission,
    add_submission,
    check_published,
    infer_category,
    load_store,
    publish,
    render_markdown,
    submission_from_run,
    validate_store,
    validate_submission,
)


def _detect_run(name="Pandera (best-effort)", version="0.31.1", score=32.51):
    return {
        "tool_name": name,
        "tool_version": version,
        "dqbench_score": score,
        "tiers": [
            {"tier": 1, "issue_f1": 0.3636},
            {"tier": 2, "issue_f1": 0.381},
            {"tier": 3, "issue_f1": 0.25},
        ],
    }


def test_infer_category_detect():
    assert infer_category(_detect_run()) == "detect"


def test_infer_category_er_and_pipeline():
    assert infer_category({"dqbench_er_score": 90, "tiers": []}) == "er"
    assert infer_category({"dqbench_pipeline_score": 80, "tiers": []}) == "pipeline"
    assert infer_category({"composite_score": 70, "tiers": []}) == "transform"
    assert infer_category({"dqbench_ocr_company_score": 60, "tiers": []}) == "ocr-company"


def test_infer_category_unknown():
    with pytest.raises(ValueError):
        infer_category({"tiers": []})


def test_submission_from_run_extracts_fields():
    sub = submission_from_run(_detect_run(), submitter="Me", adapter="pkg:Adapter")
    assert sub.category == "detect"
    assert sub.tool == "Pandera (best-effort)"
    assert sub.tool_version == "0.31.1"
    assert sub.score == 32.51
    assert sub.tier_scores == {1: 0.3636, 2: 0.381, 3: 0.25}
    assert sub.submitter == "Me"
    assert sub.adapter == "pkg:Adapter"
    assert sub.dqbench_version  # filled from package __version__
    assert sub.date


def test_validate_submission_accepts_valid():
    sub = submission_from_run(_detect_run(), submitter="Me")
    assert validate_submission(sub.to_dict()) == []


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d.update(category="bogus"), "category"),
    (lambda d: d.update(tool=""), "tool"),
    (lambda d: d.update(submitter=""), "submitter"),
    (lambda d: d.update(score=150), "score"),
    (lambda d: d.update(score="high"), "score"),
    (lambda d: d.update(tier_scores={}), "tier_scores"),
    (lambda d: d.update(tier_scores={"1": 5.0}), "tier_scores[1]"),
    (lambda d: d.update(source="made-up"), "source"),
])
def test_validate_submission_rejects(mutate, fragment):
    d = submission_from_run(_detect_run(), submitter="Me").to_dict()
    mutate(d)
    errors = validate_submission(d)
    assert any(fragment in e for e in errors), errors


def test_add_submission_writes_and_sorts(tmp_path):
    add_submission(submission_from_run(_detect_run("Low", score=10.0), submitter="Me"), root=tmp_path)
    add_submission(submission_from_run(_detect_run("High", score=90.0), submitter="Me"), root=tmp_path)

    store = load_store(tmp_path, category="detect")
    assert [s.tool for s in store] == ["High", "Low"]
    path = tmp_path / "leaderboard" / "results" / "detect.json"
    assert path.exists()


def test_add_submission_dedups_by_tool_and_version(tmp_path):
    add_submission(submission_from_run(_detect_run(score=10.0), submitter="Me"), root=tmp_path)
    add_submission(submission_from_run(_detect_run(score=40.0), submitter="Me"), root=tmp_path)
    store = load_store(tmp_path, category="detect")
    assert len(store) == 1
    assert store[0].score == 40.0


def test_add_submission_keeps_distinct_versions(tmp_path):
    add_submission(submission_from_run(_detect_run(version="1.0", score=10.0), submitter="Me"), root=tmp_path)
    add_submission(submission_from_run(_detect_run(version="2.0", score=40.0), submitter="Me"), root=tmp_path)
    assert len(load_store(tmp_path, category="detect")) == 2


def test_add_submission_rejects_invalid(tmp_path):
    bad = Submission(
        category="detect", tool="", tool_version="1.0", score=10.0,
        tier_scores={1: 0.5}, submitter="Me", date="2026-01-01",
    )
    with pytest.raises(ValueError):
        add_submission(bad, root=tmp_path)


def test_render_markdown_has_table_and_ranks():
    subs = [
        submission_from_run(_detect_run("High", score=90.0), submitter="Me"),
        submission_from_run(_detect_run("Low", score=10.0), submitter="Me"),
    ]
    md = render_markdown(subs)
    assert "# DQBench Leaderboard" in md
    assert "## Detect" in md
    # leader appears before runner-up
    assert md.index("High") < md.index("Low")


def test_render_markdown_empty():
    assert "No results published yet" in render_markdown([])


def test_publish_and_check_roundtrip(tmp_path):
    add_submission(submission_from_run(_detect_run(), submitter="Me"), root=tmp_path)
    publish(tmp_path)
    assert (tmp_path / "LEADERBOARD.md").exists()
    assert check_published(tmp_path) == []


def test_check_published_detects_stale_markdown(tmp_path):
    add_submission(submission_from_run(_detect_run(), submitter="Me"), root=tmp_path)
    publish(tmp_path)
    # add another entry but do not re-publish
    add_submission(submission_from_run(_detect_run("Other", score=5.0), submitter="Me"), root=tmp_path)
    errors = check_published(tmp_path)
    assert any("out of date" in e for e in errors)


def test_validate_store_flags_bad_entry(tmp_path):
    path = tmp_path / "leaderboard" / "results" / "detect.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"category": "detect", "tool": "X", "score": 999,
                                 "tier_scores": {"1": 0.5}, "submitter": "Me"}]))
    errors = validate_store(tmp_path)
    assert any("score" in e for e in errors)


def test_validate_store_flags_category_mismatch(tmp_path):
    path = tmp_path / "leaderboard" / "results" / "detect.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"category": "er", "tool": "X", "tool_version": "1",
                                 "score": 50, "tier_scores": {"1": 0.5}, "submitter": "Me"}]))
    errors = validate_store(tmp_path)
    assert any("does not match" in e for e in errors)
