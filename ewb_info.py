#!/usr/bin/env python3
"""
ewb_info.py — показать информацию о книге и какие файлы уже есть.

Usage:
    python ewb_info.py <book_id>
"""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LIBRARY_DIR = ROOT / "library"
OUTPUT_DIR = ROOT / "output"


def load_manifest(book_id: str) -> dict:
    manifest_path = LIBRARY_DIR / book_id / "manifest.json"
    if not manifest_path.exists():
        print(f"[ERROR] Manifest not found for book_id={book_id}")
        print(f"        Ожидаю файл: {manifest_path}")
        sys.exit(1)

    with manifest_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python ewb_info.py <book_id>")
        sys.exit(1)

    book_id = sys.argv[1]
    manifest = load_manifest(book_id)

    meta = manifest.get("metadata", {}) or {}
    title = meta.get("title", "(unknown)")
    pages = meta.get("pages", "?")
    pdf_path = manifest.get("pdf_path", "")
    source_file = Path(pdf_path).name if pdf_path else "?"

    out_dir = OUTPUT_DIR / book_id
    json_path = out_dir / "book.json"
    txt_path = out_dir / "book_ru.txt"
    docx_path = out_dir / "book_ru.docx"

    print(f"=== Book: {book_id} ===")
    print(f"Title:  {title}")
    print(f"Source: {source_file}")
    print(f"Pages:  {pages}")
    print()
    print("Available files:")
    print(f"- JSON: {'YES' if json_path.exists() else 'NO'}")
    print(f"- TXT:  {'YES' if txt_path.exists() else 'NO'}")
    print(f"- DOCX: {'YES' if docx_path.exists() else 'NO'}")


if __name__ == "__main__":
    main()
