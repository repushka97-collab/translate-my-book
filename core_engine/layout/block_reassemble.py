# core_engine/layout/block_reassemble.py

from __future__ import annotations
from typing import Dict, List, Any

from core_engine.layout.heading_detector import detect_headings


def _group_blocks(blocks: List[Dict]) -> Dict[int, List[Dict]]:
    """
    Группируем блоки по страницам и сортируем по order.
    """
    pages: Dict[int, List[Dict]] = {}

    for b in blocks:
        page = int(b.get("page", 0))
        pages.setdefault(page, []).append(b)

    for page in pages.values():
        page.sort(key=lambda x: int(x.get("order", 0)))

    return pages


def build_layout_model(book_id: str, blocks: List[Dict]) -> Dict[str, Any]:
    """
    Layout v2:
      - вызывает detect_headings()
      - раскладывает блоки по страницам
      - создаёт layout_model в согласованном формате
    """

    # --- 1) Санити-чистка ---
    clean_blocks = [b for b in blocks if isinstance(b, dict)]

    # --- 2) Проставляем роли ---
    clean_blocks = detect_headings(clean_blocks)

    # --- 3) Группируем ---
    pages_dict = _group_blocks(clean_blocks)

    pages_list = []
    for page_num in sorted(pages_dict.keys()):
        pages_list.append(
            {
                "page_num": page_num,
                "blocks": pages_dict[page_num],
            }
        )

    layout_model = {
        "book_id": book_id,
        "pages": pages_list,
    }

    return layout_model


def build_layout(blocks: List[Dict], meta: Any) -> Dict[str, Any]:
    """
    Публичный API.
    Выбирает book_id из meta и вызывает build_layout_model.
    """
    book_id = None
    if isinstance(meta, dict):
        book_id = (
            meta.get("book_id")
            or meta.get("id")
            or meta.get("source_id")
        )

    if not book_id:
        book_id = "unknown"

    return build_layout_model(book_id, blocks)
