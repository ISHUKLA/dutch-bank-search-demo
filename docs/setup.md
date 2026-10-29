# Step 1: setup

## 1. Install Python dependencies

Use Python 3.10 or newer. Python 3.11 is recommended for this prototype.
On Intel Macs, use Python 3.10–3.12: PyTorch ended native Intel Mac wheels after 2.2.x,
and these wheels do not support Python 3.13. Linux and Apple Silicon can use newer PyTorch wheels.

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -e .
python -m pip check
```

Use `.venv\Scripts\Activate.ps1` to activate on Windows PowerShell.
`pip check` should print `No broken requirements found.`
The editable install makes `src/config.py` importable as `config` from the scripts.
The requirements pin direct dependencies, not the entire transitive dependency tree.
Transformers is pinned for compatibility; the Intel Mac markers select PyTorch 2.2.2 and NumPy 1.26.4.

Sources: [PyTorch's Intel Mac support change](https://github.com/pytorch/pytorch/issues/114602),
[published PyTorch 2.2.2 wheels](https://pypi.org/project/torch/2.2.2/).

## 2. Configure the environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `ES_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `ES_USERNAME` | empty | Basic authentication username |
| `ES_PASSWORD` | empty | Basic authentication password |
| `USE_OFFLINE` | `true` | Skip Elasticsearch completely when true |

Leave both credentials empty for the Docker configuration below. For an authenticated server,
set both. Do not put credentials in the URL. The checker never prints credentials or raw connection errors.
Boolean values accept `true/false`, `1/0`, `yes/no`, and `on/off`, ignoring case and outer whitespace.
Any other value is rejected so a typo cannot silently choose the wrong backend.

Export the variables directly or copy `.env.example` to `.env`, edit it, and load it:

```bash
cp .env.example .env
set -a
. ./.env
set +a
```

Copy the template only on first setup; keep an existing `.env` with your settings.
Python does not auto-load `.env`. Restart a running Python process after changing its environment.

## 3. Start a single Elasticsearch node with a trial

Choose one startup method; they all use port 9200.
Docker must be installed and running. Allow at least 4 GB of memory for Docker.

### Option A: the repository's Compose file

```bash
docker compose up -d --wait
```

It pins Elasticsearch 8.19.23, selects a trial licence, persists data, and waits for both
cluster health and the licence endpoint. The licence endpoint can become ready slightly later.
The container has a 2 GB limit and a 512 MB heap. Authentication is disabled and port 9200
is bound only to `127.0.0.1`; this is local development configuration for fictional data.

### Option B: the equivalent standalone Docker command

Use this instead of Compose:

```bash
docker run --detach --name dutch-bank-es \
  --publish 127.0.0.1:9200:9200 \
  --memory 2g \
  --env discovery.type=single-node \
  --env xpack.security.enabled=false \
  --env xpack.license.self_generated.type=trial \
  --env xpack.ml.enabled=false \
  --env node.store.allow_mmap=false \
  --env 'ES_JAVA_OPTS=-Xms512m -Xmx512m' \
  --volume dutch-bank-es-data:/usr/share/elasticsearch/data \
  docker.elastic.co/elasticsearch/elasticsearch:8.19.23
```

This prints a container ID before the server is ready. Wait for a successful health response:

```bash
curl --fail 'http://localhost:9200/_cluster/health?wait_for_status=yellow&timeout=60s'
curl --fail http://localhost:9200/_license
```

If the connection is refused or the licence endpoint returns 404 during startup, retry after a few seconds.
Success has `timed_out: false` and a `yellow` or `green` cluster status, plus an active licence response.
Stop with `docker stop dutch-bank-es`; restart with `docker start dutch-bank-es`.

