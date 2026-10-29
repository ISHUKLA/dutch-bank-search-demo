# Step 4: indexing

`src/index.py` builds one enriched document list from `pages.json` and `enrichment_cache.json`.
The two backends receive the same title, body, URL, summary, metadata, and passage vectors.

## Offline indexing

The default setup uses no Elasticsearch service:

```bash
USE_OFFLINE=true python src/index.py
```

The first run downloads `intfloat/multilingual-e5-small` unless it is already in the local model cache.
The script encodes `passage: <title>\n<summary>` and normalizes the vectors. It then builds:

- `BM25Okapi` over tokenized Dutch title and body text;
- a NumPy matrix with one normalized, 384-dimensional vector per document;
- the complete enriched document list in memory.

Expected output begins with:

```text
Backend: offline
Document count: 40
Sample document:
```

The sample shows `embedding_dimensions: 384`, rather than all vector values.

## Elasticsearch indexing

Start the local trial node from Step 1, then run:

```bash
docker compose up -d --wait
USE_OFFLINE=false python src/index.py --recreate
```

`--recreate` explicitly deletes and recreates only `fictional-bank-help-pages` before indexing.
Without it, bulk indexing uses stable page IDs and updates existing documents instead of duplicating them.

The created mapping uses:

- the built-in Dutch analyzer for `title`, `body`, and `summary`;
- `dense_vector` with 384 dimensions, cosine similarity, and vector indexing enabled;
- `keyword` fields for `audience`, `product`, `topic`, `intent`, and `example_queries`.

Expected output begins with:

```text
Backend: elasticsearch
Document count: 40
Sample document:
```

The built-in [Dutch language analyzer](https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-lang-analyzer.html)
handles Dutch stop words and stemming. The dense-vector field is configured for
[cosine similarity](https://www.elastic.co/guide/en/elasticsearch/reference/current/dense-vector.html).

## Validate the implementation

```bash
python -m pytest tests/test_index.py -vv
```

Successful output ends with:

```text
5 passed
```

The tests use a fake embedder and fake Elasticsearch index client, so they do not download the E5 model,
connect to Elasticsearch, or delete an index.

## Interview talking points

- "Both backends receive exactly the same enriched documents and E5 passage vectors, so comparison is fair."
- "Elasticsearch gets Dutch lexical analysis and cosine vector search; offline mode keeps BM25 and vectors in memory."
- "Index replacement is opt-in, while stable document IDs make repeat runs idempotent."
