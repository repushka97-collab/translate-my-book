from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path
import os
import base64

from core_engine.normalize.text_cleaner import normalize_document
from core_engine.core.models import BookDocument, Page, Block
from core_engine.library.library_manager import LibraryManager
from core_engine.ingest.pdf_reader import (
    get_pdf_info,
    extract_pages,
    extract_blocks,
    extract_images,
)
from core_engine.ingest.rasterizer import rasterize_pdf_pages


# ====== v3 Result Structure ======


@dataclass
class IngestResult:
    """
    Результат ingest-этапа для пайплайна v3/v4.

    ВАЖНО ДЛЯ КОНТРАКТА A1:
    - book_id: str
    - blocks: list[dict] с обязательными ключами:
        * id:      стабильный ID блока в пределах книги
        * page:    номер страницы (int)
        * order:   порядок блока (int)
        * text:    сырой текст блока
      Остальные поля — расширение, но не ломают контракт.
    - meta: произвольные метаданные книги
    - doc: BookDocument (для внутренних нужд и будущих мозгов)
    """

    book_id: str
    blocks: List[Dict[str, Any]]
    meta: Dict[str, Any]
    doc: BookDocument


# ====== Main Ingest Function ======


def ingest_pdf(source_path: str) -> IngestResult:
    """
    v3/v4 ingest:
    - читает PDF
    - собирает BookDocument через pdf_reader функции
    - генерирует book_id через LibraryManager
    - разворачивает BookDocument в blocks (словарные) для пайплайна
    - возвращает IngestResult

    На выходе гарантирует соблюдение контракта блоков (id/page/order/text).
    """

    pdf_path = Path(source_path).resolve()

    # 1. Информация о PDF
    info = get_pdf_info(pdf_path)
    num_pages = info["pages"]

    # 2. Страницы
    try:
        pages: List[Page] = extract_pages(pdf_path)
        if not pages:
            raise ValueError(f"PDF {pdf_path} contains no pages")
    except Exception as e:
        raise RuntimeError(f"Failed to extract pages from {pdf_path}: {e}") from e

    # 3. Блоки (твоя логика из pdf_reader)
    try:
        blocks: List[Block] = extract_blocks(pdf_path, pages)
        if not blocks:
            print(f"[WARN] PDF {pdf_path} contains no text blocks - may be image-only")
    except Exception as e:
        raise RuntimeError(f"Failed to extract blocks from {pdf_path}: {e}") from e

    # 4. Изображения
    # Best-effort: some PDFs contain images that can't be rasterized/encoded cleanly.
    # Ingest must not fail because of that.
    try:
        extract_images(pdf_path, pages)
    except Exception:
        pass

    # 5. (Опционально) Растровые превью страниц для анализа фона/водяных знаков.
    #    Управляется env-переменной INGEST_RASTER_PREVIEW=1, по умолчанию выключено,
    #    чтобы не раздувать память/manifest.
    raster_previews_b64: List[str] = []
    if os.getenv("INGEST_RASTER_PREVIEW", "0") == "1":
        previews = rasterize_pdf_pages(str(pdf_path), dpi=200)
        for p in previews:
            if p:
                raster_previews_b64.append(base64.b64encode(p).decode("ascii"))
            else:
                raster_previews_b64.append("")

    # 6. Собираем BookDocument
    doc = BookDocument(
        source_path=str(pdf_path),
        pages=pages,
        metadata=info["metadata"],
    )

    # Добавляем растровые превью в метаданные страниц (если включено)
    if raster_previews_b64:
        for idx, page in enumerate(doc.pages):
            if idx < len(raster_previews_b64):
                page.metadata["raster_preview_png_b64"] = raster_previews_b64[idx]

    # Нормализуем документ на уровне BookDocument:
    # - заполняем normalized_text
    # - считаем protected_tokens и т.п.
    normalize_document(doc)

    # 6. Генерация book_id через LibraryManager
    mgr = LibraryManager()
    book_id = mgr.compute_book_id(pdf_path)

    # 7. Преобразуем Block → dict для пайплайна
    #    Здесь мы ЖЁСТКО соблюдаем контракт:
    #    "id", "page", "order", "text" — обязательные ключи.
    blocks_dict: List[Dict[str, Any]] = []
    order = 0
    empty_blocks_skipped = 0
    for blk in blocks:
        blk_id = blk.id  # уже уникальный ID блока из core.models
        raw_text = blk.raw_text or ""
        
        # Пропускаем пустые блоки (уже фильтруем, но на всякий случай)
        if not raw_text.strip():
            empty_blocks_skipped += 1
            continue

        # Контракт A1: ingest blocks must have non-empty text.
        # Для PDF с мусорными/пустыми блоками — просто пропускаем их,
        # чтобы не валить весь прогон книги.
        if not raw_text.strip():
            continue

        block_dict: Dict[str, Any] = {
            # контрактные поля
            "id": blk_id,
            "page": blk.page_number,
            "order": order,
            "text": raw_text,
            # расширения (для layout/аналитики и будущих мозгов)
            "type": blk.type.value,
            "bbox": {
                "x0": blk.bbox.x0,
                "y0": blk.bbox.y0,
                "x1": blk.bbox.x1,
                "y1": blk.bbox.y1,
            },
            "metadata": blk.metadata,
        }

        # Для обратной совместимости оставим alias,
        # если где-то старый код ещё смотрит на "block_id"
        block_dict["block_id"] = blk_id

        blocks_dict.append(block_dict)
        order += 1

    # 8. Метаданные ingest-результата
    meta: Dict[str, Any] = {
        "title": doc.metadata.get("title"),
        "source_path": str(pdf_path),
        "pages": num_pages,
        "pdf_meta": info["metadata"],
    }

    return IngestResult(
        book_id=book_id,
        blocks=blocks_dict,
        meta=meta,
        doc=doc,
    )
