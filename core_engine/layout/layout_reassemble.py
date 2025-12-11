from __future__ import annotations

from typing import List, Dict, Any, Tuple
import re


Block = Dict[str, Any]
Paragraph = Dict[str, Any]


def _sort_key(block: Block) -> Tuple[int, int, str]:
    """Стабильная сортировка блоков: по странице, порядку, id."""
    return (
        int(block.get("page", 0)),
        int(block.get("order", 0)),
        str(block.get("id", "")),
    )


# ============================================================
#  LIST DETECTOR
# ============================================================

def _detect_list_item(text: str) -> str | None:
    """
    Простейший детектор списков:
    - буллеты: •, -, *, ‣
    - нумерация: `1. Текст`, `2) Текст`
    Возвращает текст элемента списка без маркера, либо None.
    """
    s = text.strip()
    if not s:
        return None

    # • bullet, - bullet, * bullet, ‣ bullet
    if re.match(r"^(\u2022|\-|\*|\u2023)\s+", s):
        return re.sub(r"^(\u2022|\-|\*|\u2023)\s+", "", s).strip()

    # нумерованные: "1. Текст", "2) Текст"
    if re.match(r"^\d{1,2}[.)]\s+", s):
        return re.sub(r"^\d{1,2}[.)]\s+", "", s).strip()

    return None


# ============================================================
#  LONG PARAGRAPH SPLITTER
# ============================================================

def _split_long_paragraph(text: str, max_chars: int = 600) -> List[str]:
    """
    Семантический чанкер для очень длинных параграфов.
    Режем по предложениям, стараясь держать куски ≈ max_chars.
    """
    s = text.strip()
    if len(s) <= max_chars:
        return [s]

    sentences = re.split(r'(?<=[.!?…])\s+', s)
    chunks: List[str] = []
    current = ""

    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue

        # одно предложение само по себе слишком длинное — режем грубо
        if len(sent) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(sent), max_chars):
                part = sent[i : i + max_chars].strip()
                if part:
                    chunks.append(part)
            continue

        if not current:
            current = sent
        elif len(current) + 1 + len(sent) <= max_chars:
            current = current + " " + sent
        else:
            chunks.append(current.strip())
            current = sent

    if current:
        chunks.append(current.strip())

    return [c for c in chunks if c]


# ============================================================
#  STEP A v2: СПЛИТ СТРУКТУРНЫХ ЗАГОЛОВКОВ ПО ORIGINAL TEXT
# ============================================================

_heading_lead_re = re.compile(
    r"^\s*(?P<num>\d+[\.\)]?)\s+(?P<title_word>\S+)"
)


def _split_structural_heading_for_block(block: Block) -> tuple[str | None, str]:
    """
    НОРМАЛЬНЫЙ сплит:

    1) Детектим заголовок по ORIGINAL/normalized_text (АНГЛИЙСКОМУ):

       "1  Introduction\nMusculoskeletal ..."

       Условия:
       - строка начинается с числа + слово
       - в исходном тексте есть перевод строки \n достаточно рядом (<= 80 символов)
       → считаем, что это структурный заголовок ("1 Introduction", "2 Methods", ...).

    2) Режем РУССКИЙ translated_text:

       "1 Введение Расстройства опорно-двигательного аппарата..."
       → "1 Введение" (heading2) + "Расстройства опорно-двигательного аппарата..." (body)

    Если что-то не сошлось → возвращаем (None, russian_text) и ничего не сплитим.
    """
    src = (block.get("normalized_text") or block.get("text") or "").strip()
    ru = (block.get("translated_text") or block.get("text") or "").strip()

    if not src or not ru:
        return None, ru

    m_src = _heading_lead_re.match(src)
    if not m_src:
        return None, ru

    # проверяем, что в источнике есть перенос строки недалеко от начала:
    nl_idx = src.find("\n")
    if nl_idx == -1 or nl_idx > 80:
        # нет явного разделения на "заголовок / текст" → не трогаем
        return None, ru

    # теперь пытаемся выделить "номер + первое слово" в русской версии
    # пример: "1 Введение Расстройства ..." → "1 Введение" + "Расстройства ..."
    m_ru = re.match(r"^\s*(\d+[\.\)]?\s+\S+)\s+(.*)$", ru, flags=re.DOTALL)
    if not m_ru:
        return None, ru

    heading_ru = m_ru.group(1).strip()
    body_ru = m_ru.group(2).lstrip()

    # небольшая страховка: не создаём заголовки > 80 символов
    if len(heading_ru) > 80 or not body_ru:
        return None, ru

    return heading_ru, body_ru


# ============================================================
#  ROLE DETECTOR
# ============================================================

