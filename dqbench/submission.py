"""Public, community-submittable leaderboard.

The local leaderboard (`dqbench/leaderboard.py`) caches a developer's own runs
under `~/.dqbench/results/`. This module backs the *published* board that lives
in the repository: results are committed as JSON under `leaderboard/results/`,
contributors add entries via pull request, and `LEADERBOARD.md` is regenerated
from that store.

Submission flow:
    dqbench run <adapter> --json > run.json
    dqbench submit run.json --submitter "Your Name"
    dqbench publish            # regenerate LEADERBOARD.md
    # commit leaderboard/results/*.json + LEADERBOARD.md, open a PR
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as _date
from pathlib import Path

from dqbench import __version__
from dqbench.leaderboard import CATEGORY_META, CATEGORY_ORDER

# Repo-relative locations
RESULTS_SUBDIR = Path("leaderboard") / "results"
LEADERBOARD_MD = Path("LEADERBOARD.md")

# Map a run-JSON score key back to its category (run JSON does not name the category)
SCORE_KEY_TO_CATEGORY = {meta["score_attr"]: cat for cat, meta in CATEGORY_META.items()}

VALID_SOURCES = {"reproduced", "vendor-reported", "third-party"}


@dataclass
class Submission:
    category: str
    tool: str
    tool_version: str
    score: float
    tier_scores: dict[int, float]
    submitter: str
    date: str
    adapter: str = ""
    dqbench_version: str = ""
    source: str = "reproduced"
    notes: str = ""

    def key(self) -> str:
        """Identity within a category — one entry per (tool, version)."""
        return f"{self.tool}@{self.tool_version}"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "score": self.score,
            "tier_scores": {str(k): v for k, v in sorted(self.tier_scores.items())},
            "submitter": self.submitter,
            "date": self.date,
            "adapter": self.adapter,
            "dqbench_version": self.dqbench_version,
            "source": self.source,
            "notes": self.notes,
        }


def submission_from_dict(d: dict) -> Submission:
    return Submission(
        category=d["category"],
        tool=d["tool"],
        tool_version=str(d.get("tool_version", "")),
        score=float(d["score"]),
        tier_scores={int(k): float(v) for k, v in d.get("tier_scores", {}).items()},
        submitter=d["submitter"],
        date=d.get("date", ""),
        adapter=d.get("adapter", ""),
        dqbench_version=str(d.get("dqbench_version", "")),
        source=d.get("source", "reproduced"),
        notes=d.get("notes", ""),
    )


def infer_category(run_data: dict) -> str:
    """Determine the benchmark category from a `dqbench run --json` payload."""
    for key, cat in SCORE_KEY_TO_CATEGORY.items():
        if key in run_data:
            return cat
    raise ValueError(
        "Could not determine category from run JSON: no known score key present "
        f"(expected one of {sorted(SCORE_KEY_TO_CATEGORY)})."
    )


def submission_from_run(
    run_data: dict,
    submitter: str,
    *,
    category: str | None = None,
    tool: str | None = None,
    adapter: str = "",
    source: str = "reproduced",
    notes: str = "",
    on_date: str | None = None,
) -> Submission:
    """Build a Submission from a `dqbench run --json` payload plus metadata."""
    category = category or infer_category(run_data)
    if category not in CATEGORY_META:
        raise ValueError(f"Unknown category: {category!r}")
    meta = CATEGORY_META[category]
    metric = meta["tier_metric"]
    tier_scores = {int(t["tier"]): round(float(t[metric]), 4) for t in run_data.get("tiers", [])}
    return Submission(
        category=category,
        tool=tool or run_data.get("tool_name", "unknown"),
        tool_version=str(run_data.get("tool_version", "unknown")),
        score=round(float(run_data[meta["score_attr"]]), 2),
        tier_scores=tier_scores,
        submitter=submitter,
        date=on_date or _date.today().isoformat(),
        adapter=adapter,
        dqbench_version=__version__,
        source=source,
        notes=notes,
    )


def validate_submission(d: dict) -> list[str]:
    """Return a list of validation errors; empty means valid."""
    errors: list[str] = []

    cat = d.get("category")
    if cat not in CATEGORY_META:
        errors.append(f"category must be one of {sorted(CATEGORY_META)}, got {cat!r}")

    if not str(d.get("tool", "")).strip():
        errors.append("tool is required and must be non-empty")
    if not str(d.get("submitter", "")).strip():
        errors.append("submitter is required and must be non-empty")

    score = d.get("score")
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        errors.append("score must be a number")
    elif not (0.0 <= float(score) <= 100.0):
        errors.append(f"score must be in [0, 100], got {score}")

    tier_scores = d.get("tier_scores", {})
    if not isinstance(tier_scores, dict) or not tier_scores:
        errors.append("tier_scores must be a non-empty object")
    else:
        for k, v in tier_scores.items():
            try:
                int(k)
            except (TypeError, ValueError):
                errors.append(f"tier_scores key {k!r} must be an integer")
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                errors.append(f"tier_scores[{k}] must be a number")
            elif not (0.0 <= float(v) <= 1.0):
                errors.append(f"tier_scores[{k}] must be in [0, 1], got {v}")

    source = d.get("source", "reproduced")
    if source not in VALID_SOURCES:
        errors.append(f"source must be one of {sorted(VALID_SOURCES)}, got {source!r}")

    return errors


# ---------------------------------------------------------------------------
# Repo store
# ---------------------------------------------------------------------------


def _results_path(root: Path, category: str) -> Path:
    return root / RESULTS_SUBDIR / f"{category}.json"


def load_store(root: Path, category: str | None = None) -> list[Submission]:
    """Load all published submissions, optionally filtered to one category."""
    cats = [category] if category else CATEGORY_ORDER
    out: list[Submission] = []
    for cat in cats:
        path = _results_path(root, cat)
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        out.extend(submission_from_dict(d) for d in data)
    return out


def add_submission(submission: Submission, root: Path) -> Path:
    """Merge a submission into the repo store (one entry per tool@version)."""
    errors = validate_submission(submission.to_dict())
    if errors:
        raise ValueError("Invalid submission:\n  - " + "\n  - ".join(errors))

    path = _results_path(root, submission.category)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = json.loads(path.read_text()) if path.exists() else []

    merged = [s for s in map(submission_from_dict, existing) if s.key() != submission.key()]
    merged.append(submission)
    merged.sort(key=lambda s: (-s.score, s.tool.lower()))

    path.write_text(json.dumps([s.to_dict() for s in merged], indent=2) + "\n")
    return path


def validate_store(root: Path) -> list[str]:
    """Validate every entry in the published store; returns a flat error list."""
    errors: list[str] = []
    for cat in CATEGORY_ORDER:
        path = _results_path(root, cat)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{path}: invalid JSON ({e})")
            continue
        if not isinstance(data, list):
            errors.append(f"{path}: expected a JSON array of submissions")
            continue
        for i, entry in enumerate(data):
            for err in validate_submission(entry):
                errors.append(f"{path}[{i}]: {err}")
            if entry.get("category") not in (None, cat):
                errors.append(f"{path}[{i}]: category {entry.get('category')!r} does not match file {cat!r}")
    return errors


# ---------------------------------------------------------------------------
# Markdown publication
# ---------------------------------------------------------------------------


def render_markdown(submissions: list[Submission]) -> str:
    """Render the published board as Markdown for LEADERBOARD.md."""
    by_cat: dict[str, list[Submission]] = {}
    for s in submissions:
        by_cat.setdefault(s.category, []).append(s)

    lines: list[str] = [
        "# DQBench Leaderboard",
        "",
        "Published results across all five categories. Higher is better; the score is "
        "the tier-weighted composite (0-100).",
        "",
        "> Generated by `dqbench publish` from `leaderboard/results/`. Do not edit by hand — "
        "see [how to submit](docs/leaderboard.md).",
        "",
    ]

    any_rows = False
    for cat in CATEGORY_ORDER:
        group = by_cat.get(cat)
        if not group:
            continue
        any_rows = True
        meta = CATEGORY_META[cat]
        group = sorted(group, key=lambda s: (-s.score, s.tool.lower()))
        all_tiers = sorted({t for s in group for t in s.tier_scores})

        lines.append(f"## {meta['label']}")
        lines.append("")
        header = ["Rank", "Tool", "Version"] + [f"T{t}" for t in all_tiers] + ["Score", "Submitter", "Source", "Date"]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * len(header)) + " |")
        for rank, s in enumerate(group, 1):
            row = [str(rank), s.tool, s.tool_version or "—"]
            for t in all_tiers:
                v = s.tier_scores.get(t)
                row.append(f"{v:.1%}" if v is not None else "—")
            row.append(f"{s.score:.2f}")
            row.append(s.submitter or "—")
            row.append(s.source or "—")
            row.append(s.date or "—")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    if not any_rows:
        lines.append("_No results published yet._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def publish(root: Path) -> Path:
    """Regenerate LEADERBOARD.md from the repo store. Returns the written path."""
    md = render_markdown(load_store(root))
    path = root / LEADERBOARD_MD
    path.write_text(md)
    return path


def check_published(root: Path) -> list[str]:
    """CI helper: validate the store and confirm LEADERBOARD.md is current."""
    errors = validate_store(root)
    if errors:
        return errors

    expected = render_markdown(load_store(root))
    path = root / LEADERBOARD_MD
    current = path.read_text() if path.exists() else ""
    if current != expected:
        errors.append(
            f"{LEADERBOARD_MD} is out of date. Run `dqbench publish` and commit the result."
        )
    return errors
