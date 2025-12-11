# core_engine/layout/role_classifier.py

from __future__ import annotations

from typing import Dict, List


BLOCK_ROLE_TITLE = "title"
BLOCK_ROLE_HEADING = "heading"
BLOCK_ROLE_SUBTITLE = "subtitle"
BLOCK_ROLE_PARAGRAPH = "paragraph"
BLOCK_ROLE_LIST_ITEM = "list_item"
BLOCK_ROLE_CAPTION = "caption"
BLOCK_ROLE_FOOTNOTE = "footnote"
BLOCK_ROLE_IMAGE = "image"
BLOCK_ROLE_TABLE = "table"
BLOCK_ROLE_UNKNOWN = "unknown"


def _get_text_for_classification(block: Dict) -> str:
    """
    Берём лучший кандидат текста для анализа:
    translated_text > normalized_text > text.
    """
    return (
        block.get("translated_text")
        or block.get("normalized_text")
        or block.get("text")
        or ""
    ).strip()


def _is_list_item(text: str) -> bool:
    stripped = text.lstrip()
    if not stripped:
        return False

    # Начало с маркера списка: "-", "*", "•", "1.", "2)", "a)"
    bullets = ("- ", "* ", "• ", "∙ ", "· ")
    if any(stripped.startswith(b) for b in bullets):
        return True

    # Нумерованные списки: "1. ", "2) ", "3)  "
    import re

    if re.match(r"^(\d+[\.\)])\s+", stripped):
        return True

    return False


def _is_caption(text: str) -> bool:
    # очень грубо: короткий текст, начинающийся с "Рис.", "Figure", "Fig."
    lowered = text.lower()
    if len(text) > 120:
        return False

    prefixes = ("рис.", "figure", "fig.", "табл.", "table")
    return any(lowered.startswith(p) for p in prefixes)


def _is_footnote(text: str) -> bool:
    # короткая строка с много цифрами/ссылками
    if len(text) > 200:
        return False
    # очень простая эвристика: начинается с "[1]" или "1)"
    import re

    if re.match(r"^\[\d+\]\s+", text):
        return True
    if re.match(r"^\d+\)\s+", text):
        return True
    return False


def _is_title_or_heading(text: str) -> str | None:
    """
    Возвращает BLOCK_ROLE_TITLE / BLOCK_ROLE_HEADING или None.
    """
    if not text:
        return None

    # Обрезаем мусорные пробелы
    stripped = text.strip()

    # Если одна строка, без точки в конце и короткая — это заголовок/подзаголовок.
    # Ограничения по длине — эмпирические.
    if len(stripped) <= 120 and "\n" not in stripped:
        # нет точки на конце и нет вопросительного/восклицательного
        if not stripped.endswith((".", "?", "!", ";", ":")):
            # если очень коротко — обычно title
            if len(stripped) <= 60:
                return BLOCK_ROLE_HEADING
            return BLOCK_ROLE_SUBTITLE

        # если заканчивается двоеточием и короткое — заголовок раздела
        if stripped.endswith(":") and len(stripped) <= 120:
            return BLOCK_ROLE_HEADING

    # Простейший title — первая страница, очень короткий, много ПРОПИСНЫХ
    upper_ratio = sum(1 for c in stripped if c.isupper()) / max(
        1, sum(1 for c in stripped if c.isalpha())
    )
    if len(stripped) <= 80 and upper_ratio > 0.7:
        return BLOCK_ROLE_HEADING

    return None


def classify_block(block: Dict) -> Dict:
    """
    Классифицирует блок и записывает роль в block["metadata"]["role"].
    Контракт JSON не ломаем: metadata — уже обязательный dict.
    """
    block_type = block.get("type", "text")
    metadata = block.get("metadata") or {}
    text = _get_text_for_classification(block)

    # Сначала жёсткие типы
    if block_type == "image":
        metadata["role"] = BLOCK_ROLE_IMAGE
    elif block_type == "table":
        metadata["role"] = BLOCK_ROLE_TABLE
    else:
        # text-подобные блоки
        if _is_list_item(text):
            metadata["role"] = BLOCK_ROLE_LIST_ITEM
        elif _is_caption(text):
            metadata["role"] = BLOCK_ROLE_CAPTION
        elif _is_footnote(text):
            metadata["role"] = BLOCK_ROLE_FOOTNOTE
        else:
            heading_role = _is_title_or_heading(text)
            if heading_role is not None:
                metadata["role"] = heading_role
            else:
                # дефолт
                metadata["role"] = BLOCK_ROLE_PARAGRAPH

    block["metadata"] = metadata
    return block


def classify_blocks(blocks: List[Dict]) -> List[Dict]:
    """
    Применяет classify_block ко всем блокам.
    """
    return [classify_block(b) for b in blocks]
