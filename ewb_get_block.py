#!/usr/bin/env python3
import json
import sys

from core_engine.library.book_api import get_block

def main():
    if len(sys.argv) < 3:
        print("Usage: python ewb_get_block.py <book_id> <block_id>")
        sys.exit(1)

    book_id = sys.argv[1]
    block_id = sys.argv[2]

    block = get_block(book_id, block_id)
    print(json.dumps(block, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

