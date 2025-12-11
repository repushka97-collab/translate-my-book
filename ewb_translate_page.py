#!/usr/bin/env python3
import json
import sys

from core_engine.library.book_api import translate_page_in_library

def main():
    if len(sys.argv) < 3:
        print("Usage: python ewb_translate_page.py <book_id> <page_number>")
        sys.exit(1)

    book_id = sys.argv[1]
    page_number = int(sys.argv[2])

    result = translate_page_in_library(book_id, page_number)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

