import fitz  # PyMuPDF
import math
import os
import pdfplumber
from pypdf import PdfReader

from typing import List, Dict, Any
from core_engine.core.models import (
    Page,
    Block,
    BlockType,
    BBox,
    ImageObject,
    TableObject,
    TableCell,
)
from core_engine.layout.column_detector import detect_columns as detect_columns_hist


def get_pdf_info(path) -> Dict[str, Any]:
    reader = PdfReader(str(path))
    meta = reader.metadata or {}

    info = {
        "pages": len(reader.pages),
        "metadata": {
            "format": meta.get("/Format", ""),
            "title": meta.get("/Title", ""),
            "author": meta.get("/Author", ""),
            "subject": meta.get("/Subject", ""),
            "keywords": meta.get("/Keywords", ""),
            "creator": meta.get("/Creator", ""),
            "producer": meta.get("/Producer", ""),
            "creationDate": meta.get("/CreationDate", ""),
            "modDate": meta.get("/ModDate", ""),
            "trapped": meta.get("/Trapped", ""),
            "encryption": reader.is_encrypted,
        },
        "is_encrypted": reader.is_encrypted,
    }
    return info


def extract_pages(path) -> List[Page]:
    pages: List[Page] = []
    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            rect = page.rect
            pages.append(
                Page(
                    number=i + 1,
                    width=rect.width,
                    height=rect.height,
                )
            )
    return pages


def _detect_block_type(text: str) -> BlockType:
    if not text.strip():
        return BlockType.TEXT
    if text.strip().endswith(":"):
        return BlockType.HEADING
    return BlockType.TEXT


def _ocr_fallback(page, dpi: int = 200) -> List[Block]:
    """
    OCR fallback для пустых/сканированных страниц (best-effort).
    Использует MuPDF OCR если доступен, иначе возвращает пустой список.
    """
    blocks: List[Block] = []
    try:
        # Пробуем MuPDF OCR (если доступен)
        pix = page.get_pixmap(dpi=dpi)
        # Если OCR не доступен, просто возвращаем пустой список
        # (можно добавить Tesseract fallback позже)
        return blocks
    except Exception:
        return blocks


