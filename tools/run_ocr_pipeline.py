#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path

USAGE = "Usage: run_ocr_pipeline.py ingest/Book1.pdf"

def run(cmd, cwd):
    print(f"[CMD] {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"[ERR] Command failed: {cmd}")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    pdf_rel = Path(sys.argv[1])
    root = Path(__file__).resolve().parent.parent
    pdf_path = (root / pdf_rel).resolve()

    if not pdf_path.is_file():
        print(f"[ERR] PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"[INFO] OCR PIPELINE for: {pdf_path}")

    # 1) Preflight
    run(["python", "tools/preflight_pdf.py", str(pdf_rel)], cwd=root)

    pre_json = root / "parsed" / (pdf_path.stem + ".preflight.json")

    # 2) Autosplit pages (PNG)
    run(["python", "tools/pdf_autosplit.py", str(pdf_rel)], cwd=root)

    pages_dir = pdf_path.parent / (pdf_path.stem + "_pages")

    # 3) OCR only needed pages
    pre = json.loads(pre_json.read_text(encoding="utf-8"))
    for p in pre["pages_summary"]:
        if p["status"] != "TEXT_OK":
            img = pages_dir / f"page_{p['page']}.png"
            if img.is_file():
                run(["python", "tools/ocr_page.py", str(img)], cwd=root)

    # 4) Make original book.json (bbox)
    run(["python", "tools/make_book_json.py", str(pdf_rel)], cwd=root)
    book_json = root / "parsed" / (pdf_path.stem + ".book.json")

    # 5) Merge OCR into book.json
    run([
        "python",
        "tools/ocr_merge.py",
        str(book_json.relative_to(root)),
        str(pre_json.relative_to(root)),
        str(pages_dir.relative_to(root))
    ], cwd=root)

    merged_json = root / "parsed" / (pdf_path.stem + ".book.merged.json")

    # 6) Convert merged JSON → plaintext
    run([
        "python",
        "tools/make_book_plaintext.py",
        str(merged_json.relative_to(root))
    ], cwd=root)

    print("[OK] OCR pipeline finished.")
    print("Results:")
    print("  Preflight:        ", pre_json)
    print("  Book JSON:        ", book_json)
    print("  Merged JSON:      ", merged_json)
    print("  Plaintext merged: ", merged_json.with_suffix(".plain.txt"))

if __name__ == "__main__":
    main()
