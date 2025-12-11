#!/usr/bin/env python3
import sys
import subprocess
from pathlib import Path

USAGE = "Usage: run_pipeline.py ingest/Book1.pdf"

def run(cmd, cwd):
    print(f"[CMD] {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"[ERR] Command failed with code {res.returncode}")
        sys.exit(res.returncode)

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    pdf_rel = Path(sys.argv[1])
    project_root = Path(__file__).resolve().parent.parent
    pdf_path = (project_root / pdf_rel).resolve()

    if not pdf_path.is_file():
        print(f"[ERR] PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"[INFO] Starting pipeline for: {pdf_path}")

    # 1) Preflight
    run(
        ["python", "tools/preflight_pdf.py", str(pdf_rel)],
        cwd=project_root,
    )

    # 2) Book JSON (bbox)
    run(
        ["python", "tools/make_book_json.py", str(pdf_rel)],
        cwd=project_root,
    )

    # 3) Plaintext from book.json
    parsed_dir = project_root / "parsed"
    book_json = parsed_dir / (pdf_path.stem + ".book.json")

    if not book_json.is_file():
        print(f"[ERR] Expected book.json not found: {book_json}")
        sys.exit(1)

    run(
        ["python", "tools/make_book_plaintext.py", str(book_json.relative_to(project_root))],
        cwd=project_root,
    )

    print("[OK] Pipeline finished.")
    print(f"  Preflight JSON : {parsed_dir / (pdf_path.stem + '.preflight.json')}")
    print(f"  Book JSON      : {book_json}")
    print(f"  Plaintext TXT  : {parsed_dir / (pdf_path.stem + '.book.plain.txt')}")

if __name__ == "__main__":
    main()
