from __future__ import annotations

import base64
import os
from html import escape
from pathlib import Path
from typing import List, Dict

from core_engine.core.models import BookDocument, Page, Block, ImageObject, TableObject, BlockType


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
    
    # Улучшенное позиционирование для absolute layout
    # Предотвращаем наезд текста: используем min-height и правильный overflow
    styles = [
        f"position:absolute",
        f"left:{bbox.x0}px",
        f"top:{bbox.y0}px",
        f"width:{max(width,1)}px",
        f"min-height:{max(height,1)}px",  # min-height вместо height для предотвращения обрезки
        f"max-height:{max(height * 1.5, height + 20)}px",  # Ограничиваем максимальную высоту
        f"font-size:{font_size if font_size else 12}px",
        f"line-height:1.2",  # Улучшенный line-height для кириллицы
        f"white-space:pre-wrap",
        f"overflow-wrap:break-word",
        f"word-wrap:break-word",
        f"overflow:hidden",  # Скрываем переполнение
        f"margin:0",
        f"padding:1px",  # Минимальный padding
        f"box-sizing:border-box",  # Padding включается в размер
    ]
    
    # Улучшенная поддержка шрифтов с кириллицей
    if font_name:
        # Добавляем fallback шрифты с поддержкой кириллицы
        font_family = f"'{font_name}', 'Arial', 'DejaVu Sans', 'Liberation Sans', sans-serif"
        styles.append(f"font-family:{font_family}")
    else:
        styles.append("font-family:'Arial', 'DejaVu Sans', 'Liberation Sans', sans-serif")
    
    if is_bold:
        styles.append("font-weight:bold")
    if is_italic:
        styles.append("font-style:italic")
    
    return ";".join(styles)


