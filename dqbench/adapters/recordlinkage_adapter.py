"""recordlinkage adapter for DQBench ER benchmarks.

Deterministic, rule-based entity resolution: multi-pass blocking (exact last
name, exact email, sorted-neighbourhood on last name) + Jaro-Winkler field
comparison, thresholded on the summed similarity. No training, so runs reproduce.
"""
from __future__ import annotations

from pathlib import Path

from dqbench.adapters.base import EntityResolutionAdapter

# Fields compared when present, with per-field match thresholds.
_COMPARE_FIELDS = [
    ("first_name", 0.85),
    ("last_name", 0.85),
    ("email", 0.90),
    ("phone", 0.85),
    ("address", 0.80),
    ("city", 0.90),
]
_MATCH_THRESHOLD = 4.0  # summed binary similarity indicators required to call a match


class RecordLinkageAdapter(EntityResolutionAdapter):
    @property
    def name(self) -> str:
        return "recordlinkage"

    @property
    def version(self) -> str:
        try:
            import recordlinkage
            return recordlinkage.__version__
        except ImportError:
            return "not-installed"

    def deduplicate(self, csv_path: Path) -> list[tuple[int, int]]:
        import pandas as pd
        import recordlinkage as rl

        df = pd.read_csv(csv_path, dtype=str).fillna("")
        cols = set(df.columns)

        # Normalised blocking keys.
        if "last_name" in cols:
            df = df.assign(_ln=df["last_name"].str.lower().str.strip())
        if "email" in cols:
            df = df.assign(_em=df["email"].str.lower().str.strip())

        indexer = rl.Index()
        if "_ln" in df.columns:
            indexer.block("_ln")
            indexer.sortedneighbourhood("_ln", window=3)
        if "_em" in df.columns:
            indexer.block("_em")
        if not df.columns.intersection(["_ln", "_em"]).any():
            indexer.full()
        candidates = indexer.index(df)
        candidates = candidates[~candidates.duplicated()]

        compare = rl.Compare()
        used = []
        for field, threshold in _COMPARE_FIELDS:
            if field in cols:
                compare.string(field, field, method="jarowinkler", threshold=threshold, label=field)
                used.append(field)
        if not used:
            return []

        features = compare.compute(candidates, df)
        score = features.sum(axis=1)
        matched = score[score >= _MATCH_THRESHOLD].index
        return [(int(a), int(b)) for a, b in matched]
