from __future__ import annotations

from typing import List, Optional
import fitz  # PyMuPDF


def rasterize_pdf_pages(pdf_path: str, dpi: int = 200, page_range: tuple[int, int] = None) -> List[Optional[bytes]]:
    """
    Делает растровые превью страниц PDF в PNG (bytes).
    - Используется для анализа фона/водяных знаков/невекторных артефактов.
    - Best-effort: при ошибке по странице кладём None, не валим ingest.
    - Оптимизация для больших PDF: можно обрабатывать по частям через page_range.
    
    Args:
        pdf_path: путь к PDF
        dpi: разрешение для растеризации (по умолчанию 200)
        page_range: (start, end) для обработки только части страниц (опционально)
    """
    previews: List[Optional[bytes]] = []

    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        with fitz.open(pdf_path) as doc:
            start_idx = page_range[0] if page_range else 0
            end_idx = page_range[1] if page_range else len(doc)
            
            for page_num in range(start_idx, min(end_idx, len(doc))):
                try:
                    page = doc[page_num]
                    pix = page.get_pixmap(matrix=matrix, alpha=False)
                    previews.append(pix.tobytes("png"))
                    # Очистка памяти после каждой страницы для больших PDF
                    del pix
                except Exception:
                    previews.append(None)
    except Exception:
        # На случай проблем с файлом — вернём пустой список
        return []

    return previews

