from pathlib import Path
import json

from docx import Document

from core_engine.core.models import BookDocument
from core_engine.layout.pdf_builder import PDFBuilder
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
    HTML с абсолютными bbox, подложкой-растровкой и слоями блоков/картинок/таблиц.
    """
    export_html_absolute(doc, out_path)


def export_pdf(doc: BookDocument, out_path: str) -> None:
    """
    Экспорт PDF через layout PDFBuilder.
    """
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

