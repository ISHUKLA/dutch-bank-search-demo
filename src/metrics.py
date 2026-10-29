"""Small, dependency-free information-retrieval metrics for graded judgments."""

import math
from collections.abc import Sequence


RELEVANT_GRADE = 1


def reciprocal_rank(grades: Sequence[int], relevant_grade: int = RELEVANT_GRADE) -> float:
    """Return reciprocal rank of the first document at or above the relevance threshold."""

    for rank, grade in enumerate(grades, start=1):
        if grade >= relevant_grade:
            return 1.0 / rank
    return 0.0


def average_precision(
    grades: Sequence[int],
    total_relevant: int | None = None,
    relevant_grade: int = RELEVANT_GRADE,
) -> float:
    """Return binary average precision, normalised by all known relevant documents."""

    relevant_count = total_relevant
    if relevant_count is None:
        relevant_count = sum(grade >= relevant_grade for grade in grades)
    if relevant_count == 0:
        return 0.0

    relevant_seen = 0
    precision_sum = 0.0
    for rank, grade in enumerate(grades, start=1):
        if grade >= relevant_grade:
            relevant_seen += 1
            precision_sum += relevant_seen / rank
    return precision_sum / relevant_count


def _dcg_at_k(grades: Sequence[int], k: int) -> float:
    """Calculate DCG with linear relevance gain: grade / log2(rank + 1)."""

    return sum(grade / math.log2(rank + 1) for rank, grade in enumerate(grades[:k], start=1))


def ndcg_at_k(grades: Sequence[int], k: int, ideal_grades: Sequence[int] | None = None) -> float:
    """Return linear-gain nDCG@k using all judgments to form the ideal ranking."""

    ideal = sorted(grades if ideal_grades is None else ideal_grades, reverse=True)
    ideal_dcg = _dcg_at_k(ideal, k)
    if ideal_dcg == 0:
        return 0.0
    return _dcg_at_k(grades, k) / ideal_dcg


def recall_at_k(
    grades: Sequence[int],
    k: int,
    total_relevant: int,
    relevant_grade: int = RELEVANT_GRADE,
) -> float:
    """Return the fraction of known relevant documents present in the first ``k`` ranks."""

    if total_relevant == 0:
        return 0.0
    retrieved_relevant = sum(grade >= relevant_grade for grade in grades[:k])
    return retrieved_relevant / total_relevant
