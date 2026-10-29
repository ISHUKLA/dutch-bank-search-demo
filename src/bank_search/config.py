"""Shared constants for the planned search pipeline."""

BACKENDS = ("offline", "elasticsearch")
DEFAULT_BACKEND = "offline"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_DIMENSIONS = 384
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "
