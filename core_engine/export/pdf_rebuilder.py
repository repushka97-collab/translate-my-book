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
    КРИТИЧНО: Учитывает кириллицу (на 10-15% шире латиницы).
    """
    # Приблизительный расчет (можно улучшить через font metrics)
    # Средняя ширина символа в зависимости от шрифта
    char_width_ratios = {
        "helv": 0.6,
        "times": 0.55,
        "cour": 0.6,
    }
    base_ratio = char_width_ratios.get(fontname.lower(), 0.6)
    
    # КРИТИЧНОЕ ИСПРАВЛЕНИЕ: Проверяем наличие кириллицы
    # Кириллические символы (U+0400-U+04FF) на 10-15% шире латиницы
    has_cyrillic = any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in text)
    if has_cyrillic:
        # Увеличиваем коэффициент для кириллицы
        base_ratio *= 1.12  # 12% шире для кириллицы
    
    return len(text) * fontsize * base_ratio


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
            
            # Ищем текст в PDF по содержимому
            # Пробуем разные варианты поиска
            text_instances = []
            
            # 1. Точный поиск полного текста
            text_instances = page.search_for(original_text, flags=fitz.TEXT_DEHYPHENATE)
            
            # 2. Если не нашли, пробуем поиск по первым словам (для длинных текстов)
            if not text_instances and len(original_text) > 20:
                first_words = " ".join(original_text.split()[:5])  # Первые 5 слов
                text_instances = page.search_for(first_words, flags=fitz.TEXT_DEHYPHENATE)
            
            # 3. Если не нашли, пробуем поиск по первым 50 символам
            if not text_instances and len(original_text) > 50:
                text_instances = page.search_for(original_text[:50], flags=fitz.TEXT_DEHYPHENATE)
            
            # 4. Если все еще не нашли, используем bbox из перевода
            if not text_instances:
                bbox = trans.get("bbox", {})
                x0 = bbox.get("x0", 0)
                y0 = bbox.get("y0", 0)
                x1 = bbox.get("x1", 0)
                y1 = bbox.get("y1", 0)
                
                if x1 > x0 and y1 > y0:
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
            
            # АГРЕССИВНОЕ УДАЛЕНИЕ ТЕКСТА - используем несколько методов
            # Расширяем rect для полного покрытия текста
            expanded_rect = fitz.Rect(
                max(0, rect.x0 - 5),
                max(0, rect.y0 - 5),
                min(page.rect.width, rect.x1 + 5),
                min(page.rect.height, rect.y1 + 5)
            )
            
            # Метод 1: Получаем все текстовые блоки в области и затираем их
            try:
                text_dict = page.get_text("dict", clip=expanded_rect)
                for block in text_dict.get("blocks", []):
                    if "lines" in block:
                        for line in block["lines"]:
                            for span in line.get("spans", []):
                                span_rect = fitz.Rect(span["bbox"])
                                # Затираем каждый span отдельно
                                page.add_redact_annot(span_rect, fill=(1, 1, 1))
            except Exception:
                pass
            
            # Метод 2: Затираем всю область белым фоном
            page.add_redact_annot(expanded_rect, fill=(1, 1, 1))
            
            # Метод 3: Применяем затирание (сохраняем изображения)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            
            # Метод 4: Рисуем белый прямоугольник поверх для гарантии (несколько слоев)
            for _ in range(2):  # Два слоя для гарантии
                page.draw_rect(expanded_rect, color=(1, 1, 1), fill=(1, 1, 1), width=0)
            
            # Метод 5: Дополнительно затираем через поиск текста в области
            try:
                area_text = page.get_text("text", clip=expanded_rect).strip()
                if area_text:
                    # Ищем и затираем все вхождения текста в области
                    for word in original_text.split()[:10]:  # Первые 10 слов
                        word_instances = page.search_for(word, flags=fitz.TEXT_DEHYPHENATE)
                        for word_rect in word_instances:
                            if expanded_rect.intersects(word_rect):
                                page.add_redact_annot(word_rect, fill=(1, 1, 1))
                    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            except Exception:
                pass
            
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
                
                # КРИТИЧНОЕ ИСПРАВЛЕНИЕ: Позиционирование с учетом baseline
                # rect.tl помещает текст слишком высоко, нужно учесть высоту шрифта
                # Используем y0 + fontsize * 0.8 для правильного baseline
                text_point = fitz.Point(rect.x0, rect.y0 + adjusted_fontsize * 0.8)
                
                # Вставляем текст с правильным позиционированием
                # Используем стандартные шрифты PyMuPDF (не требуют файлов)
                try:
                    page.insert_text(
                        text_point,  # правильная позиция с учетом baseline
                        translated_text,
                        fontsize=adjusted_fontsize,
                        fontname=pdf_font,
                        color=text_color if text_color else (0, 0, 0),  # черный по умолчанию
                    )
                except (ValueError, RuntimeError) as font_error:
                    # КРИТИЧНОЕ ИСПРАВЛЕНИЕ: Проверяем кириллицу перед fallback
                    # Если шрифт не поддерживается, проверяем наличие кириллицы
                    has_cyrillic = any(ord(c) >= 0x0400 and ord(c) <= 0x04FF for c in translated_text)
                    
                    if has_cyrillic:
                        # Для кириллицы пробуем использовать Font Manager если доступен
                        try:
                            from core_engine.export.font_manager import get_font_manager
                            font_manager = get_font_manager()
                            cyrillic_font = font_manager.get_font_for_text(doc, base_font, translated_text)
                            if cyrillic_font != base_font:
                                page.insert_text(
                                    text_point,
                                    translated_text,
                                    fontsize=adjusted_fontsize,
                                    fontname=cyrillic_font,
                                    color=text_color if text_color else (0, 0, 0),
                                )
                            else:
                                raise ValueError("No Cyrillic font available")
                        except (ImportError, ValueError, RuntimeError):
                            # Если Font Manager недоступен, используем базовый (может не отобразить кириллицу)
                            page.insert_text(
                                text_point,
                                translated_text,
                                fontsize=adjusted_fontsize,
                                fontname=base_font,
                                color=text_color if text_color else (0, 0, 0),
                            )
                    else:
                        # Для не-кириллического текста используем базовый шрифт
                        try:
                            page.insert_text(
                                text_point,
                                translated_text,
                                fontsize=adjusted_fontsize,
                                fontname=base_font,
                                color=text_color if text_color else (0, 0, 0),
                            )
                        except Exception:
                            # Последний fallback: простая вставка
                            page.insert_text(text_point, translated_text, fontsize=adjusted_fontsize)
            except Exception as e:
                # Fallback: простая вставка без форматирования
                text_point = fitz.Point(rect.x0, rect.y0 + adjusted_fontsize * 0.8)
                page.insert_text(text_point, translated_text, fontsize=adjusted_fontsize)
            
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

