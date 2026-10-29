"""Lexical, vector, and hybrid retrieval over the fictional Dutch help corpus."""

import argparse
import json
import sys
from functools import lru_cache
from typing import Any

import numpy as np

import config
from bank_search.config import EMBEDDING_DIMENSIONS, QUERY_PREFIX
from index import (
    INDEX_NAME,
    OfflineIndex,
    build_offline_index,
    embed_documents,
    get_elasticsearch_client,
    load_documents,
    load_embedder,
    tokenize,
)


RRF_RANK_CONSTANT = 60
RRF_RANK_WINDOW_SIZE = 50
VALID_SEGMENTS = {"private", "business"}


class RrfRetrieverUnavailable(RuntimeError):
    """Raised when the Elasticsearch server does not support the RRF retriever."""


def lexical_query(query: str) -> dict[str, Any]:
    """Use the same Dutch-analyzed fields for lexical retrieval and explainability."""

    return {"multi_match": {"query": query, "fields": ["title^3", "body", "summary^1.5"]}}


@lru_cache(maxsize=1)
def offline_index() -> OfflineIndex:
    """Build one model-backed in-memory index per process for the offline path."""

    documents = load_documents()
    return build_offline_index(documents, embed_documents(documents, load_embedder()))


@lru_cache(maxsize=1)
def query_embedder() -> Any:
    """Reuse the embedding model for all query vectors in a process."""

    return load_embedder()


def embed_query(query: str, embedder: Any | None = None) -> np.ndarray:
    """Encode and normalize a query with the E5 query prefix."""

    model = embedder or query_embedder()
    vector = np.asarray(
        model.encode([f"{QUERY_PREFIX}{query}"], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False),
        dtype=np.float32,
    )
    if vector.shape != (1, EMBEDDING_DIMENSIONS):
        raise ValueError(f"Expected one {EMBEDDING_DIMENSIONS}-dimensional query vector, got {vector.shape}.")
    return vector[0]


def _compact_document(document: dict[str, Any], score: float, method: str) -> dict[str, Any]:
    return {
        "id": document["id"],
        "title": document["title"],
        "summary": document["summary"],
        "audience": document["audience"],
        "score": float(score),
        "method": method,
    }


def _hits_to_results(hits: list[dict[str, Any]], method: str) -> list[dict[str, Any]]:
    results = []
    for hit in hits:
        source = hit["_source"]
        document = {**source, "id": source.get("id", hit["_id"])}
        results.append(_compact_document(document, hit.get("_score", 0.0), method))
    return results


def _offline_bm25(query: str, k: int, index: OfflineIndex) -> list[dict[str, Any]]:
    scores = index.bm25.get_scores(tokenize(query))
    ranks = np.argsort(-scores)[:k]
    return [_compact_document(index.documents[rank], scores[rank], "bm25") for rank in ranks]


def _offline_vector(query: str, k: int, index: OfflineIndex, embedder: Any | None) -> list[dict[str, Any]]:
    query_vector = embed_query(query, embedder)
    scores = index.embedding_matrix @ query_vector
    ranks = np.argsort(-scores)[:k]
    return [_compact_document(index.documents[rank], scores[rank], "vector") for rank in ranks]


def bm25_search(
    query: str,
    k: int = 5,
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
) -> list[dict[str, Any]]:
    """Retrieve lexical BM25 candidates from Elasticsearch or the offline fallback."""

    if offline is not None or (client is None and config.USE_OFFLINE):
        return _offline_bm25(query, k, offline or offline_index())
    search_client = client or get_elasticsearch_client()
    response = search_client.search(
        index=INDEX_NAME,
        query=lexical_query(query),
        size=k,
        source={"excludes": ["embedding"]},
    )
    return _hits_to_results(response["hits"]["hits"], "bm25")


def vector_search(
    query: str,
    k: int = 5,
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
    embedder: Any | None = None,
) -> list[dict[str, Any]]:
    """Retrieve cosine kNN candidates using an E5 query vector or NumPy dot product."""

    if offline is not None or (client is None and config.USE_OFFLINE):
        return _offline_vector(query, k, offline or offline_index(), embedder)
    query_vector = embed_query(query, embedder)
    search_client = client or get_elasticsearch_client()
    response = search_client.search(
        index=INDEX_NAME,
        knn={"field": "embedding", "query_vector": query_vector.tolist(), "k": k, "num_candidates": max(k * 10, 100)},
        size=k,
        source={"excludes": ["embedding"]},
    )
    return _hits_to_results(response["hits"]["hits"], "vector")


