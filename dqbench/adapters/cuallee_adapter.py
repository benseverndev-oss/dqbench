"""cuallee adapter for DQBench Detect benchmarks (best-effort).

Builds a cuallee Check with hand-written rules keyed on common column names
(null, unique, enum, range, format), validates the dataframe, and turns each
failing rule into a DQBenchFinding. Rule evaluation is deterministic.
"""
from __future__ import annotations

import logging
from pathlib import Path

from dqbench.adapters.base import DQBenchAdapter
from dqbench.models import DQBenchFinding

logger = logging.getLogger(__name__)

_RULE_TO_CHECK = {
    "is_complete": "null_values",
    "is_unique": "duplicate_values",
    "is_contained_in": "enum_violation",
    "is_between": "out_of_range",
    "has_pattern": "invalid_format",
}

_ID_COLS = ["customer_id", "order_id", "patient_id", "record_number", "npi_number", "session_id", "sku"]
_EMAIL_COLS = ["email", "customer_email", "patient_email"]
_PHONE_COLS = ["phone", "phone_number", "phone_intl", "patient_phone"]
_ZIP_COLS = ["zip_code", "billing_zip", "shipping_zip", "patient_zip"]
_REQUIRED_COLS = [
    "first_name", "last_name", "customer_name", "patient_name",
    "order_date", "service_date", "signup_date",
    "primary_dx", "insurance_id", "procedure_code", "product_category", "country",
]
_ENUMS = {
    "status": ["active", "inactive", "pending", "suspended", "closed"],
    "account_type": ["standard", "premium", "enterprise", "basic", "trial", "free"],
    "gender": ["M", "F", "Male", "Female", "male", "female", "Other", "other", "U", "Unknown"],
    "currency_code": ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY"],
    "claim_status": ["pending", "approved", "denied", "paid", "submitted", "appealed",
                     "PENDING", "APPROVED", "DENIED", "PAID", "SUBMITTED"],
    "prior_auth_flag": ["Y", "N", "Yes", "No", "yes", "no", "true", "false", "1", "0"],
    "deductible_met": ["Y", "N", "Yes", "No", "yes", "no", "true", "false", "1", "0"],
}
_RANGES = {
    "age": (0, 120), "patient_age": (0, 120), "income": (0, 10_000_000),
    "order_count": (0, 100_000), "quantity": (0, 100_000), "rating": (1, 5),
    "discount_pct": (0, 100), "order_total": (0, 1_000_000), "claim_amount": (0, 10_000_000),
    "payment_amount": (0, 10_000_000), "copay_amount": (0, 10_000), "dosage_amount": (0, 10_000),
    "remittance_amount": (0, 10_000_000), "policy_max_amount": (0, 10_000_000), "lab_result": (0, 100_000),
}
_EMAIL_RE = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
_PHONE_RE = r"^[\d\s\+\-\.\(\)]{7,20}$"
_ZIP_RE = r"^\d{5}(-\d{4})?$"


class CualleeAdapter(DQBenchAdapter):
    @property
    def name(self) -> str:
        return "cuallee (best-effort)"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("cuallee")
        except Exception:
            return "unknown"

    def validate(self, csv_path: Path) -> list[DQBenchFinding]:
        import pandas as pd
        from cuallee import Check, CheckLevel

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            logger.warning("cuallee adapter could not read %s: %s", csv_path, e)
            return []
        cols = set(df.columns)
        check = Check(CheckLevel.WARNING, "dqbench")

        for c in _ID_COLS:
            if c in cols:
                check.is_complete(c)
                check.is_unique(c)
        for c in _REQUIRED_COLS:
            if c in cols:
                check.is_complete(c)
        for c, values in _ENUMS.items():
            if c in cols:
                check.is_contained_in(c, values)
        for c, (lo, hi) in _RANGES.items():
            if c in cols and pd.api.types.is_numeric_dtype(df[c]):
                check.is_between(c, (lo, hi))
        # has_pattern requires string columns — cuallee aborts the whole validate
        # if a pattern column is numeric, so only apply it to object-dtype columns.
        def _is_str(col: str) -> bool:
            return col in cols and df[col].dtype == object

        for c in _EMAIL_COLS:
            if _is_str(c):
                check.has_pattern(c, _EMAIL_RE)
        for c in _PHONE_COLS:
            if _is_str(c):
                check.has_pattern(c, _PHONE_RE)
        for c in _ZIP_COLS:
            if _is_str(c):
                check.has_pattern(c, _ZIP_RE)

        if not check.rules:
            return []

        try:
            result = check.validate(df)
        except Exception as e:
            logger.warning("cuallee validate failed: %s", e)
            return []

        findings: list[DQBenchFinding] = []
        for row in result.to_dict("records"):
            if str(row.get("status", "")).upper() != "FAIL":
                continue
            rule = str(row.get("rule", ""))
            column = str(row.get("column", ""))
            check_name = _RULE_TO_CHECK.get(rule, rule)
            findings.append(DQBenchFinding(
                column=column,
                severity="WARNING",
                check=check_name,
                message=f"cuallee rule '{rule}' failed on '{column}' ({row.get('violations')} violations)",
            ))
        return findings
