#!/usr/bin/env python3
import sys
import json
import unicodedata
from pathlib import Path
import fitz  # PyMuPDF

USAGE = "Usage: make_book_json.py <file.pdf>"

def normalize(txt: str) -> str:
    return unicodedata.normalize("NFC", txt)

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).resolve()
    if not pdf_path.is_file():
        print(f"[ERR] File not found: {pdf_path}")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    parsed_dir = project_root / "parsed"
    parsed_dir.mkdir(exist_ok=True)

    doc = fitz.open(pdf_path)

    book = {"file": str(pdf_path), "pages": []}

    print(f"[INFO] Extracting blocks from {pdf_path}")

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        page_items = []

        for b in blocks:
            if "lines" not in b:
                continue

            block_text = ""
            for line in b["lines"]:
                for span in line["spans"]:
                    block_text += span["text"]

            block_text = normalize(block_text).strip()

            if block_text:
                page_items.append({
                    "bbox": b["bbox"],
                    "text": block_text
                })

        book["pages"].append({
            "page": page_num,
            "blocks": page_items
        })

        print(f"[PAGE {page_num:03d}] blocks={len(page_items)}")

    out_path = parsed_dir / (pdf_path.stem + ".book.json")
    out_path.write_text(json.dumps(book, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Saved: {out_path}")

if __name__ == "__main__":
    main()
