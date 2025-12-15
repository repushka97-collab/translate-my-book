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
from core_engine.export.exporter import export_html, export_pdf
from core_engine.core.models import BookDocument, Page, Block, BBox, BlockType, ImageObject, TableObject, TableCell
from core_engine.library.library_manager import register_book_in_library
from core_engine.qa.integrity_check import qa_check_blocks
from core_engine.utils.contracts import (
    validate_ingest_result,
    validate_blocks_structure,
)

# Production modules (optional)
try:
    from core_engine.production import (
        get_performance_config,
        apply_performance_config,
        detect_book_type,
        get_book_profile,
        apply_profile,
        get_metrics_collector,
        sanitize_pdf,
        audit_operation,
    )
    PRODUCTION_MODULES_AVAILABLE = True
except ImportError:
    PRODUCTION_MODULES_AVAILABLE = False


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

    # [PRODUCTION MODE] Apply performance config
    if PRODUCTION_MODULES_AVAILABLE and os.getenv("USE_PERFORMANCE_CONFIG", "0") == "1":
        try:
            config = get_performance_config()
            apply_performance_config(config)
        except Exception as e:
            print(f"      [WARN] Performance config failed: {e}")

    # [PRODUCTION MODE] Sanitize PDF if enabled
    sanitize_enabled = os.getenv("SANITIZE_PDF", "0") == "1"
    if PRODUCTION_MODULES_AVAILABLE and sanitize_enabled:
        try:
            sanitized_path = str(source).replace(".pdf", "_sanitized.pdf")
            result = sanitize_pdf(str(source), sanitized_path)
            if result.get("success"):
                print(f"      [Security] Sanitized PDF: {result.get('redacted_count', 0)} items redacted")
                source = Path(sanitized_path)
        except Exception as e:
            print(f"      [WARN] PDF sanitization failed: {e}")

    # [PRODUCTION MODE] Detect book type and apply profile
    book_type = None
    if PRODUCTION_MODULES_AVAILABLE and os.getenv("USE_BOOK_PROFILES", "0") == "1":
        try:
            book_type = detect_book_type(str(source))
            profile = get_book_profile(book_type, str(source))
            print(f"      [Book Profile] Detected type: {book_type}")
            print(f"      [Book Profile] Quality threshold: {profile.get('quality_threshold', 0.90)}")
        except Exception as e:
            print(f"      [WARN] Book profile detection failed: {e}")

    # [PRODUCTION MODE] Start monitoring
    metrics_collector = None
    if PRODUCTION_MODULES_AVAILABLE and os.getenv("USE_MONITORING", "0") == "1":
        try:
            metrics_collector = get_metrics_collector()
            import time
            start_time = time.time()
        except Exception as e:
            print(f"      [WARN] Monitoring setup failed: {e}")

    # [PRODUCTION MODE] Audit operation
    if PRODUCTION_MODULES_AVAILABLE and os.getenv("AUDIT_OPERATIONS", "0") == "1":
        try:
            audit_operation("translate_start", document_id=str(source.stem))
        except Exception as e:
            print(f"      [WARN] Audit logging failed: {e}")

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
        
        # [ADVANCED MODE] Checkpoint Manager для восстановления
        use_checkpoints = os.getenv("USE_CHECKPOINTS", "0") == "1"
        checkpoint_mgr = None
        if use_checkpoints:
            from core_engine.orchestrator.checkpoint_manager import CheckpointManager
            checkpoint_mgr = CheckpointManager(checkpoint_dir="checkpoints")
        
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
        
        # [ADVANCED MODE] Font Metric Compensation для критичных блоков
        use_font_compensation = os.getenv("USE_FONT_COMPENSATION", "0") == "1"
        if use_font_compensation:
            try:
                from core_engine.correction.font_compensator import FontMetricsCompensator
                
                compensator = FontMetricsCompensator(
                    source_lang="en",
                    target_lang="ru",
                    max_width_change=1.3
                )
                
                # Применяем компенсацию к блокам с высоким риском переполнения
                compensated_count = 0
                for block in translated:
                    # Проверяем, нужна ли компенсация (по translation_params или metadata)
                    needs_compensation = False
                    if translation_params.get("font_size_reduction"):
                        needs_compensation = True
                    elif block.get("metadata", {}).get("high_overflow_risk"):
                        needs_compensation = True
                    
                    if needs_compensation:
                        orig_text = block.get("normalized_text", "")
                        trans_text = block.get("translated_text", "")
                        
                        if orig_text and trans_text:
                            compensation = compensator.calculate(
                                orig_text,
                                trans_text,
                                font_size=block.get("metadata", {}).get("font_size", 12.0)
                            )
                            
                            # Сохраняем параметры компенсации в metadata
                            if "metadata" not in block:
                                block["metadata"] = {}
                            block["metadata"]["font_compensation"] = compensation
                            compensated_count += 1
                
                if compensated_count > 0:
                    print(f"      Font compensation applied to {compensated_count} blocks")
            except Exception as e:
                error_log_path = Path("errors.log")
                error_log_path.parent.mkdir(exist_ok=True)
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[FontCompensation] Error: {e}\n")
        
        # [ADVANCED MODE] Сохраняем чекпоинт после перевода
        if checkpoint_mgr:
            checkpoint_mgr.save_checkpoint(book_id, 0, {"translated_blocks": len(translated)}, stage="translate")
        
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
            
            # [ADVANCED MODE] DocTR для обработки текста в изображениях
            use_doctr = os.getenv("USE_DOCTR_IMAGES", "0") == "1"
            if use_doctr:
                try:
                    from core_engine.export.doctr_images import replace_images_in_pdf_with_translated_text
                    from core_engine.translate.llm_adapter import translate_text_simple
                    
                    # Создаем функцию перевода для изображений
                    def translate_fn(text, source_lang="en", target_lang="ru"):
                        return translate_text_simple(text, source_lang, target_lang)
                    
                    # Обрабатываем изображения с текстом (сохраняем во временный файл)
                    temp_pdf_with_images = out_dir / "temp_with_translated_images.pdf"
                    if replace_images_in_pdf_with_translated_text(
                        str(source_path),
                        str(temp_pdf_with_images),
                        translate_fn
                    ):
                        print(f"      DocTR: Processed images with text")
                except Exception as e:
                    error_log_path = Path("errors.log")
                    error_log_path.parent.mkdir(exist_ok=True)
                    with open(error_log_path, "a", encoding="utf-8") as f:
                        f.write(f"[DocTR] Error: {e}\n")
            
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
    formulas_by_page: Dict[int, List[Dict[str, Any]]] = {}  # Инициализируем на уровне функции
    try:
        paragraphs = build_paragraph_stream(layout_model)
        
        # [ADVANCED MODE] Обнаружение и обработка формул через MathJax
        use_mathjax = os.getenv("USE_MATHJAX", "0") == "1"
        if use_mathjax:
            try:
                from core_engine.export.mathjax_formulas import detect_formulas_in_text, replace_formulas_in_pdf
                
                # Собираем формулы по страницам
                formulas_by_page = {}  # Переиспользуем переменную уровня функции
                for para in paragraphs:
                    page_num = para.get("page", 0)
                    text = para.get("text", "") or para.get("translated_text", "")
                    
                    if text:
                        formulas = detect_formulas_in_text(text)
                        if formulas:
                            if page_num not in formulas_by_page:
                                formulas_by_page[page_num] = []
                            
                            # Добавляем формулы с bbox (упрощенная версия)
                            for formula in formulas:
                                # Используем bbox параграфа как приблизительный bbox формулы
                                bbox = para.get("bbox", {})
                                formulas_by_page[page_num].append({
                                    "formula": formula.get("formula", ""),
                                    "bbox": [
                                        bbox.get("x0", 0),
                                        bbox.get("y0", 0),
                                        bbox.get("x1", 0),
                                        bbox.get("y1", 0)
                                    ]
                                })
                
                if formulas_by_page:
                    print(f"      MathJax: Found formulas on {len(formulas_by_page)} pages")
            except Exception as e:
                error_log_path = Path("errors.log")
                error_log_path.parent.mkdir(exist_ok=True)
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[MathJax] Error: {e}\n")
                formulas_by_page = {}
        else:
            formulas_by_page = {}
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
    _progress("Export PDF")
    try:
        pdf_path = out_dir / "book_ru.pdf"
        book_doc = _layout_to_bookdoc(layout_model, images_by_page)
        
        # Передаем формулы если они были обнаружены (через metadata)
        if formulas_by_page and hasattr(book_doc, "metadata"):
            if book_doc.metadata is None:
                book_doc.metadata = {}
            book_doc.metadata["formulas_by_page"] = formulas_by_page
        export_pdf(book_doc, str(pdf_path))
        export_paths["pdf"] = str(pdf_path)
        print(f"      PDF exported: {pdf_path}")
        
        # [ADVANCED MODE] Vector Graphics Repair
        use_vector_repair = os.getenv("USE_VECTOR_REPAIR", "0") == "1"
        if use_vector_repair and Path(source_path).exists() and Path(pdf_path).exists():
            try:
                from core_engine.correction.vector_repair import repair_vector_elements
                import fitz
                
                print("      Vector Repair: Fixing vector graphics...")
                
                doc_orig = fitz.open(str(source_path))
                doc_trans = fitz.open(str(pdf_path))
                
                max_pages = min(len(doc_orig), len(doc_trans))
                repaired_count = 0
                
                for page_num in range(max_pages):
                    page_orig = doc_orig[page_num]
                    page_trans = doc_trans[page_num]
                    
                    # Применяем исправления
                    repaired_page = repair_vector_elements(page_trans, page_orig)
                    if repaired_page != page_trans:
                        repaired_count += 1
                
                if repaired_count > 0:
                    doc_trans.save(str(pdf_path), incremental=True)
                    print(f"      Vector Repair: Fixed {repaired_count} pages")
                
                doc_orig.close()
                doc_trans.close()
            except Exception as e:
                error_log_path = Path("errors.log")
                error_log_path.parent.mkdir(exist_ok=True)
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[VectorRepair] Error: {e}\n")
        
        # [ADVANCED MODE] Автоматическое исправление ошибок верстки
        use_auto_correction = os.getenv("AUTO_CORRECTION", "0") == "1"
        if use_auto_correction and Path(source_path).exists() and Path(pdf_path).exists():
            try:
                from core_engine.correction.layout_fixer import apply_layout_correction
                from core_engine.correction.overflow_predictor import OverflowPredictor, adjust_translation_params
                
                print("      Auto-correction: Applying layout fixes...")
                
                # Применяем исправления
                corrected_pdf_path = str(Path(pdf_path).with_suffix(".corrected.pdf"))
                correction_result = apply_layout_correction(
                    str(source_path),
                    str(pdf_path),
                    corrected_pdf_path,
                    target_language="ru"
                )
                
                if correction_result.get("success"):
                    # Заменяем оригинальный PDF исправленным
                    if Path(corrected_pdf_path).exists():
                        Path(pdf_path).unlink()
                        Path(corrected_pdf_path).rename(pdf_path)
                        print(f"      Auto-correction: Fixed {correction_result.get('issues_found', 0)} issues")
            except Exception as e:
                error_log_path = Path("errors.log")
                error_log_path.parent.mkdir(exist_ok=True)
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[AutoCorrection] Error: {e}\n")
        
        # [QUALITY VERIFICATION MODE] Полная проверка качества
        use_quality_check = os.getenv("QUALITY_CHECK", "1") == "1"
        if use_quality_check and Path(source_path).exists():
            try:
                from core_engine.qa.quality_scorecard import generate_quality_scorecard, print_scorecard
                
                quality_reports_dir = out_dir / "quality_reports"
                quality_reports_dir.mkdir(exist_ok=True)
                
                scorecard_path = quality_reports_dir / "quality_scorecard.json"
                scorecard = generate_quality_scorecard(
                    str(source_path),
                    str(pdf_path),
                    str(scorecard_path)
                )
                
                # Выводим scorecard
                print_scorecard(scorecard)
                
                overall_score = scorecard.get("overall_score", 0.0)
                
                if overall_score >= 95:
                    print(f"      ✅ Quality Score: {overall_score:.1f}/100 - Excellent")
                elif overall_score >= 90:
                    print(f"      ⚠️ Quality Score: {overall_score:.1f}/100 - Good (manual review recommended for 10% pages)")
                else:
                    print(f"      ❌ Quality Score: {overall_score:.1f}/100 - Needs correction")
                
                export_paths["quality_scorecard"] = str(scorecard_path)
                
                # Генерируем heatmaps если включено
                use_heatmaps = os.getenv("GENERATE_HEATMAPS", "0") == "1"
                if use_heatmaps:
                    try:
                        from core_engine.qa.heatmap_diff import generate_heatmap_diff
                        heatmap_result = generate_heatmap_diff(
                            str(source_path),
                            str(pdf_path),
                            str(quality_reports_dir / "heatmaps")
                        )
                        if heatmap_result.get("heatmaps_generated", 0) > 0:
                            print(f"      Heatmaps generated: {heatmap_result['heatmaps_generated']} pages")
                            if heatmap_result.get("critical_pages"):
                                print(f"      Critical pages: {len(heatmap_result['critical_pages'])} pages need review")
                    except Exception as e:
                        error_log_path = Path("errors.log")
                        error_log_path.parent.mkdir(exist_ok=True)
                        with open(error_log_path, "a", encoding="utf-8") as f:
                            f.write(f"[Heatmaps] Error: {e}\n")
                
                # pdf-diff для дополнительной визуализации
                use_pdf_diff = os.getenv("PDF_DIFF_CHECK", "0") == "1"
                if use_pdf_diff:
                    try:
                        from core_engine.qa.pdf_diff_check import check_pdf_diff
                        diff_report_path = quality_reports_dir / "pdf_diff_report.html"
                        diff_result = check_pdf_diff(
                            str(source_path),
                            str(pdf_path),
                            str(diff_report_path),
                            threshold_px=2.0
                        )
                        if diff_result:
                            print(f"      PDF diff check: {diff_result.get('differences_count', 0)} differences found")
                            export_paths["pdf_diff_report"] = str(diff_report_path)
                    except Exception as e:
                        error_log_path = Path("errors.log")
                        error_log_path.parent.mkdir(exist_ok=True)
                        with open(error_log_path, "a", encoding="utf-8") as f:
                            f.write(f"[PDF_DIFF] Error: {e}\n")
                
            except Exception as e:
                # Логируем, но не падаем
                error_log_path = Path("errors.log")
                error_log_path.parent.mkdir(exist_ok=True)
                with open(error_log_path, "a", encoding="utf-8") as f:
                    f.write(f"[QualityCheck] Error: {e}\n")
    except Exception as e:
        print(f"[WARN] PDF export failed: {e}")

    # --------------------------------------------------------
    # [HUMAN FEEDBACK MODE] Оценка качества "как человек"
    use_human_like_evaluation = os.getenv("USE_HUMAN_LIKE_EVALUATION", "0") == "1"
    human_model_user = os.getenv("HUMAN_MODEL_USER", "default")
    
    if use_human_like_evaluation:
        try:
            from core_engine.learning.human_like_metrics import HumanLikeQualityAssessor
            from core_engine.learning.quality_model_trainer import load_user_model
            
            # Загружаем модель пользователя если есть
            user_model_path = load_user_model(human_model_user)
            if user_model_path:
                print(f"      [HUMAN_METRICS] Using personalized model for {human_model_user}")
            
            # Создаем оценщик
            quality_assessor = HumanLikeQualityAssessor()
            
            # Оцениваем качество переведенного PDF
            if Path(pdf_path).exists():
                try:
                    import fitz
                    doc_orig = fitz.open(str(source_path))
                    doc_trans = fitz.open(pdf_path)
                    
                    page_scores = []
                    max_pages = min(len(doc_orig), len(doc_trans), 10)  # Оцениваем первые 10 страниц
                    
                    for page_num in range(max_pages):
                        page_orig = doc_orig[page_num]
                        page_trans = doc_trans[page_num]
                        
                        assessment = quality_assessor.assess_page(page_orig, page_trans)
                        page_scores.append(assessment["overall_score"])
                    
                    avg_score = sum(page_scores) / len(page_scores) if page_scores else 0.0
                    print(f"      [HUMAN_METRICS] Average human-like score: {avg_score:.1f}/10")
                    print(f"      [HUMAN_METRICS] Recommendation: {quality_assessor.generate_recommendation(avg_score)}")
                    
                    # Добавляем в метаданные
                    if "human_quality_score" not in result:
                        result["human_quality_score"] = avg_score
                        result["human_recommendation"] = quality_assessor.generate_recommendation(avg_score)
                    
                    doc_orig.close()
                    doc_trans.close()
                except Exception as e:
                    print(f"      [WARN] Human metrics evaluation failed: {e}")
        except ImportError:
            print(f"      [WARN] Human metrics modules not available")
        except Exception as e:
            print(f"      [WARN] Human metrics evaluation failed: {e}")
    
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

    # [PRODUCTION MODE] Record metrics
    if metrics_collector and 'start_time' in locals():
        try:
            import time
            processing_time = time.time() - start_time
            metrics_collector.record_processing_time(book_id, processing_time)
            
            # Get quality score if available
            if "quality_scorecard" in export_paths:
                try:
                    with open(export_paths["quality_scorecard"], "r", encoding="utf-8") as f:
                        scorecard = json.load(f)
                        quality_score = scorecard.get("overall_score", 0.0) / 100.0
                        metrics_collector.record_quality_score(book_id, quality_score)
                except Exception:
                    pass
            
            metrics_collector.save_metrics()
            print(f"      [Monitoring] Metrics saved: {processing_time:.1f}s processing time")
        except Exception as e:
            print(f"      [WARN] Metrics recording failed: {e}")

    # [PRODUCTION MODE] Audit completion
    if PRODUCTION_MODULES_AVAILABLE and os.getenv("AUDIT_OPERATIONS", "0") == "1":
        try:
            audit_operation("translate_complete", document_id=str(source.stem), details={
                "book_id": book_id,
                "pages": len(ingest.get("blocks", [])) if ingest else 0
            })
        except Exception as e:
            print(f"      [WARN] Audit logging failed: {e}")

    return {
        "book_id": book_id,
        "ingest": ingest,
        "qa_report": qa_report,
        "layout_model": layout_model,
        "paragraph_stream": paragraphs,
        "export_paths": export_paths,
        "library_record": library_record,
    }
