"""frictionless adapter for DQBench Detect benchmarks.

Validates the CSV against frictionless's inferred Table Schema and turns schema
violations (type errors, missing cells, constraint errors) into DQBenchFindings,
grouped by (column, error type). Deterministic.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding

logger = logging.getLogger(__name__)

_TYPE_TO_CHECK = {
    "type-error": "wrong_dtype",
    "constraint-error": "out_of_range",
    "missing-cell": "null_values",
    "missing-label": "null_values",
    "unique-error": "duplicate_values",
    "primary-key": "duplicate_values",
    "enumerable-constraint": "enum_violation",
    "maximum-constraint": "out_of_range",
    "minimum-constraint": "out_of_range",
    "pattern-constraint": "invalid_format",
}


class FrictionlessAdapter(DQBenchAdapter):
    @property
    def name(self) -> str:
        return "frictionless (schema-inferred)"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("frictionless")
        except Exception:
            return "unknown"

    def validate(self, csv_path: Path) -> list[DQBenchFinding]:
        from frictionless import Resource, validate

        try:
            # frictionless treats absolute paths as unsafe; use name + basepath.
            resource = Resource(path=csv_path.name, basepath=str(csv_path.parent))
            report = validate(resource)
        except Exception as e:
            logger.warning("frictionless validate failed for %s: %s", csv_path, e)
            return []

        data = report.to_dict()
        tasks = data.get("tasks", [])
        if not tasks:
            return []

        seen: set[tuple[str, str]] = set()
        findings: list[DQBenchFinding] = []
        for err in tasks[0].get("errors", []):
            column = err.get("fieldName") or ""
            if not column:
                continue
            err_type = str(err.get("type", ""))
            key = (column, err_type)
            if key in seen:
                continue
            seen.add(key)
            findings.append(DQBenchFinding(
                column=column,
                severity="WARNING",
                check=_TYPE_TO_CHECK.get(err_type, err_type),
                message=f"frictionless {err_type} on '{column}'",
            ))
        return findings
