"""Build Elasticsearch or in-memory indexes for the fictional Dutch help pages."""

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from rank_bm25 import BM25Okapi

from bank_search.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, PASSAGE_PREFIX
from enrich import load_cache, load_pages, validate_cache


ROOT = Path(__file__).resolve().parents[1]
INDEX_NAME = "fictional-bank-help-pages"


class Embedder(Protocol):
    """The small surface used from SentenceTransformer, making tests model-free."""

    def encode(self, sentences: list[str], **kwargs: Any) -> np.ndarray: ...


@dataclass
class OfflineIndex:
    """In-memory equivalent of the searchable corpus used by the Elasticsearch path."""

    documents: list[dict[str, Any]]
    bm25: BM25Okapi
    embedding_matrix: np.ndarray


def tokenize(text: str) -> list[str]:
    """Simple deterministic tokenization for the offline BM25 fallback."""

    return re.findall(r"[\wÀ-ÿ]+", text.lower())


def load_documents() -> list[dict[str, Any]]:
    """Join source pages with their validated, cached enrichment fields."""

    pages = load_pages()
    enrichments = {entry["id"]: entry for entry in validate_cache(pages, load_cache())}
    documents = []
    for page in pages:
        enrichment = enrichments[page["id"]]
        documents.append(
            {
                "id": page["id"],
                "title": page["title"],
                "body": page["body"],
                "url": page["url"],
                "summary": enrichment["summary"],
                "audience": enrichment["audience"],
                "product": enrichment["product"],
                "topic": enrichment["topic"],
                "intent": enrichment["intent"],
                "example_queries": enrichment["example_queries"],
            }
        )
    return documents


def embedding_text(document: dict[str, Any]) -> str:
    """Keep the vector representation focused on the title and grounded summary."""

    return f"{document['title']}\n{document['summary']}"


def load_embedder() -> Embedder:
    """Load the required multilingual E5 model only when indexing is requested."""

    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def embed_documents(documents: list[dict[str, Any]], embedder: Embedder) -> np.ndarray:
    """Create normalized E5 passage vectors and verify the expected dimensionality."""

    passages = [f"{PASSAGE_PREFIX}{embedding_text(document)}" for document in documents]
    vectors = np.asarray(
        embedder.encode(passages, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=True),
        dtype=np.float32,
    )
    expected_shape = (len(documents), EMBEDDING_DIMENSIONS)
    if vectors.shape != expected_shape:
        raise ValueError(f"Expected embeddings with shape {expected_shape}, got {vectors.shape}.")
    return vectors


def build_offline_index(documents: list[dict[str, Any]], vectors: np.ndarray) -> OfflineIndex:
    """Build the lexical and vector structures used when Elasticsearch is unavailable."""

    if vectors.shape != (len(documents), EMBEDDING_DIMENSIONS):
        raise ValueError("Offline matrix does not match the document count and embedding dimensions.")
    corpus_tokens = [tokenize(f"{document['title']} {document['body']}") for document in documents]
    return OfflineIndex(documents=documents, bm25=BM25Okapi(corpus_tokens), embedding_matrix=vectors)


def index_mapping() -> dict[str, Any]:
    """Return the Elasticsearch settings and mapping used by the live backend."""

    return {
        "settings": {"analysis": {"analyzer": {"dutch_help": {"type": "dutch"}}}},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "id": {"type": "keyword"},
                "title": {"type": "text", "analyzer": "dutch_help"},
                "body": {"type": "text", "analyzer": "dutch_help"},
                "url": {"type": "keyword", "index": False},
                "summary": {"type": "text", "analyzer": "dutch_help"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMENSIONS,
                    "index": True,
                    "similarity": "cosine",
                },
                "audience": {"type": "keyword"},
                "product": {"type": "keyword"},
                "topic": {"type": "keyword"},
                "intent": {"type": "keyword"},
                "example_queries": {"type": "keyword"},
            },
        },
    }


def create_index(client: Any, recreate: bool = False) -> None:
    """Create the configured index, deleting it first only when requested explicitly."""

    exists = client.indices.exists(index=INDEX_NAME)
    if exists and recreate:
        client.indices.delete(index=INDEX_NAME)
        exists = False
    if not exists:
        client.indices.create(index=INDEX_NAME, **index_mapping())


def bulk_actions(documents: list[dict[str, Any]], vectors: np.ndarray) -> list[dict[str, Any]]:
    """Build deterministic bulk index actions with stable document identifiers."""

    actions = []
    for document, vector in zip(documents, vectors, strict=True):
        actions.append(
            {
                "_op_type": "index",
                "_index": INDEX_NAME,
                "_id": document["id"],
                "_source": {**document, "embedding": vector.tolist()},
            }
        )
    return actions


def index_elasticsearch(client: Any, documents: list[dict[str, Any]], vectors: np.ndarray, recreate: bool) -> int:
    """Create the live index and bulk-index all page documents."""

    from elasticsearch import helpers

    create_index(client, recreate=recreate)
    helpers.bulk(client, bulk_actions(documents, vectors), refresh="wait_for")
    return int(client.count(index=INDEX_NAME)["count"])


def public_sample(document: dict[str, Any]) -> dict[str, Any]:
    """Show one readable source document without printing its full vector."""

    sample = document.copy()
    vector = sample.pop("embedding", None)
    if vector is not None:
        sample["embedding_dimensions"] = len(vector)
    return sample


def get_elasticsearch_client() -> Any:
    """Build the configured client only for the Elasticsearch indexing path."""

    import config
    from elasticsearch import Elasticsearch

    options: dict[str, Any] = {"request_timeout": 30, "max_retries": 0}
    if bool(config.ES_USERNAME) != bool(config.ES_PASSWORD):
        raise ValueError("Set both ES_USERNAME and ES_PASSWORD, or leave both empty.")
    if config.ES_USERNAME:
        options["basic_auth"] = (config.ES_USERNAME, config.ES_PASSWORD)
    return Elasticsearch(config.ES_URL, **options)


def print_offline_result(index: OfflineIndex) -> None:
    print("Backend: offline")
    print(f"Document count: {len(index.documents)}")
    sample = {**index.documents[0], "embedding": index.embedding_matrix[0].tolist()}
    print("Sample document:")
    print(json.dumps(public_sample(sample), ensure_ascii=False, indent=2))


def print_elasticsearch_result(client: Any) -> None:
    sample = client.get(index=INDEX_NAME, id="p01")["_source"]
    print("Backend: elasticsearch")
    print(f"Document count: {client.count(index=INDEX_NAME)['count']}")
    print("Sample document:")
    print(json.dumps(public_sample(sample), ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="Index fictional Dutch help pages with E5 embeddings.")
    parser.add_argument("--recreate", action="store_true", help="Delete and recreate the Elasticsearch index first.")
    arguments = parser.parse_args()

    try:
        import config

        documents = load_documents()
        vectors = embed_documents(documents, load_embedder())
        if config.USE_OFFLINE:
            print_offline_result(build_offline_index(documents, vectors))
            return 0
        with get_elasticsearch_client() as client:
            index_elasticsearch(client, documents, vectors, recreate=arguments.recreate)
            print_elasticsearch_result(client)
        return 0
    except (ImportError, OSError, ValueError, RuntimeError) as error:
        print(f"Indexing error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
