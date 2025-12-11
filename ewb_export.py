#!/usr/bin/env python3
"""
ewb_export.py — утилита экспорта готовых файлов по book_id.

Примеры:
    python ewb_export.py 398d5642cc251cb7 --format docx
    python ewb_export.py 398d5642cc251cb7 --format txt
    python ewb_export.py 398d5642cc251cb7 --format json
"""

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LIBRARY_DIR = ROOT / "library"
OUTPUT_DIR = ROOT / "output"


def ensure_book_exists(book_id: str) -> dict:
    manifest_path = LIBRARY_DIR / book_id / "manifest.json"
    if not manifest_path.exists():
        print(f"[ERROR] Book {book_id} not found in library.")
        print(f"        Ожидаю manifest: {manifest_path}")
        sys.exit(1)

    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export book files by book_id")
    parser.add_argument("book_id", help="ID книги (как в ewb_list.py)")
    parser.add_argument(
        "--format",
        choices=["json", "txt", "docx"],
        required=True,
        help="формат для экспорта",
    )

    args = parser.parse_args()
    book_id = args.book_id
    fmt = args.format

    # Проверяем, что книга реально есть
    manifest = ensure_book_exists(book_id)
    title = (manifest.get("metadata") or {}).get("title", "(unknown)")

    out_dir = OUTPUT_DIR / book_id
    filenames = {
        "json": "book.json",
        "txt": "book_ru.txt",
        "docx": "book_ru.docx",
    }
    target = out_dir / filenames[fmt]

    if not target.exists():
        print(f"[ERROR] For book {book_id} ({title}) нет файла формата {fmt.upper()}")
        print(f"        Ожидал: {target}")
        sys.exit(1)

    print(f"[EWB] Book:   {book_id}")
    print(f"[EWB] Title:  {title}")
    print(f"[EWB] Format: {fmt.upper()}")
    print(f"[EWB] Path:   {target}")


if __name__ == "__main__":
    main()
