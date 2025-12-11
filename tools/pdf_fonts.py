#!/usr/bin/env python3
import sys
import fitz  # PyMuPDF

if len(sys.argv) < 2:
    print("Usage: pdf_fonts.py <file.pdf>")
    sys.exit(1)

doc = fitz.open(sys.argv[1])
fonts = set()

for page in doc:
    for font in page.get_fonts(full=True):
        fonts.add(font[3])

print("Fonts detected:")
for f in sorted(fonts):
    print(" ", f)
