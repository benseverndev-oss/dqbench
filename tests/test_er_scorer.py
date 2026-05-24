"""Tests for ER scorer."""
from __future__ import annotations
import pytest

from dqbench.er_scorer import score_er_tier
from dqbench.er_ground_truth import ERGroundTruth
from dqbench.models import ERTierResult


@pytest.fixture
def ground_truth() -> ERGroundTruth:
    return ERGroundTruth(
        tier=1,
        version="1.0.0",
        rows=100,
        duplicate_pairs=[(0, 50), (1, 51), (2, 52), (3, 53), (4, 54)],
        total_duplicates=5,
        difficulty="easy",
    )


class TestScoreERTier:
    def test_perfect_predictions(self, ground_truth):
        """All true pairs predicted, no false positives."""
        predictions = [(0, 50), (1, 51), (2, 52), (3, 53), (4, 54)]
        result = score_er_tier(predictions, ground_truth, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        assert isinstance(result, ERTierResult)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.false_positives == 0
        assert result.false_negatives == 0

    def test_symmetric_matching(self, ground_truth):
        """(a, b) should match (b, a)."""
        predictions = [(50, 0), (51, 1), (52, 2), (53, 3), (54, 4)]
        result = score_er_tier(predictions, ground_truth, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0

    def test_partial_predictions(self, ground_truth):
        """Only 3 of 5 true pairs predicted."""
        predictions = [(0, 50), (1, 51), (2, 52)]
        result = score_er_tier(predictions, ground_truth, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        assert result.precision == 1.0
        assert result.recall == pytest.approx(0.6)
        assert result.false_positives == 0
        assert result.false_negatives == 2

    def test_with_false_positives(self, ground_truth):
        """All true pairs plus 2 false positives."""
        predictions = [(0, 50), (1, 51), (2, 52), (3, 53), (4, 54),
                        (10, 60), (20, 70)]
        result = score_er_tier(predictions, ground_truth, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        assert result.recall == 1.0
        assert result.precision == pytest.approx(5 / 7)
        assert result.false_positives == 2
        assert result.false_negatives == 0

    def test_empty_predictions(self, ground_truth):
        """No predictions at all."""
        result = score_er_tier([], ground_truth, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.false_negatives == 5

    def test_no_true_pairs(self):
        """Ground truth has no pairs, predictions are all false positives."""
        gt = ERGroundTruth(
            tier=1, version="1.0.0", rows=100,
            duplicate_pairs=[], total_duplicates=0, difficulty="easy",
        )
        predictions = [(0, 1), (2, 3)]
        result = score_er_tier(predictions, gt, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        assert result.precision == 0.0
        assert result.recall == 0.0  # no true pairs => recall defined as 0
        assert result.false_positives == 2

    def test_f1_harmonic_mean(self, ground_truth):
        """F1 should be harmonic mean of precision and recall."""
        predictions = [(0, 50), (1, 51), (10, 60)]  # 2 correct, 1 FP
        result = score_er_tier(predictions, ground_truth, tier=1,
                               time_seconds=1.0, memory_mb=10.0)
        p = 2 / 3
        r = 2 / 5
        expected_f1 = 2 * p * r / (p + r)
        assert result.f1 == pytest.approx(expected_f1)


class TestConfusionMatrix:
    def test_confusion_counts_sum_to_total_pairs(self, ground_truth):
        predictions = [(0, 50), (1, 51), (2, 52), (3, 53), (4, 54), (10, 60), (20, 70)]
        result = score_er_tier(predictions, ground_truth, tier=1,
                               time_seconds=0.0, memory_mb=0.0)
        n = ground_truth.rows
        total = n * (n - 1) // 2
        assert result.true_positives == 5
        assert result.false_positives == 2
        assert result.false_negatives == 0
        assert result.true_negatives == total - 5 - 2 - 0
        assert (result.true_positives + result.false_positives
                + result.false_negatives + result.true_negatives) == total

    def test_perfect_has_no_off_diagonal(self, ground_truth):
        preds = [(0, 50), (1, 51), (2, 52), (3, 53), (4, 54)]
        result = score_er_tier(preds, ground_truth, tier=1, time_seconds=0.0, memory_mb=0.0)
        assert result.false_positives == 0 and result.false_negatives == 0
        assert result.true_positives == 5


class TestBCubed:
    def test_perfect_clustering_is_one(self, ground_truth):
        preds = [(0, 50), (1, 51), (2, 52), (3, 53), (4, 54)]
        result = score_er_tier(preds, ground_truth, tier=1, time_seconds=0.0, memory_mb=0.0)
        assert result.bcubed_precision == pytest.approx(1.0)
        assert result.bcubed_recall == pytest.approx(1.0)
        assert result.bcubed_f1 == pytest.approx(1.0)

    def test_empty_predictions_recall_below_one(self, ground_truth):
        # No links: every singleton predicted. Precision is perfect (each predicted
        # cluster of size 1 is "pure"), but recall misses the true 2-member clusters.
        result = score_er_tier([], ground_truth, tier=1, time_seconds=0.0, memory_mb=0.0)
        assert result.bcubed_precision == pytest.approx(1.0)
        assert result.bcubed_recall < 1.0
        assert result.bcubed_f1 < 1.0

    def test_over_merging_drops_precision(self):
        # One giant predicted cluster {0,1,2,3} but truth has two separate pairs.
        gt = ERGroundTruth(tier=1, version="1.0.0", rows=4,
                           duplicate_pairs=[(0, 1), (2, 3)], total_duplicates=2, difficulty="easy")
        result = score_er_tier([(0, 1), (1, 2), (2, 3)], gt, tier=1, time_seconds=0.0, memory_mb=0.0)
        # All 4 in one predicted cluster: each element's pred cluster has 2/4 correct.
        assert result.bcubed_precision == pytest.approx(0.5)
        assert result.bcubed_recall == pytest.approx(1.0)
