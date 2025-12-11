#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path
import subprocess
import json

USAGE = "Usage: book_build.py ingest/Book1.pdf"

def run(cmd, cwd):
    print(f"[CMD] {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    if res.returncode != 0:
        print(f"[ERR] Command failed: {cmd}")
        sys.exit(res.returncode)

def main():
    if len(sys.argv) < 2:
        print(USAGE)
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent
    pdf_rel = Path(sys.argv[1])
    pdf_path = (project_root / pdf_rel).resolve()

    if not pdf_path.is_file():
        print(f"[ERR] PDF not found: {pdf_path}")
        sys.exit(1)

    stem = pdf_path.stem
    library_dir = project_root / "library"
    book_dir = library_dir / stem
    book_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Building book package: {stem}")
    print(f"[INFO] Output folder: {book_dir}")

    # Копируем PDF в библиотеку
    shutil.copy(pdf_path, book_dir / f"{stem}.pdf")

    # 1) OCR pipeline
    run(["python", "tools/run_ocr_pipeline.py", str(pdf_rel)], cwd=project_root)

    parsed = project_root / "parsed"
    merged_json = parsed / f"{stem}.book.merged.json"
    headings_json = parsed / f"{stem}.book.merged.headings.json"
    chapters_json = parsed / f"{stem}.book.merged.headings.chapters.json"
    plain_text = parsed / f"{stem}.book.merged.plain.txt"
    meta_json = parsed / f"{stem}.meta.json"

    # 2) detect headings
    run(["python", "tools/detect_headings.py", str(merged_json.relative_to(project_root))], cwd=project_root)

    # 3) make chapter map
    run(["python", "tools/make_chapter_map.py", str(headings_json.relative_to(project_root))], cwd=project_root)

    # 4) chapter texts
    run([
        "python",
        "tools/make_chapter_texts.py",
        str(merged_json.relative_to(project_root)),
        str(chapters_json.relative_to(project_root))
    ], cwd=project_root)

    # 5) meta
    run(["python", "tools/make_book_meta.py", stem], cwd=project_root)

    # Сборка в библиотеку
    (book_dir / "chapters").mkdir(exist_ok=True)
    shutil.copy(plain_text, book_dir / "full.txt")
    shutil.copy(meta_json, book_dir / "meta.json")

    # копируем все главы
    chapters_src = project_root / "exports" / "chapters"
    for f in chapters_src.iterdir():
        if f.is_file() and f.name.startswith(tuple(str(i).zfill(2) for i in range(1, 200))):
            shutil.copy(f, book_dir / "chapters" / f.name)

    print("\n[OK] BOOK BUILD FINISHED")
    print(f"Book folder: {book_dir}")
    print("Contents:")
    for f in book_dir.rglob('*'):
        print("  ", f.relative_to(project_root))

if __name__ == "__main__":
    main()
