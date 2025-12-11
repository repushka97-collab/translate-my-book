#!/usr/bin/env python3
import sys
import fitz
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: detect_text_density.py <file.pdf>")
    sys.exit(1)

pdf_path = Path(sys.argv[1])
doc = fitz.open(pdf_path)

for i, page in enumerate(doc):
    blocks = page.get_text("blocks")
    text_len = sum(len(b[4]) for b in blocks if len(b) > 4)
    
    status = (
        "NO TEXT" if text_len == 0 else
        "WEAK TEXT" if text_len < 100 else
        "TEXT OK"
    )
    print(f"Page {i+1}: {status} ({text_len} chars)")