def _rrf(results: list[list[dict[str, Any]]], k: int, rank_constant: int = RRF_RANK_CONSTANT) -> list[dict[str, Any]]:
    """Fuse ranked result lists with reciprocal rank fusion in plain Python."""

    scores: dict[str, float] = {}
    documents: dict[str, dict[str, Any]] = {}
    for ranked_list in results:
        for rank, result in enumerate(ranked_list, start=1):
            document_id = result["id"]
            scores[document_id] = scores.get(document_id, 0.0) + 1.0 / (rank_constant + rank)
            documents[document_id] = result
    ordered = sorted(scores, key=lambda document_id: (-scores[document_id], document_id))[:k]
    return [{**documents[document_id], "score": scores[document_id], "method": "hybrid_client_rrf"} for document_id in ordered]


def _validate_segment(segment: str | None) -> None:
    """Reject unapproved segment labels instead of silently personalising incorrectly."""

    if segment is not None and segment not in VALID_SEGMENTS:
        allowed = ", ".join(sorted(VALID_SEGMENTS))
        raise ValueError(f"segment must be one of: {allowed}, or None.")


def _segment_boost(audience: str, segment: str | None) -> float:
    """Return a transparent score adjustment for exact and shared audiences."""

    if segment is None:
        return 0.0
    if audience == segment:
        return config.SEGMENT_BOOST_WEIGHT
    if audience == "both":
        return config.SEGMENT_BOOST_WEIGHT / 2
    return 0.0


def apply_segment_boost(
    results: list[dict[str, Any]],
    segment: str | None,
    k: int,
) -> list[dict[str, Any]]:
    """Rerank hybrid candidates by explicit audience applicability.

    An exact private/business audience receives the configured weight. A ``both`` page
    is still applicable to either user, so it receives half of that weight.
    """

    _validate_segment(segment)
    personalised = []
    for result in results:
        boost = _segment_boost(result["audience"], segment)
        base_score = float(result["score"])
        personalised.append(
            {
                **result,
                "base_score": base_score,
                "segment": segment,
                "segment_boost": boost,
                "score": base_score + boost,
            }
        )
    return sorted(
        personalised,
        key=lambda result: (-result["score"], -result["base_score"], result["id"]),
    )[:k]


def hybrid_client_rrf(
    query: str,
    k: int = 5,
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
    embedder: Any | None = None,
    segment: str | None = None,
    rank_window_size: int = RRF_RANK_WINDOW_SIZE,
) -> list[dict[str, Any]]:
    """Fuse BM25 and vector candidate lists in Python for all fallback paths."""

    _validate_segment(segment)
    candidate_count = max(k, rank_window_size)
    fused = _rrf(
        [
            bm25_search(query, candidate_count, client=client, offline=offline),
            vector_search(query, candidate_count, client=client, offline=offline, embedder=embedder),
        ],
        k,
    )
    return apply_segment_boost(fused, segment, k)