def _image_to_data_uri(img: ImageObject) -> str:
    mime = img.mime_type or "image/png"
    if not img.image_bytes:
        return ""
    b64 = base64.b64encode(img.image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _overlap_ratio(a0: float, a1: float, b0: float, b1: float) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    denom = max(1e-3, max(a1, b1) - min(a0, b0))
    return inter / denom


def _find_captions_for_images(blocks: List[Block], images: List[ImageObject]) -> Dict[str, str]:
    """
    Эвристика: ищем короткие блоки рядом с картинками, помечаем как подпись.
    Возвращает map image_id -> caption, и помечает блоки в used_caption_ids.
    """
    captions = {}
    used_ids = set()
    if not blocks or not images:
        return captions, used_ids

    for img in images:
        if not hasattr(img, "bbox"):
            continue
        ib = img.bbox
        best = None
        best_score = 1e9
        for b in blocks:
            bid = getattr(b, "id", None)
            if not bid or bid in used_ids:
                continue
            if b.type == BlockType.CAPTION or (isinstance(b.metadata, dict) and (b.metadata.get("role") == "caption")):
                is_caption_candidate = True
            else:
                txt = _block_text(b).strip()
                is_caption_candidate = len(txt) > 0 and len(txt) <= 240
            if not is_caption_candidate:
                continue
            bb = getattr(b, "bbox", None)
            if not bb:
                continue
            # требуем перекрытие по X
            if _overlap_ratio(ib.x0, ib.x1, bb.x0, bb.x1) < 0.25:
                continue
            # подпись обычно под или чуть над изображением
            if bb.y0 > ib.y1 + 120 or bb.y1 < ib.y0 - 120:
                continue
            dist = min(abs(bb.y0 - ib.y1), abs(bb.y1 - ib.y0))
            if dist < best_score:
                best_score = dist
                best = b
        if best:
            captions[getattr(img, "id", "")] = _block_text(best).strip()
            used_ids.add(best.id)
    return captions, used_ids


def _table_to_html(table: TableObject) -> str:
    # Отрисовка таблицы с поддержкой rowspan/colspan
    rows_by_idx = {}
    max_row = 0
    max_col = 0
    for cell in table.cells:
        rows_by_idx.setdefault(cell.row, {})
        rows_by_idx[cell.row][cell.col] = cell
        max_row = max(max_row, cell.row)
        max_col = max(max_col, cell.col)

    # Простейшая эвристика colspan: если клетка пустая и слева пустая — объединяем влево
    for r_idx, row_cells in rows_by_idx.items():
        c = 1
        while c <= max_col:
            cell = row_cells.get(c)
            prev = row_cells.get(c - 1)
            if not cell or not prev:
                c += 1
                continue
            txt = getattr(cell, "text", "").strip()
            prev_txt = getattr(prev, "text", "").strip()
            if txt == "" and prev_txt == "":
                prev.colspan = getattr(prev, "colspan", 1) + getattr(cell, "colspan", 1)
                row_cells.pop(c)
                max_col = max(max_col, c)
                continue
            c += 1

    rows_html: List[str] = []
    for r_idx in range(max_row + 1):
        cells_html = []
        row_cells = rows_by_idx.get(r_idx, {})
        for c_idx in range(max_col + 1):
            cell = row_cells.get(c_idx)
            if cell is None:
                cells_html.append("<td></td>")
                continue
            rs = getattr(cell, "rowspan", 1) or 1
            cs = getattr(cell, "colspan", 1) or 1
            txt = getattr(cell, "text", "")
            attr_rs = f" rowspan=\"{int(rs)}\"" if rs > 1 else ""
            attr_cs = f" colspan=\"{int(cs)}\"" if cs > 1 else ""
            style = "border:1px solid #ccc; padding:4px;"
            cells_html.append(f"<td style=\"{style}\"{attr_rs}{attr_cs}>{_escape(txt)}</td>")
        rows_html.append(f"<tr>{''.join(cells_html)}</tr>")

    return f"<table style='width:100%;border-collapse:collapse;border:1px solid #ccc;font-size:12px;line-height:1.25'>{''.join(rows_html)}</table>"


def export_html_absolute(doc: BookDocument, out_path: str) -> None:
    """
    HTML с абсолютным позиционированием по исходным bbox (в поинтах~px).
    Улучшенная версия для точного сохранения позиций элементов.
    """
    parts: List[str] = []
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("""
    <style>
    * { box-sizing: border-box; }
    body {
        margin: 0;
        padding: 0;
        background: #f7f7f7;
        font-family: 'Georgia', 'Times New Roman', serif;
    }
    .page {
        position: relative;
        margin: 20px auto;
        box-shadow: 0 0 6px rgba(0,0,0,0.2);
        background: #fff;
        overflow: hidden;
    }
    .layer {
        position: absolute;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    .text-layer {
        line-height: 1.2;
        margin: 0;
        padding: 0;
        z-index: 3;  /* Текст поверх всего */
        overflow: hidden;  /* Предотвращаем наезд */
        position: absolute;
        display: block;
    }
    .image-layer {
        object-fit: contain;
        z-index: 1;  /* Изображения под текстом */
        position: absolute;
        display: block;
        margin: 0;
        padding: 0;
    }
    .table-layer {
        border-collapse: collapse;
        z-index: 2;  /* Таблицы между изображениями и текстом */
        position: absolute;
    }
    </style>
    """)
    parts.append("</head><body>")

    for page in doc.pages:
        w = page.width
        h = page.height
        bg = page.metadata.get("raster_preview_png_b64", "") if hasattr(page, "metadata") and page.metadata else ""
        bg_style = ""
        if bg:
            bg_style = f"background:url(data:image/png;base64,{bg}) no-repeat left top;background-size:{w}px {h}px;"
        parts.append(f"<div class='page' style='width:{w}px;height:{h}px;{bg_style}'>")

        # Изображения ПЕРВЫМИ (нижний слой, z-index: 1)
        # КРИТИЧНО: Проверяем что изображения есть и вставляем их
        images_inserted = 0
        for img in page.images:
            if not img.image_bytes:
                print(f"      [HTML_EXPORT] Warning: Image on page {page.number} has no image_bytes")
                continue
            if not hasattr(img, "bbox") or not img.bbox:
                print(f"      [HTML_EXPORT] Warning: Image on page {page.number} has no bbox")
                continue
            bbox = img.bbox
            width = bbox.x1 - bbox.x0
            height = bbox.y1 - bbox.y0
            if width <= 0 or height <= 0:
                print(f"      [HTML_EXPORT] Warning: Image on page {page.number} has invalid dimensions")
                continue
            data_uri = _image_to_data_uri(img)
            if data_uri:
                # КРИТИЧНО: Используем position:absolute и правильный z-index
                # Добавляем display:block для гарантированного отображения
                parts.append(
                    f"<img class='layer image-layer' src='{data_uri}' style='position:absolute;left:{bbox.x0}px;top:{bbox.y0}px;width:{max(width,1)}px;height:{max(height,1)}px;object-fit:contain;z-index:1;display:block;margin:0;padding:0;'/>"
                )
                images_inserted += 1
        if images_inserted > 0:
            print(f"      [HTML_EXPORT] Inserted {images_inserted} images on page {page.number}")

        # Таблицы (средний слой, z-index: 2)
        for tbl in page.tables:
            bbox = tbl.bbox
            width = bbox.x1 - bbox.x0
            height = bbox.y1 - bbox.y0
            parts.append(
                f"<div class='layer table-layer' style='left:{bbox.x0}px;top:{bbox.y0}px;width:{max(width,1)}px;height:{max(height,1)}px;border:1px solid #ccc;background:#fff;z-index:2;'>{_table_to_html(tbl)}</div>"
            )

        # Текстовые блоки ПОСЛЕДНИМИ (верхний слой, z-index: 3)
        # Сортируем по позиции для правильного порядка
        sorted_blocks = sorted(page.blocks, key=lambda b: (b.bbox.y0 if hasattr(b, "bbox") and b.bbox else 0, b.bbox.x0 if hasattr(b, "bbox") and b.bbox else 0))
        blocks_inserted = 0
        for block in sorted_blocks:
            if not hasattr(block, "bbox") or not block.bbox:
                continue
            bbox = block.bbox
            # Проверяем валидность bbox
            if bbox.x1 <= bbox.x0 or bbox.y1 <= bbox.y0:
                continue
            font_size = block.metadata.get("font_size") if isinstance(block.metadata, dict) else None
            is_bold = bool(block.metadata.get("is_bold")) if isinstance(block.metadata, dict) else False
            is_italic = bool(block.metadata.get("is_italic")) if isinstance(block.metadata, dict) else False
            font_name = block.metadata.get("font") if isinstance(block.metadata, dict) else ""
            txt = _escape(_block_text(block))
            if not txt.strip():
                continue
            style = _inline_style_block(bbox, font_size, is_bold, is_italic, font_name or "")
            # Добавляем z-index и overflow для предотвращения наезда
            style += ";z-index:3;overflow:hidden;position:absolute;"
            parts.append(f"<div class='layer text-layer' style='{style}'>{txt}</div>")
            blocks_inserted += 1
        if blocks_inserted > 0:
            print(f"      [HTML_EXPORT] Inserted {blocks_inserted} text blocks on page {page.number}")

        parts.append("</div>")  # page

    parts.append("</body></html>")

    Path(out_path).write_text("\n".join(parts), encoding="utf-8")


# ============ FLOW HTML ============ #

def _tag_for_block(block: Block) -> str:
    role = ""
    if isinstance(block.metadata, dict):
        role = (block.metadata.get("role") or "").lower()
    btype = block.type.value if isinstance(block.type, BlockType) else str(block.type)
    txt = _block_text(block).strip()
    
    # Формулы - специальная обработка
    if role == "formula" or btype == "formula" or block.metadata.get("formula_preserved"):
        return "formula"  # Специальный тег для формул
    
    if role in {"heading1", "h1"} or btype in {"heading1", "heading"}:
        return "h2"
    if role in {"heading2", "h2"}:
        return "h3"
    if role in {"heading3", "h3"}:
        return "h4"
    if role == "caption" or btype == "caption":
        return "figcaption"
    if btype == "list_item" or role == "list_item":
        return "li"
    if txt.isupper() and 5 <= len(txt) <= 80:
        return "h3"
    return "p"


def _sort_blocks_for_flow(blocks: List[Block]) -> List[Block]:
    return sorted(blocks, key=lambda b: (b.bbox.y0 if hasattr(b, "bbox") else 0, b.bbox.x0 if hasattr(b, "bbox") else 0))


def _render_block_flow(block: Block) -> str:
    tag = _tag_for_block(block)
    # Нормализуем переносы для flow: заменяем \n на пробел и схлопываем множественные пробелы
    raw_txt = _block_text(block)
    txt_clean = " ".join(raw_txt.replace("\r", " ").replace("\n", " ").split())
    txt = _escape(txt_clean)
    style = []
    font_size = None
    is_bold = False
    is_italic = False
    text_color = None
    if isinstance(block.metadata, dict):
        font_size = block.metadata.get("font_size")
        is_bold = bool(block.metadata.get("is_bold"))
        is_italic = bool(block.metadata.get("is_italic"))
        text_color = block.metadata.get("color")  # Цвет из Layout API
    
    # Специальная обработка формул
    if tag == "formula":
        style.append("text-align:center")
        style.append("font-family:'Courier New', monospace")
        style.append("font-size:1.1em")
        style.append("margin:16px 0")
        style.append("padding:8px")
        style.append("background-color:#f9f9f9")
        style.append("border-left:3px solid #4a90e2")
        return f"<div class='formula' style=\"{' ;'.join(style)}\">{txt}</div>"
    
    if font_size:
        style.append(f"font-size:{font_size}px")
    if is_bold:
        style.append("font-weight:bold")
    if is_italic:
        style.append("font-style:italic")
    if text_color and text_color != "#000000":  # Сохраняем цвет если не черный (дефолт)
        style.append(f"color:{text_color}")
    style.append("line-height:1.35")
    style.append("margin:0 0 8px 0")
    if tag == "li":
        return f"<li style=\"{' ;'.join(style)}\">{txt}</li>"
    return f"<{tag} style=\"{' ;'.join(style)}\">{txt}</{tag}>"


def export_html_flow(doc: BookDocument, out_path: str) -> None:
    """
    Потоковый HTML: текст раскладывается по колонкам, без абсолютного позиционирования.
    Использует column_assignments если есть; иначе одна колонка. Фон — raster_preview.
    """
    parts: List[str] = []
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append("""
    <style>
    * { box-sizing: border-box; }
    body { 
        margin: 0; 
        padding: 20px; 
        background: #f7f7f7; 
        font-family: 'Georgia', 'Times New Roman', serif;
        font-size: 11pt;
        line-height: 1.6;
        color: #333;
    }
    .page { 
        position: relative; 
        margin: 20px auto; 
        box-shadow: 0 0 8px rgba(0,0,0,0.15); 
        padding: 32px 40px; 
        background: #fff; 
        max-width: 100%;
    }
    .columns { 
        display: grid; 
        gap: 32px; 
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    }
    .col { 
        display: block; 
        text-align: justify;
        hyphens: auto;
    }
    .bg { 
        position:absolute; 
        left:0; 
        top:0; 
        width:100%; 
        height:100%; 
        z-index:0; 
        opacity: 0.05;
    }
    .content { 
        position:relative; 
        z-index:1; 
    }
    p { 
        margin: 0 0 12px 0; 
        text-indent: 0;
        line-height: 1.65;
    }
    h1, h2, h3, h4, h5, h6 {
        margin: 24px 0 12px 0;
        font-weight: bold;
        line-height: 1.3;
        page-break-after: avoid;
    }
    h1 { font-size: 1.8em; margin-top: 32px; }
    h2 { font-size: 1.5em; margin-top: 28px; }
    h3 { font-size: 1.3em; margin-top: 24px; }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 16px auto;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .caption {
        font-size: 0.9em;
        font-style: italic;
        text-align: center;
        margin: 8px 0 16px 0;
        color: #666;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;
        font-size: 0.95em;
    }
    table th, table td {
        padding: 8px 12px;
        border: 1px solid #ddd;
        text-align: left;
    }
    table th {
        background-color: #f5f5f5;
        font-weight: bold;
    }
    table tr:nth-child(even) {
        background-color: #fafafa;
    }
    .formula {
        text-align: center;
        font-family: 'Courier New', monospace;
        font-size: 1.1em;
        margin: 16px 0;
        padding: 8px;
        background-color: #f9f9f9;
        border-left: 3px solid #4a90e2;
        border-radius: 4px;
    }
    </style>
    """)
    parts.append("</head><body>")

    for page in doc.pages:
        w = page.width
        h = page.height
        
        # Обработка фона и водяных знаков из raster_preview
        bg_div = ""
        use_background = os.getenv("HTML_BACKGROUND", "0") == "1"
        background_opacity = float(os.getenv("HTML_BACKGROUND_OPACITY", "0.1"))
        
        if use_background:
            meta = page.metadata or {}
            # Пробуем получить raster_preview из metadata
            bg_b64 = meta.get("raster_preview_png_b64", "")
            if not bg_b64:
                # Альтернативный путь: проверяем наличие файла
                # (можно расширить позже для загрузки из файла)
                pass
            
            if bg_b64:
                bg_style = f"position:absolute;left:0;top:0;width:{w}px;height:{h}px;background:url(data:image/png;base64,{bg_b64}) no-repeat left top;background-size:{w}px {h}px;opacity:{background_opacity};z-index:0;pointer-events:none;"
                bg_div = f"<div class='bg' style='{bg_style}'></div>"

        meta = page.metadata or {}
        assignments: Dict[str, int] = meta.get("column_assignments") or {}
        cols_meta = meta.get("columns") or []
        # Если нет явных колонок, берём 1
        num_cols = 1
        if assignments:
            num_cols = max(assignments.values(), default=-1) + 1
        elif cols_meta:
            num_cols = len(cols_meta)
        else:
            # эвристика: если средняя ширина блока < 0.6 ширины страницы и много блоков — считаем 2 колонки
            if page.blocks:
                widths = []
                xs = []
                for b in page.blocks:
                    if hasattr(b, "bbox"):
                        widths.append(b.bbox.x1 - b.bbox.x0)
                        xs.append(b.bbox.x0)
                if widths:
                    avg_w = sum(widths) / len(widths)
                    if avg_w < 0.6 * max(1.0, w) and len(widths) > 8:
                        num_cols = 2
        num_cols = max(1, min(num_cols, 3))

        columns: List[List[Dict[str, Any]]] = [[] for _ in range(num_cols)]

        def _col_by_bbox(bb) -> int:
            if num_cols == 1:
                return 0
            if bb is None:
                return 0
            cx = (bb.x0 + bb.x1) / 2.0
            col_w = max(1.0, w / num_cols)
            return int(min(num_cols - 1, max(0, cx // col_w)))

        # Находим подписи для изображений
        caption_map, used_caption_ids = _find_captions_for_images(page.blocks, getattr(page, "images", []) or [])

        items = []
        for b in _sort_blocks_for_flow(page.blocks):
            bid = b.id
            if bid in used_caption_ids:
                continue  # подпись уже привязана к изображению
            cidx = 0
            if assignments and bid in assignments:
                try:
                    cidx = int(assignments[bid])
                except Exception:
                    cidx = 0
            else:
                cidx = _col_by_bbox(b.bbox)
            items.append({"kind": "block", "obj": b, "y": getattr(b.bbox, "y0", 0), "col": cidx})

        # Таблицы (если есть)
        for tbl in getattr(page, "tables", []) or []:
            bb = getattr(tbl, "bbox", None)
            cidx = _col_by_bbox(bb) if bb else 0
            y = bb.y0 if bb else 0
            items.append({"kind": "table", "obj": tbl, "y": y, "col": cidx})

        # Изображения (если есть bytes)
        for img in getattr(page, "images", []) or []:
            data_uri = _image_to_data_uri(img)
            if not data_uri:
                continue
            bb = getattr(img, "bbox", None)
            cidx = _col_by_bbox(bb) if bb else 0
            y = bb.y0 if bb else 0
            items.append({"kind": "image", "obj": img, "data_uri": data_uri, "y": y, "col": cidx})

        items.sort(key=lambda it: it["y"])
        for it in items:
            col = max(0, min(num_cols - 1, it["col"]))
            columns[col].append(it)

        grid_style = f"grid-template-columns: repeat({num_cols}, 1fr);"
        page_style = f"width:{w}px; min-height:{h}px; overflow:hidden; position:relative;"
        parts.append(f"<div class='page' style='{page_style}'>")
        if bg_div:
            parts.append(bg_div)
        parts.append(f"<div class='content'><div class='columns' style='{grid_style}'>")
        for col in columns:
            parts.append("<div class='col'>")
            in_list = False
            for it in col:
                if it["kind"] == "block":
                    blk = it["obj"]
                    tag = _tag_for_block(blk)
                    if tag == "li":
                        if not in_list:
                            parts.append("<ul>")
                            in_list = True
                        parts.append(_render_block_flow(blk))
                    else:
                        if in_list:
                            parts.append("</ul>")
                            in_list = False
                        parts.append(_render_block_flow(blk))
                elif it["kind"] == "table":
                    if in_list:
                        parts.append("</ul>")
                        in_list = False
                    tbl = it["obj"]
                    parts.append(f"<div style='margin:12px 0; overflow-x:auto;'>{_table_to_html(tbl)}</div>")
                elif it["kind"] == "image":
                    if in_list:
                        parts.append("</ul>")
                        in_list = False
                    img = it["obj"]
                    data_uri = it.get("data_uri") or ""
                    if data_uri:
                        caption = caption_map.get(getattr(img, "id", ""), "")
                        caption_html = f"<div style='font-size:11px; line-height:1.3; margin-top:4px; text-align:center; color:#444;'>{_escape(caption)}</div>" if caption else ""
                        parts.append(f"<div style='margin:12px 0; text-align:center;'><img src='{data_uri}' style='max-width:100%; height:auto;'/>{caption_html}</div>")
            if in_list:
                parts.append("</ul>")
            parts.append("</div>")
        parts.append("</div></div>")  # columns/content
        parts.append("</div>")  # page

    parts.append("</body></html>")
    Path(out_path).write_text("\n".join(parts), encoding="utf-8")

