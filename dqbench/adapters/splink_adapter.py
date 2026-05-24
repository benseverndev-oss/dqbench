"""Splink adapter for DQBench ER benchmarks.

Splink's probabilistic (Fellegi-Sunter) model: multi-pass blocking, Jaro-Winkler
/ exact comparisons, u-probabilities estimated by *seeded* random sampling and
m-probabilities by EM, then pairs above a fixed match-probability threshold.
The seed makes u-estimation reproducible; EM and prediction are deterministic.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dqbench.adapters.base import EntityResolutionAdapter

_MATCH_PROBABILITY = 0.99


class SplinkAdapter(EntityResolutionAdapter):
    @property
    def name(self) -> str:
        return "Splink"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("splink")
        except Exception:
            return "unknown"

    def deduplicate(self, csv_path: Path) -> list[tuple[int, int]]:
        import contextlib
        import os

        import pandas as pd
        from splink import DuckDBAPI, Linker, SettingsCreator, block_on
        from splink import comparison_library as cl

        for noisy in ("splink", "duckdb"):
            logging.getLogger(noisy).setLevel(logging.ERROR)

        df = pd.read_csv(csv_path, dtype=str).fillna("")
        df["unique_id"] = range(len(df))
        cols = set(df.columns)

        comparisons = []
        for field in ("first_name", "last_name", "email", "address"):
            if field in cols:
                comparisons.append(cl.JaroWinklerAtThresholds(field, [0.9, 0.7]))
        if "phone" in cols:
            comparisons.append(cl.ExactMatch("phone"))
        if not comparisons:
            return []

        blocking = [block_on(c) for c in ("last_name", "email", "phone") if c in cols]
        if not blocking:
            return []

        settings = SettingsCreator(
            link_type="dedupe_only",
            blocking_rules_to_generate_predictions=blocking,
            comparisons=comparisons,
        )

        # Splink is chatty on stdout; keep the benchmark output clean.
        with open(os.devnull, "w") as dn, contextlib.redirect_stdout(dn):
            linker = Linker(df, settings, DuckDBAPI())
            linker.training.estimate_u_using_random_sampling(max_pairs=1_000_000, seed=42)
            # EM training fails on columns with no matching pairs (e.g. all-unique
            # values in the mistyped T4 tier); skip those rules.
            trained = 0
            for rule in blocking[:2]:
                try:
                    linker.training.estimate_parameters_using_expectation_maximisation(rule)
                    trained += 1
                except Exception:
                    continue
            if trained == 0:
                return []
            predictions = linker.inference.predict(threshold_match_probability=0.5)
            pdf = predictions.as_pandas_dataframe()

        matched = pdf[pdf["match_probability"] >= _MATCH_PROBABILITY]
        return [(int(a), int(b)) for a, b in zip(matched["unique_id_l"], matched["unique_id_r"])]
