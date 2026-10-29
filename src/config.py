"""Read setup settings from the environment; never store credentials in code."""

import os


ES_URL = os.getenv("ES_URL", "http://localhost:9200").strip()
ES_USERNAME = os.getenv("ES_USERNAME", "")
ES_PASSWORD = os.getenv("ES_PASSWORD", "")

_offline_value = os.getenv("USE_OFFLINE", "true").strip().lower()
if _offline_value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
    raise ValueError("USE_OFFLINE must be true/false, 1/0, yes/no, or on/off.")
USE_OFFLINE = _offline_value in {"true", "1", "yes", "on"}
