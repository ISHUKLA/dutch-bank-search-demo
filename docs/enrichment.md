# Step 3: LLM enrichment

`src/enrich.py` produces or validates one enrichment record for every fictional help page.
Each record contains:

- a Dutch summary of exactly two complete sentences;
- `audience`, `product`, `topic`, and `intent` metadata;
- three Dutch `example_queries`.

The controlled vocabulary lives in `CONTROLLED_VOCABULARY` in `src/enrich.py`.
The validator rejects an unknown label instead of silently accepting a synonym. This gives filters,
personalisation, evaluation slices, and the future dashboard a stable schema.

## Default: committed offline cache

The demo does not need an API key or a network call:

```bash
python src/enrich.py
python src/enrich.py --page-id p03
```

Expected output for the first command:

```text
Enrichment ready: 40 pages (source: cache)
```

`data/enrichment_cache.json` contains all 40 records and is validated against `data/pages.json`
every time the command runs. This makes the interview demo deterministic.

## Optional live refresh

Set `OPENAI_API_KEY` when you want to generate all enrichments through a live model call:

```bash
export OPENAI_API_KEY='your-key'
export OPENAI_ENRICHMENT_MODEL='gpt-4.1-mini'
python src/enrich.py
```

When an API key is present, `src/enrich.py` uses the OpenAI Responses API with a strict JSON Schema and then runs the local
validator before replacing the cache. The output is never trusted only because it has a valid shape:
the controlled vocabulary, page ID, two-sentence requirement, three-query requirement, and
number-grounding rule are all checked locally. The model name is configurable so a future demo
can use an account-approved model without changing code.

Use `python src/enrich.py --cache-only` to force the committed cache while an API key is exported.

The OpenAI Structured Outputs API supports JSON Schema and enums, which constrains the API response;
the local validation provides a second, application-owned guardrail. [Official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Number-grounding rule

The summary may not contain a numeric token that is absent from the source page body. For example,
a summary of a card page cannot claim a new limit, fee, wait time, or deadline. The current cache
avoids numeric claims in summaries, so its summaries are safe against this rule. The rule deliberately
checks digits rather than interpreting Dutch number words; it is a simple, explainable guardrail for
the prototype rather than a full factuality system.

## Run tests

```bash
python -m pytest -q
```

Successful output includes:

```text
17 passed
```

The tests prove that the cache covers all pages, unknown labels fail validation, invented numbers fail
validation, live-mode selection, and cache-only selection.

## Interview talking points

- "The LLM adds concise summaries and retrieval metadata, but a fixed vocabulary keeps the fields usable and auditable."
- "The committed cache makes the demo reproducible without an API key, model call, or network connection."
- "Structured output is only the first guardrail; the application revalidates labels, shape, and numeric claims locally."
