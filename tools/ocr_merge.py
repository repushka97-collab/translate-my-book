#!/usr/bin/env python3
import sys, json
from pathlib import Path

USAGE = "Usage: ocr_merge.py <book.json> <preflight.json> <pages_dir>"

def main():
    if len(sys.argv) < 4:
        print(USAGE)
        sys.exit(1)

    book_json = Path(sys.argv[1]).resolve()
    preflight_json = Path(sys.argv[2]).resolve()
    pages_dir = Path(sys.argv[3]).resolve()

    book = json.loads(book_json.read_text(encoding="utf-8"))
    preflight = json.loads(preflight_json.read_text(encoding="utf-8"))

    pages_summary = {p["page"]: p["status"] for p in preflight["pages_summary"]}

    print(f"[INFO] Merging OCR for: {book_json}")

    for p in book["pages"]:
        page_num = p["page"]
        status = pages_summary.get(page_num, "TEXT_OK")

        if status == "TEXT_OK":
            continue

        txt_path = pages_dir / f"page_{page_num}.txt"
        if txt_path.is_file():
            ocr_text = txt_path.read_text(encoding="utf-8").strip()
            if ocr_text:
                p["blocks"] = [{
                    "bbox": [0, 0, 0, 0],
                    "text": ocr_text
                }]
                p["source"] = "ocr"
                print(f"[OCR] Page {page_num}: merged")
        else:
            print(f"[WARN] No OCR txt for page {page_num}")

    out_path = book_json.with_suffix(".merged.json")
    out_path.write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Saved merged: {out_path}")

if __name__ == "__main__":
    main()
