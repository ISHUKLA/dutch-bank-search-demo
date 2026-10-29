"""Check setup behaviour without starting Elasticsearch or downloading models."""

import importlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_setup.py"
ENVIRONMENT_VARIABLES = ("ES_URL", "ES_USERNAME", "ES_PASSWORD", "USE_OFFLINE")


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch):
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delitem(sys.modules, "config", raising=False)


def load_checker(monkeypatch, **environment):
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    import config

    importlib.reload(config)
    spec = importlib.util.spec_from_file_location("check_setup", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_elasticsearch(monkeypatch, version="8.19.23"):
    import elasticsearch

    client = MagicMock()
    client.info.return_value = {"version": {"number": version}}
    client.license.get.return_value = {"license": {"type": "trial", "status": "active"}}
    client.__enter__.return_value = client
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(elasticsearch, "Elasticsearch", factory)
    return factory, client


def test_default_offline_runs_without_importing_elasticsearch():
    environment = os.environ.copy()
    for name in ENVIRONMENT_VARIABLES:
        environment.pop(name, None)
    code = (
        "import runpy, sys; "
        "sys.modules['elasticsearch'] = None; "
        f"runpy.run_path({str(SCRIPT)!r}, run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Mode: offline" in result.stdout
    assert "Elasticsearch check: skipped" in result.stdout


def test_invalid_offline_flag_is_rejected_without_echoing_value(monkeypatch):
    import config

    monkeypatch.setenv("USE_OFFLINE", "private-invalid-value")
    with pytest.raises(ValueError) as error:
        importlib.reload(config)
    assert "USE_OFFLINE" in str(error.value)
    assert "private-invalid-value" not in str(error.value)


@pytest.mark.parametrize("authenticated", [False, True])
def test_online_reports_version_and_license(monkeypatch, capsys, authenticated):
    factory, client = fake_elasticsearch(monkeypatch)
    environment = {"USE_OFFLINE": "false", "ES_URL": "http://localhost:9200"}
    if authenticated:
        environment.update(ES_USERNAME="elastic", ES_PASSWORD="test-secret")
    checker = load_checker(monkeypatch, **environment)

    assert checker.main() == 0
    output = capsys.readouterr().out
    assert "8.19.23" in output
    assert "trial" in output
    assert "active" in output
    assert "test-secret" not in output
    client.info.assert_called_once()
    client.license.get.assert_called_once()
    options = factory.call_args.kwargs
    assert options["request_timeout"] == 5
    assert options["max_retries"] == 0
    if authenticated:
        assert options["basic_auth"] == ("elastic", "test-secret")
    else:
        assert "basic_auth" not in options


def test_connection_failure_is_actionable_and_does_not_leak_credentials(monkeypatch, capsys):
    import elasticsearch

    _, client = fake_elasticsearch(monkeypatch)
    client.info.side_effect = elasticsearch.ConnectionError("connection failed: test-secret")
    checker = load_checker(
        monkeypatch, USE_OFFLINE="false", ES_USERNAME="elastic", ES_PASSWORD="test-secret"
    )

    assert checker.main() != 0
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "USE_OFFLINE" in output
    assert "test-secret" not in output


@pytest.mark.parametrize("credential", ["ES_USERNAME", "ES_PASSWORD"])
def test_incomplete_credentials_fail_before_connecting(monkeypatch, capsys, credential):
    factory, _ = fake_elasticsearch(monkeypatch)
    checker = load_checker(monkeypatch, USE_OFFLINE="false", **{credential: "test-secret"})

    assert checker.main() != 0
    factory.assert_not_called()
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "ES_USERNAME" in output or "ES_PASSWORD" in output
    assert "test-secret" not in output


def test_incompatible_server_major_is_reported(monkeypatch, capsys):
    fake_elasticsearch(monkeypatch, version="9.5.5")
    checker = load_checker(monkeypatch, USE_OFFLINE="false")

    assert checker.main() != 0
    captured = capsys.readouterr()
    assert "8" in captured.out + captured.err
