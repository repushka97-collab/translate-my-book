#!/usr/bin/env python3
import sys
import json
import unicodedata
from pathlib import Path
import re

USAGE = "Usage: make_chapter_texts.py <book.json> <chapters.json>"

def normalize(t: str) -> str:
    return unicodedata.normalize("NFC", t).strip()

def safe_filename(name: str) -> str:
    name = normalize(name)
    # режем слишком длинные
    if len(name) > 80:
        name = name[:80]
    # выкидываем проблемные символы для файловой системы
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name

def main():
    if len(sys.argv) < 3:
        print(USAGE)
        sys.exit(1)

    book_path = Path(sys.argv[1]).resolve()
    chapters_path = Path(sys.argv[2]).resolve()

    if not book_path.is_file():
        print(f"[ERR] Book json not found: {book_path}")
        sys.exit(1)
    if not chapters_path.is_file():
        print(f"[ERR] Chapters json not found: {chapters_path}")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    exports_dir = project_root / "exports" / "chapters"
    exports_dir.mkdir(parents=True, exist_ok=True)

    book = json.loads(book_path.read_text(encoding="utf-8"))
    chapters = json.loads(chapters_path.read_text(encoding="utf-8"))

    pages_by_num = {p["page"]: p for p in book.get("pages", [])}

    print(f"[INFO] Building chapter texts from {book_path.name}")

    for idx, ch in enumerate(chapters, start=1):
        title = normalize(ch["title"])
        start = ch["page_start"]
        end = ch["page_end"]

        if end is None:
            # до конца книги
            max_page = max(pages_by_num.keys())
            end = max_page

        texts = []
        for page_num in range(start, end + 1):
            page = pages_by_num.get(page_num)
            if not page:
                continue
            for b in page.get("blocks", []):
                t = normalize(b.get("text", ""))
                if t:
                    texts.append(t)

        chapter_text = ("\n".join(texts)).strip()
        if not chapter_text:
            print(f"[WARN] Chapter {idx} '{title}' is empty, skipping write")
            continue

        prefix = f"{idx:02d}"
        fname = f"{prefix} - {safe_filename(title)}.txt"
        out_path = exports_dir / fname
        out_path.write_text(chapter_text, encoding="utf-8")

        print(f"[OK] Chapter {idx:02d}: pages {start}-{end} -> {out_path.name}")

    print(f"[DONE] Chapters exported to: {exports_dir}")

if __name__ == "__main__":
    main()
