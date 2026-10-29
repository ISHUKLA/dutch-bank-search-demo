# Step 8: Product Owner dashboard

`src/report.py` reads the saved `results/metrics.json` file and writes one standalone HTML
file: `results/report.html`. The report embeds its chart code, CSS, data, and JavaScript, so it
can be opened from Finder or a browser without a Python server, Elasticsearch, or internet access.

## Create the report

Run Step 7 first to refresh the evaluation data, then run:

```bash
USE_OFFLINE=true python src/report.py
```

Successful output:

```text
Saved self-contained report: /path/to/dutch-bank-search-demo/results/report.html
```

Open `results/report.html` in a browser. It includes:

- a bar chart that compares how often the right page appears in the top three and how often useful pages are shown;
- a table grouped by the three search needs: finding a known page, understanding a topic, and completing an action;
- three Product Owner insights in a consistent finding → so what → recommendation format.

The report turns ranking quality into a direct statement such as “the right page appears in the
top 3 for 9.6 out of 10 searches.” This top-three rate is calculated from the highest-rated page
in each of the 25 judged searches; it complements the detailed quality score without asking a
non-technical reader to interpret it.

## Validate the report

```bash
python -m pytest tests/test_report.py -vv
```

Successful output ends with:

```text
1 passed
```

## Interview talking points

- "The report uses the evaluation artifact as its only input, so the visual story is tied to a reproducible benchmark."
- "I translate search quality into how often someone sees the right page in the first three results."
- "The recommendation is deliberately cautious: improve known-page navigation and validate customer tailoring before broad rollout."
