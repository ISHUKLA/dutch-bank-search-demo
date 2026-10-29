# Step 10: continuous integration

Every push and pull request runs `pytest` with `USE_OFFLINE=true`. This means CI exercises the
same Elasticsearch-free `rank_bm25` and NumPy path used by the interview fallback; it does not
start Docker or depend on an Elasticsearch licence. The same workflow also compiles the
dependency-free Java example with Java 17.

The workflow restores a cache of the public `intfloat/multilingual-e5-small` model. When the cache
is empty, it downloads the model once, then switches `HF_HUB_OFFLINE=true` before the test run.
This keeps the relevance test real while making routine CI runs reproducible and independent of
model-host availability.

`tests/test_metrics.py` verifies the documented grading example: grades `[0, 3, 2, 1, 0]` give
RR `0.5`, AP `0.639`, and linear-gain nDCG@5 `0.698`.

`tests/test_relevance_regression.py` runs the actual offline hybrid search over all 25 labelled
queries. Its approved mean nDCG@10 is approximately `0.797`; the guard fails below `0.79`.
The small margin permits minor platform variation but catches a material ranking regression.

## Run the same guard locally

After caching the E5 model in Step 4, run:

```bash
USE_OFFLINE=true HF_HUB_OFFLINE=true python -m pytest -q
```

Successful output ends with:

```text
38 passed
```

## Interview talking points

- "Every push proves the portable fallback path still works; CI does not need a running search cluster."
- "The relevance gate uses the real model and judged queries, not a mocked score."
- "A cached public model makes the test reliable while avoiding a network dependency during routine runs."
