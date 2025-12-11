#!/usr/bin/env python3
import sys
import json
from pathlib import Path
import fitz  # PyMuPDF

USAGE = "Usage: preflight_pdf.py <path/to/file.pdf>"

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).resolve()
    if not pdf_path.is_file():
        print(f"[ERR] File not found: {pdf_path}")
        sys.exit(1)

    # Корень проекта = родитель tools/
    project_root = Path(__file__).resolve().parent.parent
    parsed_dir = project_root / "parsed"
    parsed_dir.mkdir(exist_ok=True)

    print(f"[INFO] Preflight for: {pdf_path}")
    doc = fitz.open(pdf_path)

    pages_summary = []
    for i, page in enumerate(doc):
        page_num = i + 1
        blocks = page.get_text("blocks")
        text_len = sum(len(b[4]) for b in blocks if len(b) > 4)

        if text_len == 0:
            status = "NO_TEXT"
        elif text_len < 300:
            status = "WEAK_TEXT"
        else:
            status = "TEXT_OK"

        pages_summary.append({
            "page": page_num,
            "text_len": text_len,
            "status": status,
        })

        print(f"[PAGE {page_num:03d}] {status:8} | chars={text_len}")

    result = {
        "file": str(pdf_path),
        "pages": len(doc),
        "pages_summary": pages_summary,
    }

    out_path = parsed_dir / (pdf_path.stem + ".preflight.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Preflight JSON saved: {out_path}")

if __name__ == "__main__":
    main()
