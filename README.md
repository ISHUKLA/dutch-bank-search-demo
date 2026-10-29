# Dutch Bank Search Demo

A small interview prototype for hybrid search over original, fictional Dutch bank help pages.
Python 3.10+, Docker, and local models; no paid cloud services.

## Current step: scaffold

The package, backend selector, Docker configuration, documentation, and CI smoke checks are ready.
The command prints configuration only. Search, embeddings, LLM generation, personalisation,
evaluation, the dashboard, monitoring, and the Java example will be added in later steps.

## Run the scaffold

From a terminal with Python 3.10 or newer:

```bash
git clone https://github.com/ISHUKLA/dutch-bank-search-demo.git
cd dutch-bank-search-demo
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m bank_search --backend offline
python -m unittest discover -s tests -v
```

The repository is private, so cloning requires your GitHub credentials.
On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Expected command output:

```text
Scaffold ready
Backend: offline
Embedding model: intfloat/multilingual-e5-small (384 dimensions)
Search implementation: pending
```

The tests finish with `Ran 3 tests` and `OK`.
The scaffold needs no Docker service, model download, or API key to run.
Initial package installation requires the Python build tools; the installed scaffold runs offline.

One flag selects the future search backend:

```bash
python -m bank_search --backend elasticsearch
```

For now this changes only the printed backend. It does not make a network connection.
The default when the flag is omitted is `offline`.

## Optional: start Elasticsearch

Install and start Docker with Compose support, then run:

```bash
docker compose up -d --wait
curl --fail http://localhost:9200
```

Success means the service becomes healthy and the JSON response contains version `8.19.23`.
The container has a 2 GB memory limit and a 512 MB Java heap. Allow at least 4 GB for Docker.
Authentication is disabled for this local fictional-data demo, with the port bound to `127.0.0.1`.
The free Basic license is selected explicitly. This configuration is for local development.
The first Docker image pull needs internet access.

```bash
docker compose down
```

Stopping the container preserves its data volume.
Image reference: [official Elastic image, 8.19.23](https://www.docker.elastic.co/r/elasticsearch/elasticsearch:8.19.23).
Setup reference: [Elastic Docker documentation](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/docker.html).

## Layout

```text
data/                     Fictional Dutch pages, queries, and relevance labels
src/bank_search/           Python package and command-line entry point
notebooks/                Future exploration and evaluation walkthroughs
tests/                    Automated checks
docs/                     Architecture and future demo/governance notes
java/                     Future small Java client example
.github/workflows/        Continuous integration
compose.yaml              Optional local Elasticsearch service
pyproject.toml            Python package configuration
```

## Working agreements

- Use fictional data only: no real bank names, branding, copied pages, or customer records.
- Keep page content and search queries in Dutch; code and comments in English.
- Use `intfloat/multilingual-e5-small`, 384 dimensions, with `query: ` and `passage: ` prefixes.
- Provide each Elasticsearch search capability through the same offline interface using `rank_bm25` and NumPy.
- Cache model files and document embeddings before the interview so the later offline demo needs no network.
- Add one requested step at a time, using complete, readable files.

See [the architecture plan](docs/architecture.md) for the remaining features.

## Interview talking points

- "I separate reusable Python code, fictional data, evaluation, and presentation so each part is easy to explain."
- "The backend defaults to offline; the shared interface will let me demonstrate the same pipeline without Elasticsearch."
- "CI starts with a clean installation and checks the command-line contract before more features are added."
