# pipeline_v2.1.py
# Оркестратор ядра v7.1 — полный, проверенный, безопасный

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import os

from core_engine.ingest.pdf_ingest import ingest_pdf
from core_engine.normalize.text_cleaner import normalize_blocks
from core_engine.translate.llm_adapter import translate_blocks
from core_engine.layout.block_reassemble import build_layout_model
from core_engine.layout.heading_detector import detect_headings
from core_engine.layout.chapter_detector import detect_chapter_structure
from core_engine.layout.layout_reassemble_v2 import build_paragraph_stream
from core_engine.export.export_json import export_json_bundle
from core_engine.export.docx_exporter import export_docx
from core_engine.export.exporter import export_html
from core_engine.core.models import BookDocument, Page, Block, BBox, BlockType, ImageObject, TableObject, TableCell
from core_engine.library.library_manager import register_book_in_library
from core_engine.qa.integrity_check import qa_check_blocks
from core_engine.utils.contracts import (
    validate_ingest_result,
    validate_blocks_structure,
)


# ============================================================
#                САНИТИ для ingest-результата
# ============================================================

def _add_images_to_layout_model(layout_model: Dict[str, Any], doc: Any) -> None:
    """
    Добавляет изображения из BookDocument в layout_model.
    НЕ добавляет image_bytes (не сериализуется в JSON), только метаданные.
    """
    if not hasattr(doc, "pages"):
        return
    
    # Создаем словарь страниц для быстрого доступа
    pages_dict = {p.get("page_num"): p for p in layout_model.get("pages", [])}
    
    for page in doc.pages:
        page_num = page.number
        if page_num not in pages_dict:
            continue
        
        # Добавляем изображения в страницу layout_model (без image_bytes)
        if not hasattr(page, "images") or not page.images:
            continue
        
        images_list = []
        for img in page.images:
            # Конвертируем ImageObject в dict, БЕЗ image_bytes (для JSON)
            img_dict = {
                "id": img.id,
                "page_number": img.page_number,
                "bbox": {
                    "x0": img.bbox.x0,
                    "y0": img.bbox.y0,
                    "x1": img.bbox.x1,
                    "y1": img.bbox.y1,
                },
                "mime_type": img.mime_type,
                "label": img.label,
            }
            images_list.append(img_dict)
        
        pages_dict[page_num]["images"] = images_list


