"""Enrich fictional help pages with validated LLM metadata or a local cache."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
PAGES_PATH = ROOT / "data" / "pages.json"
CACHE_PATH = ROOT / "data" / "enrichment_cache.json"

# Keep every allowed label in this one object. Search filters use these exact values later.
CONTROLLED_VOCABULARY = {
    "audience": ("private", "business", "both"),
    "product": (
        "betaalpas",
        "creditcard",
        "betaalrekening",
        "spaarrekening",
        "hypotheek",
        "betaling",
        "app",
        "profiel",
        "contact",
        "zakelijk_portaal",
        "fraude",
    ),
    "topic": (
        "blokkeren",
        "deblokkeren",
        "verlies",
        "activeren",
        "limiet",
        "kaartbetaling",
        "rekening_openen",
        "rekeningbeheer",
        "incasso",
        "overboeking",
        "sparen",
        "hypotheekadvies",
        "hypotheekbeheer",
        "inloggen",
        "toestelbeheer",
        "phishing",
        "fraudemelding",
        "contact",
        "gegevens_wijzigen",
        "autorisatie",
        "betaalbatch",
        "buitenland",
    ),
    "intent": ("informatie", "actie", "probleem_oplossen", "veiligheid"),
}


class EnrichmentValidationError(ValueError):
    """Raised when generated enrichment violates the demo's data contract."""


def load_pages(path: Path = PAGES_PATH) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", text))


def validate_enrichment(page: dict[str, str], enrichment: dict[str, Any]) -> dict[str, Any]:
    """Return validated enrichment or raise a clear error without silently repairing it."""

    expected_keys = {"id", "summary", "audience", "product", "topic", "intent", "example_queries"}
    actual_keys = set(enrichment)
    if actual_keys != expected_keys:
        raise EnrichmentValidationError(
            f"{page['id']}: expected keys {sorted(expected_keys)}, got {sorted(actual_keys)}."
        )
    if enrichment["id"] != page["id"]:
        raise EnrichmentValidationError(f"{page['id']}: enrichment id does not match page id.")

    summary = enrichment["summary"].strip()
    sentences = [sentence for sentence in re.split(r"(?<=[.!?])\s+", summary) if sentence]
    if len(sentences) != 2 or any(not sentence.endswith((".", "!", "?")) for sentence in sentences):
        raise EnrichmentValidationError(f"{page['id']}: summary must contain exactly two complete sentences.")
    invented_numbers = _numbers(summary) - _numbers(page["body"])
    if invented_numbers:
        raise EnrichmentValidationError(
            f"{page['id']}: summary contains numbers absent from the source body: {sorted(invented_numbers)}."
        )

    for field in ("audience", "product", "topic", "intent"):
        value = enrichment[field]
        if value not in CONTROLLED_VOCABULARY[field]:
            raise EnrichmentValidationError(
                f"{page['id']}: {field}={value!r} is outside the controlled vocabulary."
            )
    example_queries = enrichment["example_queries"]
    if not isinstance(example_queries, list) or len(example_queries) != 3:
        raise EnrichmentValidationError(f"{page['id']}: example_queries must contain exactly three strings.")
    if any(not isinstance(query, str) or not query.strip() for query in example_queries):
        raise EnrichmentValidationError(f"{page['id']}: every example query must be a non-empty string.")

    return {**enrichment, "summary": summary, "example_queries": [query.strip() for query in example_queries]}


def load_cache(path: Path = CACHE_PATH) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise EnrichmentValidationError("enrichment cache has an unsupported schema version.")
    entries = payload.get("enrichments")
    if not isinstance(entries, list):
        raise EnrichmentValidationError("enrichment cache must contain an enrichments list.")
    return {entry["id"]: entry for entry in entries}


def validate_cache(pages: list[dict[str, str]], cache: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    page_ids = {page["id"] for page in pages}
    if set(cache) != page_ids:
        missing = sorted(page_ids - set(cache))
        extra = sorted(set(cache) - page_ids)
        raise EnrichmentValidationError(f"cache ids differ from page ids; missing={missing}, extra={extra}.")
    return [validate_enrichment(page, cache[page["id"]]) for page in pages]


def _schema() -> dict[str, Any]:
    properties = {
        "id": {"type": "string"},
        "summary": {"type": "string"},
        "audience": {"type": "string", "enum": list(CONTROLLED_VOCABULARY["audience"])},
        "product": {"type": "string", "enum": list(CONTROLLED_VOCABULARY["product"])},
        "topic": {"type": "string", "enum": list(CONTROLLED_VOCABULARY["topic"])},
        "intent": {"type": "string", "enum": list(CONTROLLED_VOCABULARY["intent"])},
        "example_queries": {"type": "array", "items": {"type": "string"}},
    }
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def enrich_with_openai(page: dict[str, str], api_key: str) -> dict[str, Any]:
    """Request one structured enrichment using the Responses API without an SDK dependency."""

    model = os.getenv("OPENAI_ENRICHMENT_MODEL", "gpt-4.1-mini")
    prompt = (
        "Generate JSON only for this fictional Dutch bank help page. "
        "Write exactly two Dutch summary sentences. Do not introduce a number unless it appears in the body. "
        "Select only from the supplied schema enums. Produce exactly three Dutch example queries.\n\n"
        f"id: {page['id']}\ntitle: {page['title']}\nbody: {page['body']}"
    )
    request_body = {
        "model": model,
        "input": prompt,
        "text": {"format": {"type": "json_schema", "name": "page_enrichment", "strict": True, "schema": _schema()}},
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError(f"OpenAI enrichment request failed with HTTP {error.code}.") from error
    except URLError as error:
        raise RuntimeError("OpenAI enrichment request could not reach the API.") from error

    output_text = payload.get("output_text")
    if not isinstance(output_text, str):
        raise RuntimeError("OpenAI enrichment response did not contain output_text.")
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as error:
        raise RuntimeError("OpenAI enrichment response was not valid JSON.") from error


def write_cache(enrichments: list[dict[str, Any]], path: Path | None = None) -> None:
    path = path or CACHE_PATH
    payload = {"schema_version": 1, "source": "live_openai", "enrichments": enrichments}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cached or live LLM enrichment for fictional help pages.")
    parser.add_argument("--page-id", help="Print enrichment for one page id.")
    parser.add_argument("--cache-only", action="store_true", help="Use the committed cache even when OPENAI_API_KEY is set.")
    arguments = parser.parse_args()
    pages = load_pages()
    api_key = os.getenv("OPENAI_API_KEY")

    try:
        if api_key and not arguments.cache_only:
            enrichments = [validate_enrichment(page, enrich_with_openai(page, api_key)) for page in pages]
            write_cache(enrichments)
            source = "live_openai"
        else:
            cache = load_cache()
            enrichments = validate_cache(pages, cache)
            source = "cache"
    except (EnrichmentValidationError, RuntimeError) as error:
        print(f"Enrichment error: {error}", file=sys.stderr)
        return 1

    if arguments.page_id:
        selected = next((entry for entry in enrichments if entry["id"] == arguments.page_id), None)
        if selected is None:
            print(f"Enrichment error: unknown page id {arguments.page_id!r}.", file=sys.stderr)
            return 1
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        print(f"Enrichment ready: {len(enrichments)} pages (source: {source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
