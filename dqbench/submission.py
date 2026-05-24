"""Public, community-submittable leaderboard.

The local leaderboard (`dqbench/leaderboard.py`) caches a developer's own runs
under `~/.dqbench/results/`. This module backs the *published* board that lives
in the repository: results are committed as JSON under `leaderboard/results/`,
contributors add entries via pull request, and `LEADERBOARD.md` is regenerated
from that store.

Acceptance policy: a result is only valid if it can be reproduced by a GitHub
Action. Each entry must have a *manifest* under `leaderboard/submissions/` that
declares how to run the benchmark (tool, category, adapter, pinned packages).
CI re-runs each changed manifest on the PR and rejects any entry whose committed
numbers do not match the reproduced ones.

Submission flow:
    # 1. write leaderboard/submissions/<id>.json (see docs/leaderboard.md)
    dqbench reproduce leaderboard/submissions/<id>.json --write
    # 2. commit the manifest + leaderboard/results/*.json + LEADERBOARD.md
    # 3. open a PR — CI verifies the numbers reproduce
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
SUBMISSIONS_SUBDIR = Path("leaderboard") / "submissions"
REFERENCE_SUBDIR = Path("leaderboard") / "reference"
LEADERBOARD_MD = Path("LEADERBOARD.md")

# Reproduced numbers are rounded (score 2dp, tier 4dp); this absorbs float repr only.
REPRODUCE_TOLERANCE = 1e-9

# Map a run-JSON score key back to its category (run JSON does not name the category)
SCORE_KEY_TO_CATEGORY = {meta["score_attr"]: cat for cat, meta in CATEGORY_META.items()}

VALID_SOURCES = {"reproduced", "vendor-reported", "third-party", "auto-config"}


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


def _reference_path(root: Path, category: str) -> Path:
    return root / REFERENCE_SUBDIR / f"{category}.json"


def load_reference(root: Path, category: str | None = None) -> list[Submission]:
    """Load ungated reference entries (auto-config / non-deterministic, not gate-verified)."""
    cats = [category] if category else CATEGORY_ORDER
    out: list[Submission] = []
    for cat in cats:
        path = _reference_path(root, cat)
        if not path.exists():
            continue
        out.extend(submission_from_dict(d) for d in json.loads(path.read_text()))
    return out


def add_reference(submission: Submission, root: Path) -> Path:
    """Merge an ungated reference entry (one per tool@version). Not verified by CI."""
    errors = validate_submission(submission.to_dict())
    if errors:
        raise ValueError("Invalid reference entry:\n  - " + "\n  - ".join(errors))
    path = _reference_path(root, submission.category)
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

    # Reference entries are ungated (not verified), but must still be schema-valid.
    for cat in CATEGORY_ORDER:
        path = _reference_path(root, cat)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{path}: invalid JSON ({e})")
            continue
        for i, entry in enumerate(data if isinstance(data, list) else []):
            for err in validate_submission(entry):
                errors.append(f"{path}[{i}]: {err}")

    errors.extend(_validate_manifest_linkage(root))
    return errors


# ---------------------------------------------------------------------------
# Manifests & reproducibility
# ---------------------------------------------------------------------------


def _manifest_dir(root: Path) -> Path:
    return root / SUBMISSIONS_SUBDIR


def load_manifests(root: Path) -> list[dict]:
    """Load every submission manifest under leaderboard/submissions/."""
    d = _manifest_dir(root)
    if not d.exists():
        return []
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))]


def validate_manifest(d: dict) -> list[str]:
    """Validate a single manifest; empty list means valid."""
    errors: list[str] = []
    if d.get("category") not in CATEGORY_META:
        errors.append(f"category must be one of {sorted(CATEGORY_META)}, got {d.get('category')!r}")
    if not str(d.get("tool", "")).strip():
        errors.append("tool is required and must be non-empty")
    if not str(d.get("submitter", "")).strip():
        errors.append("submitter is required and must be non-empty")
    if not (d.get("adapter") or d.get("adapter_file")):
        errors.append("manifest must set 'adapter' (built-in name or module:Class) or 'adapter_file'")
    install = d.get("install", [])
    if not isinstance(install, list) or any(not isinstance(x, str) for x in install):
        errors.append("install must be a list of pip requirement strings")
    if d.get("source", "reproduced") not in VALID_SOURCES:
        errors.append(f"source must be one of {sorted(VALID_SOURCES)}, got {d.get('source')!r}")
    return errors


def _validate_manifest_linkage(root: Path) -> list[str]:
    """Every results entry must be backed by a valid manifest (category, tool)."""
    errors: list[str] = []
    manifests = load_manifests(root)
    manifest_keys: set[tuple[str, str]] = set()
    for m in manifests:
        merrs = validate_manifest(m)
        if merrs:
            errors.append(f"manifest {m.get('id', m.get('tool', '?'))}: " + "; ".join(merrs))
            continue
        # Only gated manifests satisfy the gated-entry linkage requirement.
        if m.get("gated", True):
            manifest_keys.add((m["category"], m["tool"]))

    for cat in CATEGORY_ORDER:
        path = _results_path(root, cat)
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue  # JSON error already reported by validate_store
        if not isinstance(data, list):
            continue
        for entry in data:
            tool = entry.get("tool")
            if (cat, tool) not in manifest_keys:
                errors.append(
                    f"{path}: entry '{tool}' has no reproducible manifest in "
                    f"{SUBMISSIONS_SUBDIR}/ — leaderboard entries must be reproducible via a GitHub Action."
                )
    return errors


def load_adapter_from_manifest(manifest: dict, root: Path):
    """Instantiate the adapter a manifest points at (built-in name, file, or module:Class)."""
    from dqbench.cli import _load_adapter

    adapter_file = manifest.get("adapter_file")
    if adapter_file:
        return _load_adapter("custom", root / adapter_file)
    spec = manifest.get("adapter")
    if not spec:
        raise ValueError("manifest must set 'adapter' or 'adapter_file'")
    return _load_adapter(spec)


def run_adapter_json(adapter, category: str) -> dict:
    """Run the benchmark for `category` and return the same dict `dqbench run --json` emits."""
    import io

    from dqbench import report, runner

    runners = {
        "detect": (runner.run_benchmark, report.report_json),
        "transform": (runner.run_transform_benchmark, report.report_transform_json),
        "er": (runner.run_er_benchmark, report.report_er_json),
        "pipeline": (runner.run_pipeline_benchmark, report.report_pipeline_json),
        "ocr-company": (runner.run_ocr_company_benchmark, report.report_ocr_company_json),
    }
    if category not in runners:
        raise ValueError(f"Unknown category: {category!r}")
    run_fn, json_fn = runners[category]
    scorecard = run_fn(adapter)
    buf = io.StringIO()
    json_fn(scorecard, buf)
    return json.loads(buf.getvalue())


def reproduce(manifest: dict, root: Path) -> dict:
    """Run the benchmark described by a manifest and return its run JSON."""
    errs = validate_manifest(manifest)
    if errs:
        raise ValueError("Invalid manifest:\n  - " + "\n  - ".join(errs))
    adapter = load_adapter_from_manifest(manifest, root)
    return run_adapter_json(adapter, manifest["category"])


def submission_from_manifest(manifest: dict, run_data: dict) -> Submission:
    """Build a Submission from a manifest's metadata and a fresh run's numbers."""
    return submission_from_run(
        run_data,
        submitter=manifest["submitter"],
        category=manifest["category"],
        tool=manifest.get("tool"),
        adapter=manifest.get("adapter") or manifest.get("adapter_file", ""),
        source=manifest.get("source", "reproduced"),
        notes=manifest.get("notes", ""),
    )


def reproduce_and_write(manifest: dict, root: Path) -> Submission:
    """Reproduce a manifest's run and merge the result into the gated or reference store.

    Manifests with ``"gated": false`` go to the ungated reference store (not
    verified by CI) — used for non-deterministic auto-config runs.
    """
    submission = submission_from_manifest(manifest, reproduce(manifest, root))
    if manifest.get("gated", True):
        add_submission(submission, root)
    else:
        add_reference(submission, root)
    publish(root)
    return submission


def verify(manifest: dict, root: Path) -> list[str]:
    """Reproduce a manifest and confirm the committed entry matches. Empty = ok."""
    if not manifest.get("gated", True):
        return []  # ungated reference entries are not gate-verified
    errs = validate_manifest(manifest)
    if errs:
        return [f"manifest invalid: {e}" for e in errs]

    fresh = submission_from_manifest(manifest, reproduce(manifest, root))
    match = next(
        (s for s in load_store(root, category=fresh.category) if s.key() == fresh.key()),
        None,
    )
    if match is None:
        return [
            f"no committed entry for {fresh.tool}@{fresh.tool_version} in {fresh.category}; "
            "run `dqbench reproduce <manifest> --write` and commit the result"
        ]

    errors: list[str] = []
    if abs(match.score - fresh.score) > REPRODUCE_TOLERANCE:
        errors.append(
            f"{fresh.tool}: score does not reproduce — committed {match.score}, reproduced {fresh.score}"
        )
    if set(match.tier_scores) != set(fresh.tier_scores):
        errors.append(
            f"{fresh.tool}: tier set does not reproduce — committed {sorted(match.tier_scores)}, "
            f"reproduced {sorted(fresh.tier_scores)}"
        )
    for tier, value in fresh.tier_scores.items():
        if tier in match.tier_scores and abs(match.tier_scores[tier] - value) > REPRODUCE_TOLERANCE:
            errors.append(
                f"{fresh.tool} T{tier}: does not reproduce — committed {match.tier_scores[tier]}, "
                f"reproduced {value}"
            )
    return errors


# ---------------------------------------------------------------------------
# Markdown publication
# ---------------------------------------------------------------------------


def _render_category_tables(lines: list[str], submissions: list[Submission]) -> bool:
    """Append a per-category ranked table for each non-empty category. Returns True if any."""
    by_cat: dict[str, list[Submission]] = {}
    for s in submissions:
        by_cat.setdefault(s.category, []).append(s)

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
    return any_rows


def render_markdown(submissions: list[Submission], reference: list[Submission] | None = None) -> str:
    """Render the published board as Markdown for LEADERBOARD.md."""
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

    if not _render_category_tables(lines, submissions):
        lines.append("_No results published yet._")
        lines.append("")

    if reference:
        lines.append("# Reference — not gate-verified")
        lines.append("")
        lines.append(
            "> ⚠️ These runs are **not reproducible** and are **not enforced by CI** — "
            "the tools are non-deterministic (auto-config that learns/samples, or "
            "active-learning matchers), so they produce different numbers across runs. "
            "Shown for reference only; see each entry's notes for the observed range."
        )
        lines.append("")
        _render_category_tables(lines, reference)

    return "\n".join(lines).rstrip() + "\n"


def publish(root: Path) -> Path:
    """Regenerate LEADERBOARD.md from the gated + reference stores. Returns the written path."""
    md = render_markdown(load_store(root), load_reference(root))
    path = root / LEADERBOARD_MD
    path.write_text(md)
    return path


def check_published(root: Path) -> list[str]:
    """CI helper: validate the store and confirm LEADERBOARD.md is current."""
    errors = validate_store(root)
    if errors:
        return errors

    expected = render_markdown(load_store(root), load_reference(root))
    path = root / LEADERBOARD_MD
    current = path.read_text() if path.exists() else ""
    if current != expected:
        errors.append(
            f"{LEADERBOARD_MD} is out of date. Run `dqbench publish` and commit the result."
        )
    return errors
