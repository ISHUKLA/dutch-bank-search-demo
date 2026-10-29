"""Print scaffold configuration without loading models or contacting services."""

import argparse

from bank_search.config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL


def main() -> int:
    parser = argparse.ArgumentParser(description="Fictional Dutch bank search demo scaffold")
    parser.parse_args()
    try:
        import config
    except ValueError as error:
        parser.error(str(error))

    print("Scaffold ready")
    print(f"Backend: {'offline' if config.USE_OFFLINE else 'elasticsearch'}")
    print(f"Embedding model: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} dimensions)")
    print("Search implementation: pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
