#!/usr/bin/env python3
"""
ewb_translate_book.py — простой запуск пайплайна перевода для одного PDF.

Пока БЕЗ проверки дубликатов по book_id:
    - просто запускает run_book_pipeline(source_path)
    - запись в библиотеку делает сам пайплайн через register_book_in_library
"""

import sys
from pathlib import Path

from core_engine.orchestrator.pipeline import run_book_pipeline


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python ewb_translate_book.py path/to/book.pdf")
        sys.exit(1)

    pdf_path = Path(sys.argv[1]).resolve()
    if not pdf_path.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"[EWB] Запускаю перевод файла: {pdf_path}")
    run_book_pipeline(str(pdf_path))
    print("[EWB] Пайплайн завершён.")
    print("      Список книг:   python ewb_list.py")
    print("      Инфо по книге: python ewb_info.py <book_id>")


if __name__ == "__main__":
    main()
