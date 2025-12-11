from __future__ import annotations

import argparse
from pathlib import Path

from core_engine.orchestrator.pipeline import run_book_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run EWB translation pipeline for a single PDF.",
    )

    parser.add_argument(
        "-s",
        "--source",
        type=str,
        required=True,
        help="Path to source PDF file",
    )

    parser.add_argument(
        "-m",
        "--mode",
        type=str,
        choices=["dev", "fast", "full"],
        default="fast",
        help="LLM profile: dev (no-translate), fast (GPU 600M), full (1.3B)",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_path = Path(args.source)

    result = run_book_pipeline(source_path, mode=args.mode)
    book_id = result.get("book_id")

    print(f"[INFO] Finished. Book id={book_id}")


if __name__ == "__main__":
    main()
