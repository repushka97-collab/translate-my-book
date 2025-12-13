from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from core_engine.core.models import BookDocument
from core_engine.structure.builder import save_structure_layers


class LibraryManager:
    """
    Управляет библиотекой обработанных книг.

    Структура:
        library/
          <book_id>/
            original.pdf
            manifest.json
            layers/
              pages.json
              blocks_index.json
    """

    def __init__(self, root: str = "./library"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def compute_book_id(pdf_path: str) -> str:
        """
        Считаем SHA256 от PDF и берём первые 16 символов.
        Стабильный ID книги.
        """
        p = Path(pdf_path)
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()[:16]

    def get_book_dir(self, book_id: str) -> Path:
        return self.root / book_id

    def save_manifest(
        self,
        book_id: str,
        pdf_path: str,
        doc: BookDocument,
        exports: Dict[str, str],
        qa_report: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> str:
        """
        Создаёт каталог книги, сохраняет structural layers и manifest.json.
        Возвращает путь к манифесту.
        """
        book_dir = self.get_book_dir(book_id)
        book_dir.mkdir(parents=True, exist_ok=True)

        src_pdf = Path(pdf_path)
        dst_pdf = book_dir / "original.pdf"

        # Кладём оригинальный PDF (best-effort)
        if not dst_pdf.exists():
            try:
                shutil.copy2(src_pdf, dst_pdf)
            except Exception:
                # Не критично, если не удалось скопировать
                pass

        # === STRUCTURE LAYERS ===
        layers_paths = save_structure_layers(book_id, doc, book_dir)

        manifest = {
            "book_id": book_id,
            "source_pdf": str(src_pdf.resolve()),
            "library_pdf": str(dst_pdf),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "pages": len(doc.pages),
            "metadata": metadata,
            "exports": exports,
            "qa": qa_report,
            "layers": layers_paths,
        }

        manifest_path = book_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return str(manifest_path)
# --- v3 pipeline adapter -------------------------------------------------------

def register_book_in_library(
    ingest_result,
    export_paths: Dict[str, str],
    qa_report: Dict[str, Any],
):
    """
    Лёгкая обёртка над LibraryManager, чтобы v3-пайплайн мог работать.
    v3 скелет сейчас оперирует простым ingest_result и словарями.
    """
    mgr = LibraryManager()

    # Сбор минимальных метаданных, пока у нас нет полноценного BookDocument
    metadata = {
        "title": ingest_result.meta.get("title"),
        "source_path": ingest_result.meta.get("source_path"),
        "pages": ingest_result.meta.get("pages"),
    }

    # Берём реальный BookDocument, если он есть в ingest_result
    doc = getattr(ingest_result, "doc", None)
    if not isinstance(doc, BookDocument):
        doc = BookDocument(
    pages=[],
    source_path=ingest_result.meta.get("source_path", ""),
    )

    # Генерация book_id из твоей функции compute_book_id невозможно (нет PDF пути),
    # поэтому просто используем тот, что дал ingest.
    book_id = ingest_result.book_id

    # Cохраняем manifest через существующий механизм
    mgr.save_manifest(
        book_id=book_id,
        pdf_path=ingest_result.meta.get("source_path", ""),
        doc=doc,
        exports=export_paths,
        qa_report=qa_report,
        metadata=metadata,
    )

