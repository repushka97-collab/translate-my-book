from __future__ import annotations

from typing import List, Optional
import fitz  # PyMuPDF


def rasterize_pdf_pages(pdf_path: str, dpi: int = 200) -> List[Optional[bytes]]:
    """
    Делает растровые превью всех страниц PDF в PNG (bytes).
    - Используется для анализа фона/водяных знаков/невекторных артефактов.
    - Best-effort: при ошибке по странице кладём None, не валим ingest.
    """
    previews: List[Optional[bytes]] = []

    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        with fitz.open(pdf_path) as doc:
            for page in doc:
                try:
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    previews.append(pix.tobytes("png"))
                except Exception:
                    previews.append(None)
    except Exception:
        # На случай проблем с файлом — вернём пустой список
        return []

    return previews

