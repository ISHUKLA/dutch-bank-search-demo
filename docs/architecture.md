# Architecture plan

## Implemented in this step

- An installable Python package and pinned setup dependencies in `requirements.txt`.
- Shared environment settings in `src/config.py`, including `USE_OFFLINE`.
- An optional local Elasticsearch trial container and a version/licence checker.
- CI setup tests, plus a real Elasticsearch connection check.
- BM25, E5 vector search, hybrid RRF, and explicit audience-based reranking with Elasticsearch and pure-Python paths.
- A 25-query benchmark with RR, AP, linear-gain nDCG@10, Recall@10, query-type slices, and hybrid failure review.

The backend flag selects the implemented search backend. The Elasticsearch hybrid request uses
the RRF retriever; if the node does not support it, the client computes the same RRF formula.

## Planned pipeline

1. Create original fictional Dutch help pages and separate Dutch evaluation queries.
2. Enrich pages with two-sentence summaries and structured metadata, then validate fields and source IDs.
3. Encode pages with `passage: ` using `intfloat/multilingual-e5-small` (384 dimensions), then
   store normalized vectors with the title and summary. Query encoding follows in the search step.
4. Retrieve lexical and vector candidates through one of two interchangeable backends:
   Elasticsearch BM25 plus vector search, or `rank_bm25` plus NumPy cosine similarity.
5. Fuse the two ranked lists with Elasticsearch RRF or the equivalent shared Python reciprocal rank fusion (RRF).
6. Apply a transparent segment adjustment chosen explicitly by the demo user. Exact audience
   matches receive the configured weight; shared-audience pages receive half.
7. Generate a local LLM answer grounded in retrieved pages, showing sources and handling missing evidence.
8. Display results, scores, timings, segment controls, and evaluation results in a small Python dashboard.

Keep RRF, segment logic, evaluation, and summarisation shared across backends.
Each Elasticsearch feature must have an offline equivalent before it is added to the demo.
BM25 analyzers and approximate vector retrieval can produce different rankings; evaluate these differences.
Do not promise identical scores across backends.

## Evaluation, governance, and monitoring

- Evaluate BM25, vector, hybrid, and personalised runs using nDCG@10, MAP, MRR, and Recall@k.
- Document relevance grades, binary thresholds, cutoff conventions, and handling of queries with no relevant pages.
- Keep evaluation queries separate from tuning examples and compare results by explicit user segment.
- Record model/data versions and generation settings; validate LLM metadata and cite generated-answer sources.
- Show retrieved text as evidence, not instructions; include unsupported-answer and prompt-injection checks.
- Use synthetic segments without inferring sensitive personal characteristics.
- Measure latency, empty results, backend errors, and fallback use. Avoid storing raw query text by default.
- Add focused CI checks for ranking, fusion, evaluation, and backend behaviour when those features are implemented.
- Add a small Java client example and a 15-minute demo script in later steps.

## Laptop and offline operation

The default backend is `offline`. The final offline path will use `rank_bm25`, NumPy,
and cached local model files. Download model weights and prepare embeddings before the interview.
Do not substitute random or hash vectors for the required E5 embeddings.
Select a small local generation model and pin dependencies when implementing those features.

The setup tests do not download a model. The first real indexing run downloads the E5 model unless it is cached locally.
The optional Elasticsearch container uses a 30-day trial to enable the built-in RRF retriever.
The offline implementation provides Python RRF without depending on this trial.
