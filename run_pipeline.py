from __future__ import annotations

import argparse
from pathlib import Path

from core_engine.orchestrator.pipeline import run_book_pipeline


def _log_cuda_status(mode: str) -> str:
    """
    Лёгкий health-check перед запуском.
    Не меняет поведение, только предупреждает, если fast запущен без CUDA.
    """
    if mode != "fast":
        return mode

    try:
        import torch
    except Exception:
        print("[WARN] torch не установлен — режим fast пойдёт на CPU и будет медленным. Рассмотрите --mode full.")
        return mode

    if torch.cuda.is_available():
        try:
            name = torch.cuda.get_device_name(0)
            print(f"[INFO] CUDA доступна: {name}")
        except Exception:
            print("[INFO] CUDA доступна")
    else:
        print("[WARN] CUDA недоступна — режим fast пойдёт на CPU и будет медленным. Рассмотрите --mode full.")

    return mode


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
    mode = _log_cuda_status(args.mode)

    result = run_book_pipeline(source_path, mode=mode)
    book_id = result.get("book_id")

    print(f"[INFO] Finished. Book id={book_id}")


if __name__ == "__main__":
    main()
