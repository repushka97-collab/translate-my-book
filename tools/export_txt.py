import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List


def load_book(book_dir: Path) -> Dict[str, Any]:
    book_path = book_dir / "book.json"
    if not book_path.exists():
        raise FileNotFoundError(f"book.json not found in {book_dir}")
    with book_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def sort_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # На всякий случай сортируем по странице и order
    return sorted(
        blocks,
        key=lambda b: (b.get("page", 0), b.get("order", 0)),
    )


def export_to_txt(book: Dict[str, Any], book_dir: Path) -> Path:
    blocks = book.get("blocks", [])
    blocks = sort_blocks(blocks)

    lines: List[str] = []

    for blk in blocks:
        text = blk.get("translated_text") or blk.get("normalized_text") or blk.get("text") or ""
        text = str(text).strip()
        if not text:
            continue

        page = blk.get("page")
        if page is not None:
            lines.append(f"[page {page}]")
        lines.append(text)
        lines.append("")  # пустая строка между блоками

    out_path = book_dir / "book_ru.txt"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export translated blocks from book.json to plain text file."
    )
    parser.add_argument(
        "book_dir",
        nargs="?",
        default="output",
        help="Path to book directory or output root (default: ./output)",
    )
    args = parser.parse_args()

    root = Path(args.book_dir)

    # Если указали именно папку книги (с book.json)
    if (root / "book.json").exists():
        book_dir = root
    else:
        # Иначе берём единственную папку внутри output (как сейчас у тебя)
        subdirs = [p for p in root.iterdir() if p.is_dir()]
        if not subdirs:
            raise RuntimeError(f"No book directories found in {root}")
        # Берём самую свежую по времени модификации
        book_dir = max(subdirs, key=lambda p: p.stat().st_mtime)

    book = load_book(book_dir)
    out_path = export_to_txt(book, book_dir)
    print(f"Exported to {out_path}")


if __name__ == "__main__":
    main()
