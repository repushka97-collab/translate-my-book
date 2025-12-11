#!/usr/bin/env python3
import sys
import json
from pathlib import Path
import unicodedata

USAGE = "Usage: detect_headings.py <book.json>"

def normalize(t):
    return unicodedata.normalize("NFC", t).strip()

def is_heading_candidate(text: str) -> bool:
    if not text:
        return False
    t = text.strip()

    # Основные эвристики
    if len(t) < 4:
        return False

    # Короткие строки
    if len(t) < 60:
        return True

    # ALL CAPS (много учебников так оформляют)
    if t.isupper():
        return True

    # Нет точки в конце — чаще всего заголовок
    if not t.endswith((".", "!", "?")) and len(t) < 120:
        return True

    return False

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    json_path = Path(sys.argv[1]).resolve()
    if not json_path.is_file():
        print(f"[ERR] File not found: {json_path}")
        sys.exit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    pages = data["pages"]

    heading_candidates = []

    for p in pages:
        page_num = p["page"]
        blocks = p["blocks"]

        for b in blocks:
            text = normalize(b["text"])
            if is_heading_candidate(text):
                heading_candidates.append({
                    "page": page_num,
                    "text": text,
                    "bbox": b["bbox"]
                })

    out = json_path.with_suffix(".headings.json")
    out.write_text(
        json.dumps(heading_candidates, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"[OK] Headings saved: {out}")
    print(f"Found {len(heading_candidates)} heading candidates")

if __name__ == "__main__":
    main()
