# Step 6: personalisation

`hybrid_search` now accepts one explicit segment parameter: `"private"`, `"business"`,
or `None`. It applies the adjustment after hybrid retrieval, so BM25, E5 vector search,
and RRF remain inspectable and unchanged.

The configured `SEGMENT_BOOST_WEIGHT` is `0.01` by default. A page tagged with the exact
audience receives the full boost. A page tagged `both` is applicable to either audience
and receives half the boost. Pages tagged for the other audience receive no boost.

Each personalised result retains `base_score`, `segment_boost`, and final `score`. That makes
the adjustment easy to audit in a dashboard or explanation: this prototype never infers a
segment from queries, behaviour, or personal data.

## Run the comparison

```bash
USE_OFFLINE=true python src/search.py --personalisation-demo
```

Successful output begins like this:

```text
Query: rekening openen
Segment boost weight: 0.010 (both: half weight)

Rank Private user                                                       | Business user
----------------------------------------------------------------------------------------------------------------------------------------------------------
1    p11      Betaalrekening openen                private   +0.010 | 1    p12      Zakelijke betaalrekening aanvragen   business  +0.010
```

To make the adjustment more or less prominent for the demo, set a non-negative environment
variable before running the script:

```bash
SEGMENT_BOOST_WEIGHT=0.005 USE_OFFLINE=true python src/search.py --personalisation-demo
```

## Use from Python

```python
private_results = hybrid_search("rekening openen", segment="private")
business_results = hybrid_search("rekening openen", segment="business")
neutral_results = hybrid_search("rekening openen", segment=None)
```

The segment is validated. Any other value raises `ValueError` instead of silently changing a
ranking. For a segment-aware run, the search retrieves up to 50 hybrid candidates before
applying the boost, rather than attempting to personalise only the initial top five.

## Test the feature

```bash
python -m pytest tests/test_search.py -vv
```

Successful output ends with:

```text
10 passed
```

The tests verify exact-audience and `both` boosts, invalid segments, and the 50-result
candidate window used for reranking. They do not require Elasticsearch or the E5 download.

## Interview talking points

- "Personalisation is an explicit, synthetic user choice—not an inference about a person."
- "I rerank a wider hybrid candidate set, then retain the base score and the boost for auditability."
- "A shared-audience page remains useful to both segments, while the exact audience gets the stronger signal."
