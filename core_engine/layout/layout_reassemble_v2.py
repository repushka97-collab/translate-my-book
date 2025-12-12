# layout_reassemble_v2.1.py
# Улучшенный layout-процессор для ядра v7.1

from __future__ import annotations

from typing import Any, Dict, List
import re


# ============================================================
#               РЕГУЛЯРКИ ДЛЯ СТРУКТУРНЫХ ЗАГОЛОВКОВ
# ============================================================

_HEADING_SPLIT_RE = re.compile(
    r"""
    ^\s*
    (?P<num>\d+(\.\d+)*[\.\)]?)     
    \s+
    (?P<title>[A-ZА-ЯЁ][^\n]{0,120})
    (?:\s+(?P<body>.+))?            
    """,
    re.VERBOSE | re.UNICODE,
)


def _split_structural_heading(text: str) -> tuple[str, str, str]:
    """
    Извлекает структурные заголовки:
    '1 Введение ...', '1.2 Methods ...'
    Возвращает (head, body, level) где level: "heading1" | "heading2" | "heading3"
    """
    t = text.strip()
    if not t:
        return "", "", ""

    # Нормализуем "С H А Р Т Е R\n1" → "CHAPTER 1"
    # Убираем лишние пробелы и переносы, но сохраняем структуру
    t_normalized = re.sub(r"\s+", " ", t.replace("\n", " ")).strip()
    
    # Детектируем разорванный CHAPTER/PART (буквы через пробелы)
    # "С H А Р Т Е R 1" → "CHAPTER 1"
    chapter_broken = re.match(r"^([СC]\s+[HН]\s+[АA]\s+[РP]\s+[ТT]\s+[ЕE]\s+[RР])\s+(\d+)", t_normalized, re.IGNORECASE)
    if chapter_broken:
        return f"CHAPTER {chapter_broken.group(2)}", "", "heading1"
    
    # "Р А R Т I" → "PART I"
    part_broken = re.match(r"^([РP]\s+[АA]\s+[RР]\s+[ТT])\s+([IVXLCDM]+)", t_normalized, re.IGNORECASE)
    if part_broken:
        return f"PART {part_broken.group(2).upper()}", "", "heading1"
    
    # Также обрабатываем "Р А R Т" без номера (может быть на отдельной строке)
    if re.match(r"^[РP]\s+[АA]\s+[RР]\s+[ТT]\s*$", t_normalized, re.IGNORECASE):
        # Ищем номер в следующем блоке или используем "I" по умолчанию
        return "PART I", "", "heading1"

    # CHAPTER 1 / PART I / Глава 1 → Heading1
    if re.match(r"^\s*(chapter|part|глава|часть)\s+[ivxlcdm\d]+\b", t_normalized, re.IGNORECASE):
        # Нормализуем текст: "CHAPTER 1" вместо "С H А Р Т Е R 1"
        if "chapter" in t_normalized.lower():
            match = re.search(r"chapter\s+(\d+)", t_normalized, re.IGNORECASE)
            if match:
                return f"CHAPTER {match.group(1)}", "", "heading1"
        if "part" in t_normalized.lower():
            match = re.search(r"part\s+([ivxlcdm]+)", t_normalized, re.IGNORECASE)
            if match:
                return f"PART {match.group(1).upper()}", "", "heading1"
        return t_normalized, "", "heading1"
    
    # "CHAPTER 1" в капсе → Heading1
    if re.match(r"^\s*CHAPTER\s+\d+\b", t_normalized):
        return t_normalized, "", "heading1"
    if re.match(r"^\s*PART\s+[IVXLCDM]+\b", t_normalized):
        return t_normalized, "", "heading1"

    # Формат: "1 Введение ..." → Heading2
    m = re.match(
        r"^\s*(\d+[\.\)]?)\s+([A-ZА-ЯЁ][\w\-\(\) ]{2,60})\s+(.*)$",
        t,
    )
    if m:
        head = f"{m.group(1).strip()} {m.group(2).strip()}"
        body = m.group(3).strip()
        return head, body, "heading2"

    # Классический split: "1.2 Title ..." → Heading2, "1.2.3 Title" → Heading3
    m = _HEADING_SPLIT_RE.match(t)
    if m:
        num = m.group("num").strip()
        title = m.group("title").strip()
        body = (m.group("body") or "").strip()
        
        # Определяем уровень по глубине нумерации
        depth = num.count(".") + 1
        if depth == 1:
            level = "heading1"
        elif depth == 2:
            level = "heading2"
        else:
            level = "heading3"

        if len(title) <= 120:
            return f"{num} {title}", body if len(body) > 10 else "", level

    return "", "", ""


