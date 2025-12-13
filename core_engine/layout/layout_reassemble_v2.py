# layout_reassemble_v2.1.py
# Улучшенный layout-процессор для ядра v7.1

from __future__ import annotations

from typing import Any, Dict, List
import re

from core_engine.layout.sentence_merger import merge_paragraphs_in_stream
from core_engine.layout.column_detector import detect_columns


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
    
    # "1 I Р А R Т" → "PART I" (разорванный PART в начале)
    part_broken_start = re.match(r"^(\d+)\s+([I1])\s+([РP]\s+[АA]\s+[RР]\s+[ТT])", t_normalized, re.IGNORECASE)
    if part_broken_start:
        return f"PART {part_broken_start.group(2).upper()}", "", "heading1"
    
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


def _looks_like_footnote(text: str) -> bool:
    """
    Детектирует сноски:
    - Короткий текст внизу страницы
    - Начинается с цифры/звездочки/буквы и скобки
    - Очень маленький шрифт (если есть metadata)
    """
    t = text.strip()
    if not t or len(t) > 200:  # Сноски обычно короткие
        return False
    
    # Исключаем заголовки и длинные тексты
    if len(t) > 100:  # Сноски короткие
        return False
    
    # Исключаем если это похоже на заголовок (много заглавных букв)
    if len(t) > 20:
        upper_ratio = sum(1 for c in t if c.isupper()) / max(len([c for c in t if c.isalpha()]), 1)
        if upper_ratio > 0.5:  # Больше 50% заглавных - это заголовок, не сноска
            return False
    
    # Паттерны сносок: "1)", "1.", "*", "a)", "[1]", "¹"
    # Но только если это действительно короткая строка
    footnote_patterns = [
        r"^\d+[\.\)\]\}]$",  # "1)", "1.", "1]", "1}" - только если это вся строка
        r"^\d+[\.\)\]\}]\s+",  # "1) текст" - начинается с номера и скобки
        r"^[a-z][\.\)\]\}]$",  # "a)", "a." - только если это вся строка
        r"^[\*\†\‡\§]\s+",  # "* текст" - начинается со символа
        r"^\[?\d+\]?\s+",  # "[1] текст" или "1 текст"
        r"^[¹²³⁴⁵⁶⁷⁸⁹⁰]\s+",  # Верхние индексы с текстом
    ]
    
    for pattern in footnote_patterns:
        if re.match(pattern, t, re.IGNORECASE):
            return True
    
    return False


def _looks_like_formula(text: str) -> bool:
    """
    Детектирует математические формулы:
    - Содержит математические символы (∑, ∫, √, ≤, ≥, ≠, ≈, etc.)
    - Содержит индексы/степени
    - Содержит дроби (a/b, \frac)
    - Содержит греческие буквы в математическом контексте
    """
    t = text.strip()
    if not t or len(t) < 3:
        return False
    
    # Математические символы
    math_symbols = r"[∑∫√≤≥≠≈±×÷∞∈∉⊂⊃∪∩∅→←⇒⇐]"
    if re.search(math_symbols, t):
        return True
    
    # Верхние/нижние индексы
    if re.search(r"[¹²³⁴⁵⁶⁷⁸⁹⁰₀₁₂₃₄₅₆₇₈₉]", t):
        return True
    
    # Дроби вида a/b или \frac
    if re.search(r"\b\d+/\d+\b", t) or "\\frac" in t:
        return True
    
    # Греческие буквы в математическом контексте (α, β, γ, δ, etc.)
    greek_letters = r"[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]"
    if re.search(greek_letters, t) and len(t) < 100:  # Короткие формулы
        return True
    
    # LaTeX-подобные команды
    if re.search(r"\\[a-zA-Z]+\{", t):
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
    """
    Улучшенная детекция таблиц:
    - Таблицы с разделителями |
    - Markdown-style таблицы
    - Таблицы с множеством табуляций/пробелов
    - Таблицы с числами в колонках
    """
    if not text or len(text.strip()) < 10:
        return False
    
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    
    # Таблицы с разделителями |
    if "|" in text:
        pipe_lines = sum(1 for ln in lines if "|" in ln)
        if pipe_lines >= 2 and pipe_lines >= len(lines) * 0.7:  # 70%+ строк с |
            return True
    
    # Markdown-style таблицы
    if re.search(r"^-{2,}\s+-{2,}", text, flags=re.MULTILINE):
        return True
    
    # Таблицы с множеством табуляций (TSV-style)
    tab_lines = sum(1 for ln in lines if "\t" in ln and ln.count("\t") >= 2)
    if tab_lines >= 2 and tab_lines >= len(lines) * 0.6:
        return True
    
    # Таблицы с множеством пробелов между колонками (фиксированная ширина)
    space_separated = 0
    for ln in lines:
        # Ищем строки с множеством последовательных пробелов (>= 3)
        if re.search(r"\s{3,}", ln):
            parts = re.split(r"\s{3,}", ln)
            if len(parts) >= 3:  # Минимум 3 колонки
                space_separated += 1
    if space_separated >= 2 and space_separated >= len(lines) * 0.5:
        return True
    
    return False


