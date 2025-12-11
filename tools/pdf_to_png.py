#!/usr/bin/env python3
import sys
import fitz  # PyMuPDF
from pathlib import Path

if len(sys.argv) < 3:
    print("Usage: pdf_to_png.py <file.pdf> <page_number>")
    sys.exit(1)

pdf_path = Path(sys.argv[1])
page_num = int(sys.argv[2]) - 1

doc = fitz.open(pdf_path)
page = doc[page_num]
pix = page.get_pixmap(dpi=150)

out = pdf_path.with_suffix(f".page{page_num+1}.png")
pix.save(out.as_posix())
print(f"Saved: {out}")
