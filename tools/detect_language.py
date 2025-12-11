#!/usr/bin/env python3
import sys
from pathlib import Path
from langdetect import detect, detect_langs

if len(sys.argv) < 2:
    print("Usage: detect_language.py <textfile>")
    sys.exit(1)

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8", errors="ignore")

if not text.strip():
    print("Empty text")
    sys.exit(0)

try:
    main = detect(text)
    probs = detect_langs(text)
    print("Main language:", main)
    print("Distribution:")
    for p in probs:
        print(" ", p)
except Exception as e:
    print("Detection error:", e)
