"""Persisted leaderboard of benchmarked tools across all categories.

Each `dqbench run` writes a normalised entry to `~/.dqbench/results/<category>.json`
keyed by tool name (latest run wins). `dqbench leaderboard` reads those files and
renders a ranked board per category.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO

RESULTS_DIR = Path.home() / ".dqbench" / "results"

# category key -> how to pull a composite score and a per-tier metric off a scorecard
CATEGORY_META: dict[str, dict[str, str]] = {
    "detect": {"label": "Detect", "score_attr": "dqbench_score", "tier_metric": "issue_f1"},
    "transform": {"label": "Transform", "score_attr": "composite_score", "tier_metric": "accuracy"},
    "er": {"label": "ER", "score_attr": "dqbench_er_score", "tier_metric": "f1"},
    "pipeline": {"label": "Pipeline", "score_attr": "dqbench_pipeline_score", "tier_metric": "composite"},
    "ocr-company": {"label": "OCR Company", "score_attr": "dqbench_ocr_company_score", "tier_metric": "composite"},
}

# Display order for categories on the board
CATEGORY_ORDER = ["detect", "transform", "er", "pipeline", "ocr-company"]


@dataclass
class LeaderboardEntry:
    category: str
    tool_name: str
    tool_version: str
    score: float
    tier_scores: dict[int, float] = field(default_factory=dict)
    timestamp: str = ""


def _resolve_dir(results_dir: Path | None) -> Path:
    """Resolve the results directory, honouring a runtime override of RESULTS_DIR."""
    return results_dir if results_dir is not None else RESULTS_DIR


def entry_from_scorecard(scorecard, category: str) -> LeaderboardEntry:
    """Normalise any category scorecard into a leaderboard entry."""
    if category not in CATEGORY_META:
        raise ValueError(f"Unknown category: {category!r}")
    meta = CATEGORY_META[category]
    metric = meta["tier_metric"]
    tier_scores = {t.tier: round(getattr(t, metric), 4) for t in scorecard.tiers}
    return LeaderboardEntry(
        category=category,
        tool_name=scorecard.tool_name,
        tool_version=scorecard.tool_version,
        score=round(getattr(scorecard, meta["score_attr"]), 2),
        tier_scores=tier_scores,
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _entry_to_dict(entry: LeaderboardEntry) -> dict:
    return {
        "tool_name": entry.tool_name,
        "tool_version": entry.tool_version,
        "score": entry.score,
        "tier_scores": {str(k): v for k, v in entry.tier_scores.items()},
        "timestamp": entry.timestamp,
    }


def _entry_from_dict(category: str, d: dict) -> LeaderboardEntry:
    return LeaderboardEntry(
        category=category,
        tool_name=d["tool_name"],
        tool_version=d.get("tool_version", ""),
        score=d.get("score", 0.0),
        tier_scores={int(k): v for k, v in d.get("tier_scores", {}).items()},
        timestamp=d.get("timestamp", ""),
    )


def save_scorecard(scorecard, category: str, results_dir: Path | None = None) -> LeaderboardEntry:
    """Persist a scorecard's result, keyed by tool name (latest run wins)."""
    entry = entry_from_scorecard(scorecard, category)
    target = _resolve_dir(results_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{category}.json"
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text())
    data[entry.tool_name] = _entry_to_dict(entry)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return entry


def load_entries(results_dir: Path | None = None, category: str | None = None) -> list[LeaderboardEntry]:
    """Load saved entries, optionally filtered to a single category."""
    target = _resolve_dir(results_dir)
    cats = [category] if category else CATEGORY_ORDER
    entries: list[LeaderboardEntry] = []
    for cat in cats:
        path = target / f"{cat}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        entries.extend(_entry_from_dict(cat, d) for d in data.values())
    return entries


def ranked_by_category(entries: list[LeaderboardEntry]) -> dict[str, list[LeaderboardEntry]]:
    """Group entries by category and sort each group by score, descending."""
    by_cat: dict[str, list[LeaderboardEntry]] = {}
    for e in entries:
        by_cat.setdefault(e.category, []).append(e)
    for group in by_cat.values():
        group.sort(key=lambda e: e.score, reverse=True)
    return by_cat


def clear_results(results_dir: Path | None = None) -> None:
    """Remove all persisted leaderboard files."""
    target = _resolve_dir(results_dir)
    for cat in CATEGORY_ORDER:
        path = target / f"{cat}.json"
        if path.exists():
            path.unlink()


def entries_to_json(entries: list[LeaderboardEntry], output: IO[str]) -> None:
    """Serialise ranked entries to JSON, grouped by category."""
    by_cat = ranked_by_category(entries)
    data = {
        cat: [
            {
                "rank": rank,
                "tool_name": e.tool_name,
                "tool_version": e.tool_version,
                "score": e.score,
                "tier_scores": {str(k): v for k, v in e.tier_scores.items()},
                "timestamp": e.timestamp,
            }
            for rank, e in enumerate(group, 1)
        ]
        for cat, group in by_cat.items()
    }
    json.dump(data, output, indent=2)
    output.write("\n")
