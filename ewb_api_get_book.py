#!/usr/bin/env python3
import json
import sys

from core_engine.api.local_api import api_get_book

def main():
    if len(sys.argv) < 2:
        print("Usage: python ewb_api_get_book.py <book_id>")
        sys.exit(1)

    book_id = sys.argv[1]
    result = api_get_book(book_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

