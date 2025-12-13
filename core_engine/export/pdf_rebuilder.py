"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

PyMuPDF Deep Layout Manipulation - точная замена текста с сохранением шрифтов, размеров и позиций.
Основано на: https://pymupdf.readthedocs.io/en/latest/recipes-text.html#how-to-search-for-text-and-mark-it
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from pathlib import Path
import fitz  # PyMuPDF


def calculate_text_width(text: str, fontsize: float, fontname: str = "helv") -> float:
    """
    Вычисляет ширину текста для определения переполнения.
    """
    # Приблизительный расчет (можно улучшить через font metrics)
    # Средняя ширина символа в зависимости от шрифта
    char_width_ratios = {
        "helv": 0.6,
        "times": 0.55,
        "cour": 0.6,
    }
    ratio = char_width_ratios.get(fontname.lower(), 0.6)
    return len(text) * fontsize * ratio


def adjust_fontsize_for_overflow(
    text: str,
    rect_width: float,
    original_fontsize: float,
    fontname: str = "helv"
) -> float:
    """
    Автоматическое сжатие шрифта при переполнении без сдвига верстки.
    Основано на: https://github.com/pymupdf/PyMuPDF/issues/2370
    """
    text_width = calculate_text_width(text, original_fontsize, fontname)
    
    if text_width > rect_width:
        scale = rect_width / text_width
        # Минимальный размер шрифта - 6pt
        new_fontsize = max(6.0, original_fontsize * scale * 0.95)  # 0.95 для запаса
        return new_fontsize
    
    return original_fontsize


