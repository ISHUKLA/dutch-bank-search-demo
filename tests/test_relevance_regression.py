"""Guard the offline hybrid benchmark against an accidental relevance regression."""

import evaluate
from search import hybrid_search, load_embedder, offline_index


HYBRID_NDCG_AT_10_FLOOR = 0.79


def test_offline_hybrid_ndcg_stays_near_the_approved_baseline():
    """Run the real offline hybrid stack over all 25 judged queries.

    The approved score is about 0.797. The 0.79 floor permits small platform-level
    variation while failing a meaningful ranking regression before it is merged.
    """

    index = offline_index()
    embedder = load_embedder()
    scores = []
    for query in evaluate.load_queries():
        results = hybrid_search(query["query"], k=10, offline=index, embedder=embedder)
        scores.append(evaluate.metrics_for_ranking(results, query["judgments"])["ndcg_at_10"])

    mean_ndcg = sum(scores) / len(scores)
    assert mean_ndcg >= HYBRID_NDCG_AT_10_FLOOR, (
        f"Offline hybrid nDCG@10 regressed to {mean_ndcg:.3f}; "
        f"expected at least {HYBRID_NDCG_AT_10_FLOOR:.2f}."
    )
