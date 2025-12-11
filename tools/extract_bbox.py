#!/usr/bin/env python3
import sys
import fitz
import json
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: extract_bbox.py <file.pdf>")
    sys.exit(1)

pdf_path = Path(sys.argv[1])
doc = fitz.open(pdf_path)

pages = []

for page_num, page in enumerate(doc, start=1):
    blocks = page.get_text("dict")["blocks"]
    items = []

    for b in blocks:
        if "lines" not in b:
            continue
        block_text = ""
        for l in b["lines"]:
            for s in l["spans"]:
                block_text += s["text"]
        items.append({
            "bbox": b["bbox"],
            "text": block_text.strip()
        })

    pages.append({
        "page": page_num,
        "blocks": items
    })

out = pdf_path.with_suffix(".bbox.json")
out.write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"[BBOX] Saved {out}")
