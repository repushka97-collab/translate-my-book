# core_engine/export/weasyprint_css.py
"""
[ADVANCED PDF TRANSLATION MODE] WeasyPrint + CSS для динамических отступов.
Автоматическая подгонка кириллического текста под исходные отступы.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path


def generate_css_for_cyrillic_adjustment(
    original_width: float,
    translated_width: float,
    base_font_size: float = 12.0
) -> str:
    """
    Генерирует CSS для компенсации длины текста при переводе на кириллицу.
    
    Args:
        original_width: ширина оригинального текста в px
        translated_width: ширина переведенного текста в px
        base_font_size: базовый размер шрифта
    
    Returns:
        CSS строка с правилами компенсации
    """
    if original_width <= 0:
        return ""
    
    # Вычисляем коэффициент масштабирования
    scale_factor = original_width / max(translated_width, 1.0)
    
    # Ограничиваем масштаб (не более 1.2x и не менее 0.8x)
    scale_factor = max(0.8, min(1.2, scale_factor))
    
    adjusted_font_size = base_font_size * scale_factor
    
    css = f"""
    .text-block {{
        font-size: {adjusted_font_size}pt;
        line-height: 1.2;
        text-align: justify;
        hyphens: auto;
        word-spacing: normal;
        letter-spacing: normal;
    }}
    
    .cyrillic-compensated {{
        font-size: calc(1em * {scale_factor:.3f});
        line-height: 1.2;
    }}
    """
    
    return css


def apply_weasyprint_compensation(
    html_path: str,
    output_pdf_path: str,
    page_width: float = 595.0,
    page_height: float = 842.0,
    original_text_widths: Optional[Dict[str, float]] = None
) -> bool:
    """
    Применяет WeasyPrint для генерации PDF с CSS-компенсацией.
    
    Args:
        html_path: путь к HTML файлу
        output_pdf_path: путь для сохранения PDF
        page_width: ширина страницы в pt
        page_height: высота страницы в pt
        original_text_widths: словарь {block_id: original_width} для компенсации
    
    Returns:
        True при успехе, False при ошибке
    """
    try:
        from weasyprint import HTML, CSS  # type: ignore
        from weasyprint.text.fonts import FontConfiguration  # type: ignore
    except ImportError:
        # Логируем, но не падаем
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write("[WeasyPrint] Library not installed\n")
        return False
    
    try:
        # Читаем HTML
        html_content = Path(html_path).read_text(encoding="utf-8")
        
        # Генерируем CSS для компенсации
        css_rules = []
        if original_text_widths:
            for block_id, orig_width in original_text_widths.items():
                # Упрощенная версия - в реальности нужно знать translated_width
                # Здесь используем общий коэффициент
                css_rules.append(generate_css_for_cyrillic_adjustment(
                    orig_width, orig_width * 1.1  # предполагаем +10% для кириллицы
                ))
        
        # Базовый CSS для страницы
        base_css = f"""
        @page {{
            size: {page_width}pt {page_height}pt;
            margin: 0;
        }}
        
        body {{
            font-family: 'Times New Roman', 'DejaVu Serif', serif;
            font-size: 12pt;
            line-height: 1.6;
            color: #000;
        }}
        
        {generate_css_for_cyrillic_adjustment(595, 650, 12.0)}
        """
        
        # Комбинируем CSS
        full_css = base_css + "\n".join(css_rules)
        
        # Генерируем PDF
        font_config = FontConfiguration()
        html_doc = HTML(string=html_content)
        html_doc.write_pdf(
            output_pdf_path,
            stylesheets=[CSS(string=full_css)],
            font_config=font_config
        )
        
        return True
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[WeasyPrint] Error: {e}\n")
        return False

