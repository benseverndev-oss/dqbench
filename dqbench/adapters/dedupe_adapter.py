"""dedupe (dedupe.io) adapter for DQBench ER benchmarks.

`dedupe` is an active-learning matcher: it needs labelled example pairs and
learns field weights + blocking predicates from them. There is no ground-truth
labelling here, so the adapter uses deterministic *weak supervision* — pairs
that share a normalised email (or phone) are treated as "match" examples, random
non-sharing pairs as "distinct". Even with seeded RNGs, dedupe's training/
blocking is not reproducible run-to-run, so this adapter targets the **ungated
reference board only**, never the gated leaderboard.
"""
from __future__ import annotations

import logging
import random
import re
from collections import defaultdict
from pathlib import Path

from dqbench.adapters.base import EntityResolutionAdapter

logger = logging.getLogger(__name__)

_FIELDS = ["first_name", "last_name", "email", "phone", "address", "city"]


def _norm_email(rec: dict) -> str | None:
    return ((rec.get("email") or "").lower().strip()) or None


def _norm_phone(rec: dict) -> str | None:
    return re.sub(r"\D", "", rec.get("phone") or "") or None


class DedupeAdapter(EntityResolutionAdapter):
    @property
    def name(self) -> str:
        return "dedupe"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("dedupe")
        except Exception:
            return "unknown"

    def deduplicate(self, csv_path: Path) -> list[tuple[int, int]]:
        import json
        import tempfile

        import dedupe
        import numpy as np
        import polars as pl
        from dedupe.serializer import TupleEncoder

        random.seed(0)
        np.random.seed(0)
        logging.getLogger("dedupe").setLevel(logging.WARNING)

        df = pl.read_csv(csv_path, infer_schema_length=0)
        fields = [f for f in _FIELDS if f in df.columns]
        if not fields:
            return []
        rows = df.to_dicts()
        data = {
            i: {f: ((str(rows[i].get(f) or "").strip()) or None) for f in fields}
            for i in range(len(rows))
        }

        # Weak-supervision labels: shared email/phone -> match, random -> distinct.
        matches = self._match_examples(data)
        if not matches:
            logger.warning("dedupe adapter: no weak-supervision matches found; skipping")
            return []
        distinct = self._distinct_examples(data)

        # mark_pairs requires records the active learner sampled; a training file
        # loads the labels directly, which is the supported way to inject our own.
        deduper = dedupe.Dedupe([dedupe.variables.String(f) for f in fields])
        with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tf:
            json.dump({"match": matches, "distinct": distinct}, tf, cls=TupleEncoder)
            training_path = tf.name
        with open(training_path) as tf:
            deduper.prepare_training(data, training_file=tf)
        deduper.train()
        clusters = deduper.partition(data, 0.5)

        pairs: list[tuple[int, int]] = []
        for record_ids, _scores in clusters:
            members = sorted(int(r) for r in record_ids)
            for a in range(len(members)):
                for b in range(a + 1, len(members)):
                    pairs.append((members[a], members[b]))
        return pairs

    @staticmethod
    def _match_examples(data: dict) -> list[tuple[dict, dict]]:
        examples: list[tuple[dict, dict]] = []
        for key_fn in (_norm_email, _norm_phone):
            groups: dict[str, list[int]] = defaultdict(list)
            for i, rec in data.items():
                k = key_fn(rec)
                if k:
                    groups[k].append(i)
            for ids in groups.values():
                if len(ids) > 1:
                    examples.append((data[ids[0]], data[ids[1]]))
                if len(examples) >= 20:
                    return examples
            if examples:
                break
        return examples

    @staticmethod
    def _distinct_examples(data: dict) -> list[tuple[dict, dict]]:
        ids = list(data)
        out: list[tuple[dict, dict]] = []
        tries = 0
        while len(out) < 40 and tries < 4000:
            tries += 1
            a, b = random.sample(ids, 2)
            ea, eb = _norm_email(data[a]), _norm_email(data[b])
            if ea and ea == eb:
                continue
            pa, pb = _norm_phone(data[a]), _norm_phone(data[b])
            if pa and pa == pb:
                continue
            out.append((data[a], data[b]))
        return out
