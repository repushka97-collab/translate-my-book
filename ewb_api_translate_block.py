#!/usr/bin/env python3
import json
import sys

from core_engine.api.local_api import api_translate_block

def main():
    if len(sys.argv) < 3:
        print("Usage: python ewb_api_translate_block.py <book_id> <block_id>")
        sys.exit(1)

    book_id = sys.argv[1]
    block_id = sys.argv[2]

    result = api_translate_block(book_id, block_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

