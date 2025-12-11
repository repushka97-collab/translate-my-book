#!/usr/bin/env python3
import sys
import fitz  # PyMuPDF

if len(sys.argv) < 2:
    print("Usage: pdf_info.py <file.pdf>")
    sys.exit(1)

path = sys.argv[1]
doc = fitz.open(path)

print(f"Pages: {doc.page_count}")
print(f"Metadata: {doc.metadata}")
print("Page sizes:")
for i, page in enumerate(doc):
    print(f"  Page {i+1}: {page.rect}")
