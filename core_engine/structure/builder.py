from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List

from core_engine.core.models import BookDocument


def _safe_text(val: Any) -> str:
    """Приводим всё к строке, None → ''."""
    if val is None:
        return ""
    return str(val)


def build_pages_layer(book_id: str, doc: BookDocument) -> Dict[str, Any]:
    """
    Лёгкий слой по страницам:
      - номер страницы
      - размеры (если есть)
      - id блоков на странице
    """
    pages: List[Dict[str, Any]] = []

    for page in getattr(doc, "pages", []):
        blocks = getattr(page, "blocks", [])
        page_entry: Dict[str, Any] = {
            "number": getattr(page, "number", None),
            "width": getattr(page, "width", None),
            "height": getattr(page, "height", None),
            "blocks": [getattr(b, "id", None) for b in blocks],
        }
        pages.append(page_entry)

    return {
        "book_id": book_id,
        "pages": pages,
    }


def build_blocks_layer(book_id: str, doc: BookDocument) -> Dict[str, Any]:
    """
    Индекс всех блоков:
      - id
      - номер страницы
      - тип (text/heading/caption/...)
      - исходный / нормализованный / переведённый текст
    """
    blocks_index: List[Dict[str, Any]] = []

    for page in getattr(doc, "pages", []):
        page_number = getattr(page, "number", None)
        for block in getattr(page, "blocks", []):
            entry: Dict[str, Any] = {
                "id": getattr(block, "id", None),
                "page_number": page_number,
                "type": getattr(block, "type", None),
                "raw_text": _safe_text(getattr(block, "raw_text", "")),
                "normalized_text": _safe_text(
                    getattr(block, "normalized_text", "")
                ),
                "translated_text": _safe_text(
                    getattr(block, "translated_text", "")
                ),
            }
            blocks_index.append(entry)

    return {
        "book_id": book_id,
        "blocks": blocks_index,
    }


def save_structure_layers(
    book_id: str,
    doc: BookDocument,
    book_dir: Path,
) -> Dict[str, str]:
    """
    Сохраняет структурные слои книги в:
      <book_dir>/layers/pages.json
      <book_dir>/layers/blocks_index.json

    Возвращает словарь с путями (для записи в manifest.json).
    """
    layers_dir = book_dir / "layers"
    layers_dir.mkdir(parents=True, exist_ok=True)

    pages_payload = build_pages_layer(book_id, doc)
    blocks_payload = build_blocks_layer(book_id, doc)

    pages_path = layers_dir / "pages.json"
    blocks_path = layers_dir / "blocks_index.json"

    pages_path.write_text(
        json.dumps(pages_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    blocks_path.write_text(
        json.dumps(blocks_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "pages": str(pages_path),
        "blocks_index": str(blocks_path),
    }