# ============================================================
#                       ДЕТЕКТОРЫ МУСОРА
# ============================================================

def _looks_like_page_header_footer(text: str) -> bool:
    t = text.strip().lower()
    if not t:
        return False
    if t.startswith("страница ") and " из " in t:
        return True
    if t.startswith("page ") and " of " in t:
        return True
    return False


def _looks_like_table_of_contents(text: str) -> bool:
    """
    Детектирует строки оглавления:
    - "Title 2" (название + номер страницы)
    - "1. Introduction 5" (нумерация + название + номер)
    - Много коротких строк с номерами в конце
    """
    t = text.strip()
    if not t:
        return False
    
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    if len(lines) < 2:
        return False
    
    # Проверяем, что большинство строк заканчиваются на цифры (номера страниц)
    ends_with_digit = sum(1 for ln in lines if ln and ln[-1].isdigit() and len(ln.split()) >= 2)
    if ends_with_digit >= len(lines) * 0.6:  # 60%+ строк с номерами
        return True
    
    # Паттерн: "Title 2" или "1. Title 5"
    toc_pattern = re.compile(r"^(.+?)\s+\d{1,3}$", re.MULTILINE)
    matches = len(toc_pattern.findall(t))
    if matches >= 2:
        return True
    
    return False


def _looks_like_page_number(text: str) -> bool:
    """
    Одиночные цифры или очень короткие строки - часто номера страниц
    """
    t = text.strip()
    if not t:
        return False
    # Одиночная цифра или очень короткая строка (1-3 символа) из цифр
    if re.match(r"^\d{1,3}$", t):
        return True
    return False


def _looks_like_license_or_publisher_note(text: str) -> bool:
    t = text.lower().strip()
    if "creative commons" in t:
        return True
    if "springer nature" in t and ("neutral" in t or "нейтральн" in t):
        return True
    if "open access" in t:
        return True
    return False


def _is_graphical_abstract_label(text: str) -> bool:
    t = text.lower()
    return "graphical abstract" in t or ("графическ" in t and "абстрак" in t)


# ============================================================
#                     ДЕТЕКТОРЫ СМЫСЛОВЫХ БЛОКОВ
# ============================================================

