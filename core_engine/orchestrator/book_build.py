from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Dict, Any

from core_engine.ingest.pdf_reader import (
    get_pdf_info,
    extract_pages,
    extract_blocks,
    extract_images,
    detect_tables,
    detect_columns,
)
from core_engine.normalize.text_cleaner import normalize_document
from core_engine.translate.translator import translate_document
from core_engine.qa.validator import run_all_checks
from core_engine.layout.pdf_builder import PDFBuilder
from core_engine.export.exporter import (
    export_json,
    export_html,
    export_pdf,
    export_docx,
)
from core_engine.llm.router import LLMRouter
from core_engine.core.models import BookDocument
from core_engine.library.library_manager import LibraryManager

logger = logging.getLogger("book_build")


class BookBuilder:
    """
    Главный пайплайн:
    PDF → ingest → normalize → translate → QA → layout → export → library
    """

    def __init__(
        self,
        workdir: str = "./output",
        llm_config_path: Optional[str] = None,
        library_root: str = "./library",
    ):
        self.router = LLMRouter(config_path=llm_config_path)

        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)

        self.library_root = Path(library_root)
        self.library_root.mkdir(parents=True, exist_ok=True)

    def build(self, pdf_path: str) -> Dict[str, Any]:
        pdf_path = Path(pdf_path)
        logger.info("Starting build for %s", pdf_path)

        # === INGEST ===
        info = get_pdf_info(pdf_path)
        logger.info("PDF info: %s", info)

        pages = extract_pages(pdf_path)
        blocks = extract_blocks(pdf_path, pages)
        extract_images(pdf_path, pages)
        detect_columns(pages, blocks)
        detect_tables(pdf_path, pages)

        doc = BookDocument(
            source_path=str(pdf_path),
            pages=pages,
            metadata=info.get("metadata", {}),
        )

        # === NORMALIZE ===
        normalize_document(doc)

        # === TRANSLATE (через LLMAdapter) ===
        try:
            adapter = self.router.get_translation_adapter()
            translate_document(doc, adapter, source_lang="en", target_lang="ru")
        except Exception:
            logger.exception("Translate failed, leaving normalized_text only")

        # === QA ===
        qa_report = run_all_checks(doc)
        logger.info("QA report: %s", qa_report)

        # === EXPORT ===
        stem = pdf_path.stem
        out_json = self.workdir / f"{stem}.json"
        out_html = self.workdir / f"{stem}.html"
        out_pdf = self.workdir / f"{stem}_ru.pdf"
        out_docx = self.workdir / f"{stem}.docx"

        export_json(doc, str(out_json))
        export_html(doc, str(out_html))
        export_pdf(doc, str(out_pdf))
        export_docx(doc, str(out_docx))

        exports = {
            "json": str(out_json),
            "html": str(out_html),
            "pdf": str(out_pdf),
            "docx": str(out_docx),
        }

        # === LIBRARY MANIFEST ===
        lib = LibraryManager(root=str(self.library_root))
        book_id = lib.compute_book_id(str(pdf_path))
        manifest_path = lib.save_manifest(
            book_id=book_id,
            pdf_path=str(pdf_path),
            doc=doc,
            exports=exports,
            qa_report=qa_report,
            metadata=info.get("metadata", {}),
        )

        logger.info("Build completed for %s", pdf_path)

        return {
            "book_id": book_id,
            "source": str(pdf_path),
            "exports": exports,
            "qa": qa_report,
            "library": {
                "root": str(self.library_root),
                "manifest": manifest_path,
            },
        }