def _parse_table_rows(text: str) -> List[List[str]]:
    """
    Парсит таблицу в список строк.
    Поддерживает разные форматы: | разделители, табуляции, пробелы.
    """
    rows = []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    
    if not lines:
        return rows
    
    # Определяем формат таблицы
    has_pipes = any("|" in ln for ln in lines)
    has_tabs = any("\t" in ln for ln in lines)
    
    for ln in lines:
        # Пропускаем markdown разделители
        if re.match(r"^-{2,}\s+-{2,}", ln):
            continue
        
        if has_pipes:
            # Таблица с | разделителями
        parts = [c.strip() for c in ln.split("|")]
            # Убираем пустые элементы в начале/конце (от разделителей)
            if parts and not parts[0]:
                parts = parts[1:]
            if parts and not parts[-1]:
                parts = parts[:-1]
            if parts:
                rows.append(parts)
        elif has_tabs:
            # TSV-style таблица
            parts = [c.strip() for c in ln.split("\t")]
            if parts:
                rows.append(parts)
        else:
            # Таблица с множеством пробелов
            parts = re.split(r"\s{3,}", ln)
            parts = [c.strip() for c in parts if c.strip()]
            if parts:
        rows.append(parts)
    
    # Нормализуем количество колонок (дополняем пустыми строками)
    if rows:
        max_cols = max(len(r) for r in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")
    
    return rows


# ============================================================
#                          ДВЕ КОЛОНКИ
# ============================================================

def _order_blocks_two_columns(
    blocks: List[Dict[str, Any]],
    col_assignments: Dict[str, int] | None = None,
    columns: List[Any] | None = None,
) -> List[Dict[str, Any]]:
    """
    Улучшенная двухколоночная верстка:
    - Определяет есть ли две колонки
    - Чередует блоки из левой и правой колонок по y-позиции
    - Сохраняет правильный порядок чтения (слева направо, сверху вниз)
    """
    col_assignments = col_assignments or {}
    columns = columns or []

    with_bbox = [b for b in blocks if b.get("bbox")]
    no_bbox = [b for b in blocks if not b.get("bbox")]

    if not with_bbox:
        return sorted(blocks, key=lambda b: b.get("order", 0))

    # Если есть уверенные назначения колонок (>=40% блоков с bbox имеют assignment) — используем их
    def _bucket_idx(b: Dict[str, Any]) -> int | None:
        bid = b.get("id") or b.get("block_id")
        if bid in col_assignments:
            try:
                return int(col_assignments[bid])
            except Exception:
                return None
        return None

    assigned = [b for b in with_bbox if _bucket_idx(b) is not None]
    use_assignments = assigned and len(assigned) >= 0.4 * len(with_bbox)

    ordered: List[Dict[str, Any]]

    if use_assignments:
        buckets: Dict[int, List[Dict[str, Any]]] = {}
        max_idx = -1
        for b in assigned:
            idx = _bucket_idx(b)
            if idx is None:
                continue
            buckets.setdefault(idx, []).append(b)
            max_idx = max(max_idx, idx)

        # Сортировка внутри каждой колонки по y
        for arr in buckets.values():
            arr.sort(key=lambda b: (b["bbox"]["y0"], b.get("order", 0)))

        # Interleave по колонкам (для 2 колонок — предыдущая логика)
        if max_idx == 1 and len(buckets) == 2:
            left = buckets.get(0, [])
            right = buckets.get(1, [])
            ordered = []
            left_idx = 0
            right_idx = 0
            while left_idx < len(left) or right_idx < len(right):
                left_y = left[left_idx]["bbox"]["y0"] if left_idx < len(left) else float("inf")
                right_y = right[right_idx]["bbox"]["y0"] if right_idx < len(right) else float("inf")
                if abs(left_y - right_y) < 50:
                    if left_idx < len(left):
                        ordered.append(left[left_idx])
                        left_idx += 1
                    if right_idx < len(right):
                        ordered.append(right[right_idx])
                        right_idx += 1
                elif left_y < right_y:
                    ordered.append(left[left_idx])
                    left_idx += 1
                else:
                    ordered.append(right[right_idx])
                    right_idx += 1
        else:
            # >2 колонок или несбалансировано: глобальная слияние по ближайшему y
            ordered = []
            heads = {k: 0 for k in buckets}
            while True:
                best_col = None
                best_y = float("inf")
                for k, arr in buckets.items():
                    idx = heads[k]
                    if idx >= len(arr):
                        continue
                    y = arr[idx]["bbox"]["y0"]
                    if y < best_y:
                        best_y = y
                        best_col = k
                if best_col is None:
                    break
                ordered.append(buckets[best_col][heads[best_col]])
                heads[best_col] += 1

        # Добавляем необработанные блоки (без assignment) по y
        leftovers = [b for b in with_bbox if _bucket_idx(b) is None]
        if leftovers:
            ordered += sorted(leftovers, key=lambda b: (b["bbox"]["y0"], b.get("order", 0)))
    else:
        # Fallback: старая эвристика по spread
    xs = [b["bbox"]["x0"] for b in with_bbox]
    spread = max(xs) - min(xs)

    if spread < 120:
            # Одна колонка - просто сортируем по y
        ordered = sorted(with_bbox, key=lambda b: (b["bbox"]["y0"], b.get("order", 0)))
    else:
            # Две колонки - определяем границу
        mid = sorted(xs)[len(xs) // 2]
        left = sorted(
            [b for b in with_bbox if b["bbox"]["x0"] <= mid],
            key=lambda b: (b["bbox"]["y0"], b.get("order", 0)),
        )
        right = sorted(
            [b for b in with_bbox if b["bbox"]["x0"] > mid],
            key=lambda b: (b["bbox"]["y0"], b.get("order", 0)),
        )
            
            # Чередуем блоки из левой и правой колонок по y-позиции
            ordered = []
            left_idx = 0
            right_idx = 0
            
            while left_idx < len(left) or right_idx < len(right):
                # Определяем какой блок идет следующим по y-позиции
                left_y = left[left_idx]["bbox"]["y0"] if left_idx < len(left) else float('inf')
                right_y = right[right_idx]["bbox"]["y0"] if right_idx < len(right) else float('inf')
                
                # Если блоки близко по y (в пределах 50px), берем левый первым
                if abs(left_y - right_y) < 50:
                    if left_idx < len(left):
                        ordered.append(left[left_idx])
                        left_idx += 1
                    if right_idx < len(right):
                        ordered.append(right[right_idx])
                        right_idx += 1
                elif left_y < right_y:
                    ordered.append(left[left_idx])
                    left_idx += 1
                else:
                    ordered.append(right[right_idx])
                    right_idx += 1

    tail = sorted(no_bbox, key=lambda b: b.get("order", 0))
    return ordered + tail


# ============================================================
#                     БЛОК → ПАРАГРАФЫ
# ============================================================

def _block_to_paragraphs(block: Dict[str, Any], page: int) -> List[Dict[str, Any]]:
    text = (block.get("translated_text") or "").strip()
    if not text:
        return []
    
    # Нормализуем переносы строк внутри текста: заменяем \n на пробелы в параграфах
    # (но сохраняем для списков и других специальных типов)
    text = re.sub(r"\n+", " ", text)  # Множественные переносы → один пробел
    text = re.sub(r"\s+", " ", text)  # Множественные пробелы → один
    text = text.strip()

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
    
    # FOOTNOTE
    if _looks_like_footnote(text) or role == "footnote":
        return [{"type": "footnote", "text": text, "page": page}]
    
    # FORMULA
    if _looks_like_formula(text):
        return [{"type": "formula", "text": text, "page": page}]
    
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
    
    # Детекция обрывков заголовков: короткий текст с числом в конце
    # "в Физической терапии 5" - вероятно обрывок заголовка
    if len(text) < 50 and re.search(r"\s+\d+\s*$", text):
        # Проверяем что это не просто номер страницы
        if not re.match(r"^\d+$", text.strip()):
            # Вероятно обрывок заголовка - помечаем как heading2
        return [{"type": "heading2", "text": text, "page": page}]

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


def _table_to_paragraph(table: Dict[str, Any], page: int) -> List[Dict[str, Any]]:
    """
    Конвертация таблицы (dict или TableObject) в paragraph-stream формат.
    """
    rows_out: List[List[str]] = []

    # Извлекаем ячейки
    cells = table.get("cells") or []
    if hasattr(table, "cells"):
        try:
            cells = table.cells  # TableObject
        except Exception:
            pass

    if cells:
        # Группируем по row/col
        rows_by_idx: Dict[int, Dict[int, str]] = {}
        max_col = 0
        for c in cells:
            try:
                r_idx = int(getattr(c, "row", c.get("row", 0)))
                c_idx = int(getattr(c, "col", c.get("col", 0)))
                txt = getattr(c, "text", None) if not isinstance(c, dict) else c.get("text")
            except Exception:
                continue
            max_col = max(max_col, c_idx)
            rows_by_idx.setdefault(r_idx, {})
            rows_by_idx[r_idx][c_idx] = (txt or "").strip()

        for r_idx in sorted(rows_by_idx.keys()):
            row_cells = []
            for c_idx in range(max_col + 1):
                row_cells.append(rows_by_idx[r_idx].get(c_idx, ""))
            rows_out.append(row_cells)

    label = table.get("label") if isinstance(table, dict) else getattr(table, "label", None)
    caption = table.get("caption") if isinstance(table, dict) else getattr(table, "caption", None)

    para = {
        "type": "table",
        "rows": rows_out,
        "text": label or "",
        "page": page,
    }
    out = [para]
    if caption:
        out.append({"type": "caption", "text": caption, "page": page})
    return out


def _get_text_from_block(block: Dict[str, Any]) -> str:
    return (
        block.get("translated_text")
        or block.get("normalized_text")
        or block.get("text")
        or block.get("raw_text")
        or ""
    )


def _looks_like_caption(text: str, kind: str) -> bool:
    t = text.lower().strip()
    if not t:
        return False
    if kind == "figure":
        return bool(re.match(r"^(fig(?:ure)?\.?|рис\.?|рисунок)\b", t, re.IGNORECASE))
    if kind == "table":
        return bool(re.match(r"^(table|табл\.?|таблица)\b", t, re.IGNORECASE))
    return False


def _overlap_ratio(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    denom = max(1e-3, max(a1, b1) - min(a0, b0))
    return inter / denom


def _find_captions(blocks: List[Dict[str, Any]], images: List[Dict[str, Any]], tables: List[Dict[str, Any]]):
    """
    Находим подписи рядом с изображениями/таблицами.
    Эвристика: короткий текст, триггерные слова (Figure/Fig/Рис или Table/Таблица),
    bbox близко по y и с перекрытием по x.
    """
    captions_by_obj: Dict[str, str] = {}
    used_blocks: set[str] = set()

    def search_for(obj: Dict[str, Any], kind: str) -> None:
        bbox = obj.get("bbox") or {}
        x0, y0, x1, y1 = bbox.get("x0", 0), bbox.get("y0", 0), bbox.get("x1", 0), bbox.get("y1", 0)
        if x1 <= x0 and y1 <= y0:
            return

        best_block = None
        best_score = 1e9
        for b in blocks:
            bid = b.get("id") or b.get("block_id")
            if not bid or bid in used_blocks:
                continue
            bb = b.get("bbox") or {}
            bx0, by0, bx1, by1 = bb.get("x0", 0), bb.get("y0", 0), bb.get("x1", 0), bb.get("y1", 0)
            if bx1 <= bx0 and by1 <= by0:
                continue
            txt = _get_text_from_block(b)
            if len(txt) > 180:
                continue
            if not _looks_like_caption(txt, kind):
                continue
            # Требуем перекрытие по X
            if _overlap_ratio(x0, x1, bx0, bx1) < 0.25:
                continue
            # Близость по Y: подпись под объектом или чуть сверху
            if by0 > y1 + 120 or by1 < y0 - 60:
                continue
            dist = min(abs(by0 - y1), abs(by1 - y0))
            if dist < best_score:
                best_score = dist
                best_block = b

        if best_block:
            bid = best_block.get("id") or best_block.get("block_id")
            captions_by_obj[id(obj)] = _get_text_from_block(best_block).strip()
            used_blocks.add(bid)

    for img in images:
        search_for(img, "figure")
    for tbl in tables:
        search_for(tbl, "table")

    return captions_by_obj, used_blocks


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
        images = page.get("images", [])  # Изображения из layout_model
        tables = page.get("tables", [])

        # Колонки из ingest (best-effort)
        col_meta = page.get("metadata", {}) or {}
        col_assignments = col_meta.get("column_assignments", {}) or {}

        # Page break между страницами (кроме первой)
        if prev_page > 0 and page_num != prev_page:
            result.append({"type": "page_break", "page": page_num})
        prev_page = page_num

        # Подписи к изображениям/таблицам (эвристика)
        captions_map, caption_blocks_used = _find_captions(blocks, images, tables)

        ordered = _order_blocks_two_columns(
            blocks,
            col_assignments=col_assignments,
            columns=col_meta.get("columns", []),
        )

        # Добавляем изображения в правильном порядке (по позиции y0)
        # Сортируем изображения по позиции на странице
        images_sorted = sorted(images, key=lambda img: img.get("bbox", {}).get("y0", 0))
        image_idx = 0
        tables_sorted = sorted(
            tables,
            key=lambda t: (t.get("bbox", {}).get("y0", 0) if isinstance(t, dict) else getattr(t, "bbox", None).y0 if getattr(t, "bbox", None) else 0),
        )
        table_idx = 0

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
            # Проверяем, нужно ли вставить изображение/таблицу перед этим блоком
            block_y0 = b.get("bbox", {}).get("y0", 0) if isinstance(b.get("bbox"), dict) else 0
            
            # Вставляем таблицы выше текущего блока
            while table_idx < len(tables_sorted):
                tbl = tables_sorted[table_idx]
                tbl_y0 = tbl.get("bbox", {}).get("y0", 0) if isinstance(tbl, dict) else getattr(tbl, "bbox", None).y0 if getattr(tbl, "bbox", None) else 0
                if tbl_y0 < block_y0 or block_y0 == 0:
                    result.extend(_table_to_paragraph(tbl, page_num))
                    table_idx += 1
                else:
                    break

            # Вставляем изображения выше текущего блока
            while image_idx < len(images_sorted):
                img = images_sorted[image_idx]
                img_y0 = img.get("bbox", {}).get("y0", 0)
                if img_y0 < block_y0 or block_y0 == 0:
                    # НЕ добавляем image_bytes здесь - он будет восстановлен в pipeline из images_by_page
                    label = captions_map.get(id(img), img.get("label"))
                    result.append({
                        "type": "image",
                        "image_id": img.get("id", f"img_{fig_id}"),
                        "label": label,
                        "page": page_num,
                    })
                    image_idx += 1
                    fig_id += 1
                else:
                    break
            
            # Пропускаем блоки, использованные как подписи
            bid = b.get("id") or b.get("block_id")
            if bid and bid in caption_blocks_used:
                continue

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
                    
                    if not p_text or not prev_text:
                        result.append(p)
                        continue
                    
                    # Улучшенная логика слияния разорванных предложений
                    prev_ends_punct = prev_text and prev_text[-1] in ".!?;:"
                    prev_ends_comma = prev_text and prev_text[-1] in ","
                    p_starts_lower = p_text and p_text[0].islower()
                    p_starts_upper = p_text and p_text[0].isupper()
                    
                    # Признаки разорванного предложения:
                    # 1. Предыдущий текст не заканчивается точкой/восклицательным/вопросительным
                    # 2. Текущий текст начинается с маленькой буквы (продолжение)
                    # 3. Или текущий текст очень короткий (< 40 символов)
                    should_merge = False
                    
                    if not prev_ends_punct:
                        if p_starts_lower:
                            # Продолжение предложения (начинается с маленькой буквы)
                            should_merge = True
                        elif len(p_text) < 40 and len(prev_text) < 200:
                            # Короткий фрагмент после незавершенного предложения
                            should_merge = True
                        elif prev_ends_comma and len(p_text) < 60:
                            # После запятой короткий фрагмент - скорее всего продолжение
                            should_merge = True
                    
                    if should_merge:
                        # Слияние с правильным пробелом
                        if prev_text[-1] in ",;:":
                            result[-1]["text"] = prev_text + " " + p_text
                        else:
                            result[-1]["text"] = prev_text + " " + p_text
                    else:
                        result.append(p)
                else:
                    result.append(p)
        
        # Добавляем оставшиеся изображения в конце страницы
        while image_idx < len(images_sorted):
            img = images_sorted[image_idx]
            # НЕ добавляем image_bytes здесь - он будет восстановлен в pipeline из images_by_page
            label = captions_map.get(id(img), img.get("label"))
            result.append({
                "type": "image",
                "image_id": img.get("id", f"img_{fig_id}"),
                "label": label,
                "page": page_num,
            })
            image_idx += 1
            fig_id += 1

        # Добавляем оставшиеся таблицы
        while table_idx < len(tables_sorted):
            tbl = tables_sorted[table_idx]
            result.extend(_table_to_paragraph(tbl, page_num))
            table_idx += 1

    print(f"[LAYOUT v2.1] paragraphs built: {len(result)}")
    
    # Разделяем смешанные параграфы (заголовки + текст)
    from core_engine.layout.paragraph_splitter import split_paragraphs_with_headings
    result = split_paragraphs_with_headings(result)
    print(f"[LAYOUT v2.1] after splitting mixed paragraphs: {len(result)}")
    
    # Улучшенное слияние разорванных предложений
    result = merge_paragraphs_in_stream(result)
    
    print(f"[LAYOUT v2.1] after sentence merging: {len(result)}")
    return result
