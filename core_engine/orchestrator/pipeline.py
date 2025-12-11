# pipeline_v2.1.py
# Оркестратор ядра v7.1 — полный, проверенный, безопасный

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json

from core_engine.ingest.pdf_ingest import ingest_pdf
from core_engine.normalize.text_cleaner import normalize_blocks
from core_engine.translate.llm_adapter import translate_blocks
from core_engine.layout.block_reassemble import build_layout_model
from core_engine.layout.heading_detector import detect_headings
from core_engine.layout.layout_reassemble_v2 import build_paragraph_stream
from core_engine.export.export_json import export_json_bundle
from core_engine.export.docx_exporter import export_docx
from core_engine.library.library_manager import register_book_in_library
from core_engine.qa.integrity_check import qa_check_blocks
from core_engine.utils.contracts import (
    validate_ingest_result,
    validate_blocks_structure,
)


# ============================================================
#                САНИТИ для ingest-результата
# ============================================================

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
) -> Dict[str, Any]:

    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source PDF not found: {source}")

    # --------------------------------------------------------
    print("[1/9] Ingest PDF...")
    ingest_raw = ingest_pdf(source)
    ingest = _normalize_ingest_result(ingest_raw)
    validate_ingest_result(ingest)
    book_id = ingest["book_id"]

    # --------------------------------------------------------
    print("[2/9] Normalize blocks...")
    normalized = normalize_blocks(ingest["blocks"])
    normalized = detect_headings(normalized)
    validate_blocks_structure(normalized, stage="normalize")

    # --------------------------------------------------------
    print("[3/9] Translate blocks...")
    translated = translate_blocks(
        normalized,
        source_lang="en",
        target_lang="ru",
        mode=mode,
    )
    validate_blocks_structure(translated, stage="translate")

    # --------------------------------------------------------
    print("[4/9] QA check...")
    qa_report = qa_check_blocks(normalized, translated)

    # prepare output folder
    out_dir = Path("output") / str(book_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "qa_report.json").open("w", encoding="utf-8") as f:
        json.dump(qa_report, f, ensure_ascii=False, indent=2)

    if qa_report.get("status") == "error":
        raise RuntimeError("QA failed: critical translation mismatch")

    # --------------------------------------------------------
    print("[5/9] Build layout model...")
    layout_model = build_layout_model(book_id, translated)

    # --------------------------------------------------------
    print("[6/9] Save JSON bundle...")
    json_paths = export_json_bundle(layout_model, book_id)

    # --------------------------------------------------------
    print("[7/9] Build paragraph_stream (Layout v2.1)...")
    paragraphs = build_paragraph_stream(layout_model)

    # sanity check paragraph stream
    para_count = len(paragraphs)
    non_empty = [p for p in paragraphs if (p.get("text") or "").strip()]
    print(f"[7/9] Paragraphs built: {para_count}")

    if para_count == 0:
        raise RuntimeError("Layout v2.1 produced an empty paragraph_stream")
    if not non_empty:
        raise RuntimeError("Layout v2.1 produced paragraphs with empty text only")

    # save debug version
    with (out_dir / "paragraph_stream.json").open("w", encoding="utf-8") as f:
        json.dump(paragraphs, f, ensure_ascii=False, indent=2)

    # --------------------------------------------------------
    print("[8/9] Export DOCX...")
    docx_path = out_dir / "book_ru.docx"
    export_docx_path = export_docx(paragraphs, docx_path)

    export_paths = {**json_paths, "docx_main": export_docx_path}

    # --------------------------------------------------------
    print("[9/9] Register in library...")
    library_record = register_book_in_library(
        ingest_raw,
        export_paths,
        qa_report,
    )

    return {
        "book_id": book_id,
        "ingest": ingest,
        "qa_report": qa_report,
        "layout_model": layout_model,
        "paragraph_stream": paragraphs,
        "export_paths": export_paths,
        "library_record": library_record,
    }
