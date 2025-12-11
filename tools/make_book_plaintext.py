#!/usr/bin/env python3
import sys
import json
import unicodedata
from pathlib import Path

USAGE = "Usage: make_book_plaintext.py <path/to/book.json>"

def normalize(txt: str) -> str:
    return unicodedata.normalize("NFC", txt).strip()

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    json_path = Path(sys.argv[1]).resolve()
    if not json_path.is_file():
        print(f"[ERR] File not found: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))

    project_root = Path(__file__).resolve().parent.parent
    parsed_dir = project_root / "parsed"

    out_path = parsed_dir / (json_path.stem + ".plain.txt")

    all_text = []

    print(f"[INFO] Converting {json_path.name} → plaintext...")

    for p in data["pages"]:
        page_num = p["page"]
        blocks = p["blocks"]

        page_lines = []

        for b in blocks:
            t = normalize(b["text"])
            if t:
                page_lines.append(t)

        # Собираем страницу
        page_text = "\n".join(page_lines).strip()
        if page_text:
            all_text.append(f"=== PAGE {page_num} ===\n{page_text}\n")

        print(f"[PAGE {page_num:03d}] lines={len(page_lines)}")

    out_path.write_text("\n".join(all_text), encoding="utf-8")
    print(f"[OK] Saved plaintext: {out_path}")

if __name__ == "__main__":
    main()
