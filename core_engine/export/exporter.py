from pathlib import Path
import json
import os
import tempfile

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
    - Иначе fallback на PDFBuilder (старый путь).
    """
    use_playwright = os.getenv("HTML_TO_PDF_PLAYWRIGHT", "0") == "1"
    if use_playwright:
        tmp_dir = Path(tempfile.gettempdir())
        tmp_html = tmp_dir / "tmp_export_abs.html"
        try:
            use_abs = os.getenv("HTML_ABSOLUTE", "0") == "1"
            if use_abs:
                export_html_absolute(doc, str(tmp_html))
            else:
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

