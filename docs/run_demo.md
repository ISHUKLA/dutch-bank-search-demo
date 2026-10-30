# Step-by-step demo run guide

Use this guide to run the fictional Dutch help-search demo from Terminal on the interview laptop.
The recommended walkthrough uses the offline backend, so Elasticsearch and Docker are optional.

## Recommended: offline walkthrough

Run each command from the project root, one at a time.

### 1. Open the project and activate its Python environment

On the configured Mac, run:

```bash
cd "/Users/coralieroland/Documents/Codex/2026-10-29/demo/Rabobank NLP"
source .venv/bin/activate
python --version
```

Expected version on this laptop:

```text
Python 3.12.11
```

If you cloned the repository into another folder, change to that folder instead. If `.venv` does
not exist on this Mac, create it with the already-installed Python 3.12 environment:

```bash
/Users/coralieroland/miniconda3/envs/rag-env/bin/python -m venv .venv
source .venv/bin/activate
```

For a fresh environment, install the project dependencies:

```bash
python -m pip install -r requirements.txt -e .
```

### 2. Confirm offline mode

```bash
USE_OFFLINE=true python scripts/check_setup.py
```

Expected output:

```text
Mode: offline
Elasticsearch check: skipped
```

### 3. Warm up the embedding model and inspect the corpus

```bash
USE_OFFLINE=true python src/index.py
```

Expected output begins with:

```text
Backend: offline
Document count: 40
Sample document:
```

The first run downloads `intfloat/multilingual-e5-small` if it is not already cached. Do this
while internet access is available and before the interview. Later commands can run without
network access once the model is cached.

### 4. Compare keyword, vector, and hybrid search

```bash
USE_OFFLINE=true python src/search.py --query "pas kwijt"
```

The command prints five results for BM25, vector search, and hybrid reciprocal-rank fusion side
by side. Point out how lexical matching finds exact wording while vectors can find similar meaning.

### 5. Compare private and business results

```bash
USE_OFFLINE=true python src/search.py --personalisation-demo
```

The same query, `rekening openen`, is shown for both segments. The output includes the audience
and applied segment boost so the change can be inspected.

### 6. Run the judged evaluation

```bash
USE_OFFLINE=true python src/evaluate.py
```

This evaluates 25 queries with BM25, vector, hybrid, and hybrid plus segment adjustment. It prints
mean metrics, a breakdown by query type, and the three weakest hybrid queries. The full results
are saved to `results/metrics.json`. Elasticsearch `_rank_eval` is skipped in offline mode.

### 7. Build and open the dashboard

```bash
USE_OFFLINE=true python src/report.py
open results/report.html
```

The report is a standalone HTML file with a chart, a query-type table, and three plain-language
product insights. It does not need a web server.

### 8. Show governance and the timed narrative

Open these files from the project root:

```bash
open docs/model_card.md
open docs/demo_script.md
```

The model card covers risks, privacy, explainability, and monitoring. The demo script has the
15-minute timing, Dutch opening, and likely interviewer questions.

### 9. Optional: run the offline CI checks

```bash
USE_OFFLINE=true python -m pytest -q
```

The workflow tests metrics, regression quality, and the generated report without contacting
Elasticsearch. Run this before the interview if you want to show the regression guard.

## Optional: run against Elasticsearch

Use this path if Docker is available and you want to show the live Elasticsearch RRF retriever.
The local compose file starts a single node with a trial licence and no authentication.

```bash
docker compose up -d --wait
USE_OFFLINE=false python scripts/check_setup.py
USE_OFFLINE=false python src/index.py --recreate
USE_OFFLINE=false python src/search.py --query "pas kwijt"
USE_OFFLINE=false python src/search.py --personalisation-demo
USE_OFFLINE=false python src/evaluate.py
USE_OFFLINE=true python src/report.py
open results/report.html
```

The setup check should print Elasticsearch version, `Licence type: trial`, `Licence status: active`,
and `Elasticsearch check: OK`. The live evaluation also calls Elasticsearch `_rank_eval` and reports
whether its BM25 MRR agrees with the local calculation. If Docker or the trial licence is unavailable,
switch back to the offline walkthrough above.

Stop Elasticsearch when finished:

```bash
docker compose down
```

## Quick troubleshooting

- **`python3.11: command not found`:** activate `.venv` and use `python`; this laptop's environment
  uses Python 3.12.11.
- **`No such file or directory` while changing folders:** use the quoted project path above; the
  folder name contains a space.
- **Model download or Hugging Face error:** run Step 3 once with internet access, then retry. Do not
  set `HF_HUB_OFFLINE=true` until the model has been cached.
- **Elasticsearch connection error:** confirm Docker is running, then use `docker compose up -d --wait`,
  or use `USE_OFFLINE=true` for the no-Docker demo.

