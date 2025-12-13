from __future__ import annotations

import base64
from html import escape
from pathlib import Path
from typing import List

from core_engine.core.models import BookDocument, Page, Block, ImageObject, TableObject


def _escape(txt: str) -> str:
    return escape(txt, quote=True)


def _block_text(block: Block) -> str:
    return (
        block.translated_text
        or block.normalized_text
        or block.raw_text
        or ""
    )


def _inline_style_block(bbox, font_size: float | None, is_bold: bool, is_italic: bool, font_name: str) -> str:
    width = bbox.x1 - bbox.x0
    height = bbox.y1 - bbox.y0
    styles = [
        f"position:absolute",
        f"left:{bbox.x0}px",
        f"top:{bbox.y0}px",
        f"width:{max(width,1)}px",
        f"height:{max(height,1)}px",
        f"font-size:{font_size if font_size else 12}px",
        f"line-height:1.25",
        f"white-space:pre-wrap",
    ]
    if font_name:
        styles.append(f"font-family:'{font_name}', serif")
    if is_bold:
        styles.append("font-weight:bold")
    if is_italic:
        styles.append("font-style:italic")
    return ";".join(styles)


def _image_to_data_uri(img: ImageObject) -> str:
    mime = img.mime_type or "image/png"
    b64 = base64.b64encode(img.image_bytes).decode("ascii") if img.image_bytes else ""
    return f"data:{mime};base64,{b64}"


def _table_to_html(table: TableObject) -> str:
    # Простая отрисовка таблицы без colspan/rowspan (их пока нет в модели)
    rows_by_idx = {}
    max_col = 0
    for cell in table.cells:
        rows_by_idx.setdefault(cell.row, {})
        rows_by_idx[cell.row][cell.col] = cell.text
        max_col = max(max_col, cell.col)

    rows_html: List[str] = []
    for r_idx in sorted(rows_by_idx.keys()):
        cells_html = []
        for c_idx in range(max_col + 1):
            txt = rows_by_idx[r_idx].get(c_idx, "")
            cells_html.append(f"<td>{_escape(txt)}</td>")
        rows_html.append(f"<tr>{''.join(cells_html)}</tr>")

    return f"<table style='width:100%;height:100%;border-collapse:collapse;border:1px solid #ccc;font-size:12px;line-height:1.25'>{''.join(rows_html)}</table>"


def export_html_absolute(doc: BookDocument, out_path: str) -> None:
    """
    HTML с абсолютным позиционированием по исходным bbox (в поинтах~px).
    - Использует raster_preview как фон (если есть).
    - Блоки, изображения, таблицы кладутся слоями поверх.
    """
    parts: List[str] = []
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append(
        "<style>body{margin:0;padding:0;background:#f7f7f7;} .page{position:relative;margin:20px auto;box-shadow:0 0 6px rgba(0,0,0,0.2);} .layer{position:absolute;}</style>"
    )
    parts.append("</head><body>")

    for page in doc.pages:
        w = page.width
        h = page.height
        bg = page.metadata.get("raster_preview_png_b64", "")
        bg_style = ""
        if bg:
            bg_style = f"background:url(data:image/png;base64,{bg}) no-repeat left top;background-size:{w}px {h}px;"
        parts.append(f"<div class='page' style='width:{w}px;height:{h}px;{bg_style}'>")

        # Таблицы под текстом, но над фоном
        for tbl in page.tables:
            bbox = tbl.bbox
            width = bbox.x1 - bbox.x0
            height = bbox.y1 - bbox.y0
            parts.append(
                f"<div class='layer' style='left:{bbox.x0}px;top:{bbox.y0}px;width:{max(width,1)}px;height:{max(height,1)}px;border:1px solid #ccc;background:#fff'>{_table_to_html(tbl)}</div>"
            )

        # Изображения
        for img in page.images:
            bbox = img.bbox
            width = bbox.x1 - bbox.x0
            height = bbox.y1 - bbox.y0
            data_uri = _image_to_data_uri(img)
            parts.append(
                f"<img class='layer' src='{data_uri}' style='left:{bbox.x0}px;top:{bbox.y0}px;width:{max(width,1)}px;height:{max(height,1)}px;object-fit:contain;'/>"
            )

        # Текстовые блоки
        for block in page.blocks:
            bbox = block.bbox
            font_size = block.metadata.get("font_size") if isinstance(block.metadata, dict) else None
            is_bold = bool(block.metadata.get("is_bold")) if isinstance(block.metadata, dict) else False
            is_italic = bool(block.metadata.get("is_italic")) if isinstance(block.metadata, dict) else False
            font_name = block.metadata.get("font") if isinstance(block.metadata, dict) else ""
            txt = _escape(_block_text(block))
            style = _inline_style_block(bbox, font_size, is_bold, is_italic, font_name or "")
            parts.append(f"<div class='layer' style='{style}'>{txt}</div>")

        parts.append("</div>")  # page

    parts.append("</body></html>")

    Path(out_path).write_text("\n".join(parts), encoding="utf-8")

