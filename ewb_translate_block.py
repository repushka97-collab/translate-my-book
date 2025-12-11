#!/usr/bin/env python3
import json
import sys

from core_engine.library.book_api import translate_block_in_library

def main():
    if len(sys.argv) < 3:
        print("Usage: python ewb_translate_block.py <book_id> <block_id>")
        sys.exit(1)

    book_id = sys.argv[1]
    block_id = sys.argv[2]

    result = translate_block_in_library(book_id, block_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

