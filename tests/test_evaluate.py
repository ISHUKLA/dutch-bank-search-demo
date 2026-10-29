"""Tests for the evaluation report and its Elasticsearch rank-eval comparison."""

import pytest

import evaluate


def sample_queries():
    return [
        {
            "id": "q01",
            "query": "eerste vraag",
            "type": "informational",
            "segment": "private",
            "judgments": {"p01": 3, "p02": 1},
        },
        {
            "id": "q02",
            "query": "tweede vraag",
            "type": "navigational",
            "segment": "business",
            "judgments": {"p03": 3, "p04": 0},
        },
    ]


def fake_retrievers():
    def results(query, k):
        if query["id"] == "q01":
            return [{"id": "p02"}, {"id": "p01"}]
        return [{"id": "p04"}, {"id": "p03"}]

    return {method: results for method in evaluate.METHODS}


def test_evaluation_reports_means_types_and_worst_hybrid_queries():
    queries = sample_queries()
    report = evaluate.evaluate_queries(queries, fake_retrievers(), k=2)
    assert report["bm25"]["mean"]["reciprocal_rank"] == pytest.approx(0.75)
    assert report["hybrid_segment"]["by_query_type"]["informational"]["recall_at_10"] == 1.0
    worst = evaluate.worst_hybrid_queries(report, queries, count=1)
    assert worst[0]["id"] == "q02"
    assert "First relevant page is rank 2" in worst[0]["diagnosis"]


def test_rank_eval_payload_and_comparison_use_same_mrr():
    class FakeClient:
        def __init__(self):
            self.arguments = None

        def rank_eval(self, **kwargs):
            self.arguments = kwargs
            return {"rank_eval": {"metric_score": 0.5}}

    client = FakeClient()
    comparison = evaluate.compare_rank_eval(client, sample_queries(), local_mrr=0.5, k=10)
    assert comparison["matches"] is True
    assert client.arguments["metric"]["mean_reciprocal_rank"]["k"] == 10
    assert client.arguments["requests"][0]["ratings"][0]["_id"] == "p01"
