#!/usr/bin/env python3
import sys
import pytesseract
from PIL import Image
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: ocr_page.py <page.png>")
    sys.exit(1)

img_path = Path(sys.argv[1])
img = Image.open(img_path)

text = pytesseract.image_to_string(img, lang="eng+rus")
out = img_path.with_suffix(".txt")
out.write_text(text, encoding="utf-8")

print(f"[OCR] Saved {out}")
