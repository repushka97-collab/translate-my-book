"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

Обработка векторной графики с текстом (SVG-диаграммы).
Основано на: https://github.com/pymupdf/PyMuPDF/issues/1884
"""

from __future__ import annotations

from typing import List, Dict, Any
import fitz  # PyMuPDF


def extract_vector_graphics_with_text(page) -> List[Dict[str, Any]]:
    """
    Извлекает векторные объекты (paths) со страницы, включая текст в них.
    
    Проблема: SVG-диаграммы с надписями ломаются при переводе.
    Решение: извлечение векторных объектов и замена текста без изменения геометрии.
    """
    vector_objects: List[Dict[str, Any]] = []
    
    try:
        # Получаем векторные пути
        drawings = page.get_drawings()
        
        for drawing in drawings:
            # Ищем текст в путях
            items = drawing.get("items", [])
            text_elements = []
            
            for item in items:
                if isinstance(item, (list, tuple)) and len(item) > 0:
                    op = item[0]
                    # Проверяем, есть ли текст в пути
                    if op == "text" or (len(item) > 1 and isinstance(item[1], str)):
                        text_elements.append(item)
            
            if text_elements:
                vector_objects.append({
                    "type": "vector_path",
                    "rect": drawing.get("rect"),
                    "items": items,
                    "text_elements": text_elements,
                })
    except Exception as e:
        print(f"[WARN] Failed to extract vector graphics: {e}")
    
    return vector_objects


def translate_vector_graphics(
    vector_objects: List[Dict[str, Any]],
    translate_fn: callable
) -> List[Dict[str, Any]]:
    """
    Переводит текст в векторных объектах без изменения геометрии.
    """
    translated_objects = []
    
    for obj in vector_objects:
        translated_obj = obj.copy()
        translated_items = []
        
        for item in obj.get("items", []):
            if isinstance(item, (list, tuple)) and len(item) > 0:
                op = item[0]
                # Если это текст - переводим
                if op == "text" or (len(item) > 1 and isinstance(item[1], str)):
                    original_text = item[1] if len(item) > 1 else ""
                    if original_text:
                        translated_text = translate_fn(original_text)
                        # Создаем новый item с переведенным текстом
                        new_item = list(item)
                        new_item[1] = translated_text
                        translated_items.append(tuple(new_item))
                    else:
                        translated_items.append(item)
                else:
                    translated_items.append(item)
            else:
                translated_items.append(item)
        
        translated_obj["items"] = translated_items
        translated_objects.append(translated_obj)
    
    return translated_objects

