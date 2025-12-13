import fitz  # PyMuPDF
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


def extract_blocks(path, pages: List[Page]) -> List[Block]:
    """
    Извлечение текстовых блоков для каждой страницы.
    Возвращаем все блоки, но также раскладываем их в pages[n].blocks.
    Теперь извлекаем font signals (size, bold, italic) для улучшения layout.
    """
    blocks: List[Block] = []

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
    Простая универсальная детекция таблиц на основе page.get_text(\"words\"):
    - Кластеризация по Y в строки (tolerance=4)
    - Кластеризация по X в столбцы (tolerance=25)
    - Требования: >=3 строк и >=2 колонок, ширина таблицы < 90% ширины страницы.
    - Заполняет page.tables TableObject с cells (row/col/text).
    """
    detected: List[TableObject] = []

    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            words = page.get_text("words") or []
            if not words or len(words) < 10:
                continue

            # Сортируем слова по y0, затем x0
            words = sorted(words, key=lambda w: (w[1], w[0]))

            # Кластеризация в строки по Y
            rows_raw: List[List[Any]] = []
            tol_y = 4
            current: List[Any] = []
            current_y = None
            for w in words:
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

            # Удаляем строки с очень малым количеством слов
            rows_raw = [r for r in rows_raw if len(r) >= 2]
            if len(rows_raw) < 3:
                continue

            # Выделяем X-позиции для колонок
            all_x = []
            for r in rows_raw:
                for w in r:
                    all_x.append(w[0])
            all_x = sorted(all_x)
            cols: List[float] = []
            tol_x = 25
            for x in all_x:
                if not cols or abs(x - cols[-1]) > tol_x:
                    cols.append(x)

            if len(cols) < 2:
                continue

            # Ограничение по ширине (90% от ширины страницы)
            min_x = min(w[0] for w in words)
            max_x = max(w[2] for w in words)
            if (max_x - min_x) > page.rect.width * 0.9:
                continue

            # Строим ячейки строк по ближайшему столбцу
            table_rows: List[List[str]] = []
            for r in rows_raw:
                cell_texts = [""] * len(cols)
                for w in r:
                    x0, y0, x1, y1, text, *_ = w
                    # Пропускаем пустые токены
                    if not text:
                        continue
                    # Находим ближайший столбец по x0
                    best_idx = min(range(len(cols)), key=lambda idx: abs(x0 - cols[idx]))
                    cell_texts[best_idx] = (cell_texts[best_idx] + " " + text).strip()
                table_rows.append(cell_texts)

            # Проверяем, что есть содержимое в большинстве ячеек
            non_empty_cells = sum(1 for row in table_rows for c in row if c)
            if non_empty_cells < len(table_rows) * len(cols) * 0.4:
                continue

            bbox = BBox(min_x, min(w[1] for w in words), max_x, max(w[3] for w in words))

            # Формируем TableCells
            cells: List[TableCell] = []
            for r_idx, row in enumerate(table_rows):
                for c_idx, cell_text in enumerate(row):
                    cells.append(TableCell(row=r_idx, col=c_idx, text=cell_text))

            tbl = TableObject(
                id=f"p{i+1}_tbl{len(pages[i].tables) + 1}",
                page_number=i + 1,
                bbox=bbox,
                cells=cells,
                label=None,
                caption=None,
            )

            pages[i].tables.append(tbl)
            detected.append(tbl)

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

