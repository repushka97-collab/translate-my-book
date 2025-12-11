from __future__ import annotations
from typing import List, Dict, Any
import re

Block = Dict[str, Any]


_CAPTION_RE = re.compile(r"^(figure|рис(унок)?)[\\.:\\s]", re.IGNORECASE)
_LIST_RE = re.compile(r"^(\\d+[\\.)]|[•\\-–—])\\s+")


def _looks_like_caption(text: str) -> bool:
    return bool(_CAPTION_RE.match(text.strip()))


def _looks_like_list_item(text: str) -> bool:
    return bool(_LIST_RE.match(text.lstrip()))


def _classify_heading_level(text: str, page: int, order: int) -> str:
    """
    Определяем уровень заголовка:
    - heading1: короткий, без точки, вверху страницы / сильно заглавный
    - heading2: остальное «заголовочное»
    - paragraph: обычный текст
    """
    if not text:
        return "paragraph"

    s = text.strip()
    if not s:
        return "paragraph"

    length = len(s)

    # Очень длинные строки редко бывают заголовками
    if length > 120:
        return "paragraph"

    # Если заканчивается на точку — почти всегда обычный текст
    if s.endswith("."):
        return "paragraph"

    # Верх страницы: первый/второй блок на странице — кандидат в heading1
    is_top_of_page = order <= 2 and page <= 3

    # Есть ли хотя бы одна заглавная буква
    has_upper = any(ch.isupper() for ch in s if ch.isalpha())

    # Полный КАПС (но не слишком длинный) — тоже часто заголовок
    is_caps = s.isupper() and length <= 80

    # Не начинаем с цифры (типа "1. Введение") — такие лучше отдаём на layout как обычный параграф/список
    if s[0].isdigit():
        return "paragraph"

    # Одно короткое слово с заглавной — почти всегда заголовок
    if " " not in s and length <= 40 and has_upper:
        return "heading1" if is_top_of_page or is_caps else "heading2"

    # Короткая фраза без точки, с заглавными — heading
    if length <= 70 and has_upper:
        if is_top_of_page or is_caps:
            return "heading1"
        return "heading2"

    return "paragraph"


def detect_headings(blocks: List[Block]) -> List[Block]:
    """
    Проставляет metadata.role эвристически:
      heading1 / heading2 / list_item / caption / body
    По умолчанию — body.
    """
    new_blocks: List[Block] = []

    for b in blocks:
        page = int(b.get("page", 1))
        order = int(b.get("order", 0))

        text = b.get("translated_text") or b.get("text") or ""
        meta = b.get("metadata") or {}

        role = "body"

        if _looks_like_caption(text):
            role = "caption"
        elif _looks_like_list_item(text):
            role = "list_item"
        else:
            level = _classify_heading_level(text, page, order)
            if level.startswith("heading"):
                role = level
            else:
                role = "body"

        new_b = dict(b)
        new_b["metadata"] = dict(meta)
        new_b["metadata"]["role"] = role
        new_blocks.append(new_b)

    return new_blocks
