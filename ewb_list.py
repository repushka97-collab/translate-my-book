#!/usr/bin/env python3
"""
EWB Core v3 — просмотр библиотеки книг.

Простой CLI:
    python ewb_list.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
LIB_DIR = PROJECT_ROOT / "library"


@dataclass
class BookInfo:
    book_id: str
    title: str
    source_file: str
    pages: Optional[int]
    manifest_path: Path

    @classmethod
    def from_manifest(cls, manifest_path: Path) -> "BookInfo":
        with manifest_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        book_id = data.get("book_id") or manifest_path.parent.name
        meta = data.get("metadata") or {}
        title = meta.get("title") or "(no title)"
        source_path = meta.get("source_path") or ""
        pages = meta.get("pages")

        # оставляем только имя файла, без полного пути
        source_file = Path(source_path).name if source_path else ""

        return cls(
            book_id=book_id,
            title=str(title),
            source_file=source_file,
            pages=pages,
            manifest_path=manifest_path,
        )


def collect_books() -> List[BookInfo]:
    if not LIB_DIR.exists():
        print(f"[warn] Папка library не найдена: {LIB_DIR}")
        return []

    books: List[BookInfo] = []

    for book_dir in sorted(LIB_DIR.iterdir()):
        if not book_dir.is_dir():
            continue

        manifest = book_dir / "manifest.json"
        if not manifest.exists():
            continue

        try:
            info = BookInfo.from_manifest(manifest)
            books.append(info)
        except Exception as e:
            print(f"[warn] Не удалось прочитать {manifest}: {e}")

    return books


def print_table(books: List[BookInfo]) -> None:
    if not books:
        print("[info] В библиотеке пока нет ни одной книги.")
        return

    # Вычисляем ширину колонок
    id_w = max(len("book_id"), max(len(b.book_id) for b in books))
    title_w = max(len("title"), max(len(b.title) for b in books))
    src_w = max(len("source"), max(len(b.source_file) for b in books))

    header = f"{'book_id':<{id_w}}  {'title':<{title_w}}  {'source':<{src_w}}  pages"
    print(header)
    print("-" * len(header))

    for b in books:
        pages = str(b.pages) if b.pages is not None else "?"
        print(f"{b.book_id:<{id_w}}  {b.title:<{title_w}}  {b.source_file:<{src_w}}  {pages}")


def main() -> None:
    books = collect_books()
    print_table(books)


if __name__ == "__main__":
    main()