def rebuild_pdf_with_translations(
    source_pdf_path: str,
    output_pdf_path: str,
    translations: List[Dict[str, Any]],
    compress: bool = True
) -> None:
    """
    Пересобирает PDF с переведенным текстом, сохраняя шрифты, размеры и позиции.
    
    Args:
        source_pdf_path: путь к исходному PDF
        output_pdf_path: путь для сохранения переведенного PDF
        translations: список словарей с переводами:
            {
                "page": int,
                "bbox": {"x0": float, "y0": float, "x1": float, "y1": float},
                "original_text": str,
                "translated_text": str,
                "font_size": float,
                "font": str,
                "is_bold": bool,
                "is_italic": bool,
                "color": str (optional, RGB hex)
            }
        compress: сжимать ли PDF после перевода
    """
    doc = fitz.open(source_pdf_path)
    
    # Группируем переводы по страницам
    translations_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for trans in translations:
        page_num = trans.get("page", 1) - 1  # 0-based
        translations_by_page.setdefault(page_num, []).append(trans)
    
    # Обрабатываем каждую страницу
    total_replacements = 0
    for page_num, page_translations in translations_by_page.items():
        if page_num >= len(doc):
            continue
        
        page = doc[page_num]
        page_replacements = 0
        
        # Сортируем переводы по позиции (сверху вниз, слева направо)
        page_translations.sort(key=lambda t: (
            t.get("bbox", {}).get("y0", 0),
            t.get("bbox", {}).get("x0", 0)
        ))
        
        # Применяем переводы
        for trans in page_translations:
            original_text = trans.get("original_text", "").strip()
            translated_text = trans.get("translated_text", "").strip()
            
            if not translated_text or translated_text == original_text or not original_text:
                continue
            
            # Ищем текст в PDF по содержимому (более надежно чем по bbox)
            # Используем поиск текста для получения точных координат
            text_instances = page.search_for(original_text, flags=fitz.TEXT_DEHYPHENATE)
            
            # Если не нашли точное совпадение, используем bbox из перевода
            if not text_instances:
                bbox = trans.get("bbox", {})
                x0 = bbox.get("x0", 0)
                y0 = bbox.get("y0", 0)
                x1 = bbox.get("x1", 0)
                y1 = bbox.get("y1", 0)
                
                if x1 <= x0 or y1 <= y0:
                    continue
                
                text_instances = [fitz.Rect(x0, y0, x1, y1)]
            
            # Используем первое найденное вхождение (или bbox если поиск не дал результатов)
            rect = text_instances[0] if text_instances else None
            if not rect:
                continue
            
            # Получаем параметры шрифта
            font_size = trans.get("font_size", 12.0)
            font_name = trans.get("font", "helv")
            is_bold = trans.get("is_bold", False)
            is_italic = trans.get("is_italic", False)
            color = trans.get("color")
            
            # Определяем имя шрифта PyMuPDF (используем стандартные встроенные шрифты)
            # PyMuPDF поддерживает: helv, times, cour, symb, zadb
            if "times" in font_name.lower() or "roman" in font_name.lower():
                base_font = "times"
            elif "courier" in font_name.lower() or "mono" in font_name.lower():
                base_font = "cour"
            else:
                base_font = "helv"  # Helvetica по умолчанию
            
            # Формируем полное имя шрифта
            if is_bold and is_italic:
                pdf_font = f"{base_font}-boldoblique"
            elif is_bold:
                pdf_font = f"{base_font}-bold"
            elif is_italic:
                pdf_font = f"{base_font}-oblique"
            else:
                pdf_font = base_font
            
            # Корректируем размер шрифта при переполнении
            adjusted_fontsize = adjust_fontsize_for_overflow(
                translated_text,
                rect.width,
                font_size,
                pdf_font
            )
            
            # Затираем оригинальный текст
            page.add_redact_annot(rect, fill=(1, 1, 1))  # белый фон
            
            # Применяем затирание (сохраняем изображения)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            
            # Вставляем переведенный текст с сохранением позиции и шрифта
            try:
                # Определяем цвет если указан
                text_color = None
                if color and color.startswith("#"):
                    # Конвертируем hex в RGB tuple (0-1)
                    r = int(color[1:3], 16) / 255.0
                    g = int(color[3:5], 16) / 255.0
                    b = int(color[5:7], 16) / 255.0
                    text_color = (r, g, b)
                
                # Вставляем текст в верхний левый угол rect
                # Используем стандартные шрифты PyMuPDF (не требуют файлов)
                try:
                    page.insert_text(
                        rect.tl,  # top-left corner
                        translated_text,
                        fontsize=adjusted_fontsize,
                        fontname=pdf_font,
                        color=text_color if text_color else (0, 0, 0),  # черный по умолчанию
                    )
                except (ValueError, RuntimeError) as font_error:
                    # Если шрифт не поддерживается, используем базовый
                    try:
                        page.insert_text(
                            rect.tl,
                            translated_text,
                            fontsize=adjusted_fontsize,
                            fontname=base_font,  # используем базовый шрифт без модификаторов
                            color=text_color if text_color else (0, 0, 0),
                        )
                    except Exception:
                        # Последний fallback: простая вставка
                        page.insert_text(rect.tl, translated_text, fontsize=adjusted_fontsize)
            except Exception as e:
                # Fallback: простая вставка без форматирования
                page.insert_text(rect.tl, translated_text, fontsize=adjusted_fontsize)
            
            page_replacements += 1
            total_replacements += 1
    
    if total_replacements > 0:
        print(f"[PDF_REBUILD] Applied {total_replacements} text replacements")
    
    # Сохраняем PDF с опциональным сжатием
    save_options = {}
    if compress:
        # Сжатие без потерь (основано на: https://pymupdf.readthedocs.io/en/latest/recipes-pages.html#how-to-compress-a-pdf)
        save_options = {
            "garbage": 4,  # максимальная очистка
            "deflate": True,  # сжатие потоков
            "clean": True,  # очистка структуры
        }
    
    doc.save(output_pdf_path, **save_options)
    doc.close()


def compress_pdf(input_path: str, output_path: str) -> None:
    """
    Сжимает PDF без потерь качества.
    Русский текст увеличивает размер на 25-40%, поэтому сжатие критично.
    """
    doc = fitz.open(input_path)
    doc.save(
        output_path,
        garbage=4,
        deflate=True,
        clean=True,
    )
    doc.close()

