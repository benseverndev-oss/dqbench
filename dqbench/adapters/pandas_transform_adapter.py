"""A pandas cleaning baseline for the DQBench Transform benchmark.

Not a data-quality product — a reference baseline that applies common-sense
normalisations (whitespace, zero-width/smart-quote stripping, phone -> E.164,
date -> ISO, zip normalisation) with pandas. Deterministic.
"""
from __future__ import annotations

import re
from pathlib import Path

import polars as pl

from dqbench.adapters.base import TransformAdapter

_ZERO_WIDTH = ["​", "‌", "‍", "﻿", "⁠"]
_SMART = {"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-"}
_PHONE_COLS = {"phone", "phone_number", "patient_phone"}
_DATE_COLS_SUFFIX = ("_date", "_login")
_MMDDYYYY = re.compile(r"^(\d{2})[-/](\d{2})[-/](\d{4})$")


def _clean_text(v: str) -> str:
    for z in _ZERO_WIDTH:
        v = v.replace(z, "")
    for a, b in _SMART.items():
        v = v.replace(a, b)
    return v.strip()


def _to_e164(v: str) -> str:
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"+1{digits}" if len(digits) == 10 else v


def _to_iso_date(v: str) -> str:
    m = _MMDDYYYY.match(v)
    if m:
        mm, dd, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"
    return v


class PandasTransformAdapter(TransformAdapter):
    @property
    def name(self) -> str:
        return "pandas (cleaning baseline)"

    @property
    def version(self) -> str:
        try:
            import importlib.metadata
            return importlib.metadata.version("pandas")
        except Exception:
            return "unknown"

    def transform(self, csv_path: Path) -> pl.DataFrame:
        import pandas as pd

        df = pd.read_csv(csv_path, dtype=str).fillna("")
        for col in df.columns:
            s = df[col].map(_clean_text)
            if col in _PHONE_COLS:
                s = s.map(_to_e164)
            elif col == "billing_zip":
                s = s.map(lambda v: v.zfill(5) if v.isdigit() else v)
            elif col == "zip_code":
                s = s.map(lambda v: v.split("-")[0])
            elif col.endswith(_DATE_COLS_SUFFIX):
                s = s.map(_to_iso_date)
            df[col] = s
        return pl.DataFrame({c: df[c].tolist() for c in df.columns})
