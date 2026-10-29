"""Check Elasticsearch version and licence, or skip it explicitly in offline mode."""


def fail(message: str) -> int:
    print(f"Setup error: {message}")
    print("For offline mode, set USE_OFFLINE=true.")
    return 1


def main() -> int:
    try:
        import config
    except ImportError:
        return fail("Install the project first: python -m pip install -e .")
    except ValueError as error:
        return fail(str(error))

    if config.USE_OFFLINE:
        print("Mode: offline")
        print("Elasticsearch check: skipped")
        return 0

    print("Mode: elasticsearch")
    if bool(config.ES_USERNAME) != bool(config.ES_PASSWORD):
        return fail("Set both ES_USERNAME and ES_PASSWORD, or leave both empty.")

    # Offline mode does not need to import or contact Elasticsearch.
    try:
        from elasticsearch import (
            ApiError,
            AuthenticationException,
            AuthorizationException,
            ConnectionError,
            ConnectionTimeout,
            Elasticsearch,
            TransportError,
        )
    except ImportError:
        return fail("Install dependencies: python -m pip install -r requirements.txt")

    options = {"request_timeout": 5, "max_retries": 0}
    if config.ES_USERNAME:
        options["basic_auth"] = (config.ES_USERNAME, config.ES_PASSWORD)

    try:
        with Elasticsearch(config.ES_URL, **options) as client:
            version = client.info()["version"]["number"]
            licence = client.license.get()["license"]
    except AuthenticationException:
        return fail("Authentication failed. Check ES_USERNAME and ES_PASSWORD.")
    except AuthorizationException:
        return fail("The account needs the monitor cluster privilege to read the licence.")
    except (ConnectionError, ConnectionTimeout):
        return fail("Cannot reach Elasticsearch. Start Docker and check ES_URL.")
    except (ApiError, TransportError, ValueError, KeyError):
        # Raw exception text can contain URLs or credentials; do not print it.
        return fail("Check ES_URL and server readiness, then retry the setup check.")

    print(f"Elasticsearch version: {version}")
    print(f"Licence type: {licence.get('type', 'unknown')}")
    print(f"Licence status: {licence.get('status', 'unknown')}")

    if not version.startswith("8."):
        return fail("This demo targets Elasticsearch 8.x. Use the documented 8.19.23 image.")
    if licence.get("status") != "active":
        return fail("The licence is not active. Use an active trial or offline mode.")
    if licence.get("type") != "trial":
        print("Note: this demo expects a trial licence for the RRF retriever.")
        print("See docs/setup.md to activate a trial, or use USE_OFFLINE=true.")

    print("Elasticsearch check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
