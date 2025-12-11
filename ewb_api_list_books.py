#!/usr/bin/env python3
import json
import sys

from core_engine.api.local_api import api_list_books

def main():
    library_root = "library"
    if len(sys.argv) >= 2:
        library_root = sys.argv[1]

    result = api_list_books(library_root=library_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()


