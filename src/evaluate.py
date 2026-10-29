"""Evaluate lexical, vector, hybrid, and segment-aware search on judged Dutch queries."""

import argparse
import json
import math
import sys
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

import config
from index import INDEX_NAME, OfflineIndex, get_elasticsearch_client
from metrics import average_precision, ndcg_at_k, recall_at_k, reciprocal_rank
from search import bm25_search, hybrid_search, lexical_query, vector_search


ROOT = Path(__file__).resolve().parents[1]
QUERIES_PATH = ROOT / "data" / "queries.json"
RESULTS_PATH = ROOT / "results" / "metrics.json"
CUTOFF = 10
METHODS = ("bm25", "vector", "hybrid", "hybrid_segment")
METRICS = ("reciprocal_rank", "average_precision", "ndcg_at_10", "recall_at_10")

Retriever = Callable[[dict[str, Any], int], list[dict[str, Any]]]


def load_queries(path: Path = QUERIES_PATH) -> list[dict[str, Any]]:
    """Load the small, version-controlled query and relevance-judgment set."""

    return json.loads(path.read_text(encoding="utf-8"))


def metrics_for_ranking(
    results: list[dict[str, Any]],
    judgments: dict[str, int],
    k: int = CUTOFF,
) -> dict[str, float]:
    """Score one ranked list, treating unjudged returned pages as grade zero.

    The denominator for AP and recall remains all positively judged pages, even if
    some are absent from the top ``k``. nDCG uses every available graded judgment
    to construct the ideal ranking.
    """

    grades = [int(judgments.get(result["id"], 0)) for result in results[:k]]
    known_grades = list(judgments.values())
    relevant_count = sum(grade >= 1 for grade in known_grades)
    return {
        "reciprocal_rank": reciprocal_rank(grades),
        "average_precision": average_precision(grades, total_relevant=relevant_count),
        "ndcg_at_10": ndcg_at_k(grades, k, ideal_grades=known_grades),
        "recall_at_10": recall_at_k(grades, k, total_relevant=relevant_count),
    }


def default_retrievers(
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
    embedder: Any | None = None,
) -> dict[str, Retriever]:
    """Build the four comparable retrieval methods with shared optional dependencies."""

    return {
        "bm25": lambda query, k: bm25_search(query["query"], k, client=client, offline=offline),
        "vector": lambda query, k: vector_search(
            query["query"], k, client=client, offline=offline, embedder=embedder
        ),
        "hybrid": lambda query, k: hybrid_search(
            query["query"], k, client=client, offline=offline, embedder=embedder
        ),
        "hybrid_segment": lambda query, k: hybrid_search(
            query["query"],
            k,
            client=client,
            offline=offline,
            embedder=embedder,
            segment=query["segment"],
        ),
    }


def _mean(metric_rows: list[dict[str, float]]) -> dict[str, float]:
    return {metric: sum(row[metric] for row in metric_rows) / len(metric_rows) for metric in METRICS}


def evaluate_queries(
    queries: list[dict[str, Any]],
    retrievers: dict[str, Retriever],
    k: int = CUTOFF,
) -> dict[str, dict[str, Any]]:
    """Run every query through every method and aggregate overall and type-level scores."""

    report: dict[str, dict[str, Any]] = {}
    for method in METHODS:
        per_query = []
        for query in queries:
            results = retrievers[method](query, k)
            scores = metrics_for_ranking(results, query["judgments"], k)
            per_query.append(
                {
                    "id": query["id"],
                    "query": query["query"],
                    "type": query["type"],
                    "segment": query["segment"],
                    "ranked_ids": [result["id"] for result in results[:k]],
                    **scores,
                }
            )

        by_type: dict[str, dict[str, float]] = {}
        for query_type in sorted({query["type"] for query in queries}):
            type_rows = [row for row in per_query if row["type"] == query_type]
            by_type[query_type] = _mean(type_rows)
        report[method] = {"mean": _mean(per_query), "by_query_type": by_type, "per_query": per_query}
    return report


def diagnose_hybrid_failure(row: dict[str, Any], query: dict[str, Any], k: int = CUTOFF) -> str:
    """Produce a compact, evidence-based description of a weak hybrid result."""

    judgments = query["judgments"]
    best_grade = max(judgments.values())
    best_ids = sorted(document_id for document_id, grade in judgments.items() if grade == best_grade)
    ranked_ids = row["ranked_ids"]
    best_ranks = [ranked_ids.index(document_id) + 1 for document_id in best_ids if document_id in ranked_ids]
    if not best_ranks:
        return f"Best judged page ({', '.join(best_ids)}, grade {best_grade}) is absent from top {k}; wording likely diverges."

    first_relevant_rank = next(
        (rank for rank, document_id in enumerate(ranked_ids, start=1) if judgments.get(document_id, 0) >= 1),
        None,
    )
    if first_relevant_rank is None:
        return f"No judged relevant page is in top {k}; lexical and semantic candidates missed the labelled intent."
    if first_relevant_rank > 1:
        return f"First relevant page is rank {first_relevant_rank}; generic wording outranked the labelled intent."
    if min(best_ranks) > 1:
        return f"A related page ranks first; the best grade-{best_grade} page appears at rank {min(best_ranks)}."
    return "The direct answer ranks first, but secondary judged pages are lower or absent from the top ten."


