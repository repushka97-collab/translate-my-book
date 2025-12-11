#!/usr/bin/env python3
import sys
import unicodedata
from pathlib import Path

if len(sys.argv) < 2:
    print("Usage: normalize_unicode.py <textfile>")
    sys.exit(1)

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
norm = unicodedata.normalize("NFC", text)

out = path.with_suffix(".norm.txt")
out.write_text(norm, encoding="utf-8")

print(f"[UNICODE] Saved {out}")
