# Java hybrid-search client

`HybridSearchExample.java` is a Java 11+ example with **no dependencies**. It uses only the
JDK `HttpClient` to send the same Elasticsearch RRF request as `src/search.py`.

## Run it

First start and index Elasticsearch:

```bash
docker compose up -d --wait
USE_OFFLINE=false python src/index.py --recreate
```

Create the required E5 query vector with the existing Python code. The `query: ` prefix remains
in the Python embedding path, so Java does not risk creating an incompatible vector:

```bash
export ES_QUERY_VECTOR="$(USE_OFFLINE=true HF_HUB_OFFLINE=true PYTHONPATH=src python -c "from search import embed_query; import json; print(json.dumps(embed_query('pas kwijt').tolist()))")"
```

Compile and run:

```bash
javac java/HybridSearchExample.java
java -cp java HybridSearchExample "pas kwijt"
```

The GitHub workflow also compiles this source with Temurin Java 17 on every push.

Successful output begins like this:

```text
Query: pas kwijt
HTTP 200
{"took":...
```

Set `ES_URL`, `ES_USERNAME`, and `ES_PASSWORD` only when your Elasticsearch node requires them.
The local Docker setup has security disabled, so no credentials are needed there. `ES_QUERY_VECTOR`
is intentionally required: JDK-only Java has no E5 dependency, and using the Python-prepared
384-dimensional vector keeps this request identical to the demo's vector retrieval path.

## Read-aloud explanation

1. “I read the Elasticsearch address and optional credentials from environment variables, so no secrets live in code.”
2. “Python creates the multilingual E5 query vector; Java simply transports that same 384-number vector.”
3. “The JSON request contains one keyword search and one meaning-based nearest-neighbour search.”
4. “Elasticsearch uses reciprocal rank fusion to combine their positions, with the same window of 50 and rank constant of 60 as Python.”
5. “The standard JDK HTTP client posts the request and prints the JSON hits; no Elasticsearch Java SDK is required.”
