"""Tests for the small, explicit information-retrieval metric functions."""

import pytest

from metrics import average_precision, ndcg_at_k, recall_at_k, reciprocal_rank


def test_requested_graded_example():
    grades = [0, 3, 2, 1, 0]
    assert reciprocal_rank(grades) == 0.5
    assert average_precision(grades, total_relevant=3) == pytest.approx(0.6388888889)
    assert ndcg_at_k(grades, 5) == pytest.approx(0.6979344)
    assert recall_at_k(grades, 5, total_relevant=3) == 1.0


def test_metrics_return_zero_when_no_relevant_document_exists():
    assert reciprocal_rank([0, 0]) == 0.0
    assert average_precision([0, 0], total_relevant=0) == 0.0
    assert ndcg_at_k([0, 0], 2) == 0.0
    assert recall_at_k([0, 0], 2, total_relevant=0) == 0.0