def _looks_like_heading(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if len(t) <= 80 and t[0].isupper() and not t.endswith((".", ":", ";")):
        return True

    letters = [c for c in t if c.isalpha()]
    if letters:
        upper_ratio = sum(c.isupper() for c in letters) / len(letters)
        if upper_ratio > 0.4:
            return True

    return False


def _looks_like_figure_caption(text: str) -> bool:
    t = text.lower().strip()
    return t.startswith(("figure ", "рисунок", "рис."))


def _split_abstract_block(text: str) -> tuple[str, str]:
    t = text.strip().lower()
    mapping = {
        "аннотация": "Аннотация",
        "abstract": "Abstract",
        "резюме": "Резюме",
        "summary": "Summary",
    }
    if t in mapping:
        return mapping[t], ""
    for key, title in mapping.items():
        if t.startswith(key + " "):
            body = text[len(key):].strip()
            return title, body if len(body) > 10 else ""
    return "", ""


# ============================================================
#                         СПИСКИ
# ============================================================

def _looks_like_list_item(text: str) -> bool:
    t = text.lstrip()
    if t.startswith(("•", "-", "–", "—", "*")):
        return True
    if re.match(r"^\(?\d+[\.\)]\s+", t):
        return True
    if re.match(r"^[ivxlcdm]+\.\s+", t.lower()):
        return True
    return False


def _is_list_continuation(prev: str, now: str) -> bool:
    return now.startswith((" ", "\t")) and len(now.strip()) > 5


# ============================================================
#                          ТАБЛИЦЫ
# ============================================================

def _looks_like_table_block(text: str) -> bool:
    if "|" in text:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return len(lines) >= 2 and all("|" in ln for ln in lines)
    # markdown style
    if re.search(r"^-{2,}\s+-{2,}", text, flags=re.MULTILINE):
        return True
    return False


def _parse_table_rows(text: str) -> List[List[str]]:
    rows = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        parts = [c.strip() for c in ln.split("|")]
        rows.append(parts)
    return rows


# ============================================================
#                          ДВЕ КОЛОНКИ
# ============================================================

def _order_blocks_two_columns(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    with_bbox = [b for b in blocks if b.get("bbox")]
    no_bbox = [b for b in blocks if not b.get("bbox")]

    if not with_bbox:
        return sorted(blocks, key=lambda b: b.get("order", 0))

    xs = [b["bbox"]["x0"] for b in with_bbox]
    spread = max(xs) - min(xs)

    if spread < 120:
        ordered = sorted(with_bbox, key=lambda b: (b["bbox"]["y0"], b.get("order", 0)))
    else:
        mid = sorted(xs)[len(xs) // 2]
        left = sorted(
            [b for b in with_bbox if b["bbox"]["x0"] <= mid],
            key=lambda b: (b["bbox"]["y0"], b.get("order", 0)),
        )
        right = sorted(
            [b for b in with_bbox if b["bbox"]["x0"] > mid],
            key=lambda b: (b["bbox"]["y0"], b.get("order", 0)),
        )
        ordered = left + right

    tail = sorted(no_bbox, key=lambda b: b.get("order", 0))
    return ordered + tail


# ============================================================
#                     БЛОК → ПАРАГРАФЫ
# ============================================================

def _block_to_paragraphs(block: Dict[str, Any], page: int) -> List[Dict[str, Any]]:
    text = (block.get("translated_text") or "").strip()
    if not text:
        return []

    if _looks_like_page_header_footer(text):
        return []
    if _looks_like_license_or_publisher_note(text):
        return []
    if _is_graphical_abstract_label(text):
        return []
    if _looks_like_table_of_contents(text):
        return []
    if _looks_like_page_number(text):
        return []

    # Используем metadata.role из heading_detector если есть
    metadata = block.get("metadata", {})
    role = metadata.get("role", "")
    
    # Font signals для улучшения детекции заголовков
    font_size = metadata.get("font_size", 0)
    is_bold = metadata.get("is_bold", False)
    is_italic = metadata.get("is_italic", False)

    out = []

    # ABSTRACT
    abs_title, abs_body = _split_abstract_block(text)
    if abs_title:
        out.append({"type": "heading2", "text": abs_title, "page": page})
        if abs_body:
            out.append({"type": "paragraph", "text": abs_body, "page": page})
        return out

    # CAPTION
    if _looks_like_figure_caption(text) or role == "caption":
        return [{"type": "caption", "text": text, "page": page}]

    # TABLE
    if _looks_like_table_block(text):
        rows = _parse_table_rows(text)
        preview = " / ".join(" | ".join(r) for r in rows[:3])
        return [
            {
                "type": "table",
                "rows": rows,
                "text": preview[:200] or "[TABLE]",
                "page": page,
            }
        ]

    # STRUCTURAL HEADING
    head, body, level = _split_structural_heading(text)
    if head:
        heading_type = level if level else "heading2"
        # Нормализуем текст заголовка: убираем лишние переносы
        head_clean = re.sub(r"\s+", " ", head.replace("\n", " ")).strip()
        out.append({"type": heading_type, "text": head_clean, "page": page})
        if body:
            out.append({"type": "paragraph", "text": body, "page": page})
        return out

    # LIST ITEM (используем role если есть)
    if role == "list_item" or _looks_like_list_item(text):
        return [{"type": "list_item", "text": text, "page": page}]

    # HEADING по role или font signals
    if role in ("heading1", "heading2", "heading3"):
        return [{"type": role, "text": text, "page": page}]
    
    # HEADING по font signals: большой размер + bold = заголовок
    if font_size > 0:
        # Определяем уровень по размеру шрифта
        if font_size >= 14 and is_bold:
            heading_type = "heading1" if font_size >= 16 else "heading2"
            return [{"type": heading_type, "text": text, "page": page}]
        elif font_size >= 12 and is_bold:
            return [{"type": "heading2", "text": text, "page": page}]
        elif font_size >= 11 and is_bold:
            return [{"type": "heading3", "text": text, "page": page}]

    # SOFT HEADING (эвристика по тексту)
    if _looks_like_heading(text):
        # Определяем уровень: полный капс/короткий → heading1, остальное → heading2
        t_upper = text.strip()
        # Нормализуем: убираем лишние переносы и пробелы
        t_clean = re.sub(r"\s+", " ", t_upper.replace("\n", " ")).strip()
        is_caps = t_clean.isupper() and len(t_clean) <= 60
        is_short = len(t_clean) <= 40 and " " not in t_clean
        heading_type = "heading1" if (is_caps or is_short) else "heading2"
        return [{"type": heading_type, "text": t_clean, "page": page}]

    # NORMAL PARAGRAPH
    return [{"type": "paragraph", "text": text, "page": page}]


# ============================================================
#                   GRAPHICAL ABSTRACT
# ============================================================

def _page_has_graphical_abstract(blocks: List[Dict[str, Any]]) -> bool:
    for b in blocks:
        txt = (b.get("translated_text") or "").lower()
        if _is_graphical_abstract_label(txt):
            return True
    return False


# ============================================================
#                        MAIN API
# ============================================================

def build_paragraph_stream(book: Dict[str, Any]) -> List[Dict[str, Any]]:
    pages = book.get("pages", [])
    result = []
    fig_id = 1
    prev_page = 0

    for page in sorted(pages, key=lambda p: p.get("page_num", 0)):
        page_num = page.get("page_num", 0)
        blocks = page.get("blocks", [])

        # Page break между страницами (кроме первой)
        if prev_page > 0 and page_num != prev_page:
            result.append({"type": "page_break", "page": page_num})
        prev_page = page_num

        ordered = _order_blocks_two_columns(blocks)

        if _page_has_graphical_abstract(blocks):
            result.append(
                {
                    "type": "figure",
                    "text": f"Graphical Abstract — Figure {fig_id}",
                    "page": page_num,
                }
            )
            fig_id += 1

        # Блок → параграфы
        for b in ordered:
            out = _block_to_paragraphs(b, page_num)

            # Авто-слияние коротких абзацев
            for p in out:
                # Группировка списков: если предыдущий элемент тоже список, не добавляем пустую строку
                if (
                    result
                    and p["type"] == "list_item"
                    and result[-1].get("type") == "list_item"
                ):
                    # Списки идут подряд - просто добавляем
                    result.append(p)
                elif (
                    result
                    and p["type"] == "paragraph"
                    and result[-1].get("type") == "paragraph"
                ):
                    # Проверяем что у обоих есть текст
                    p_text = (p.get("text") or "").strip()
                    prev_text = (result[-1].get("text") or "").strip()
                    if len(p_text) < 40 and len(prev_text) < 90:
                        # Слияние коротких параграфов
                        result[-1]["text"] = prev_text + " " + p_text
                    else:
                        result.append(p)
                else:
                    result.append(p)

    print(f"[LAYOUT v2.1] paragraphs built: {len(result)}")
    return result
