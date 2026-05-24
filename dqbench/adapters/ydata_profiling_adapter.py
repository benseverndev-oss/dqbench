"""ydata-profiling adapter for DQBench Detect benchmarks (auto-profiled).

ydata-profiling is a profiler, not a validator: it surfaces statistical
"alerts" (missing values, skew, zeros, high cardinality, ...) rather than rule
violations. Only the MISSING alert maps to a planted DQBench issue type
(nullability); the rest are emitted as INFO so they contribute column-level
recall without being penalised as false positives. Profiling runs in `minimal`
mode with sampling/correlations/duplicates/interactions disabled, which is
deterministic.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding

logger = logging.getLogger(__name__)


class YDataProfilingAdapter(DQBenchAdapter):
    @property
    def name(self) -> str:
        return "ydata-profiling (auto-profiled)"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("ydata-profiling")
        except Exception:
            return "unknown"

    def validate(self, csv_path: Path) -> list[DQBenchFinding]:
        import pandas as pd
        from ydata_profiling import ProfileReport

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.warning("ydata-profiling adapter could not read %s: %s", csv_path, e)
            return []

        try:
            report = ProfileReport(
                df, minimal=True, progress_bar=False,
                samples=None, correlations=None, duplicates=None, interactions=None,
            )
            alerts = report.get_description().alerts
        except Exception as e:
            logger.warning("ydata-profiling failed on %s: %s", csv_path, e)
            return []

        findings: list[DQBenchFinding] = []
        for alert in alerts:
            column = getattr(alert, "column_name", None)
            if not column:
                continue  # table-level alert, no column to attribute
            atype = alert.alert_type.name
            if atype == "MISSING":
                findings.append(DQBenchFinding(
                    column=column, severity="WARNING", check="null_values",
                    message=f"ydata-profiling: missing values in '{column}'",
                ))
            else:
                findings.append(DQBenchFinding(
                    column=column, severity="INFO", check=f"profile_{atype.lower()}",
                    message=f"ydata-profiling alert {atype} on '{column}'",
                ))
        return findings
