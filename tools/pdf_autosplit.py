#!/usr/bin/env python3
import sys
import fitz
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: pdf_autosplit.py <file.pdf>")
    sys.exit(1)

pdf_path = Path(sys.argv[1])
doc = fitz.open(pdf_path)

out_dir = pdf_path.parent / (pdf_path.stem + "_pages")
out_dir.mkdir(exist_ok=True)

for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=200)
    out_file = out_dir / f"page_{i+1}.png"
    pix.save(out_file.as_posix())
    print(f"[OK] Saved {out_file}")
