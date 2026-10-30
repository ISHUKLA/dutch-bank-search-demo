# Architecture plan

## Implemented in this step

- An installable Python package and pinned setup dependencies in `requirements.txt`.
- Shared environment settings in `src/config.py`, including `USE_OFFLINE`.
- An optional local Elasticsearch trial container and a version/licence checker.
- Offline CI with metric unit tests and a real hybrid relevance-regression check.
- BM25, E5 vector search, hybrid RRF, and explicit audience-based reranking with Elasticsearch and pure-Python paths.
- A 25-query benchmark with RR, AP, linear-gain nDCG@10, Recall@10, query-type slices, and hybrid failure review.
- A self-contained Product Owner report that presents comparison data and plain-language recommendations.
- A model card describing purpose, data, limitations, privacy prompts, and monitoring thresholds.
- A dependency-free Java 11+ client that sends the live Elasticsearch RRF request.

The backend flag selects the implemented search backend. The Elasticsearch hybrid request uses
the RRF retriever; if the node does not support it, the client computes the same RRF formula.

## End-to-end flow

![Architecture diagram: fictional content through enrichment, indexing, hybrid search, evaluation, and monitoring](architecture.svg)

The optional private/business adjustment happens after hybrid retrieval and is included in the
evaluation and monitoring slices. A future extension may add local, source-grounded answer
generation; it is intentionally outside this retrieval-first prototype.

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
- Add a 15-minute demo script in a later step.

## Laptop and offline operation

The default backend is `offline`. The final offline path will use `rank_bm25`, NumPy,
and cached local model files. Download model weights and prepare embeddings before the interview.
Do not substitute random or hash vectors for the required E5 embeddings.
Select a small local generation model and pin dependencies when implementing those features.

The setup tests do not download a model. The first real indexing run downloads the E5 model unless it is cached locally.
The optional Elasticsearch container uses a 30-day trial to enable the built-in RRF retriever.
The offline implementation provides Python RRF without depending on this trial.
