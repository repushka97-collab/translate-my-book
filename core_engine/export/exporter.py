from pathlib import Path
import json
import os
import tempfile
import uuid

from docx import Document

from core_engine.core.models import BookDocument
from core_engine.layout.pdf_builder import PDFBuilder
from core_engine.export.html_exporter import export_html_absolute, export_html_flow
from core_engine.export.html_to_pdf import convert_html_to_pdf
from core_engine.export.html_exporter import export_html_absolute


def export_json(doc: BookDocument, out_path: str) -> None:
    """
    Сохраняем BookDocument в JSON.
    """
    out = Path(out_path)
    out.write_text(
        json.dumps(doc.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_html(doc: BookDocument, out_path: str) -> None:
    """
    HTML экспорт.
    По умолчанию — потоковый (flow) без наложений; если HTML_ABSOLUTE=1, то абсолютный.
    """
    use_abs = os.getenv("HTML_ABSOLUTE", "0") == "1"
    if use_abs:
        export_html_absolute(doc, out_path)
    else:
        export_html_flow(doc, out_path)


def export_pdf(doc: BookDocument, out_path: str) -> None:
    """
    Экспорт PDF.
    - Если доступен Playwright и включен HTML_TO_PDF_PLAYWRIGHT=1, генерируем HTML (flow по умолчанию) и конвертим браузером.
    - Переключатель HTML_ABSOLUTE=1 даст абсолютную версию.
    - Если включен PDF_REBUILD=1, использует PyMuPDF Deep Layout Manipulation для точной замены текста.
    - Иначе fallback на PDFBuilder (старый путь).
    """
    # [PDF TRANSLATION EXPERT MODE] PyMuPDF Deep Layout Manipulation
    # КРИТИЧНО: PDF_REBUILD_V2 имеет приоритет для точного копирования изображений
    use_pdf_rebuild = os.getenv("PDF_REBUILD", "0") == "1"
    use_playwright = os.getenv("HTML_TO_PDF_PLAYWRIGHT", "0") == "1" and not use_pdf_rebuild
    
    # Если включен Playwright, используем его (более надежно для переведенного текста)
    if use_playwright:
        # Сначала генерируем HTML, потом конвертируем в PDF
        tmp_dir = Path(tempfile.gettempdir())
        html_tmp = tmp_dir / f"pdf_export_{uuid.uuid4().hex[:8]}.html"
        try:
            # Генерируем HTML - используем absolute для лучшего сохранения layout
            # HTML_ABSOLUTE=0 для flow (быстрее, но менее точный)
            # HTML_ABSOLUTE=1 для absolute (медленнее, но точнее) - ПО УМОЛЧАНИЮ
            use_absolute = os.getenv("HTML_ABSOLUTE", "1") == "1"  # По умолчанию absolute для качества
            if use_absolute:
                from core_engine.export.html_exporter import export_html_absolute
                export_html_absolute(doc, str(html_tmp))
            else:
                from core_engine.export.html_exporter import export_html_flow
                export_html_flow(doc, str(html_tmp))
            
            # Конвертируем HTML в PDF через Playwright
            from core_engine.export.html_to_pdf import convert_html_to_pdf
            temp_pdf = str(Path(out_path).with_suffix(".tmp.pdf"))
            convert_html_to_pdf(str(html_tmp), temp_pdf, page_width=doc.pages[0].width if doc.pages else 595, page_height=doc.pages[0].height if doc.pages else 842)
            
            # [ADVANCED MODE] Финальное сжатие (Ghostscript или PyMuPDF fallback)
            use_ghostscript = os.getenv("GHOSTSCRIPT_COMPRESS", "1") != "0"  # По умолчанию включено
            compressed = False
            
            if use_ghostscript and Path(temp_pdf).exists():
                from core_engine.export.ghostscript_compress import compress_pdf_with_ghostscript
                # Используем "ebook" для лучшего баланса качества и размера (можно изменить на "screen" для максимального сжатия)
                compression_quality = os.getenv("GHOSTSCRIPT_QUALITY", "ebook")  # screen, ebook, prepress, printer
                if compress_pdf_with_ghostscript(temp_pdf, out_path, quality=compression_quality):
                    compressed = True
                    if Path(temp_pdf).exists():
                        Path(temp_pdf).unlink()
            
            # Fallback: сжатие через PyMuPDF если Ghostscript не доступен
            if not compressed and Path(temp_pdf).exists():
                try:
                    import fitz
                    doc = fitz.open(temp_pdf)
                    # Агрессивное сжатие через PyMuPDF
                    # Более агрессивное сжатие
                    # Более агрессивное сжатие
                    doc.save(
                        out_path,
                        garbage=4,  # максимальная очистка
                        deflate=True,  # сжатие потоков
                        deflate_images=True,  # сжатие изображений
                        deflate_fonts=True,  # сжатие шрифтов
                        clean=True,  # очистка структуры
                        ascii=False,  # бинарный формат
                        no_new_id=True,  # не создавать новые ID
                        encryption=0,  # без шифрования
                    )
                    doc.close()
                    if Path(temp_pdf).exists():
                        Path(temp_pdf).unlink()
                    print(f"[PDF] Compressed via PyMuPDF (Ghostscript not available)")
                    compressed = True
                except Exception as e:
                    print(f"[WARN] PyMuPDF compression failed: {e}")
            
            # Если сжатие не сработало, просто переименовываем
            if not compressed and Path(temp_pdf).exists():
                try:
                    if Path(out_path).exists():
                        Path(out_path).unlink()
                    Path(temp_pdf).rename(out_path)
                except Exception as e:
                    # Если переименование не работает, копируем
                    import shutil
                    if Path(out_path).exists():
                        Path(out_path).unlink()
                    shutil.copy2(temp_pdf, out_path)
                    Path(temp_pdf).unlink()
            
            print(f"[PDF] Generated via HTML to PDF (Playwright)")
            if html_tmp.exists():
                html_tmp.unlink()
            return
        except Exception as e:
            print(f"[WARN] HTML to PDF conversion failed: {e}, falling back to PDF rebuild")
            if html_tmp.exists():
                html_tmp.unlink()
    
    if use_pdf_rebuild:
        try:
            # Используем улучшенную версию v2 для гарантированного удаления текста
            use_v2 = os.getenv("PDF_REBUILD_V2", "1") == "1"
            if use_v2:
                from core_engine.export.pdf_rebuilder_v2 import rebuild_pdf_with_translations_v2 as rebuild_pdf_with_translations
            else:
                from core_engine.export.pdf_rebuilder import rebuild_pdf_with_translations
            
            # Подготавливаем переводы из документа
            translations = []
            blocks_with_translation = 0
            blocks_total = 0
            
            for page in doc.pages:
                for block in page.blocks:
                    blocks_total += 1
                    original = block.raw_text or block.normalized_text or ""
                    translated = getattr(block, "translated_text", None) or ""
                    
                    if translated and translated.strip() and translated != original and hasattr(block, "bbox"):
                        blocks_with_translation += 1
                        metadata = block.metadata or {}
                        translations.append({
                            "page": page.number,
                            "bbox": {
                                "x0": block.bbox.x0,
                                "y0": block.bbox.y0,
                                "x1": block.bbox.x1,
                                "y1": block.bbox.y1,
                            },
                            "original_text": original,
                            "translated_text": translated,
                            "font_size": metadata.get("font_size", 12.0),
                            "font": metadata.get("font", "helv"),
                            "is_bold": metadata.get("is_bold", False),
                            "is_italic": metadata.get("is_italic", False),
                            "color": metadata.get("color"),
                        })
            
            print(f"[PDF_REBUILD] Found {blocks_with_translation}/{blocks_total} blocks with translations")
            
            if translations:
                print(f"[PDF_REBUILD] Applying {len(translations)} translations to PDF...")
                # Временно сохраняем без сжатия
                temp_out = str(Path(out_path).with_suffix(".tmp.pdf"))
                rebuild_pdf_with_translations(
                    doc.source_path,
                    temp_out,
                    translations,
                    compress=False  # Сжатие сделаем через Ghostscript
                )
                
                # [ADVANCED MODE] Обработка формул через MathJax
                formulas_by_page = doc.metadata.get("formulas_by_page") if hasattr(doc, "metadata") and doc.metadata else None
                if formulas_by_page and Path(temp_out).exists():
                    try:
                        from core_engine.export.mathjax_formulas import replace_formulas_in_pdf
                        temp_with_formulas = str(Path(out_path).with_suffix(".tmp_formulas.pdf"))
                        if replace_formulas_in_pdf(temp_out, temp_with_formulas, formulas_by_page):
                            # Заменяем временный файл
                            if Path(temp_with_formulas).exists():
                                Path(temp_out).unlink()
                                Path(temp_with_formulas).rename(temp_out)
                    except Exception as e:
                        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
                        with open(error_log_path, "a", encoding="utf-8") as f:
                            f.write(f"[MathJax] Export error: {e}\n")
                
                # [ADVANCED MODE] Финальное сжатие через Ghostscript
                use_ghostscript = os.getenv("GHOSTSCRIPT_COMPRESS", "1") == "1"
                if use_ghostscript:
                    from core_engine.export.ghostscript_compress import compress_pdf_with_ghostscript
                    compression_quality = os.getenv("GHOSTSCRIPT_QUALITY", "ebook")  # screen, ebook, prepress, printer
                    if compress_pdf_with_ghostscript(temp_out, out_path, quality=compression_quality):
                        # Удаляем временный файл
                        try:
                            if Path(temp_out).exists():
                                Path(temp_out).unlink()
                        except Exception:
                            pass  # Игнорируем ошибки удаления
                    else:
                        # Если Ghostscript не сработал, копируем временный файл
                        try:
                            if Path(temp_out).exists():
                                import shutil
                                shutil.copy2(temp_out, out_path)
                                Path(temp_out).unlink()
                        except Exception:
                            # Если не получилось, оставляем temp файл
                            pass
                else:
                    # Копируем временный файл
                    try:
                        if Path(temp_out).exists():
                            import shutil
                            shutil.copy2(temp_out, out_path)
                            Path(temp_out).unlink()
                    except Exception as e:
                        # Если не получилось переименовать, пробуем скопировать
                        try:
                            import shutil
                            if Path(temp_out).exists():
                                shutil.copy2(temp_out, out_path)
                        except Exception:
                            pass
                
                return
        except Exception as e:
            print(f"[WARN] PDF rebuild failed: {e}, falling back to standard export")
    
    use_playwright = os.getenv("HTML_TO_PDF_PLAYWRIGHT", "0") == "1"
    if use_playwright:
        tmp_dir = Path(tempfile.gettempdir())
        tmp_html = tmp_dir / "tmp_export_abs.html"
        try:
            # КРИТИЧНО: По умолчанию используем absolute для точного позиционирования
            use_abs = os.getenv("HTML_ABSOLUTE", "1") == "1"  # По умолчанию 1 для качества
            if use_abs:
                print(f"      [PDF] Using HTML_ABSOLUTE layout for precise positioning")
                export_html_absolute(doc, str(tmp_html))
            else:
                print(f"      [PDF] Using HTML_FLOW layout (less precise)")
                export_html_flow(doc, str(tmp_html))
            
            # Получаем размеры страницы из документа (если есть)
            page_width = None
            page_height = None
            if doc.pages:
                first_page = doc.pages[0]
                page_width = getattr(first_page, "width", None)
                page_height = getattr(first_page, "height", None)
            
            ok = convert_html_to_pdf(str(tmp_html), out_path, page_width, page_height)
            if ok:
                return
        except Exception as e:
            print(f"[WARN] Playwright PDF export failed: {e}")
            pass

    # Fallback
    builder = PDFBuilder()
    builder.build_pdf(doc, out_path)


def export_docx(doc: BookDocument, out_path: str) -> None:
    """
    Простой DOCX.
    """
    d = Document()

    for page in doc.pages:
        d.add_heading(f"Page {page.number}", level=2)
        for block in page.blocks:
            txt = (
                block.translated_text
                or block.normalized_text
                or block.raw_text
                or ""
            )
            d.add_paragraph(txt)

    d.save(out_path)

