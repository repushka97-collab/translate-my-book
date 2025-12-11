#!/usr/bin/env python3
import sys
import json
from pathlib import Path
from langdetect import detect, detect_langs

USAGE = "Usage: make_book_meta.py <pdf_path_stem>  (например: Book1)"

def safe_detect_lang(text: str):
    text = text.strip()
    if not text:
        return None, []
    try:
        main = detect(text)
        probs = [str(p) for p in detect_langs(text)]
        return main, probs
    except Exception as e:
        return None, [f"error: {e}"]

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    stem = sys.argv[1]

    project_root = Path(__file__).resolve().parent.parent
    ingest_dir = project_root / "ingest"
    parsed_dir = project_root / "parsed"

    pdf_path = ingest_dir / f"{stem}.pdf"
    preflight_path = parsed_dir / f"{stem}.preflight.json"
    book_json_path = parsed_dir / f"{stem}.book.merged.json"
    if not book_json_path.is_file():
        # fallback: без OCR-merge
        book_json_path = parsed_dir / f"{stem}.book.json"
    plain_path = parsed_dir / f"{stem}.book.merged.plain.txt"
    if not plain_path.is_file():
        plain_path = parsed_dir / f"{stem}.book.plain.txt"

    if not pdf_path.is_file():
        print(f"[ERR] PDF not found: {pdf_path}")
        sys.exit(1)

    meta = {
        "stem": stem,
        "pdf_file": str(pdf_path),
        "size_bytes": pdf_path.stat().st_size,
    }

    # preflight
    if preflight_path.is_file():
        pre = json.loads(preflight_path.read_text(encoding="utf-8"))
        meta["pages_total"] = pre.get("pages", None)
        counts = {"TEXT_OK": 0, "WEAK_TEXT": 0, "NO_TEXT": 0, "OTHER": 0}
        for p in pre.get("pages_summary", []):
            s = p.get("status", "OTHER")
            if s not in counts:
                counts["OTHER"] += 1
            else:
                counts[s] += 1
        meta["pages_status"] = counts
    else:
        meta["pages_total"] = None
        meta["pages_status"] = None

    # источники по страницам (book_json)
    if book_json_path.is_file():
        book = json.loads(book_json_path.read_text(encoding="utf-8"))
        pages = book.get("pages", [])
        src_counts = {"ocr": 0, "text": 0}
        for p in pages:
            if p.get("source") == "ocr":
                src_counts["ocr"] += 1
            else:
                src_counts["text"] += 1
        meta["pages_source"] = src_counts

    # язык книги
    if plain_path.is_file():
        text = plain_path.read_text(encoding="utf-8", errors="ignore")
        # ограничимся куском, чтобы не дохнуть на огромных файлах
        snippet = text[:20000]
        main, probs = safe_detect_lang(snippet)
        meta["language_main"] = main
        meta["language_probs"] = probs

    out_path = parsed_dir / f"{stem}.meta.json"
    out_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Saved meta: {out_path}")

if __name__ == "__main__":
    main()
