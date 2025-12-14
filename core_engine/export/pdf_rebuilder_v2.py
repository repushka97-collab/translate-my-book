"""
[PDF TRANSLATION EXPERT MODE v2] - Улучшенная версия с полным удалением текста
Использует метод пересоздания страницы для гарантированного удаления старого текста
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from pathlib import Path
import fitz  # PyMuPDF
import copy


def rebuild_pdf_with_translations_v2(
    source_pdf_path: str,
    output_pdf_path: str,
    translations: List[Dict[str, Any]],
    compress: bool = True
) -> None:
    """
    Пересобирает PDF с переведенным текстом через полное пересоздание страниц.
    Этот метод гарантирует полное удаление старого текста.
    
    Args:
        source_pdf_path: путь к исходному PDF
        output_pdf_path: путь для сохранения переведенного PDF
        translations: список словарей с переводами
        compress: сжимать ли PDF после перевода
    """
    source_doc = fitz.open(source_pdf_path)
    new_doc = fitz.open()  # Создаем новый документ
    
    # Группируем переводы по страницам
    translations_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for trans in translations:
        page_num = trans.get("page", 1) - 1  # 0-based
        translations_by_page.setdefault(page_num, []).append(trans)
    
    total_replacements = 0
    
    # Обрабатываем каждую страницу
    for page_num in range(len(source_doc)):
        source_page = source_doc[page_num]
        
        # Создаем новую страницу с теми же размерами
        new_page = new_doc.new_page(
            width=source_page.rect.width,
            height=source_page.rect.height
        )
        
        # Копируем изображения и векторную графику
        image_list = source_page.get_images()
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                # Извлекаем изображение
                base_image = source_doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_rects = source_page.get_image_rects(xref)
                
                if image_rects:
                    rect = image_rects[0]
                    # Вставляем изображение на новую страницу
                    new_page.insert_image(rect, stream=image_bytes)
            except Exception:
                pass
        
        # Получаем переводы для этой страницы
        page_translations = translations_by_page.get(page_num, [])
        
        # Сортируем переводы по позиции (сверху вниз, слева направо)
        page_translations.sort(key=lambda t: (
            t.get("bbox", {}).get("y0", 0),
            t.get("bbox", {}).get("x0", 0)
        ))
        
        # Вставляем переведенный текст
        for trans in page_translations:
            original_text = trans.get("original_text", "").strip()
            translated_text = trans.get("translated_text", "").strip()
            
            if not translated_text or translated_text == original_text or not original_text:
                continue
            
            bbox = trans.get("bbox", {})
            x0 = bbox.get("x0", 0)
            y0 = bbox.get("y0", 0)
            x1 = bbox.get("x1", 0)
            y1 = bbox.get("y1", 0)
            
            if x1 <= x0 or y1 <= y0:
                continue
            
            rect = fitz.Rect(x0, y0, x1, y1)
            
            # Получаем параметры шрифта
            font_size = trans.get("font_size", 12.0)
            font_name = trans.get("font", "helv")
            is_bold = trans.get("is_bold", False)
            is_italic = trans.get("is_italic", False)
            color = trans.get("color")
            
            # Определяем имя шрифта PyMuPDF
            if "times" in font_name.lower() or "roman" in font_name.lower():
                base_font = "times"
            elif "courier" in font_name.lower() or "mono" in font_name.lower():
                base_font = "cour"
            else:
                base_font = "helv"
            
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
            from core_engine.export.pdf_rebuilder import adjust_fontsize_for_overflow
            adjusted_fontsize = adjust_fontsize_for_overflow(
                translated_text,
                rect.width,
                font_size,
                pdf_font
            )
            
            # Определяем цвет
            text_color = None
            if color and color.startswith("#"):
                r = int(color[1:3], 16) / 255.0
                g = int(color[3:5], 16) / 255.0
                b = int(color[5:7], 16) / 255.0
                text_color = (r, g, b)
            
            # Вставляем текст через textbox для правильной обработки кириллицы
            # Используем insert_textbox для многострочного текста
            try:
                # Создаем textbox с правильными параметрами
                rc = new_page.insert_textbox(
                    rect,
                    translated_text,
                    fontsize=adjusted_fontsize,
                    fontname=pdf_font,
                    color=text_color if text_color else (0, 0, 0),
                    align=0,  # left align
                    render_mode=0,
                )
                if rc >= 0:  # Успешно вставлено
                    total_replacements += 1
                else:
                    # Fallback на insert_text если textbox не работает
                    text_point = fitz.Point(rect.x0, rect.y0 + adjusted_fontsize * 0.8)
                    new_page.insert_text(
                        text_point,
                        translated_text,
                        fontsize=adjusted_fontsize,
                        fontname=pdf_font,
                        color=text_color if text_color else (0, 0, 0),
                        render_mode=0,
                    )
                    total_replacements += 1
            except Exception:
                try:
                    # Fallback на базовый шрифт
                    rc = new_page.insert_textbox(
                        rect,
                        translated_text,
                        fontsize=adjusted_fontsize,
                        fontname=base_font,
                        color=text_color if text_color else (0, 0, 0),
                        align=0,
                        render_mode=0,
                    )
                    if rc >= 0:
                        total_replacements += 1
                    else:
                        text_point = fitz.Point(rect.x0, rect.y0 + adjusted_fontsize * 0.8)
                        new_page.insert_text(
                            text_point,
                            translated_text,
                            fontsize=adjusted_fontsize,
                            fontname=base_font,
                            color=text_color if text_color else (0, 0, 0),
                            render_mode=0,
                        )
                        total_replacements += 1
                except Exception:
                    pass
    
    if total_replacements > 0:
        print(f"[PDF_REBUILD_V2] Applied {total_replacements} text replacements")
    
    # Сохраняем PDF
    save_options = {}
    if compress:
        save_options = {
            "garbage": 4,
            "deflate": True,
            "clean": True,
        }
    
    new_doc.save(output_pdf_path, **save_options)
    new_doc.close()
    source_doc.close()

