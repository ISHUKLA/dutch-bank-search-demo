"""Tests for offline retrieval, client-side RRF, and Elasticsearch request construction."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from rank_bm25 import BM25Okapi


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("search_module", ROOT / "src" / "search.py")
search = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(search)


def offline_fixture():
    documents = [
        {"id": "p01", "title": "Betaalpas kwijt", "body": "Blokkeer een verloren betaalpas.", "summary": "Pas kwijt melden. Nieuwe pas aanvragen.", "audience": "both"},
        {"id": "p02", "title": "Creditcard limiet", "body": "Pas de limiet van je creditcard aan.", "summary": "Creditcard limiet wijzigen. Controleer de kaart.", "audience": "private"},
        {"id": "p03", "title": "Contact opnemen", "body": "Bel de kaartservice bij fraude.", "summary": "Gebruik officiële contactgegevens. Meld fraude snel.", "audience": "business"},
    ]
    vectors = np.zeros((3, 384), dtype=np.float32)
    vectors[0, 0] = 1.0
    vectors[1, 1] = 1.0
    vectors[2, 2] = 1.0
    tokenized_documents = [search.tokenize(f"{document['title']} {document['body']}") for document in documents]
    return search.OfflineIndex(
        documents=documents,
        bm25=BM25Okapi(tokenized_documents),
        embedding_matrix=vectors,
    )


class FakeEmbedder:
    def __init__(self):
        self.sentences = []

    def encode(self, sentences, **kwargs):
        self.sentences = sentences
        vector = np.zeros((len(sentences), 384), dtype=np.float32)
        vector[:, 0] = 1.0
        return vector


def test_offline_bm25_vector_and_rrf_use_shared_documents():
    offline = offline_fixture()
    embedder = FakeEmbedder()
    bm25 = search.bm25_search("pas kwijt", offline=offline)
    vector = search.vector_search("kaart", offline=offline, embedder=embedder)
    hybrid = search.hybrid_client_rrf("pas kwijt", offline=offline, embedder=embedder)
    assert bm25[0]["id"] == "p01"
    assert vector[0]["id"] == "p01"
    assert hybrid[0]["id"] == "p01"
    assert hybrid[0]["method"] == "hybrid_client_rrf"


def test_query_embeddings_use_the_e5_query_prefix():
    embedder = FakeEmbedder()
    vector = search.embed_query("pas kwijt", embedder)
    assert vector.shape == (384,)
    assert embedder.sentences == ["query: pas kwijt"]


def test_client_rrf_combines_ranked_lists():
    first = [{"id": "p01", "title": "A", "summary": "", "audience": "both", "score": 4.0, "method": "bm25"}]
    second = [{"id": "p02", "title": "B", "summary": "", "audience": "both", "score": 0.9, "method": "vector"}, first[0]]
    results = search._rrf([first, second], k=2, rank_constant=1)
    assert [result["id"] for result in results] == ["p01", "p02"]


def test_segment_boost_prefers_exact_audience_then_shared_audience(monkeypatch):
    monkeypatch.setattr(search.config, "SEGMENT_BOOST_WEIGHT", 0.01)
    results = [
        {"id": "p01", "title": "Shared", "summary": "", "audience": "both", "score": 0.020, "method": "hybrid"},
        {"id": "p02", "title": "Private", "summary": "", "audience": "private", "score": 0.017, "method": "hybrid"},
        {"id": "p03", "title": "Business", "summary": "", "audience": "business", "score": 0.019, "method": "hybrid"},
    ]
    private = search.apply_segment_boost(results, "private", k=3)
    business = search.apply_segment_boost(results, "business", k=3)
    assert [result["id"] for result in private] == ["p02", "p01", "p03"]
    assert [result["id"] for result in business] == ["p03", "p01", "p02"]
    assert private[0]["base_score"] == 0.017
    assert private[0]["segment_boost"] == 0.01


def test_invalid_segment_is_rejected():
    with pytest.raises(ValueError, match="segment must be"):
        search.apply_segment_boost([], "student", k=5)


def test_hybrid_search_fetches_a_reranking_window_for_a_segment(monkeypatch):
    captured = {}
    candidates = [
        {"id": "p01", "title": "Shared", "summary": "", "audience": "both", "score": 0.020, "method": "hybrid_es_rrf"},
        {"id": "p02", "title": "Private", "summary": "", "audience": "private", "score": 0.017, "method": "hybrid_es_rrf"},
    ]

    def fake_rrf(query, k, client, embedder):
        captured["k"] = k
        return candidates

    monkeypatch.setattr(search, "_elasticsearch_rrf_search", fake_rrf)
    results = search.hybrid_search("rekening openen", k=1, client=object(), segment="private")
    assert captured["k"] == search.RRF_RANK_WINDOW_SIZE
    assert results[0]["id"] == "p02"


def test_personalisation_demo_prints_private_and_business_columns(monkeypatch, capsys):
    private = [{"id": "p11", "title": "Privé", "summary": "", "audience": "private", "segment_boost": 0.01}]
    business = [{"id": "p12", "title": "Zakelijk", "summary": "", "audience": "business", "segment_boost": 0.01}]
    monkeypatch.setattr(search, "hybrid_search", lambda query, k, **kwargs: private if kwargs["segment"] == "private" else business)
    search.personalisation_demo("rekening openen")
    output = capsys.readouterr().out
    assert "Query: rekening openen" in output
    assert "Private user" in output
    assert "Business user" in output
    assert "p11" in output
    assert "p12" in output


def test_es_rrf_payload_contains_standard_and_knn_retrievers(monkeypatch):
    class FakeClient:
        def __init__(self):
            self.arguments = None

        def search(self, **kwargs):
            self.arguments = kwargs
            return {"hits": {"hits": []}}

    client = FakeClient()
    monkeypatch.setattr(search, "embed_query", lambda query, embedder: np.ones(384, dtype=np.float32))
    assert search._elasticsearch_rrf_search("pas kwijt", 5, client, None) == []
    rrf = client.arguments["retriever"]["rrf"]
    assert "standard" in rrf["retrievers"][0]
    assert rrf["retrievers"][1]["knn"]["field"] == "embedding"


def test_rrf_unavailable_uses_client_fallback(monkeypatch):
    monkeypatch.setattr(search, "_elasticsearch_rrf_search", lambda *args: (_ for _ in ()).throw(search.RrfRetrieverUnavailable()))
    monkeypatch.setattr(search, "_rrf_is_unavailable", lambda error: isinstance(error, search.RrfRetrieverUnavailable))
    expected = [{"id": "p01", "title": "A", "summary": "", "audience": "both", "score": 0.1, "method": "hybrid_client_rrf"}]
    monkeypatch.setattr(search, "hybrid_client_rrf", lambda *args, **kwargs: expected)
    assert search.hybrid_search("pas kwijt", client=object()) == expected


def test_explain_output_is_readable(monkeypatch, capsys):
    class FakeClient:
        def explain(self, **kwargs):
            return {"matched": True, "explanation": {"value": 2.0, "description": "sum of:", "details": [{"value": 1.0, "description": "weight(title:pas)", "details": []}]}}

    search.explain_result("pas kwijt", "p01", client=FakeClient())
    output = capsys.readouterr().out
    assert "BM25 score breakdown" in output
    assert "weight(title:pas)" in output
