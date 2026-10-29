# 15-minute interview demo script

## Dutch opening (30 seconds)

“Ik laat een klein maar volledig reproduceerbaar zoekprototype voor fictieve bankhulp zien.
Het combineert exacte zoekwoorden met meertalige semantische zoekresultaten, en het werkt ook
zonder Elasticsearch. Daarna laat ik zien hoe ik kwaliteit, uitlegbaarheid, privacy en regressies
meet, omdat een goed zoekresultaat alleen waardevol is als het ook controleerbaar blijft.”

## Timed walkthrough

| Time | Show | What to say |
| --- | --- | --- |
| 0:00–0:30 | This opening and the repository root | “This is fictional Dutch content only; the goal is a clear retrieval demo, not banking advice or an automated decision.” |
| 0:30–1:30 | notebooks/walkthrough.ipynb, setup and dataset sections | “One offline switch removes the Elasticsearch dependency. The data has deliberate near-duplicates, typos, synonyms, and business cases so ranking is not artificial.” |
| 1:30–3:00 | Enrichment and index sections | “The LLM produces short summaries and controlled metadata; local validation rejects unknown labels and invented numeric claims. The index combines Dutch text analysis with 384-dimensional E5 vectors.” |
| 3:00–6:00 | Run USE_OFFLINE=true python src/search.py --query "pas kwijt" | “Keyword search catches literal wording, vector search catches meaning, and RRF combines ranks instead of trying to compare unrelated score scales. Offline mode uses the same idea with BM25 and NumPy.” |
| 6:00–7:30 | Run USE_OFFLINE=true python src/search.py --personalisation-demo | “The segment is chosen explicitly, never inferred. I retain the original score and adjustment, so the ranking change is auditable.” |
| 7:30–10:00 | results/metrics.json and results/report.html | “Across 25 judged queries, combined retrieval leads AP and recall. The dashboard translates that into: the best page is in the top three for 9.6 of 10 searches.” |
| 10:00–11:30 | docs/model_card.md | “I call out summary hallucination, unfair tailoring, stale content, and privacy before deployment. The monitoring thresholds turn these into operating checks.” |
| 11:30–12:45 | .github/workflows/ci.yml and tests/test_relevance_regression.py | “Every push runs the real offline benchmark and blocks a meaningful nDCG drop; this protects the laptop fallback too.” |
| 12:45–13:45 | java/HybridSearchExample.java | “The Java example uses only the standard HTTP client and sends the identical RRF structure. Python prepares the E5 vector so embedding behaviour stays consistent.” |
| 13:45–15:00 | Architecture diagram and closing | “The main trade-off is intentional: a small, inspectable demo over a feature-rich opaque system. Next I would add cited local answers, operational signals, and broader human judging.” |

## Hard interviewer questions

1. **Why use RRF instead of adding BM25 and vector scores?**  
   The score ranges mean different things. RRF combines rank positions, which is stable and easy to explain; I keep both individual lists for diagnosis.

2. **Why are E5 prefixes important?**  
   The model was trained with query and passage roles. Omitting them can reduce retrieval quality because the input format no longer matches training.

3. **Is the offline fallback identical to Elasticsearch?**  
   No. It has the same retrieval stages and RRF formula, but its tokenisation and exact vector retrieval differ from Elasticsearch's Dutch analysis and approximate kNN. That is why I evaluate both rather than promise identical ranks.

4. **Why is the labelled dataset so small?**  
   It is an interview-sized, reproducible test set. In production I would sample real consented queries, use multiple assessors, measure agreement, and keep a held-out regression set.

5. **Could personalisation be unfair?**  
   Yes. It can hide broadly useful pages. Here the segment is explicit and synthetic, the boost is visible, and results show it currently performs worse overall; I would not enable it by default.

6. **How do you prevent an LLM from inventing a limit or deadline?**  
   Summaries use a controlled schema and a local numeric-grounding check, but those are guardrails, not proof. Production output needs source citations, review, and a refusal path for unsupported answers.

7. **What happens when content becomes stale?**  
   Retrieval can still rank a stale page perfectly, so every page needs an owner and review date. The model card sets a 30-day review alert and a withdrawal process.

8. **How would this scale and remain private?**  
   Elasticsearch handles indexed retrieval; I would cache embeddings, track latency and fallback rate, minimise logs, avoid raw query storage by default, and complete privacy/security reviews before any customer data is processed.

## Preparation checklist

- Cache intfloat/multilingual-e5-small by running Step 4 once while online.
- Open results/report.html, notebooks/walkthrough.ipynb, and docs/model_card.md before the interview.
- Run USE_OFFLINE=true HF_HUB_OFFLINE=true python -m pytest -q and keep the passing output available.