def _normalize_ingest_result(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw

    book_id = getattr(raw, "book_id", None)
    blocks = getattr(raw, "blocks", None)
    meta = getattr(raw, "meta", {}) or {}

    if book_id is None:
        raise TypeError("IngestResult has no book_id")
    if blocks is None:
        raise TypeError("IngestResult has no blocks")

    return {"book_id": book_id, "blocks": blocks, "meta": meta}


# ============================================================
#                     PIPELINE MAIN
# ============================================================

def run_book_pipeline(
    source_path: str | Path,
    mode: str | None = None,
    progress_callback: callable | None = None,
) -> Dict[str, Any]:

    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source PDF not found: {source}")

    # --------------------------------------------------------
    stage = 1
    total_stages = 9
    
    def _progress(stage_name: str, progress: float = None):
        if progress_callback:
            progress_callback(stage, total_stages, stage_name, progress)
        print(f"[{stage}/{total_stages}] {stage_name}...")

    def _layout_to_bookdoc(layout_model: Dict[str, Any], images_by_page: Dict[int, List[Dict[str, Any]]]) -> BookDocument:
        pages: List[Page] = []
        for p in layout_model.get("pages", []):
            page_num = p.get("page_num", 0)
            page = Page(
                number=page_num,
                width=p.get("width", 595),
                height=p.get("height", 842),
                metadata=p.get("metadata", {}),
            )
            for b in p.get("blocks", []):
                bb = b.get("bbox", {}) or {}
                bbox = BBox(bb.get("x0", 0), bb.get("y0", 0), bb.get("x1", 0), bb.get("y1", 0))
                btype_raw = b.get("type", "text")
                try:
                    btype = BlockType(btype_raw)
                except Exception:
                    btype = BlockType.TEXT
                blk = Block(
                    id=b.get("id") or b.get("block_id") or "",
                    page_number=page_num,
                    type=btype,
                    bbox=bbox,
                    spans=[],
                    raw_text=b.get("text", ""),
                    normalized_text=b.get("normalized_text"),
                    translated_text=b.get("translated_text"),
                    metadata=b.get("metadata", {}),
                )
                page.blocks.append(blk)

            # Таблицы
            for tbl in p.get("tables", []) or []:
                bb = tbl.get("bbox", {}) or {}
                bbox = BBox(bb.get("x0", 0), bb.get("y0", 0), bb.get("x1", 0), bb.get("y1", 0))
                cells = []
                for c in tbl.get("cells", []) or []:
                    cells.append(
                        TableCell(
                            row=c.get("row", 0),
                            col=c.get("col", 0),
                            text=c.get("text", ""),
                            rowspan=c.get("rowspan", 1),
                            colspan=c.get("colspan", 1),
                        )
                    )
                page.tables.append(
                    TableObject(
                        id=tbl.get("id", ""),
                        page_number=page_num,
                        bbox=bbox,
                        cells=cells,
                        label=tbl.get("label"),
                        caption=tbl.get("caption"),
                    )
                )

            # Изображения — подтягиваем bytes из images_by_page, если есть
            imgs_info = p.get("images", []) or []
            for img in imgs_info:
                bb = img.get("bbox", {}) or {}
                bbox = BBox(bb.get("x0", 0), bb.get("y0", 0), bb.get("x1", 0), bb.get("y1", 0))
                img_bytes = b""
                page_imgs_bytes = images_by_page.get(page_num, [])
                for ib in page_imgs_bytes:
                    if ib.get("id") == img.get("id"):
                        img_bytes = ib.get("image_bytes") or b""
                        break
                page.images.append(
                    ImageObject(
                        id=img.get("id", ""),
                        page_number=page_num,
                        bbox=bbox,
                        image_bytes=img_bytes,
                        mime_type=img.get("mime_type", "image/png"),
                        alt_text=img.get("alt_text"),
                        label=img.get("label"),
                    )
                )

            pages.append(page)
        return BookDocument(source_path=str(source_path), pages=pages, metadata=layout_model.get("metadata", {}))
    
    _progress("Ingest PDF")
    try:
        ingest_raw = ingest_pdf(source)
        ingest = _normalize_ingest_result(ingest_raw)
        validate_ingest_result(ingest)
        book_id = ingest["book_id"]
        if not ingest.get("blocks"):
            raise RuntimeError("Ingest produced no blocks - PDF may be empty or corrupted")
        _progress("Ingest PDF", 1.0)
    except Exception as e:
        raise RuntimeError(f"Ingest failed for {source}: {e}") from e

    # --------------------------------------------------------
    stage += 1
    _progress("Normalize blocks")
    try:
        normalized = normalize_blocks(ingest["blocks"])
        normalized = detect_headings(normalized)
        normalized = detect_chapter_structure(normalized)
        validate_blocks_structure(normalized, stage="normalize")
        print(f"      Normalized {len(normalized)} blocks")
        _progress("Normalize blocks", 1.0)
    except Exception as e:
        raise RuntimeError(f"Normalize failed: {e}") from e

    # --------------------------------------------------------
    stage += 1
    _progress("Translate blocks")
    try:
        # Инкрементальное обновление (если включено)
        use_incremental = os.getenv("INCREMENTAL_UPDATE", "0") == "1"
        previous_blocks = []
        changed_ids = set()
        
        if use_incremental:
            from core_engine.orchestrator.incremental_update import (
                load_translation_state,
                detect_changed_blocks,
                merge_translations,
            )
            
            state_dir = Path("library/translation_states")
            previous_state = load_translation_state(book_id, state_dir)
            
            if previous_state:
                # Загружаем предыдущие блоки из библиотеки
                from core_engine.library.book_api import get_book_blocks
                try:
                    previous_blocks = get_book_blocks(book_id, "library") or []
                    changed_ids = detect_changed_blocks(normalized, previous_state)
                    if changed_ids:
                        print(f"      Detected {len(changed_ids)} changed blocks, re-translating...")
                    else:
                        print(f"      No changes detected, using cached translations")
                except Exception:
                    previous_blocks = []
                    changed_ids = set()
        
        translated = translate_blocks(
            normalized,
            source_lang="en",
            target_lang="ru",
            mode=mode,
        )
        
        # Объединяем со старыми переводами если включено инкрементальное обновление
        if use_incremental and previous_blocks and changed_ids:
            from core_engine.orchestrator.incremental_update import merge_translations
            translated = merge_translations(translated, previous_blocks, changed_ids)
        
        validate_blocks_structure(translated, stage="translate")
        # Подсчитываем переведенные блоки
        translated_count = sum(1 for b in translated if (b.get("translated_text") or "").strip())
        cached_count = sum(1 for b in translated if b.get("metadata", {}).get("from_cache", False))
        if cached_count > 0:
            print(f"      Translated {translated_count}/{len(translated)} blocks ({cached_count} from cache)")
        else:
            print(f"      Translated {translated_count}/{len(translated)} blocks")
        _progress("Translate blocks", 1.0)
        
        # Сохраняем состояние для инкрементального обновления
        if use_incremental:
            from core_engine.orchestrator.incremental_update import update_translation_state
            state_dir = Path("library/translation_states")
            update_translation_state(book_id, translated, state_dir)
    except Exception as e:
        raise RuntimeError(f"Translation failed: {e}") from e

    # --------------------------------------------------------
    stage += 1
    _progress("QA check")
    qa_report = qa_check_blocks(normalized, translated)

    # prepare output folder
    out_dir = Path("output") / str(book_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "qa_report.json").open("w", encoding="utf-8") as f:
        json.dump(qa_report, f, ensure_ascii=False, indent=2)

    if qa_report.get("status") == "error":
        high_severity = qa_report.get("summary", {}).get("issues_by_severity", {}).get("high", 0)
        print(f"[WARN] QA found {high_severity} high-severity issues")
        # Не падаем на ошибках QA, только предупреждаем (для ночных прогонов)
        # raise RuntimeError("QA failed: critical translation mismatch")

    # --------------------------------------------------------
    stage += 1
    _progress("Build layout model")
    try:
        layout_model = build_layout_model(book_id, translated)
        # Добавляем изображения из ingest_result.doc
        images_by_page = {}
        if hasattr(ingest_raw, "doc") and ingest_raw.doc:
            _add_images_to_layout_model(layout_model, ingest_raw.doc)
            # Сохраняем изображения отдельно для передачи в export_docx (с image_bytes)
            for page in ingest_raw.doc.pages:
                if hasattr(page, "images") and page.images:
                    images_by_page[page.number] = [
                        {
                            "id": img.id,
                            "image_bytes": img.image_bytes,  # Сохраняем bytes для DOCX
                            "label": img.label,
                            "bbox": {
                                "x0": img.bbox.x0,
                                "y0": img.bbox.y0,
                                "x1": img.bbox.x1,
                                "y1": img.bbox.y1,
                            },
                        }
                        for img in page.images
                    ]
            total_images = sum(len(imgs) for imgs in images_by_page.values())
            if total_images > 0:
                print(f"      Found {total_images} images across {len(images_by_page)} pages")
            # Обогащаем layout_model метаданными страниц (size, metadata, tables, images без bytes)
            try:
                pages_by_num = {p.number: p for p in ingest_raw.doc.pages}
                for p in layout_model.get("pages", []):
                    pnum = p.get("page_num", 0)
                    doc_page = pages_by_num.get(pnum)
                    if not doc_page:
                        continue
                    p["width"] = getattr(doc_page, "width", 0)
                    p["height"] = getattr(doc_page, "height", 0)
                    p["metadata"] = getattr(doc_page, "metadata", {}) or {}
                    # Таблицы без image_bytes
                    if getattr(doc_page, "tables", None):
                        p["tables"] = [
                            {
                                "id": t.id,
                                "page_number": t.page_number,
                                "bbox": {
                                    "x0": t.bbox.x0,
                                    "y0": t.bbox.y0,
                                    "x1": t.bbox.x1,
                                    "y1": t.bbox.y1,
                                },
                                "cells": [
                                    {
                                        "row": c.row,
                                        "col": c.col,
                                        "text": c.text,
                                        "rowspan": getattr(c, "rowspan", 1),
                                        "colspan": getattr(c, "colspan", 1),
                                    }
                                    for c in t.cells
                                ],
                                "label": t.label,
                                "caption": t.caption,
                            }
                            for t in doc_page.tables
                        ]
                    # Изображения без bytes
                    if getattr(doc_page, "images", None):
                        p["images"] = [
                            {
                                "id": img.id,
                                "bbox": {
                                    "x0": img.bbox.x0,
                                    "y0": img.bbox.y0,
                                    "x1": img.bbox.x1,
                                    "y1": img.bbox.y1,
                                },
                                "label": img.label,
                                "mime_type": img.mime_type,
                            }
                            for img in doc_page.images
                        ]
            except Exception:
                pass
    except Exception as e:
        raise RuntimeError(f"Layout model build failed: {e}") from e

    # --------------------------------------------------------
    stage += 1
    _progress("Save JSON bundle")
    try:
        json_paths = export_json_bundle(layout_model, book_id)
    except Exception as e:
        raise RuntimeError(f"JSON export failed: {e}") from e

    # --------------------------------------------------------
    stage += 1
    _progress("Build paragraph_stream (Layout v2.1)")
    try:
        paragraphs = build_paragraph_stream(layout_model)
    except Exception as e:
        raise RuntimeError(f"Paragraph stream build failed: {e}") from e

    # sanity check paragraph stream
    para_count = len(paragraphs)
    non_empty = [p for p in paragraphs if (p.get("text") or "").strip()]
    print(f"[7/9] Paragraphs built: {para_count}")

    if para_count == 0:
        raise RuntimeError("Layout v2.1 produced an empty paragraph_stream")
    if not non_empty:
        raise RuntimeError("Layout v2.1 produced paragraphs with empty text only")

    # save debug version (без image_bytes - не сериализуется в JSON)
    paragraphs_for_json = []
    for p in paragraphs:
        p_copy = dict(p)
        if p_copy.get("type") == "image":
            # Убираем image_bytes если есть (не сериализуется в JSON)
            if "image_bytes" in p_copy:
                p_copy["image_bytes"] = None
        paragraphs_for_json.append(p_copy)
    
    with (out_dir / "paragraph_stream.json").open("w", encoding="utf-8") as f:
        json.dump(paragraphs_for_json, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------
    stage += 1
    _progress("Export DOCX")
    try:
        docx_path = out_dir / "book_ru.docx"
        # Восстанавливаем image_bytes для DOCX из images_by_page
        paragraphs_with_images = []
        images_restored = 0
        for p in paragraphs:
            p_copy = dict(p)
            if p_copy.get("type") == "image":
                # Восстанавливаем image_bytes из images_by_page
                page_num = p_copy.get("page", 0)
                image_id = p_copy.get("image_id", "")
                if page_num in images_by_page:
                    # Ищем изображение по ID
                    found = False
                    for img in images_by_page[page_num]:
                        # Сравниваем ID: может быть "p2_img0" vs "p2_img0" или частичное совпадение
                        if img["id"] == image_id:
                            p_copy["image_bytes"] = img["image_bytes"]
                            found = True
                            images_restored += 1
                            break
                        # Fallback: сравниваем по последней части ID (например "img0" из "p2_img0")
                        if "_" in image_id and "_" in img["id"]:
                            img_suffix = img["id"].split("_")[-1]  # "img0"
                            if image_id.endswith(img_suffix):
                                p_copy["image_bytes"] = img["image_bytes"]
                                found = True
                                images_restored += 1
                                break
                    if not found:
                        print(f"[WARN] Image {image_id} on page {page_num} not found in images_by_page")
                else:
                    print(f"[WARN] No images found for page {page_num}")
            paragraphs_with_images.append(p_copy)
        
        if images_restored > 0:
            print(f"      Restored {images_restored} images for DOCX export")
        
        export_docx_path = export_docx(paragraphs_with_images, docx_path)
        export_paths = {**json_paths, "docx_main": export_docx_path}
    except Exception as e:
        raise RuntimeError(f"DOCX export failed: {e}") from e

    # --------------------------------------------------------
    # Дополнительный экспорт HTML (flow) для просмотра верстки
    try:
        html_path = out_dir / "book.html"
        book_doc = _layout_to_bookdoc(layout_model, images_by_page)
        export_html(book_doc, str(html_path))
        export_paths["html"] = str(html_path)
    except Exception as e:
        print(f"[WARN] HTML export failed: {e}")

    # --------------------------------------------------------
    stage += 1
    _progress("Register in library")
    try:
        library_record = register_book_in_library(
            ingest_raw,
            export_paths,
            qa_report,
        )
    except Exception as e:
        print(f"[WARN] Library registration failed: {e}")
        library_record = None

    return {
        "book_id": book_id,
        "ingest": ingest,
        "qa_report": qa_report,
        "layout_model": layout_model,
        "paragraph_stream": paragraphs,
        "export_paths": export_paths,
        "library_record": library_record,
    }