def _get_role(block: Block) -> str:
    """
    Определяем роль блока по metadata и простым эвристикам.

    ВАЖНО: сплит "1 Введение" / тело мы делаем в reassemble_blocks
    через _split_structural_heading_for_block, здесь только тип блока.
    """
    meta = block.get("metadata") or {}
    base_role = str(meta.get("role", "paragraph")).lower()

    # Явные роли из предыдущих слоёв
    if base_role in ("heading1", "chapter", "title"):
        return "heading1"
    if base_role in ("heading2", "subtitle", "subheading"):
        return "heading2"
    if base_role == "heading":
        return "heading1"

    text = (block.get("translated_text") or block.get("text") or "").strip()
    if not text:
        return "paragraph"

    s = text.strip()
    lowered = s.lower()

    # Короткие служебные заголовки
    if len(s) <= 80 and not s.endswith((".", "!", "?", "…")):
        heading_keywords = (
            "abstract",
            "резюме",
            "аннотация",
            "summary",
            "keywords",
            "ключевые слова",
            "graphical abstract",
            "графическая абстракция",
        )
        for kw in heading_keywords:
            if lowered.startswith(kw):
                return "heading2"

    return "paragraph"


# ============================================================
#  MAIN REASSEMBLER
# ============================================================

def reassemble_blocks(blocks: List[Block]) -> List[Paragraph]:
    """
    Собираем финальный список параграфов для DOCX.

    STEP A v2:
      - если в оригинале блок выглядит как "1 Introduction\n...",
        а в переводе начинается с "1 Введение ...", мы делим его на:
          * heading2: "1 Введение"
          * paragraph: остальной текст
    """
    if not isinstance(blocks, list):
        return []

    sorted_blocks = sorted(
        [b for b in blocks if isinstance(b, dict)],
        key=_sort_key,
    )

    paragraphs: List[Paragraph] = []
    current_para: str | None = None
    current_page: int | None = None

    for b in sorted_blocks:
        page = int(b.get("page", 0))
        raw_text = (b.get("translated_text") or b.get("text") or "").strip()
        if not raw_text:
            # Пустой блок → закрываем текущий параграф
            if current_para:
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "text": current_para.strip(),
                        "page": current_page,
                    }
                )
                current_para = None
                current_page = None
            continue

        # ===== STEP A v2: пробуем сплит "1 Введение ..." внутри блока =====
        heading_text, body_text = _split_structural_heading_for_block(b)

        if heading_text is not None:
            # закрываем висящий параграф перед новым заголовком
            if current_para:
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "text": current_para.strip(),
                        "page": current_page,
                    }
                )
                current_para = None
                current_page = None

            # сам заголовок
            paragraphs.append(
                {
                    "type": "heading2",
                    "text": heading_text,
                    "page": page,
                }
            )

            text = body_text
            role = "paragraph"
        else:
            text = raw_text
            role = _get_role(b)

        # Списки — только для параграфов
        if role == "paragraph":
            list_text = _detect_list_item(text)
            if list_text is not None:
                if current_para:
                    paragraphs.append(
                        {
                            "type": "paragraph",
                            "text": current_para.strip(),
                            "page": current_page,
                        }
                    )
                current_para = None
                current_page = None

                paragraphs.append(
                    {
                        "type": "list_item",
                        "text": list_text,
                        "page": page,
                    }
                )
                continue

        # Явные заголовки (без inline-сплита)
        if heading_text is None and role in ("heading1", "heading2"):
            if current_para:
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "text": current_para.strip(),
                        "page": current_page,
                    }
                )
                current_para = None
                current_page = None

            paragraphs.append(
                {
                    "type": role,
                    "text": text,
                    "page": page,
                }
            )
            continue

        # Очень длинные параграфы — режем на чанки
        if role == "paragraph" and len(text) > 800:
            if current_para:
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "text": current_para.strip(),
                        "page": current_page,
                    }
                )
                current_para = None
                current_page = None

            for chunk in _split_long_paragraph(text, max_chars=600):
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "text": chunk,
                        "page": page,
                    }
                )
            continue

        # Обычный текст → накапливаем в текущем параграфе
        if current_para is None:
            current_para = text
            current_page = page
        else:
            sep = " " if not current_para.endswith(("\n", " ")) else ""
            current_para = current_para + sep + text

        # Если блок заканчивается на пунктуацию — закрываем параграф
        if text.endswith((".", "!", "?", "…")):
            paragraphs.append(
                {
                    "type": "paragraph",
                    "text": current_para.strip(),
                    "page": current_page,
                }
            )
            current_para = None
            current_page = None

    # Хвост
    if current_para:
        paragraphs.append(
            {
                "type": "paragraph",
                "text": current_para.strip(),
                "page": current_page,
            }
        )

    # Fallback, если вдруг ничего не собрали
    if not paragraphs:
        for b in sorted_blocks:
            t = (b.get("translated_text") or b.get("text") or "").strip()
            if t:
                paragraphs.append(
                    {
                        "type": "paragraph",
                        "text": t,
                        "page": int(b.get("page", 0)),
                    }
                )

    return paragraphs
