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
    """
    blocks: List[Block] = []

    with fitz.open(str(path)) as doc:
        for i, page in enumerate(doc):
            text_blocks = page.get_text("blocks")

            for idx, b in enumerate(text_blocks):
                x0, y0, x1, y1, txt, *_ = b

                blk = Block(
                    id=f"p{i+1}_b{idx}",
                    page_number=i + 1,
                    type=_detect_block_type(txt),
                    bbox=BBox(x0, y0, x1, y1),
                    spans=[],
                    raw_text=txt,
                    metadata={},
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
                pix = fitz.Pixmap(doc, xref)

                if pix.n < 5:  # RGB
                    data = pix.tobytes()
                else:          # CMYK → RGB
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                    data = pix.tobytes()

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

