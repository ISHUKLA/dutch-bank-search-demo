"""Tests for controlled-vocabulary enrichment and its offline cache."""

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("enrich", ROOT / "src" / "enrich.py")
enrich = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enrich)


def test_cache_covers_and_validates_every_page():
    pages = enrich.load_pages()
    validated = enrich.validate_cache(pages, enrich.load_cache())
    assert len(validated) == 40
    assert all(len(entry["example_queries"]) == 3 for entry in validated)


def test_rejects_an_out_of_vocabulary_label():
    page = enrich.load_pages()[0]
    entry = enrich.load_cache()[page["id"]].copy()
    entry["topic"] = "unknown_topic"
    with pytest.raises(enrich.EnrichmentValidationError, match="controlled vocabulary"):
        enrich.validate_enrichment(page, entry)


def test_rejects_summary_number_that_is_absent_from_source_body():
    page = enrich.load_pages()[0]
    entry = enrich.load_cache()[page["id"]].copy()
    entry["summary"] = "Deze samenvatting noemt 999 dagen. De pagina geeft uitleg over een betaalpas."
    with pytest.raises(enrich.EnrichmentValidationError, match="numbers absent"):
        enrich.validate_enrichment(page, entry)


def test_api_key_uses_live_enrichment_and_updates_cache(monkeypatch, tmp_path, capsys):
    page = enrich.load_pages()[0]
    entry = enrich.validate_enrichment(page, enrich.load_cache()[page["id"]])
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(enrich, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(enrich, "load_pages", lambda: [page])
    monkeypatch.setattr(enrich, "enrich_with_openai", lambda _, __: entry)
    monkeypatch.setattr("sys.argv", ["enrich.py"])
    assert enrich.main() == 0
    assert "source: live_openai" in capsys.readouterr().out
    assert enrich.load_cache(enrich.CACHE_PATH)[page["id"]] == entry


def test_cache_only_skips_a_present_api_key(monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(enrich, "enrich_with_openai", pytest.fail)
    monkeypatch.setattr("sys.argv", ["enrich.py", "--cache-only"])
    assert enrich.main() == 0
    assert "source: cache" in capsys.readouterr().out


def test_cache_is_valid_json():
    payload = json.loads((ROOT / "data" / "enrichment_cache.json").read_text(encoding="utf-8"))
    assert payload["source"] in {"curated_cache", "live_openai"}
