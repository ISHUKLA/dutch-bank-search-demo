# Model card: fictional Dutch bank help search prototype

## Purpose and scope

This laptop prototype helps a visitor find fictional Dutch help pages. It compares keyword,
meaning-based, combined, and optional audience-tailored retrieval. It is a demonstration of
search design, not a decision system: it must not approve products, assess creditworthiness,
detect fraud, give regulated advice, or replace a human support channel.

## Data and models

The corpus contains 40 original fictional Dutch help pages and 25 manually judged fictional
queries. No customer records, production queries, real bank branding, or copied content are
included. Page enrichments are either a committed reviewed cache or optional structured LLM
output; summaries are two sentences and metadata comes from a controlled vocabulary.

Retrieval uses Dutch-analyzed BM25 plus `intfloat/multilingual-e5-small` (384-dimensional,
locally run embeddings). Elasticsearch RRF combines the two result lists when available; a
`rank_bm25` and NumPy implementation is the offline fallback. An optional `private` or
`business` setting reranks pages using their declared audience. It is never inferred from a
person, their behaviour, or their query.

## Evaluation snapshot

On the 25-query offline benchmark, combined retrieval had the highest AP (0.618) and Recall@10
(0.820); meaning-based retrieval had the highest nDCG@10 (0.799). The audience-tailored variant
was weaker overall (nDCG@10 0.745), so it remains an optional demonstration control. The combined
method placed a highest-graded page in the top three for 24 of 25 queries (96%). Known-page
navigation remains weak: only one of two navigation queries had the best page in the top three.
These are small synthetic results, not a production-performance claim.

## Known limitations and risks

- **Hallucinated numbers in summaries:** an LLM could invent a fee, limit, deadline, or wait time.
  The validator rejects digit-based numbers absent from source text; human review and source links
  remain required before publishing any generated summary.
- **Unfair personalisation:** a private/business label can suppress a generally helpful page or
  encode an inappropriate proxy. The segment is explicit, synthetic, optional, logged as a ranking
  factor, and evaluated separately. Do not use protected, sensitive, or inferred characteristics.
- **Stale content:** search can accurately surface an out-of-date help page. Every production page
  needs an owner, reviewed-at date, and withdrawal process; retrieval is not proof of policy accuracy.
- **Benchmark gaps:** labels are limited, unjudged retrieved pages are scored as zero, and the
  corpus does not represent real language variation, accessibility needs, or adversarial inputs.

## Explainability and human oversight

Each result keeps its source page ID, title, URL, method, score, and—when tailored—the base score
and audience adjustment. The demo shows lexical, semantic, and combined rankings side by side.
Elasticsearch's `explain` endpoint exposes term-level lexical scoring; client-side RRF is a short,
inspectable formula. Surface source links with any future generated answer, provide contact escalation,
and do not present a summary as a binding policy statement.

## Privacy Impact Assessment prompts

Before any real deployment, document the search purpose, lawful basis, controller/processor roles,
data flow, hosting location, retention, and access controls. Keep raw query logging off by default;
prefer aggregated counts and short, documented retention for debugging. Do not combine search logs
with account, transaction, behavioural, or special-category data unless a separate necessity and
proportionality assessment supports it. Define deletion/access request handling, encryption in
transit and at rest, role-based access, vendor/model transfer assessment, and a human escalation
path. Obtain privacy, security, legal, and accessibility review before using customer data.

## Monitoring plan

| Check | Frequency | Alert / action |
| --- | --- | --- |
| nDCG@10, Recall@10, top-3 rate; overall and by segment/type | Every release; weekly with new labels | Block release if nDCG@10 or Recall@10 falls >0.05 from approved baseline; investigate a segment/type gap >0.10. |
| Empty results, errors, offline-fallback use, and p95 latency | Every 15 minutes | Investigate errors >1%, empty results >2%, fallback >5% when Elasticsearch is expected, p95 >1.5s; page at >5% errors or p95 >3s. |
| Summary validation and source/metadata coverage | Every enrichment or content build | Block publication on any invented numeric token, unknown metadata value, missing source, or cache/page mismatch. |
| Content freshness and user feedback/escalations | Daily; owner review monthly | Notify owner at 30 days without review; withdraw or correct content confirmed stale or harmful. |

Thresholds are conservative starting points for this prototype. A production owner should set and
approve baselines from real, privacy-reviewed traffic before alerting or automated action.