def worst_hybrid_queries(report: dict[str, dict[str, Any]], queries: list[dict[str, Any]], count: int = 3) -> list[dict[str, Any]]:
    """Return the three lowest-nDCG hybrid runs with a short, deterministic diagnosis."""

    queries_by_id = {query["id"]: query for query in queries}
    rows = sorted(report["hybrid"]["per_query"], key=lambda row: (row["ndcg_at_10"], row["id"]))[:count]
    return [
        {
            "id": row["id"],
            "query": row["query"],
            "type": row["type"],
            "ndcg_at_10": row["ndcg_at_10"],
            "diagnosis": diagnose_hybrid_failure(row, queries_by_id[row["id"]]),
        }
        for row in rows
    ]


def rank_eval_payload(queries: list[dict[str, Any]], k: int = CUTOFF) -> dict[str, Any]:
    """Build Elasticsearch's MRR@k request for the same BM25 query and labels."""

    return {
        "requests": [
            {
                "id": query["id"],
                "request": {"query": lexical_query(query["query"])},
                "ratings": [
                    {"_index": INDEX_NAME, "_id": document_id, "rating": grade}
                    for document_id, grade in query["judgments"].items()
                ],
            }
            for query in queries
        ],
        "metric": {"mean_reciprocal_rank": {"k": k, "relevant_rating_threshold": 1}},
    }


def compare_rank_eval(client: Any, queries: list[dict[str, Any]], local_mrr: float, k: int = CUTOFF) -> dict[str, Any]:
    """Run Elasticsearch `_rank_eval` and compare its MRR@k to local reciprocal rank."""

    response = client.rank_eval(index=INDEX_NAME, **rank_eval_payload(queries, k))
    elasticsearch_mrr = float(response["rank_eval"]["metric_score"])
    return {
        "method": "bm25",
        "metric": "mean_reciprocal_rank_at_10",
        "local": local_mrr,
        "elasticsearch": elasticsearch_mrr,
        "matches": math.isclose(local_mrr, elasticsearch_mrr, abs_tol=1e-12),
    }


def print_table(report: dict[str, dict[str, Any]]) -> None:
    """Print compact aggregate and query-type evaluation tables."""

    print("Mean metrics (25 queries)")
    print(f"{'Method':<18} {'RR':>7} {'AP':>7} {'nDCG@10':>9} {'Recall@10':>10}")
    for method in METHODS:
        scores = report[method]["mean"]
        print(f"{method:<18} {scores['reciprocal_rank']:>7.3f} {scores['average_precision']:>7.3f} {scores['ndcg_at_10']:>9.3f} {scores['recall_at_10']:>10.3f}")

    print("\nBreakdown by query type")
    print(f"{'Type':<16} {'Method':<18} {'RR':>7} {'AP':>7} {'nDCG@10':>9} {'Recall@10':>10}")
    for query_type in ("navigational", "informational", "transactional"):
        for method in METHODS:
            scores = report[method]["by_query_type"][query_type]
            print(f"{query_type:<16} {method:<18} {scores['reciprocal_rank']:>7.3f} {scores['average_precision']:>7.3f} {scores['ndcg_at_10']:>9.3f} {scores['recall_at_10']:>10.3f}")


def print_worst_queries(worst_queries: list[dict[str, Any]]) -> None:
    """Print three low-quality hybrid results without hiding their limitation."""

    print("\nWorst hybrid queries by nDCG@10")
    for item in worst_queries:
        print(f"- {item['id']} ({item['ndcg_at_10']:.3f}): {item['query']} — {item['diagnosis']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the fictional Dutch bank search methods.")
    parser.add_argument("--k", type=int, default=CUTOFF, help="Evaluation cutoff; defaults to 10.")
    arguments = parser.parse_args()
    if arguments.k <= 0:
        print("Evaluation error: --k must be positive.", file=sys.stderr)
        return 1

    try:
        queries = load_queries()
        client = None if config.USE_OFFLINE else get_elasticsearch_client()
        report = evaluate_queries(queries, default_retrievers(client=client), arguments.k)
        worst_queries = worst_hybrid_queries(report, queries)
        rank_eval: dict[str, Any]
        if client is None:
            rank_eval = {"status": "skipped", "reason": "USE_OFFLINE=true; local metrics are the offline fallback."}
        else:
            rank_eval = compare_rank_eval(client, queries, report["bm25"]["mean"]["reciprocal_rank"], arguments.k)

        payload = {
            "backend": "offline" if config.USE_OFFLINE else "elasticsearch",
            "cutoff": arguments.k,
            "relevant_grade": 1,
            "methods": report,
            "worst_hybrid_queries": worst_queries,
            "es_rank_eval": rank_eval,
        }
        RESULTS_PATH.parent.mkdir(exist_ok=True)
        RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print_table(report)
        print_worst_queries(worst_queries)
        if rank_eval.get("status") == "skipped":
            print(f"\nES _rank_eval: skipped ({rank_eval['reason']})")
        else:
            print(f"\nES _rank_eval MRR@{arguments.k}: {rank_eval['elasticsearch']:.6f}")
            print(f"Local BM25 mean RR@{arguments.k}: {rank_eval['local']:.6f}")
            print(f"Match: {rank_eval['matches']}")
        print(f"Saved: {RESULTS_PATH.relative_to(ROOT)}")
        return 0
    except (ImportError, OSError, RuntimeError, ValueError, KeyError) as error:
        print(f"Evaluation error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
