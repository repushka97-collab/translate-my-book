# core_engine/export/mathjax_formulas.py
"""
[ADVANCED PDF TRANSLATION MODE] MathJax для математических формул.
Конвертация LaTeX → SVG с точными размерами и вставка в PDF.
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
import fitz  # PyMuPDF
from pathlib import Path
import io
import base64


def render_formula_mathjax(
    latex_formula: str,
    width: Optional[float] = None,
    output_format: str = "svg"
) -> Optional[bytes]:
    """
    Рендерит математическую формулу через MathJax.
    
    Args:
        latex_formula: формула в LaTeX формате
        width: желаемая ширина в px (опционально)
        output_format: "svg" или "png"
    
    Returns:
        Байты SVG/PNG изображения или None при ошибке
    """
    try:
        # Используем MathJax через Node.js API или веб-сервис
        # Для простоты используем веб-API MathJax (можно заменить на локальный)
        
        import requests  # type: ignore
        
        # MathJax API endpoint (можно использовать локальный сервер)
        api_url = os.getenv("MATHJAX_API_URL", "https://api.mathjax.org/v2/latex")
        
        params = {
            "latex": latex_formula,
            "format": output_format,
        }
        
        if width:
            params["width"] = width
        
        response = requests.get(api_url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.content
        else:
            # Fallback на matplotlib
            return _render_formula_matplotlib(latex_formula, width)
            
    except Exception:
        # Fallback на matplotlib
        return _render_formula_matplotlib(latex_formula, width)


def _render_formula_matplotlib(
    latex_formula: str,
    width: Optional[float] = None
) -> Optional[bytes]:
    """Fallback рендеринг через matplotlib."""
    try:
        import matplotlib.pyplot as plt  # type: ignore
        from matplotlib import mathtext  # type: ignore
        import io
        
        # Создаем фигуру
        fig = plt.figure(figsize=(width / 100.0 if width else 6, 1) if width else (6, 1))
        ax = fig.add_axes([0, 0, 1, 1])
        ax.axis("off")
        
        # Рендерим формулу
        ax.text(0.5, 0.5, f"${latex_formula}$", 
                fontsize=12, ha="center", va="center",
                transform=ax.transAxes)
        
        # Сохраняем в байты
        output = io.BytesIO()
        fig.savefig(output, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        
        return output.getvalue()
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[MathJax] Matplotlib fallback error: {e}\n")
        return None


def detect_formulas_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Обнаруживает математические формулы в тексте.
    
    Args:
        text: текст для анализа
    
    Returns:
        Список словарей: [{"formula": str, "start": int, "end": int, "type": str}, ...]
    """
    formulas = []
    
    # Паттерны для формул
    patterns = [
        (r'\$([^$]+)\$', "inline"),  # inline: $formula$
        (r'\$\$([^$]+)\$\$', "display"),  # display: $$formula$$
        (r'\\begin\{equation\}(.*?)\\end\{equation\}', "equation"),  # LaTeX equation
        (r'\\begin\{align\}(.*?)\\end\{align\}', "align"),  # LaTeX align
        (r'\\\[(.*?)\\\]', "display"),  # LaTeX \[ \]
        (r'\\\((.*?)\\\)', "inline"),  # LaTeX \( \)
    ]
    
    for pattern, formula_type in patterns:
        for match in re.finditer(pattern, text, re.DOTALL):
            formulas.append({
                "formula": match.group(1).strip(),
                "start": match.start(),
                "end": match.end(),
                "type": formula_type,
                "full_match": match.group(0)
            })
    
    return formulas


def replace_formulas_in_pdf(
    pdf_path: str,
    output_path: str,
    formulas_by_page: Dict[int, List[Dict[str, Any]]],
    page_range: Optional[Tuple[int, int]] = None
) -> bool:
    """
    Заменяет формулы в PDF на отрендеренные изображения.
    
    Args:
        pdf_path: путь к исходному PDF
        output_path: путь для сохранения нового PDF
        formulas_by_page: словарь {page_num: [{"formula": str, "bbox": [x0,y0,x1,y1]}, ...]}
        page_range: (start_page, end_page) или None для всех страниц
    
    Returns:
        True при успехе
    """
    try:
        doc = fitz.open(pdf_path)
        
        start_page = 0
        end_page = len(doc) - 1
        
        if page_range:
            start_page = max(0, page_range[0] - 1)
            end_page = min(len(doc) - 1, page_range[1] - 1)
        
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num]
            page_key = page_num + 1  # 1-based
            
            if page_key not in formulas_by_page:
                continue
            
            formulas = formulas_by_page[page_key]
            
            for formula_info in formulas:
                formula_text = formula_info.get("formula", "")
                bbox = formula_info.get("bbox")
                
                if not formula_text or not bbox:
                    continue
                
                # Рендерим формулу
                formula_image = render_formula_mathjax(
                    formula_text,
                    width=bbox[2] - bbox[0] if len(bbox) >= 4 else None
                )
                
                if formula_image:
                    # Создаем rect для вставки
                    rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                    
                    # Удаляем оригинальный текст (закрашиваем)
                    page.add_redact_annot(rect, fill=(1, 1, 1))
                    page.apply_redactions()
                    
                    # Вставляем изображение формулы
                    page.insert_image(rect, stream=formula_image)
        
        doc.save(output_path)
        doc.close()
        return True
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[MathJax] Replace formulas error: {e}\n")
        return False