def _rrf_is_unavailable(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    text = str(error).lower()
    return status in {400, 404, 501} and ("rrf" in text or "retriever" in text)


def _elasticsearch_rrf_search(query: str, k: int, client: Any, embedder: Any | None) -> list[dict[str, Any]]:
    """Run Elasticsearch's server-side RRF retriever over lexical and kNN candidates."""

    query_vector = embed_query(query, embedder)
    candidate_count = max(k, RRF_RANK_WINDOW_SIZE)
    response = client.search(
        index=INDEX_NAME,
        retriever={
            "rrf": {
                "retrievers": [
                    {"standard": {"query": lexical_query(query)}},
                    {
                        "knn": {
                            "field": "embedding",
                            "query_vector": query_vector.tolist(),
                            "k": candidate_count,
                            "num_candidates": max(candidate_count * 2, 100),
                        }
                    },
                ],
                "rank_constant": RRF_RANK_CONSTANT,
                "rank_window_size": candidate_count,
            }
        },
        size=k,
        source={"excludes": ["embedding"]},
    )
    return _hits_to_results(response["hits"]["hits"], "hybrid_es_rrf")


def hybrid_search(
    query: str,
    k: int = 5,
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
    embedder: Any | None = None,
    segment: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve hybrid candidates, then apply an optional audience-based rerank."""

    _validate_segment(segment)
    candidate_count = max(k, RRF_RANK_WINDOW_SIZE) if segment else k
    if offline is not None or (client is None and config.USE_OFFLINE):
        return hybrid_client_rrf(
            query,
            candidate_count,
            offline=offline or offline_index(),
            embedder=embedder,
            segment=segment,
        )[:k]
    search_client = client or get_elasticsearch_client()
    try:
        candidates = _elasticsearch_rrf_search(query, candidate_count, search_client, embedder)
    except Exception as error:
        if not _rrf_is_unavailable(error):
            raise
        return hybrid_client_rrf(
            query,
            candidate_count,
            client=search_client,
            embedder=embedder,
            segment=segment,
        )[:k]
    return apply_segment_boost(candidates, segment, k)


def _format_explanation(node: dict[str, Any], indent: int = 0) -> list[str]:
    prefix = "  " * indent
    lines = [f"{prefix}{node.get('value', 0.0):.4f}  {node.get('description', 'score')}"]
    for detail in node.get("details", []):
        lines.extend(_format_explanation(detail, indent + 1))
    return lines


def explain_result(query: str, doc_id: str, *, client: Any | None = None) -> None:
    """Print Elasticsearch's readable BM25 explain tree for one indexed document."""

    if config.USE_OFFLINE and client is None:
        raise RuntimeError("explain_result requires Elasticsearch; set USE_OFFLINE=false.")
    search_client = client or get_elasticsearch_client()
    response = search_client.explain(index=INDEX_NAME, id=doc_id, query=lexical_query(query))
    print(f"Query: {query}")
    print(f"Document: {doc_id}")
    print(f"Matched: {response['matched']}")
    print("BM25 score breakdown:")
    print("\n".join(_format_explanation(response["explanation"])))


def _table_row(rank: int, result: dict[str, Any] | None) -> str:
    if result is None:
        return f"{rank:<4} {'':<8} {'':<42}"
    return f"{rank:<4} {result['id']:<8} {result['title'][:42]:<42}"


def _personalised_table_row(rank: int, result: dict[str, Any] | None) -> str:
    if result is None:
        return f"{rank:<4} {'':<8} {'':<35} {'':<9}"
    return (
        f"{rank:<4} {result['id']:<8} {result['title'][:35]:<35} "
        f"{result['audience']:<9} +{result['segment_boost']:.3f}"
    )


def demo(
    query: str,
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
    embedder: Any | None = None,
) -> None:
    """Print five lexical, vector, and hybrid results next to each other for one query."""

    methods = {
        "BM25": bm25_search(query, 5, client=client, offline=offline),
        "Vector": vector_search(query, 5, client=client, offline=offline, embedder=embedder),
        "Hybrid": hybrid_search(query, 5, client=client, offline=offline, embedder=embedder),
    }
    print(f"Query: {query}\n")
    print(f"{'Rank':<4} {'BM25':<52} {'Vector':<52} Hybrid")
    print("-" * 164)
    for rank in range(1, 6):
        values = [_table_row(rank, methods[name][rank - 1] if len(methods[name]) >= rank else None) for name in methods]
        print(" | ".join(values))


def personalisation_demo(
    query: str = "rekening openen",
    *,
    client: Any | None = None,
    offline: OfflineIndex | None = None,
    embedder: Any | None = None,
) -> None:
    """Print the same hybrid query for a private and business user side by side."""

    private = hybrid_search(query, 5, client=client, offline=offline, embedder=embedder, segment="private")
    business = hybrid_search(query, 5, client=client, offline=offline, embedder=embedder, segment="business")
    print(f"Query: {query}")
    print(f"Segment boost weight: {config.SEGMENT_BOOST_WEIGHT:.3f} (both: half weight)\n")
    print(f"{'Rank':<4} {'Private user':<66} | Business user")
    print("-" * 154)
    for rank in range(1, 6):
        private_result = private[rank - 1] if len(private) >= rank else None
        business_result = business[rank - 1] if len(business) >= rank else None
        print(f"{_personalised_table_row(rank, private_result)} | {_personalised_table_row(rank, business_result)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the fictional Dutch bank help corpus.")
    parser.add_argument("--query", help="Dutch query for the selected demo or explanation.")
    parser.add_argument("--explain-id", help="Print only the Elasticsearch BM25 explanation for this document id.")
    parser.add_argument(
        "--personalisation-demo",
        action="store_true",
        help="Compare private and business hybrid results for the selected query.",
    )
    arguments = parser.parse_args()
    try:
        if arguments.explain_id:
            explain_result(arguments.query or "pas kwijt", arguments.explain_id)
        elif arguments.personalisation_demo:
            personalisation_demo(arguments.query or "rekening openen")
        else:
            demo(arguments.query or "pas kwijt")
        return 0
    except (ImportError, OSError, RuntimeError, ValueError) as error:
        print(f"Search error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
