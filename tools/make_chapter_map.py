#!/usr/bin/env python3
import sys
import json
import unicodedata
from pathlib import Path

USAGE = "Usage: make_chapter_map.py <book.headings.json>"

IGNORE_SET = {
    "СОДЕРЖАНИЕ",
    "ОГЛАВЛЕНИЕ",
    "ПРЕДИСЛОВИЕ",
    "ВВЕДЕНИЕ",
    "ИТОГИ",
    "ЗАКЛЮЧЕНИЕ",
    "ЛИТЕРАТУРА",
    "СПИСОК ЛИТЕРАТУРЫ",
}

def normalize(t):
    return unicodedata.normalize("NFC", t).strip()

def is_valid_heading(h: str) -> bool:
    t = h.upper().strip()
    if not t:
        return False
    if t in IGNORE_SET:
        return False
    if len(t) < 5:
        return False
    # заголовок обычно не длиннее 200 символов
    if len(t) > 200:
        return False
    return True

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    head_json_path = Path(sys.argv[1]).resolve()

    if not head_json_path.is_file():
        print(f"[ERR] File not found: {head_json_path}")
        sys.exit(1)

    headings = json.loads(head_json_path.read_text(encoding="utf-8"))

    # нормализуем
    cleaned = []
    for h in headings:
        text = normalize(h["text"])
        if is_valid_heading(text):
            cleaned.append({
                "page": h["page"],
                "text": text
            })

    # сортировка по порядку страниц
    cleaned.sort(key=lambda x: x["page"])

    # убираем дубликаты подряд
    unique = []
    for h in cleaned:
        if not unique or unique[-1]["text"] != h["text"]:
            unique.append(h)

    # Создаём карту глав
    chapters = []
    for i, h in enumerate(unique):
        start = h["page"]
        if i + 1 < len(unique):
            end = unique[i+1]["page"] - 1
        else:
            end = None  # последняя глава до конца книги

        chapters.append({
            "title": h["text"],
            "page_start": start,
            "page_end": end
        })

    # путь сохранения
    out = head_json_path.with_suffix(".chapters.json")
    out.write_text(json.dumps(chapters, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Saved chapter map: {out}")
    print(f"Chapters detected: {len(chapters)}")

if __name__ == "__main__":
    main()