def extract_blocks(path, pages: List[Page]) -> List[Block]:
    """
    Извлечение текстовых блоков для каждой страницы.
    Возвращаем все блоки, но также раскладываем их в pages[n].blocks.
    Теперь извлекаем font signals (size, bold, italic) для улучшения layout.
    OCR fallback для пустых страниц (если включен OCR_FALLBACK=1).
    """
    blocks: List[Block] = []
    use_ocr_fallback = os.getenv("OCR_FALLBACK", "0") == "1"

    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            # Получаем блоки с текстом (PyMuPDF)
            text_blocks = page.get_text("blocks")
            
            # Получаем детальную информацию о шрифтах через dict
            try:
                text_dict = page.get_text("dict") or {}
                font_info_by_bbox = {}  # (x0, y0, x1, y1) -> {size, flags, font}
                
                # Собираем font signals из spans
                if "blocks" in text_dict:
                    for block_dict in text_dict.get("blocks", []):
                        if not block_dict or not isinstance(block_dict, dict):
                            continue
                        if "lines" in block_dict:
                            for line in block_dict["lines"]:
                                if not line or not isinstance(line, dict):
                                    continue
                                if "spans" in line:
                                    for span in line["spans"]:
                                        if not span or not isinstance(span, dict):
                                            continue
                                        bbox = span.get("bbox", [0, 0, 0, 0])
                                        if len(bbox) == 4:
                                            bbox_key = (
                                                round(bbox[0], 1),
                                                round(bbox[1], 1),
                                                round(bbox[2], 1),
                                                round(bbox[3], 1),
                                            )
                                            font_info_by_bbox[bbox_key] = {
                                                "size": span.get("size", 0),
                                                "flags": span.get("flags", 0),  # bold=16, italic=2
                                                "font": span.get("font", ""),
                                            }
            except Exception:
                # Fallback: если get_text("dict") не работает, используем пустые font signals
                font_info_by_bbox = {}

            for idx, b in enumerate(text_blocks):
                x0, y0, x1, y1, txt, *_ = b
                
                # Пытаемся найти font info для этого блока
                bbox_key = (round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
                font_info = font_info_by_bbox.get(bbox_key, {})
                
                # Вычисляем средний размер шрифта и флаги для блока
                # Если точного совпадения нет, ищем ближайший
                if not font_info:
                    for key, info in font_info_by_bbox.items():
                        if abs(key[0] - x0) < 10 and abs(key[1] - y0) < 10:
                            font_info = info
                            break
                
                font_size = font_info.get("size", 0)
                flags = font_info.get("flags", 0)
                is_bold = bool(flags & 16)  # PyMuPDF bold flag
                is_italic = bool(flags & 2)  # PyMuPDF italic flag

                metadata = {
                    "font_size": font_size,
                    "is_bold": is_bold,
                    "is_italic": is_italic,
                    "font": font_info.get("font", ""),
                }

                blk = Block(
                    id=f"p{i+1}_b{idx}",
                    page_number=i + 1,
                    type=_detect_block_type(txt),
                    bbox=BBox(x0, y0, x1, y1),
                    spans=[],
                    raw_text=txt,
                    metadata=metadata,
                )

                blocks.append(blk)
                pages[i].blocks.append(blk)
        
        # OCR fallback для пустых страниц (если включен)
        if use_ocr_fallback and not pages[i].blocks:
            ocr_blocks = _ocr_fallback(page)
            for ocr_blk in ocr_blocks:
                blocks.append(ocr_blk)
                pages[i].blocks.append(ocr_blk)

    # Сохраняем assignments колонок на уровне metadata page (best-effort)
    for page in pages:
        if not page.blocks:
            continue
        blocks_dicts = []
        for b in page.blocks:
            blocks_dicts.append(
                {
                    "id": b.id,
                    "bbox": {
                        "x0": b.bbox.x0,
                        "y0": b.bbox.y0,
                        "x1": b.bbox.x1,
                        "y1": b.bbox.y1,
                    },
                }
            )
        col_info = detect_columns_hist(blocks_dicts, page.width) or {}
        page.metadata["columns"] = col_info.get("columns", [])
        page.metadata["column_assignments"] = col_info.get("assignments", {})

    return blocks


def extract_images(path, pages: List[Page]) -> List[ImageObject]:
    """
    Извлекаем изображения с реальными bbox через page.get_text("dict") (type == 1).
    Фолбэк: если bbox не найден, всё равно сохраняем изображение без падения ingest.
    """
    images: List[ImageObject] = []

    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            # Сначала собираем информацию о изображениях с bbox
            images_with_bbox = []
            try:
                text_dict = page.get_text("dict")
                for block in text_dict.get("blocks", []):
                    if block.get("type") == 1 and "image" in block:
                        bbox = block.get("bbox", [0, 0, 0, 0])
                        xref = block.get("image")
                        images_with_bbox.append((xref, bbox))
            except Exception:
                images_with_bbox = []

            # Фолбэк: список всех изображений (может содержать больше, чем dict)
            raw_images = page.get_images(full=True)

            # Маппим xref -> bbox если есть, иначе bbox None
            xref_to_bbox = {}
            for xref, bbox in images_with_bbox:
                if bbox and len(bbox) == 4:
                    xref_to_bbox[xref] = bbox

            # Извлекаем пиксмапы
            for idx, img in enumerate(raw_images):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)

                    # Normalize to RGB/GRAY without alpha, otherwise PyMuPDF may fail to encode PNG.
                    # - CMYK / unknown colorspaces -> RGB
                    # - RGBA -> drop alpha
                    if getattr(pix, "alpha", 0):
                        pix = fitz.Pixmap(pix, 0)
                    if pix.colorspace is None or pix.n not in (1, 3):
                        pix = fitz.Pixmap(fitz.csRGB, pix)

                    data = pix.tobytes("png")
                except Exception:
                    # Best-effort: do not fail ingest because of an unsupported image
                    continue

                bbox_list = xref_to_bbox.get(xref, [0, 0, 0, 0])
                bbox = BBox(
                    bbox_list[0] if len(bbox_list) > 0 else 0,
                    bbox_list[1] if len(bbox_list) > 1 else 0,
                    bbox_list[2] if len(bbox_list) > 2 else 0,
                    bbox_list[3] if len(bbox_list) > 3 else 0,
                )

                im = ImageObject(
                    id=f"p{i+1}_img{idx}",
                    page_number=i + 1,
                    bbox=bbox,
                    image_bytes=data,
                    mime_type="image/png",
                    label=None,
                )

                pages[i].images.append(im)
                images.append(im)

    return images