The trial lasts 30 days and enables Elasticsearch's built-in RRF retriever.
Our later Python RRF implementation will keep the offline demo independent of the trial.
Sources: [Elastic's Docker tutorial](https://www.elastic.co/search-labs/tutorials/install-elasticsearch/docker),
[8.19 licence settings](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/license-settings.html).

### Option C: Elastic's start-local

Elastic's official command installs Elasticsearch and Kibana with a trial:

```bash
curl -fsSL https://elastic.co/start-local | sh
```

For this small demo, prefer a pinned version and Elasticsearch only:

```bash
curl -fsSL https://elastic.co/start-local | sh -s -- -v 8.19.23 --esonly
```

Use one command, not both. The unpinned command uses the latest server version; this demo
deliberately checks for 8.x so the pinned option matches its tested target.
`start-local` generates a password for the `elastic` user and saves it in `elastic-start-local/.env`.
From the repository root, map its variables to this project's settings:

```bash
. ./elastic-start-local/.env
export ES_URL="$ES_LOCAL_URL"
export ES_USERNAME=elastic
export ES_PASSWORD="$ES_LOCAL_PASSWORD"
export USE_OFFLINE=false
python scripts/check_setup.py
```

Keep the generated directory local; `.gitignore` excludes it.
Stop with `(cd elastic-start-local && ./stop.sh)` and restart with
`(cd elastic-start-local && ./start.sh)`.
Sources: [Elastic local-development quickstart](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/local-development-installation-quickstart),
[start-local options](https://github.com/elastic/start-local).

## 4. Run the check

For the unauthenticated Compose or standalone Docker option:

```bash
ES_URL=http://localhost:9200 ES_USERNAME= ES_PASSWORD= USE_OFFLINE=false \
  python scripts/check_setup.py
```

Expected output for a fresh instance:

```text
Mode: elasticsearch
Elasticsearch version: 8.19.23
Licence type: trial
Licence status: active
Elasticsearch check: OK
```

The script reads `info()` and `license.get()`, uses a five-second timeout per request,
disables retries, and closes the client. `OK` means the connection and licence API checks passed;
it does not execute a search or prove that every RRF request will work.
A non-trial active licence is reported with a note instead of being misrepresented as a trial.
The read calls need the `monitor` cluster privilege on an authenticated server.
Sources: [Python authentication](https://www.elastic.co/guide/en/elasticsearch/client/python-api/8.19/connecting.html),
[licence API](https://www.elastic.co/guide/en/elasticsearch/reference/8.19/get-license.html).

To run without Elasticsearch:

```bash
USE_OFFLINE=true python scripts/check_setup.py
```

Expected output:

```text
Mode: offline
Elasticsearch check: skipped
```

No Elasticsearch client import, connection, or licence is required for this branch.
The actual offline search pipeline comes in a later step.
Connection, credential, inactive-licence, or version errors return a non-zero exit code with guidance.

## Existing Basic licence or expired trial

Changing the Compose setting does not replace a licence already stored in a data volume.
If the checker prints `basic`, activate a trial without deleting existing data:

```bash
curl --fail --request POST \
  'http://localhost:9200/_license/start_trial?acknowledge=true'
```

For `start-local`, include `--user "$ES_USERNAME:$ES_PASSWORD"` in the same command.
A successful activation includes `"trial_was_started": true`. Then rerun the checker.
If this cluster already used its trial for Elasticsearch 8, another trial cannot be started this way.
Use `USE_OFFLINE=true` if the trial is unavailable; do not delete data to try to renew it.
Source: [Elastic trial activation API](https://www.elastic.co/guide/en/elasticsearch/reference/current/start-trial.html/).

## Tests and shutdown

```bash
python -m pytest -q
docker compose down
```

The setup tests simulate server responses and failure modes without a model download.
CI also starts the pinned Elasticsearch image and checks its real version and trial licence.
`docker compose down` stops the Compose service and preserves its data volume.

## Interview talking points

- "I check server compatibility and the active licence before demonstrating Elasticsearch RRF."
- "Environment variables keep credentials out of code, while one flag selects offline mode."
- "I test setup failures and the real Docker connection, so environment problems are visible before the demo."
