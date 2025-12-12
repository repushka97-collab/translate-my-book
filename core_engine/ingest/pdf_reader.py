import fitz  # PyMuPDF
import pdfplumber
from pypdf import PdfReader

from typing import List, Dict, Any
from core_engine.core.models import Page, Block, BlockType, BBox, ImageObject


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
            # Получаем блоки с текстом
            text_blocks = page.get_text("blocks")
            
            # Получаем детальную информацию о шрифтах через dict
            try:
                text_dict = page.get_text("dict")
                font_info_by_bbox = {}  # (x0, y0, x1, y1) -> {size, flags, font}
                
                # Собираем font signals из spans
                if "blocks" in text_dict:
                    for block_dict in text_dict["blocks"]:
                        if "lines" in block_dict:
                            for line in block_dict["lines"]:
                                if "spans" in line:
                                    for span in line["spans"]:
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

    return blocks


def extract_images(path, pages: List[Page]) -> List[ImageObject]:
    images: List[ImageObject] = []

    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            for idx, img in enumerate(page.get_images(full=True)):
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

                bbox = BBox(0, 0, 0, 0)  # пока не извлекаем bbox изображений (сложно)
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


def detect_tables(path, pages: List[Page]):
    """
    Пока фейковая заглушка таблиц.
    Если очень нужно — можно распарсить через pdfplumber.
    """
    pass


def detect_columns(pages: List[Page], blocks: List[Block]):
    """
    Лёгкая заглушка колонок.
    """
    pass

