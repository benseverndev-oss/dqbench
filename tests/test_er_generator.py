"""Tests for ER tier generators."""
from __future__ import annotations
import polars as pl

from dqbench.generator.er_tier1 import generate_er_tier1
from dqbench.generator.er_tier2 import generate_er_tier2
from dqbench.generator.er_tier3 import generate_er_tier3
from dqbench.generator.er_tier4 import generate_er_tier4
from dqbench.er_ground_truth import ERGroundTruth


class TestERTier1:
    def test_returns_dataframe_and_ground_truth(self):
        df, gt = generate_er_tier1()
        assert isinstance(df, pl.DataFrame)
        assert isinstance(gt, ERGroundTruth)

    def test_row_count(self):
        df, gt = generate_er_tier1()
        assert df.shape[0] == 1000
        assert gt.rows == 1000

    def test_expected_columns(self):
        df, _ = generate_er_tier1()
        expected = {"first_name", "last_name", "email", "phone",
                    "address", "city", "state", "zip", "company"}
        assert set(df.columns) == expected

    def test_duplicate_pair_count(self):
        _, gt = generate_er_tier1()
        assert gt.total_duplicates == 100
        assert len(gt.duplicate_pairs) == 100

    def test_duplicate_pair_breakdown(self):
        """50 case-change, 30 typo, 20 name-swap = 100 total."""
        _, gt = generate_er_tier1()
        assert len(gt.duplicate_pairs) == 100

    def test_pairs_reference_valid_rows(self):
        df, gt = generate_er_tier1()
        n = df.shape[0]
        for a, b in gt.duplicate_pairs:
            assert 0 <= a < n, f"Invalid row index {a}"
            assert 0 <= b < n, f"Invalid row index {b}"
            assert a != b, f"Self-pair ({a}, {a})"

    def test_determinism(self):
        """Two calls produce identical output."""
        df1, gt1 = generate_er_tier1()
        df2, gt2 = generate_er_tier1()
        assert df1.equals(df2)
        assert gt1.duplicate_pairs == gt2.duplicate_pairs

    def test_ground_truth_metadata(self):
        _, gt = generate_er_tier1()
        assert gt.tier == 1
        assert gt.difficulty == "easy"
        assert gt.version == "1.0.0"


class TestERTier2:
    def test_returns_dataframe_and_ground_truth(self):
        df, gt = generate_er_tier2()
        assert isinstance(df, pl.DataFrame)
        assert isinstance(gt, ERGroundTruth)

    def test_row_count(self):
        df, gt = generate_er_tier2()
        assert df.shape[0] == 5000
        assert gt.rows == 5000

    def test_expected_columns(self):
        df, _ = generate_er_tier2()
        expected = {"first_name", "last_name", "email", "phone",
                    "address", "city", "state", "zip", "company"}
        assert set(df.columns) == expected

    def test_duplicate_pair_count(self):
        _, gt = generate_er_tier2()
        assert gt.total_duplicates == 750
        assert len(gt.duplicate_pairs) == 750

    def test_pairs_reference_valid_rows(self):
        df, gt = generate_er_tier2()
        n = df.shape[0]
        for a, b in gt.duplicate_pairs:
            assert 0 <= a < n, f"Invalid row index {a}"
            assert 0 <= b < n, f"Invalid row index {b}"
            assert a != b, f"Self-pair ({a}, {a})"

    def test_determinism(self):
        df1, gt1 = generate_er_tier2()
        df2, gt2 = generate_er_tier2()
        assert df1.equals(df2)
        assert gt1.duplicate_pairs == gt2.duplicate_pairs

    def test_ground_truth_metadata(self):
        _, gt = generate_er_tier2()
        assert gt.tier == 2
        assert gt.difficulty == "fuzzy"


