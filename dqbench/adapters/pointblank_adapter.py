"""Pointblank adapter for DQBench Detect benchmarks (best-effort).

Builds a Pointblank `Validate` plan with rules keyed on common column names
(not-null, distinct, in-set, between, regex), interrogates the frame, and turns
each failing step into a DQBenchFinding. Interrogation is deterministic.

Pointblank aborts the whole interrogation if a numeric check lands on a string
column (or vice versa), so rules are gated on the column's dtype before they're
added — mirroring the cuallee adapter's dtype guards.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding

logger = logging.getLogger(__name__)

_ASSERTION_TO_CHECK = {
    "col_vals_not_null": "null_values",
    "rows_distinct": "duplicate_values",
    "col_vals_in_set": "enum_violation",
    "col_vals_between": "out_of_range",
    "col_vals_regex": "invalid_format",
}

_ID_COLS = ["customer_id", "order_id", "patient_id", "record_number", "npi_number", "session_id", "sku"]
_REQUIRED_COLS = [
    "first_name", "last_name", "customer_name", "patient_name",
    "order_date", "service_date", "signup_date",
    "primary_dx", "insurance_id", "procedure_code", "product_category", "country",
]
_EMAIL_COLS = ["email", "customer_email", "patient_email"]
_PHONE_COLS = ["phone", "phone_number", "phone_intl", "patient_phone"]
_ZIP_COLS = ["zip_code", "billing_zip", "shipping_zip", "patient_zip"]
_ENUMS = {
    "status": ["active", "inactive", "pending", "suspended", "closed"],
    "account_type": ["standard", "premium", "enterprise", "basic", "trial", "free"],
    "currency_code": ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY"],
    "gender": ["M", "F", "Male", "Female", "male", "female", "Other", "other", "U", "Unknown"],
}
_RANGES = {
    "age": (0, 120), "patient_age": (0, 120), "income": (0, 10_000_000),
    "order_count": (0, 100_000), "quantity": (0, 100_000), "rating": (1, 5),
    "discount_pct": (0, 100), "order_total": (0, 1_000_000), "claim_amount": (0, 10_000_000),
    "payment_amount": (0, 10_000_000), "copay_amount": (0, 10_000), "dosage_amount": (0, 10_000),
}
_EMAIL_RE = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
_PHONE_RE = r"^[\d\s\+\-\.\(\)]{7,20}$"
_ZIP_RE = r"^\d{5}(-\d{4})?$"


def _step_column(step) -> str:
    col = step.column
    if isinstance(col, (list, tuple)):
        return col[0] if len(col) == 1 else ",".join(str(c) for c in col)
    return str(col) if col is not None else ""


class PointblankBestEffortAdapter(DQBenchAdapter):
    @property
    def name(self) -> str:
        return "Pointblank (best-effort)"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("pointblank")
        except Exception:
            return "unknown"

    def validate(self, csv_path: Path) -> list[DQBenchFinding]:
        import pointblank as pb
        import polars as pl

        try:
            df = pl.read_csv(csv_path, infer_schema_length=20000)
        except Exception as e:
            logger.warning("pointblank adapter could not read %s: %s", csv_path, e)
            return []

        cols = set(df.columns)
        numeric = {c for c, dt in zip(df.columns, df.dtypes) if dt.is_numeric()}
        strings = {c for c, dt in zip(df.columns, df.dtypes) if dt == pl.Utf8}

        v = pb.Validate(data=df)
        for c in _ID_COLS:
            if c in cols:
                v = v.col_vals_not_null(columns=c).rows_distinct(columns_subset=[c])
        for c in _REQUIRED_COLS:
            if c in cols:
                v = v.col_vals_not_null(columns=c)
        for c, vals in _ENUMS.items():
            if c in strings:
                v = v.col_vals_in_set(columns=c, set=vals)
        for c, (lo, hi) in _RANGES.items():
            if c in numeric:
                v = v.col_vals_between(columns=c, left=lo, right=hi, na_pass=True)
        for c in _EMAIL_COLS:
            if c in strings:
                v = v.col_vals_regex(columns=c, pattern=_EMAIL_RE, na_pass=True)
        for c in _PHONE_COLS:
            if c in strings:
                v = v.col_vals_regex(columns=c, pattern=_PHONE_RE, na_pass=True)
        for c in _ZIP_COLS:
            if c in strings:
                v = v.col_vals_regex(columns=c, pattern=_ZIP_RE, na_pass=True)

        try:
            v = v.interrogate()
        except Exception as e:
            logger.warning("pointblank interrogate failed: %s", e)
            return []

        findings: list[DQBenchFinding] = []
        for step in v.validation_info:
            if step.eval_error or not (step.n_failed or 0):
                continue
            column = _step_column(step)
            check = _ASSERTION_TO_CHECK.get(step.assertion_type, step.assertion_type)
            findings.append(DQBenchFinding(
                column=column,
                severity="WARNING",
                check=check,
                message=f"pointblank {step.assertion_type} failed on '{column}' ({step.n_failed} rows)",
            ))
        return findings