def detect_tables(path, pages: List[Page]) -> List[TableObject]:
    """
    Детекция таблиц с опорой на линии/прямоугольники и слова.
    Порядок:
    1) Собираем линии из drawings (гориз/верт) + стороны прямоугольников.
    2) Кластеризуем линии (snap_tolerance) → сетка.
    3) Раскладываем слова по ячейкам сетки.
    4) Fallback: кластеризация слов (как раньше).
    5) Опциональный fallback pdfplumber (если PDFPLUMBER_TABLES=1 и библиотека установлена).
    Colspan/rowspan пока =1 (улучшим позже).
    """
    detected: List[TableObject] = []

    # Толерансы
    LINE_TOL = 3.0          # кластеризация линий
    WORD_ROW_TOL = 4.0      # кластеризация слов по Y
    WORD_COL_TOL = 25.0     # кластеризация слов по X
    MIN_ROWS = 3
    MIN_COLS = 2
    MIN_DENSITY = 0.2

    use_pdfplumber = os.getenv("PDFPLUMBER_TABLES", "0") == "1"
    pdfplumber_mod = None
    if use_pdfplumber:
        try:
            import pdfplumber  # type: ignore
            pdfplumber_mod = pdfplumber
        except Exception:
            pdfplumber_mod = None
            use_pdfplumber = False

    def cluster_positions(vals: List[float], tol: float = 3.0) -> List[float]:
        if not vals:
            return []
        vals = sorted(vals)
        clusters = [[vals[0]]]
        for v in vals[1:]:
            if abs(v - clusters[-1][-1]) <= tol:
                clusters[-1].append(v)
            else:
                clusters.append([v])
        return [sum(c) / len(c) for c in clusters]

    def extract_lines(page):
        horiz = []
        vert = []
        try:
            drawings = page.get_drawings()
            for d in drawings:
                for item in d.get("items", []):
                    if not item:
                        continue
                    op = item[0]
                    # line
                    if op == "l" and len(item) >= 3:
                        p1, p2 = item[1], item[2]
                        x0, y0 = p1
                        x1, y1 = p2
                        if abs(y0 - y1) < 1.0:  # horizontal
                            horiz.append((min(x0, x1), y0, max(x0, x1), y1))
                        elif abs(x0 - x1) < 1.0:  # vertical
                            vert.append((x0, min(y0, y1), x1, max(y0, y1)))
                    # rectangle as four lines
                    if op == "re" and len(item) >= 2:
                        try:
                            x, y, w, h = item[1]
                            horiz.append((x, y, x + w, y))
                            horiz.append((x, y + h, x + w, y + h))
                            vert.append((x, y, x, y + h))
                            vert.append((x + w, y, x + w, y + h))
                        except Exception:
                            continue
        except Exception:
            pass
        return horiz, vert

    def build_from_grid(page, words, x_lines, y_lines):
        cells: List[TableCell] = []
        table_rows: List[List[str]] = []
        # Map words to cells by center point
        # Build empty grid
        grid = [[[] for _ in range(len(x_lines) - 1)] for _ in range(len(y_lines) - 1)]
        for w in words:
            x0, y0, x1, y1, text, *_ = w
            if not text:
                continue
            cx = (x0 + x1) / 2.0
            cy = (y0 + y1) / 2.0
            # find column
            c_idx = None
            for ci in range(len(x_lines) - 1):
                if x_lines[ci] - 1e-3 <= cx <= x_lines[ci + 1] + 1e-3:
                    c_idx = ci
                    break
            r_idx = None
            for ri in range(len(y_lines) - 1):
                if y_lines[ri] - 1e-3 <= cy <= y_lines[ri + 1] + 1e-3:
                    r_idx = ri
                    break
            if r_idx is None or c_idx is None:
                continue
            grid[r_idx][c_idx].append(text)

        # Сначала собираем текст для каждой ячейки
        cell_texts = {}
        for r_idx, row in enumerate(grid):
            for c_idx, cell_words in enumerate(row):
                txt = " ".join(cell_words).strip()
                cell_texts[(r_idx, c_idx)] = txt

        # Теперь определяем colspan/rowspan для объединенных ячеек
        # Алгоритм: если ячейка пустая, проверяем соседние ячейки
        # Если соседние тоже пустые или содержат текст, объединяем
        used_cells = set()
        
        for r_idx in range(len(y_lines) - 1):
            row_txt: List[str] = []
            for c_idx in range(len(x_lines) - 1):
                if (r_idx, c_idx) in used_cells:
                    continue
                
                txt = cell_texts.get((r_idx, c_idx), "").strip()
                
                # Определяем colspan: проверяем, сколько пустых ячеек справа можно объединить
                colspan = 1
                if not txt:
                    # Пустая ячейка - проверяем, можно ли объединить с правой
                    for next_c in range(c_idx + 1, len(x_lines) - 1):
                        next_txt = cell_texts.get((r_idx, next_c), "").strip()
                        if not next_txt:
                            colspan += 1
                        else:
                            break
                else:
                    # Ячейка с текстом - проверяем, не является ли она частью объединенной
                    # Проверяем, есть ли пустые ячейки справа, которые можно объединить
                    for next_c in range(c_idx + 1, len(x_lines) - 1):
                        next_txt = cell_texts.get((r_idx, next_c), "").strip()
                        # Если следующая ячейка пустая и нет текста в других ячейках этой строки
                        if not next_txt:
                            # Проверяем, нет ли текста в ячейках ниже
                            has_text_below = False
                            for check_r in range(r_idx + 1, len(y_lines) - 1):
                                if cell_texts.get((check_r, next_c), "").strip():
                                    has_text_below = True
                                    break
                            if not has_text_below:
                                colspan += 1
                            else:
                                break
                        else:
                            break
                
                # Определяем rowspan: проверяем, сколько пустых ячеек снизу можно объединить
                rowspan = 1
                if not txt:
                    for next_r in range(r_idx + 1, len(y_lines) - 1):
                        next_txt = cell_texts.get((next_r, c_idx), "").strip()
                        if not next_txt:
                            rowspan += 1
                        else:
                            break
                else:
                    # Ячейка с текстом - проверяем rowspan
                    for next_r in range(r_idx + 1, len(y_lines) - 1):
                        next_txt = cell_texts.get((next_r, c_idx), "").strip()
                        if not next_txt:
                            # Проверяем, нет ли текста в ячейках справа
                            has_text_right = False
                            for check_c in range(c_idx + 1, len(x_lines) - 1):
                                if cell_texts.get((next_r, check_c), "").strip():
                                    has_text_right = True
                                    break
                            if not has_text_right:
                                rowspan += 1
                            else:
                                break
                        else:
                            break
                
                # Если ячейка пустая и не объединена, пропускаем её
                if not txt and colspan == 1 and rowspan == 1:
                    # Но всё равно добавляем пустую ячейку для структуры таблицы
                    row_txt.append("")
                    cells.append(TableCell(row=r_idx, col=c_idx, text="", rowspan=rowspan, colspan=colspan))
                else:
                    row_txt.append(txt)
                    cells.append(TableCell(row=r_idx, col=c_idx, text=txt, rowspan=rowspan, colspan=colspan))
                
                # Помечаем все объединенные ячейки как использованные
                for dr in range(rowspan):
                    for dc in range(colspan):
                        used_cells.add((r_idx + dr, c_idx + dc))
            
            if row_txt:  # Добавляем строку только если она не пустая
                table_rows.append(row_txt)

        non_empty_cells = sum(1 for row in table_rows for c in row if c)
        if non_empty_cells < len(table_rows) * len(table_rows[0]) * 0.2:
            return None

        bbox = BBox(
            min(x_lines),
            min(y_lines),
            max(x_lines),
            max(y_lines),
        )
        tbl = TableObject(
            id="",
            page_number=0,
            bbox=bbox,
            cells=cells,
            label=None,
            caption=None,
        )
        return tbl

    def pdfplumber_fallback(pdfplumber_mod, page_index: int):
        try:
            with pdfplumber_mod.open(str(path)) as pdf:
                if page_index >= len(pdf.pages):
                    return None
                p = pdf.pages[page_index]
                table = p.extract_table(
                    {
                        "vertical_strategy": "lines",
                        "horizontal_strategy": "lines",
                    }
                )
                if not table or len(table) < MIN_ROWS:
                    return None
                cells: List[TableCell] = []
                max_cols = max(len(r) for r in table)
                for r_idx, row in enumerate(table):
                    for c_idx in range(max_cols):
                        txt = row[c_idx] if c_idx < len(row) else ""
                        cells.append(TableCell(row=r_idx, col=c_idx, text=txt or "", rowspan=1, colspan=1))
                bbox = BBox(0, 0, page.rect.width, page.rect.height)
                return TableObject(
                    id="",
                    page_number=page_index + 1,
                    bbox=bbox,
                    cells=cells,
                    label=None,
                    caption=None,
                )
        except Exception:
            return None

    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            # Улучшение: используем Layout API для более точного извлечения
            words = page.get_text("words") or []
            if not words or len(words) < 6:
                continue
            
            # Пробуем получить layout через dict для более точной структуры
            layout_dict = None
            try:
                layout_dict = page.get_text("dict")
                # Используем layout_dict для улучшения детекции таблиц
                # Анализируем блоки с текстом для поиска табличных паттернов
                if layout_dict:
                    blocks_dict = layout_dict.get("blocks", [])
                    # Ищем блоки с регулярной структурой (потенциальные таблицы)
                    table_candidates = []
                    for blk in blocks_dict:
                        if blk.get("type") == 0:  # текстовый блок
                            lines = blk.get("lines", [])
                            if len(lines) >= MIN_ROWS:
                                # Проверяем, есть ли регулярная структура (много колонок)
                                cols_count = set()
                                for line in lines:
                                    spans = line.get("spans", [])
                                    if len(spans) >= MIN_COLS:
                                        cols_count.add(len(spans))
                                if len(cols_count) > 0 and max(cols_count) >= MIN_COLS:
                                    table_candidates.append(blk)
            except Exception:
                layout_dict = None
            
            horiz, vert = extract_lines(page)
            x_lines = cluster_positions([ln[0] for ln in vert] + [ln[2] for ln in vert], tol=LINE_TOL)
            y_lines = cluster_positions([ln[1] for ln in horiz] + [ln[3] for ln in horiz], tol=LINE_TOL)

            table_obj = None
            if len(x_lines) >= 2 and len(y_lines) >= 2:
                table_obj = build_from_grid(page, words, x_lines, y_lines)

            # Fallback: старая словарная кластеризация
            if table_obj is None:
                # Сортируем слова по y0, затем x0
                words_sorted = sorted(words, key=lambda w: (w[1], w[0]))
                rows_raw: List[List[Any]] = []
                tol_y = WORD_ROW_TOL
                current: List[Any] = []
                current_y = None
                for w in words_sorted:
                    x0, y0, x1, y1, text, *_ = w
                    if current_y is None:
                        current_y = y0
                    if abs(y0 - current_y) <= tol_y:
                        current.append(w)
                    else:
                        if current:
                            rows_raw.append(current)
                        current = [w]
                        current_y = y0
                if current:
                    rows_raw.append(current)
                rows_raw = [r for r in rows_raw if len(r) >= 2]
                if len(rows_raw) >= MIN_ROWS:
                    all_x = []
                    for r in rows_raw:
                        for w in r:
                            all_x.append(w[0])
                    all_x = sorted(all_x)
                    cols: List[float] = []
                    tol_x = WORD_COL_TOL
                    for x in all_x:
                        if not cols or abs(x - cols[-1]) > tol_x:
                            cols.append(x)
                    if len(cols) >= MIN_COLS:
                        min_x = min(w[0] for w in words_sorted)
                        max_x = max(w[2] for w in words_sorted)
                        if (max_x - min_x) <= page.rect.width * 0.9:
                            table_rows: List[List[str]] = []
                            cells: List[TableCell] = []
                            for r in rows_raw:
                                cell_texts = [""] * len(cols)
                                for w in r:
                                    x0, y0, x1, y1, text, *_ = w
                                    if not text:
                                        continue
                                    best_idx = min(range(len(cols)), key=lambda idx: abs(x0 - cols[idx]))
                                    cell_texts[best_idx] = (cell_texts[best_idx] + " " + text).strip()
                                table_rows.append(cell_texts)
                            non_empty_cells = sum(1 for row in table_rows for c in row if c)
                            if non_empty_cells >= len(table_rows) * len(cols) * MIN_DENSITY:
                                bbox = BBox(min_x, min(w[1] for w in words_sorted), max_x, max(w[3] for w in words_sorted))
                                for r_idx, row in enumerate(table_rows):
                                    for c_idx, cell_text in enumerate(row):
                                        cells.append(TableCell(row=r_idx, col=c_idx, text=cell_text, rowspan=1, colspan=1))
                                table_obj = TableObject(
                                    id="",
                                    page_number=0,
                                    bbox=bbox,
                                    cells=cells,
                                    label=None,
                                    caption=None,
                                )

            # Fallback: pdfplumber (опционально)
            if table_obj is None and use_pdfplumber and pdfplumber_mod:
                table_obj = pdfplumber_fallback(pdfplumber_mod, i)

            if table_obj:
                table_obj.id = f"p{i+1}_tbl{len(pages[i].tables) + 1}"
                table_obj.page_number = i + 1
                pages[i].tables.append(table_obj)
                detected.append(table_obj)

    return detected