class TestERTier3:
    def test_returns_dataframe_and_ground_truth(self):
        df, gt = generate_er_tier3()
        assert isinstance(df, pl.DataFrame)
        assert isinstance(gt, ERGroundTruth)

    def test_row_count(self):
        df, gt = generate_er_tier3()
        assert df.shape[0] == 10000
        assert gt.rows == 10000

    def test_expected_columns(self):
        df, _ = generate_er_tier3()
        expected = {"first_name", "last_name", "email", "phone",
                    "address", "city", "state", "zip", "company"}
        assert set(df.columns) == expected

    def test_duplicate_pair_count(self):
        _, gt = generate_er_tier3()
        assert gt.total_duplicates == 2000
        assert len(gt.duplicate_pairs) == 2000

    def test_pairs_reference_valid_rows(self):
        df, gt = generate_er_tier3()
        n = df.shape[0]
        for a, b in gt.duplicate_pairs:
            assert 0 <= a < n, f"Invalid row index {a}"
            assert 0 <= b < n, f"Invalid row index {b}"
            assert a != b, f"Self-pair ({a}, {a})"

    def test_determinism(self):
        df1, gt1 = generate_er_tier3()
        df2, gt2 = generate_er_tier3()
        assert df1.equals(df2)
        assert gt1.duplicate_pairs == gt2.duplicate_pairs

    def test_ground_truth_metadata(self):
        _, gt = generate_er_tier3()
        assert gt.tier == 3
        assert gt.difficulty == "adversarial"


class TestERTier4:
    def test_returns_dataframe_and_ground_truth(self):
        df, gt = generate_er_tier4()
        assert isinstance(df, pl.DataFrame)
        assert isinstance(gt, ERGroundTruth)

    def test_row_count(self):
        df, gt = generate_er_tier4()
        assert df.shape[0] == 800
        assert gt.rows == 800

    def test_expected_columns(self):
        df, _ = generate_er_tier4()
        expected = {"first_name", "last_name", "email", "phone",
                    "address", "city", "state", "zip", "company", "industry"}
        assert set(df.columns) == expected

    def test_duplicate_pair_count(self):
        _, gt = generate_er_tier4()
        assert gt.total_duplicates == 80
        assert len(gt.duplicate_pairs) == 80

    def test_pairs_reference_valid_rows(self):
        df, gt = generate_er_tier4()
        n = df.shape[0]
        for a, b in gt.duplicate_pairs:
            assert 0 <= a < n, f"Invalid row index {a}"
            assert 0 <= b < n, f"Invalid row index {b}"
            assert a != b, f"Self-pair ({a}, {a})"

    def test_determinism(self):
        df1, gt1 = generate_er_tier4()
        df2, gt2 = generate_er_tier4()
        assert df1.equals(df2)
        assert gt1.duplicate_pairs == gt2.duplicate_pairs

    def test_ground_truth_metadata(self):
        _, gt = generate_er_tier4()
        assert gt.tier == 4
        assert gt.difficulty == "mistyped"
        assert gt.version == "1.0.0"

    def test_first_name_column_is_hex(self):
        """Mistyped: first_name holds 12-char hex tokens, not names."""
        import re
        df, _ = generate_er_tier4()
        hex_re = re.compile(r"^[0-9a-f]{12}$")
        for val in df["first_name"].to_list():
            assert hex_re.match(val), f"first_name {val!r} is not a 12-char hex token"

    def test_last_name_column_is_numeric_id(self):
        """Mistyped: last_name holds 6-8 digit numeric IDs."""
        df, _ = generate_er_tier4()
        for val in df["last_name"].to_list():
            assert val.isdigit(), f"last_name {val!r} is not all digits"
            assert 6 <= len(val) <= 8, f"last_name {val!r} length out of range"

    def test_industry_column_holds_person_names(self):
        """Mistyped: industry holds person-style names (two whitespace-separated tokens)."""
        df, _ = generate_er_tier4()
        for val in df["industry"].to_list():
            parts = val.split()
            assert len(parts) == 2, f"industry {val!r} is not a two-token name"
            assert all(p[0].isupper() for p in parts), f"industry {val!r} not title-cased"

    def test_address_column_is_free_form_note(self):
        """Mistyped: address holds free-form notes, not street addresses."""
        from dqbench.generator.er_tier4 import FREE_FORM_NOTES
        df, _ = generate_er_tier4()
        note_set = set(FREE_FORM_NOTES)
        for val in df["address"].to_list():
            assert val in note_set, f"address {val!r} is not a known free-form note"

    def test_email_signal_is_intact(self):
        """Email column must still look like an email — that's where the dupe signal lives."""
        df, _ = generate_er_tier4()
        for val in df["email"].to_list():
            assert "@" in val and "." in val, f"email {val!r} is not email-shaped"
