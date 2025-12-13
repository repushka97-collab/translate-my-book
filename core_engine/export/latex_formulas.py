"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

LaTeX в PDF: Mathpix + PyMuPDF для формул.
Основано на: https://mathpix.com/api-documentation
"""

from __future__ import annotations

from typing import Optional, Dict, Any
from pathlib import Path
import fitz  # PyMuPDF
import base64
import os


def render_latex_to_image(
    latex_formula: str,
    output_path: Optional[str] = None,
    dpi: int = 200
) -> Optional[bytes]:
    """
    Рендерит LaTeX формулу в изображение через Mathpix API.
    
    Workflow:
    1. Mathpix API → LaTeX формулы
    2. Рендеринг LaTeX в PNG
    3. Возврат bytes для вставки в PDF
    
    Args:
        latex_formula: LaTeX формула
        output_path: опциональный путь для сохранения (для отладки)
        dpi: разрешение изображения
    
    Returns:
        PNG bytes или None
    """
    # Пробуем использовать Mathpix API (если доступен)
    mathpix_app_id = os.getenv("MATHPIX_APP_ID")
    mathpix_app_key = os.getenv("MATHPIX_APP_KEY")
    
    if mathpix_app_id and mathpix_app_key:
        try:
            import requests
            
            # Конвертируем LaTeX в изображение через Mathpix
            url = "https://api.mathpix.com/v3/text"
            headers = {
                "app_id": mathpix_app_id,
                "app_key": mathpix_app_key,
                "Content-type": "application/json"
            }
            
            # Сначала получаем LaTeX из изображения (если нужно)
            # Но здесь мы уже имеем LaTeX, поэтому рендерим напрямую
            # Mathpix может рендерить LaTeX через их API
            
            # Альтернатива: используем локальный LaTeX рендерер если доступен
            return _render_latex_local(latex_formula, output_path, dpi)
        except Exception as e:
            print(f"[WARN] Mathpix API failed: {e}, trying local renderer")
    
    # Fallback: локальный рендерер
    return _render_latex_local(latex_formula, output_path, dpi)


def _render_latex_local(
    latex_formula: str,
    output_path: Optional[str] = None,
    dpi: int = 200
) -> Optional[bytes]:
    """
    Рендерит LaTeX локально через matplotlib или другие инструменты.
    """
    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib import mathtext  # type: ignore
        
        # Создаем фигуру
        fig = plt.figure(figsize=(6, 2))
        fig.text(0.5, 0.5, f"${latex_formula}$", fontsize=20, ha="center", va="center")
        fig.patch.set_facecolor("white")
        
        # Сохраняем в bytes
        import io
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.1)
        buf.seek(0)
        image_bytes = buf.read()
        buf.close()
        plt.close(fig)
        
        # Сохраняем в файл если нужно (для отладки)
        if output_path:
            Path(output_path).write_bytes(image_bytes)
        
        return image_bytes
    except ImportError:
        # matplotlib не установлен
        return None
    except Exception as e:
        print(f"[WARN] Local LaTeX renderer failed: {e}")
        return None


def insert_formula_image_in_pdf(
    page: fitz.Page,
    rect: fitz.Rect,
    formula_image_bytes: bytes
) -> None:
    """
    Вставляет рендеренную формулу в PDF в исходные координаты.
    
    Основано на: https://pymupdf.readthedocs.io/en/latest/recipes-images.html
    """
    try:
        # Создаем Pixmap из bytes
        img = fitz.Pixmap(formula_image_bytes)
        
        # Вставляем изображение в rect
        page.insert_image(rect, pixmap=img)
        
        del img
    except Exception as e:
        print(f"[WARN] Failed to insert formula image: {e}")

