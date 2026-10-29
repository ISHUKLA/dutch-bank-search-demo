"""Read setup settings from the environment; never store credentials in code."""

import os


ES_URL = os.getenv("ES_URL", "http://localhost:9200").strip()
ES_USERNAME = os.getenv("ES_USERNAME", "")
ES_PASSWORD = os.getenv("ES_PASSWORD", "")

_offline_value = os.getenv("USE_OFFLINE", "true").strip().lower()
if _offline_value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
    raise ValueError("USE_OFFLINE must be true/false, 1/0, yes/no, or on/off.")
USE_OFFLINE = _offline_value in {"true", "1", "yes", "on"}

try:
    SEGMENT_BOOST_WEIGHT = float(os.getenv("SEGMENT_BOOST_WEIGHT", "0.01"))
except ValueError as error:
    raise ValueError("SEGMENT_BOOST_WEIGHT must be a non-negative number.") from error

if SEGMENT_BOOST_WEIGHT < 0:
    raise ValueError("SEGMENT_BOOST_WEIGHT must be a non-negative number.")
