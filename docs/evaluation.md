# Step 7: evaluation

`src/metrics.py` implements four small, explicit retrieval metrics:

- reciprocal rank (RR): the inverse rank of the first grade-1-or-higher result;
- average precision (AP): binary precision at each relevant result, divided by all known relevant pages;
- linear-gain nDCG@10: grade divided by `log2(rank + 1)`, normalised by the ideal judged ordering;
- recall@10: known relevant pages retrieved in the first ten results.

For the requested worked example, grades `[0, 3, 2, 1, 0]` with three relevant documents
produce RR `0.500`, AP `0.639`, nDCG@5 `0.698`, and Recall@5 `1.000`.

## Run the offline evaluation

First cache the required E5 model by completing Step 4. Then run:

```bash
USE_OFFLINE=true python src/evaluate.py
```

The evaluator runs all 25 queries through `bm25`, `vector`, `hybrid`, and
`hybrid_segment`. It prints overall means, a query-type breakdown, and the three lowest
hybrid nDCG@10 rows with an evidence-based short diagnosis. It saves the full per-query
report to `results/metrics.json`.

Successful output starts like this:

```text
Mean metrics (25 queries)
Method                  RR      AP   nDCG@10  Recall@10
bm25                 ...
vector               ...
hybrid               ...
hybrid_segment       ...
```

Offline mode ends with an explicit `_rank_eval` skip because it deliberately makes no
Elasticsearch connection.

## Compare local BM25 with Elasticsearch `_rank_eval`

Start and index Elasticsearch first, then run:

```bash
docker compose up -d --wait
USE_OFFLINE=false python src/index.py --recreate
USE_OFFLINE=false python src/evaluate.py
```

The live run sends the exact same 25 lexical queries and manual ratings to Elasticsearch
`_rank_eval` using mean reciprocal rank at ten with relevance threshold one. It prints:

```text
ES _rank_eval MRR@10: 0.xxx
Local BM25 mean RR@10: 0.xxx
Match: True
```

Both paths treat returned, unjudged pages as grade zero. This is intentional: it matches the
default Elasticsearch rank-evaluation treatment and makes the RR comparison meaningful.
Elasticsearch's [ranking evaluation API documentation](https://www.elastic.co/docs/reference/elasticsearch/rest-apis/search-rank-eval)
describes the request ratings, MRR metric, and per-query details.

## Synthetic segments and limitations

Every query now declares an explicit synthetic segment. Retail scenarios are marked
`private`; `q07`, `q22`, and `q23` are marked `business`. The evaluator does not infer a
segment from text or user behaviour. The labels are intentionally small and incomplete; an
unjudged document scoring zero is a conservative benchmark convention, not a claim that it
is truly irrelevant.

## Test the evaluator

```bash
python -m pytest tests/test_metrics.py tests/test_evaluate.py -vv
```

Successful output ends with:

```text
4 passed
```

## Interview talking points

- "I use graded nDCG for answer quality and binary RR, AP, and recall for findability and coverage."
- "The query-type split shows whether gains come from navigation, information seeking, or actions—not just an aggregate average."
- "Elasticsearch `_rank_eval` independently verifies the local BM25 MRR calculation against the same labels."
