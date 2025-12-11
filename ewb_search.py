#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import List, Dict, Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Поиск книг в библиотеке по метаданным"
    )
    parser.add_argument(
        "--library-root",
        default="./library",
        help="Корень библиотеки (по умолчанию ./library)",
    )
    parser.add_argument(
        "--book-id",
        help="Фильтр по book_id (подстрока, регистронезависимо)",
    )
    parser.add_argument(
        "--title",
        help="Фильтр по title (подстрока, регистронезависимо)",
    )
    parser.add_argument(
        "--author",
        help="Фильтр по author (подстрока, регистронезависимо)",
    )
    parser.add_argument(
        "--min-pages",
        type=int,
        help="Минимальное число страниц",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        help="Максимальное число страниц",
    )
    return parser.parse_args()


def load_books(library_root: Path) -> List[Dict[str, Any]]:
    books: List[Dict[str, Any]] = []

    if not library_root.exists():
        return books

    for sub in sorted(library_root.iterdir()):
        if not sub.is_dir():
            continue
        manifest_path = sub / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        meta = data.get("metadata", {})
        exports = data.get("exports", {})

        books.append(
            {
                "book_id": data.get("book_id", sub.name),
                "pages": data.get("pages"),
                "title": meta.get("title") or "",
                "author": meta.get("author") or "",
                "created_at": data.get("created_at"),
                "pdf": exports.get("pdf"),
                "json": exports.get("json"),
            }
        )

    return books


def matches(book: Dict[str, Any], args: argparse.Namespace) -> bool:
    def contains(field: str, value: str | None) -> bool:
        if not value:
            return True
        return value.lower() in (field or "").lower()

    if not contains(book.get("book_id", ""), args.book_id):
        return False
    if not contains(book.get("title", ""), args.title):
        return False
    if not contains(book.get("author", ""), args.author):
        return False

    pages = book.get("pages")
    if isinstance(pages, int):
        if args.min_pages is not None and pages < args.min_pages:
            return False
        if args.max_pages is not None and pages > args.max_pages:
            return False

    return True


def main() -> None:
    args = parse_args()
    library_root = Path(args.library_root).expanduser().resolve()
    books = load_books(library_root)
    filtered = [b for b in books if matches(b, args)]
    print(json.dumps(filtered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