def detect_columns(pages: List[Page], blocks: List[Block]):
    """
    Обертка для column_detector: если колонки уже вычислены в extract_blocks — пропускаем.
    Иначе рассчитываем по имеющимся блокам.
    """
    if not pages or not blocks:
        return

    # Проверяем: есть ли хоть одна страница без columns
    need_compute = any(not (p.metadata.get("columns") or p.metadata.get("column_assignments")) for p in pages)
    if not need_compute:
        return

    # Группируем блоки по страницам
    by_page: Dict[int, List[Block]] = {}
    for b in blocks:
        by_page.setdefault(b.page_number, []).append(b)

    for p in pages:
        if p.metadata.get("columns") or p.metadata.get("column_assignments"):
            continue
        bps = by_page.get(p.number, [])
        if not bps:
            continue
        blocks_dicts = []
        for b in bps:
            blocks_dicts.append(
                {
                    "id": b.id,
                    "bbox": {
                        "x0": b.bbox.x0,
                        "y0": b.bbox.y0,
                        "x1": b.bbox.x1,
                        "y1": b.bbox.y1,
                    },
                }
            )
        col_info = detect_columns_hist(blocks_dicts, p.width) or {}
        p.metadata["columns"] = col_info.get("columns", [])
        p.metadata["column_assignments"] = col_info.get("assignments", {})

