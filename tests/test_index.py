"""Tests for shared Elasticsearch and in-memory index construction."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SPEC = importlib.util.spec_from_file_location("index_module", ROOT / "src" / "index.py")
index_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(index_module)


class FakeEmbedder:
    def __init__(self):
        self.passages = []

    def encode(self, sentences, **kwargs):
        self.passages = sentences
        return np.ones((len(sentences), 384), dtype=np.float32)


class FakeIndices:
    def __init__(self, exists=False):
        self.exists_value = exists
        self.created = None
        self.deleted = []

    def exists(self, *, index):
        return self.exists_value

    def create(self, *, index, **mapping):
        self.created = (index, mapping)

    def delete(self, *, index):
        self.deleted.append(index)


class FakeClient:
    def __init__(self, exists=False):
        self.indices = FakeIndices(exists=exists)


def test_mapping_has_dutch_text_vector_and_keyword_metadata():
    mapping = index_module.index_mapping()
    properties = mapping["mappings"]["properties"]
    assert properties["title"]["analyzer"] == "dutch_help"
    assert properties["body"]["analyzer"] == "dutch_help"
    assert properties["embedding"] == {"type": "dense_vector", "dims": 384, "index": True, "similarity": "cosine"}
    for field in ("audience", "product", "topic", "intent", "example_queries"):
        assert properties[field]["type"] == "keyword"


def test_e5_passages_and_offline_bm25_matrix_use_the_same_documents():
    documents = index_module.load_documents()
    embedder = FakeEmbedder()
    vectors = index_module.embed_documents(documents, embedder)
    offline = index_module.build_offline_index(documents, vectors)
    assert len(documents) == 40
    assert vectors.shape == (40, 384)
    assert all(text.startswith("passage: ") for text in embedder.passages)
    assert "\n" in embedder.passages[0]
    assert offline.embedding_matrix.shape == (40, 384)
    assert len(offline.bm25.get_scores(index_module.tokenize("pas kwijt"))) == 40


def test_create_index_never_deletes_without_recreate():
    client = FakeClient(exists=True)
    index_module.create_index(client, recreate=False)
    assert client.indices.deleted == []
    assert client.indices.created is None


def test_recreate_deletes_then_creates_index():
    client = FakeClient(exists=True)
    index_module.create_index(client, recreate=True)
    assert client.indices.deleted == [index_module.INDEX_NAME]
    assert client.indices.created[0] == index_module.INDEX_NAME


def test_embedding_dimension_mismatch_fails_fast():
    class WrongSizeEmbedder:
        def encode(self, sentences, **kwargs):
            return np.ones((len(sentences), 3), dtype=np.float32)

    with pytest.raises(ValueError, match="shape"):
        index_module.embed_documents([{ "title": "Titel", "summary": "Samenvatting."}], WrongSizeEmbedder())
