"""Print scaffold configuration without loading models or contacting services."""

import argparse

from bank_search.config import (
    BACKENDS,
    DEFAULT_BACKEND,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fictional Dutch bank search demo scaffold")
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default=DEFAULT_BACKEND,
        help="Select the planned search backend (default: offline).",
    )
    args = parser.parse_args()

    print("Scaffold ready")
    print(f"Backend: {args.backend}")
    print(f"Embedding model: {EMBEDDING_MODEL} ({EMBEDDING_DIMENSIONS} dimensions)")
    print("Search implementation: pending")


if __name__ == "__main__":
    main()
