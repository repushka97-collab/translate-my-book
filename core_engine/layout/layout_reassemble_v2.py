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


def _split_structural_heading(text: str) -> tuple[str, str]:
    """
    Извлекает структурные заголовки:
    '1 Введение ...', '1.2 Methods ...'
    """
    t = text.strip()
    if not t:
        return "", ""

    # Глава 1 / Chapter 1 → Heading1
    if re.match(r"^\s*(глава|chapter)\s+\d+\b", t.lower()):
        return t, ""

    # Формат: "1 Введение ..."
    m = re.match(
        r"^\s*(\d+[\.\)]?)\s+([A-ZА-ЯЁ][\w\-\(\) ]{2,60})\s+(.*)$",
        t,
    )
    if m:
        head = f"{m.group(1).strip()} {m.group(2).strip()}"
        body = m.group(3).strip()
        return head, body

    # Классический split
    m = _HEADING_SPLIT_RE.match(t)
    if m:
        num = m.group("num").strip()
        title = m.group("title").strip()
        body = (m.group("body") or "").strip()

        if len(title) <= 120:
            return f"{num} {title}", body if len(body) > 10 else ""

    return "", ""


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

    out = []

    # ABSTRACT
    abs_title, abs_body = _split_abstract_block(text)
    if abs_title:
        out.append({"type": "heading2", "text": abs_title, "page": page})
        if abs_body:
            out.append({"type": "paragraph", "text": abs_body, "page": page})
        return out

    # CAPTION
    if _looks_like_figure_caption(text):
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
    head, body = _split_structural_heading(text)
    if head:
        out.append({"type": "heading2", "text": head, "page": page})
        if body:
            out.append({"type": "paragraph", "text": body, "page": page})
        return out

    # LIST ITEM
    if _looks_like_list_item(text):
        return [{"type": "list_item", "text": text, "page": page}]

    # SOFT HEADING
    if _looks_like_heading(text):
        return [{"type": "heading2", "text": text, "page": page}]

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

    for page in sorted(pages, key=lambda p: p.get("page_num", 0)):
        page_num = page.get("page_num", 0)
        blocks = page.get("blocks", [])

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
                if (
                    result
                    and p["type"] == "paragraph"
                    and len(p["text"]) < 40
                    and len(result[-1]["text"]) < 90
                ):
                    result[-1]["text"] += " " + p["text"]
                else:
                    result.append(p)

    print(f"[LAYOUT v2.1] paragraphs built: {len(result)}")
    return result
