# Dataset design

`data/pages.json` contains 40 original, fictional help pages. Every page has an `id`, Dutch `title`,
80–150-word Dutch `body`, and a fictional `.example` URL. The corpus mixes private and business
customers across cards, accounts, mortgages, savings, payments, fraud, contact, and app/login.

The corpus intentionally contains hard near-duplicates: for example, `p01` is a blocked debit card,
`p02` is a blocked credit card, and `p03`/`p04` are the corresponding lost-card pages. A lexical
retriever can over-weight shared words such as “geblokkeerd” or “kaart”, while a vector retriever
can use the broader meaning. The query set also includes the short query `pas kwijt`, a typo (`phising`),
synonyms such as “afschrijving terug laten storten” for direct-debit chargeback, and an exact-term
query such as “betaalbatch” that gives lexical search a useful advantage. Three queries (`q07`, `q22`,
and `q23`) explicitly target business customers.

Each query has one of three task types:

- `navigational`: the user is trying to find a known destination or contact page;
- `informational`: the user wants an explanation or policy;
- `transactional`: the user wants to perform or fix an action.

Judgments use a 0–3 graded relevance scale: `3` is the direct answer page, `2` is a useful closely
related page or prerequisite, `1` is weak context or a plausible near-duplicate, and `0` is explicitly
non-relevant. Pages omitted from a query's `judgments` map are unjudged and should be treated as unknown
when computing evaluation metrics. This keeps the labels small enough to explain in an interview while
still making the ranking problem non-trivial.
