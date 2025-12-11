"""
Local CLI-friendly API поверх EWB Core Engine.

Задача модуля — дать простые вызовы с понятным JSON-контрактом
для Telegram-бота, n8n и любых внешних интеграций.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from core_engine.library.book_api import (
    load_manifest,
    load_pages_layer,
    get_book_structure,
    get_page,
    get_block,
    translate_block_in_library,
    translate_page_in_library,
    translate_book_in_library,
)


# =============================================================================
# Вспомогательные
# =============================================================================


def _iter_manifests(library_root: str = "library") -> List[Path]:
    root = Path(library_root)
    if not root.exists():
        return []
    manifests: List[Path] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        manifest = child / "manifest.json"
        if manifest.exists():
            manifests.append(manifest)
    return manifests


# =============================================================================
# Публичный API
# =============================================================================


def api_list_books(library_root: str = "library") -> Dict[str, Any]:
    """
    Возвращает список всех книг в библиотеке.

    {
      "library_root": "library",
      "books": [
        {
          "book_id": "...",
          "pages": 564,
          "title": "...",
          "author": "...",
          "created_at": "...",
        },
        ...
      ]
    }
    """
    books: List[Dict[str, Any]] = []
    for manifest_path in _iter_manifests(library_root):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        meta = data.get("metadata") or {}
        books.append(
            {
                "book_id": data.get("book_id"),
                "pages": data.get("pages"),
                "title": meta.get("title") or "",
                "author": meta.get("author") or "",
                "created_at": data.get("created_at") or "",
            }
        )

    return {
        "library_root": library_root,
        "books": books,
    }


def api_get_book(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Краткая инфа по книге.

    {
      "book_id": "...",
      "pages": 564,
      "metadata": {...},
      "exports": {...},
      "qa": {...}
    }
    """
    manifest = load_manifest(book_id, library_root)
    return {
        "book_id": manifest.get("book_id", book_id),
        "pages": manifest.get("pages"),
        "metadata": manifest.get("metadata", {}),
        "exports": manifest.get("exports", {}),
        "qa": manifest.get("qa", {}),
    }


def api_get_book_structure(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Полная структура книги с блоками (для тяжёлых случаев / отладки).
    Просто прокси к get_book_structure().
    """
    return get_book_structure(book_id, library_root)


def api_get_pages(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Список страниц и количества блоков на каждой.

    {
      "book_id": "...",
      "pages": [
        {"page": 1, "blocks": 10},
        ...
      ]
    }
    """
    pages_layer = load_pages_layer(book_id, library_root)
    pages_info: List[Dict[str, Any]] = []
    for p in pages_layer.get("pages", []) or []:
        num = int(p.get("number"))
        blocks = p.get("blocks", []) or []
        pages_info.append({"page": num, "blocks": len(blocks)})

    return {
        "book_id": book_id,
        "pages": pages_info,
    }


def api_get_page(book_id: str, page_number: int, library_root: str = "library") -> Dict[str, Any]:
    """
    Возвращает страницу с блоками (аналог ewb_get_page.py).
    """
    return get_page(book_id, page_number, library_root)


def api_get_block(book_id: str, block_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Возвращает один блок (аналог ewb_get_block.py).
    """
    return get_block(book_id, block_id, library_root)


def api_translate_block(
    book_id: str,
    block_id: str,
    library_root: str = "library",
) -> Dict[str, Any]:
    """
    Переводит один блок и возвращает результат translate_block_in_library().
    """
    return translate_block_in_library(book_id, block_id, library_root=library_root)


def api_translate_page(
    book_id: str,
    page_number: int,
    library_root: str = "library",
) -> Dict[str, Any]:
    """
    Переводит страницу целиком (обёртка над translate_page_in_library()).
    """
    return translate_page_in_library(book_id, page_number, library_root=library_root)


def api_translate_book(
    book_id: str,
    library_root: str = "library",
) -> Dict[str, Any]:
    """
    Переводит всю книгу (обёртка над translate_book_in_library()).
    """
    return translate_book_in_library(book_id, library_root=library_root)

