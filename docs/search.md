# Step 5: search

`src/search.py` exposes the same four retrieval functions for either backend:

- `bm25_search`: Dutch-analyzed Elasticsearch BM25 or `rank_bm25` in memory;
- `vector_search`: Elasticsearch kNN or a NumPy dot product over normalized E5 vectors;
- `hybrid_search`: Elasticsearch's RRF retriever when it is available;
- `hybrid_client_rrf`: deterministic reciprocal rank fusion in Python.

`hybrid_search` sends one `standard` lexical retriever and one `knn` retriever to
Elasticsearch. If Elasticsearch reports that `rrf` or `retriever` is unsupported, it
automatically performs the same fusion in Python. The fallback asks both backends for
50 candidates, uses `1 / (60 + rank)`, and keeps the first five fused documents.

## Run the offline demo

The offline path needs the E5 model already available locally, just as Step 4 did:

```bash
USE_OFFLINE=true python src/search.py --query "pas kwijt"
```

Successful output begins like this:

```text
Query: pas kwijt

Rank BM25                                                 Vector                                               Hybrid
--------------------------------------------------------------------------------------------------------------------------------------------------------------------
1    p01      Betaalpas kwijt                              | 1    p01      Betaalpas kwijt                              | 1    p01      Betaalpas kwijt
```

The three columns intentionally make disagreements visible. In a live interview, use a
short or ambiguous query first, then explain how hybrid RRF balances exact lexical terms
with semantic meaning.

## Run the Elasticsearch demo

After starting and indexing the local node:

```bash
docker compose up -d --wait
USE_OFFLINE=false python src/index.py --recreate
USE_OFFLINE=false python src/search.py --query "pas kwijt"
```

For a readable lexical score explanation, run:

```bash
USE_OFFLINE=false python src/search.py --query "pas kwijt" --explain-id p01
```

Successful output includes:

```text
Query: pas kwijt
Document: p01
Matched: True
BM25 score breakdown:
```

The nested lines below that heading are Elasticsearch's BM25 calculation: field weights,
term frequency, inverse document frequency, and length normalization. `explain_result`
requires Elasticsearch because the in-memory fallback does not reproduce its Dutch analyzer
or score tree.

Elasticsearch documents the server-side [RRF retriever](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/retrievers/rrf-retriever)
and [kNN retriever parameters](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/retriever.html).

## Test the search layer

```bash
python -m pytest tests/test_search.py -vv
```

Successful output ends with:

```text
6 passed
```

The tests use tiny fake embeddings and a fake Elasticsearch client. They validate E5 query
prefixing, RRF order and fallback, request construction, and readable explain output without
starting Docker or downloading a model.

## Interview talking points

- "I keep BM25 and dense retrieval separately inspectable, so I can show why a result appeared."
- "The primary hybrid path uses Elasticsearch RRF; a deterministic Python RRF path protects the demo from a licence or version mismatch."
- "The explain view turns the lexical score into field and term-level evidence instead of a black box."
