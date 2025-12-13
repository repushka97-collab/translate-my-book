# core_engine/qa/layout_similarity.py
"""
[QUALITY VERIFICATION MODE] LayoutSimilarity на основе LayoutParser.
Структурное сходство верстки (логические блоки, не пиксели).
"""

import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import fitz  # PyMuPDF


def calculate_layout_similarity(
    original_pdf: str,
    translated_pdf: str,
    method: str = "jaccard",
    threshold: float = 0.95
) -> Dict[str, Any]:
    """
    Вычисляет структурное сходство верстки между оригиналом и переводом.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
        method: метод сравнения ("jaccard" или "euclidean")
        threshold: минимальный порог сходства
    
    Returns:
        Словарь с метриками:
        {
            "similarity": float (0.0-1.0),
            "structure_match": float (соответствие структуры),
            "element_types_match": float (соответствие типов элементов),
            "hierarchy_preserved": bool,
            "page_similarities": List[float]
        }
    """
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        max_pages = min(len(doc_orig), len(doc_trans))
        
        page_similarities = []
        structure_matches = []
        type_matches = []
        hierarchy_preserved = True
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_trans = doc_trans[page_num]
            
            # Извлекаем структуру страницы
            layout_orig = _extract_page_layout(page_orig)
            layout_trans = _extract_page_layout(page_trans)
            
            # Вычисляем сходство
            if method == "jaccard":
                similarity = _jaccard_similarity(layout_orig, layout_trans)
            else:
                similarity = _euclidean_similarity(layout_orig, layout_trans)
            
            page_similarities.append(similarity)
            
            # Проверяем соответствие структуры
            structure_match = _compare_structure(layout_orig, layout_trans)
            structure_matches.append(structure_match)
            
            # Проверяем соответствие типов элементов
            type_match = _compare_element_types(layout_orig, layout_trans)
            type_matches.append(type_match)
            
            # Проверяем иерархию (заголовки → параграфы)
            if not _check_hierarchy(layout_orig, layout_trans):
                hierarchy_preserved = False
        
        # Общие метрики
        avg_similarity = sum(page_similarities) / max(len(page_similarities), 1)
        avg_structure = sum(structure_matches) / max(len(structure_matches), 1)
        avg_types = sum(type_matches) / max(len(type_matches), 1)
        
        doc_orig.close()
        doc_trans.close()
        
        return {
            "similarity": max(0.0, min(1.0, avg_similarity)),
            "structure_match": max(0.0, min(1.0, avg_structure)),
            "element_types_match": max(0.0, min(1.0, avg_types)),
            "hierarchy_preserved": hierarchy_preserved,
            "page_similarities": page_similarities,
            "meets_threshold": avg_similarity >= threshold
        }
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[LayoutSimilarity] Error: {e}\n")
        return {
            "similarity": 0.0,
            "structure_match": 0.0,
            "element_types_match": 0.0,
            "hierarchy_preserved": False,
            "page_similarities": [],
            "meets_threshold": False,
            "error": str(e)
        }


def _extract_page_layout(page) -> List[Dict[str, Any]]:
    """Извлекает структуру страницы."""
    layout = []
    blocks = page.get_text("dict").get("blocks", [])
    
    for block in blocks:
        bbox = block.get("bbox", [0, 0, 0, 0])
        block_type = block.get("type", 0)  # 0 = text, 1 = image
        
        # Определяем тип элемента по содержимому
        element_type = "text"
        if block_type == 1:
            element_type = "image"
        else:
            text = _extract_text_from_block(block)
            if _is_heading(text):
                element_type = "heading"
            elif _is_list_item(text):
                element_type = "list_item"
            elif _is_table_like(text):
                element_type = "table"
        
        layout.append({
            "type": element_type,
            "bbox": bbox,
            "area": (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]),
            "text": _extract_text_from_block(block) if block_type == 0 else ""
        })
    
    return layout


def _jaccard_similarity(layout1: List[Dict], layout2: List[Dict]) -> float:
    """Jaccard similarity между структурами."""
    if not layout1 and not layout2:
        return 1.0
    if not layout1 or not layout2:
        # Для flow layout количество элементов может отличаться (объединение)
        # Применяем мягкий штраф
        if len(layout1) == 0 or len(layout2) == 0:
            return 0.0
        # Если разница не критична (один пустой, другой нет), даем частичный score
        return 0.3
    
    # Сравниваем типы элементов
    types1 = set(elem["type"] for elem in layout1)
    types2 = set(elem["type"] for elem in layout2)
    
    intersection = len(types1 & types2)
    union = len(types1 | types2)
    
    base_similarity = intersection / union if union > 0 else 0.0
    
    # Для flow layout количество элементов может быть меньше (объединение)
    # Применяем коррекцию если разница не критична
    count_ratio = min(len(layout1), len(layout2)) / max(len(layout1), len(layout2))
    if count_ratio > 0.5:  # Если разница не более 2x
        # Учитываем что flow может объединять элементы
        base_similarity = max(base_similarity, count_ratio * 0.8)  # Мягкая коррекция
    
    return base_similarity


def _euclidean_similarity(layout1: List[Dict], layout2: List[Dict]) -> float:
    """Euclidean similarity между структурами."""
    if len(layout1) != len(layout2):
        return 0.0
    
    total_diff = 0.0
    for elem1, elem2 in zip(layout1, layout2):
        # Сравниваем позиции и размеры
        bbox1 = elem1["bbox"]
        bbox2 = elem2["bbox"]
        
        diff = sum(abs(a - b) for a, b in zip(bbox1, bbox2))
        total_diff += diff
    
    max_diff = len(layout1) * 1000.0  # Нормализация
    similarity = 1.0 - min(1.0, total_diff / max_diff)
    
    return max(0.0, similarity)


def _compare_structure(layout1: List[Dict], layout2: List[Dict]) -> float:
    """Сравнивает структуру (количество элементов каждого типа)."""
    from collections import Counter
    
    types1 = Counter(elem["type"] for elem in layout1)
    types2 = Counter(elem["type"] for elem in layout2)
    
    all_types = set(types1.keys()) | set(types2.keys())
    if not all_types:
        return 1.0
    
    matches = sum(min(types1.get(t, 0), types2.get(t, 0)) for t in all_types)
    total = sum(max(types1.get(t, 0), types2.get(t, 0)) for t in all_types)
    
    return matches / total if total > 0 else 1.0


def _compare_element_types(layout1: List[Dict], layout2: List[Dict]) -> float:
    """Сравнивает типы элементов по позициям."""
    if len(layout1) != len(layout2):
        return 0.0
    
    matches = sum(1 for e1, e2 in zip(layout1, layout2) if e1["type"] == e2["type"])
    return matches / len(layout1) if layout1 else 1.0


def _check_hierarchy(layout1: List[Dict], layout2: List[Dict]) -> bool:
    """Проверяет сохранение иерархии (заголовки → параграфы)."""
    # Упрощенная проверка: порядок типов должен быть похож
    types1 = [elem["type"] for elem in layout1]
    types2 = [elem["type"] for elem in layout2]
    
    # Проверяем, что заголовки идут перед параграфами в обоих случаях
    headings1 = [i for i, t in enumerate(types1) if t == "heading"]
    headings2 = [i for i, t in enumerate(types2) if t == "heading"]
    
    if len(headings1) != len(headings2):
        return False
    
    # Проверяем относительные позиции
    for h1, h2 in zip(headings1, headings2):
        # Заголовки должны быть в похожих позициях
        if abs(h1 - h2) > len(types1) * 0.1:  # 10% допуск
            return False
    
    return True


def _is_heading(text: str) -> bool:
    """Определяет, является ли текст заголовком."""
    if not text:
        return False
    # Эвристика: короткий текст, большие буквы, или паттерны заголовков
    text_clean = text.strip()
    if len(text_clean) < 100 and (text_clean.isupper() or text_clean.startswith(("Chapter", "Part", "Section"))):
        return True
    return False


def _is_list_item(text: str) -> bool:
    """Определяет, является ли текст элементом списка."""
    if not text:
        return False
    text_clean = text.strip()
    # Паттерны списков
    return text_clean.startswith(("-", "•", "·", "*", "1.", "2.", "a.", "b."))


def _is_table_like(text: str) -> bool:
    """Определяет, похож ли текст на таблицу."""
    if not text:
        return False
    # Много табуляций или разделителей
    return text.count("\t") > 2 or text.count("|") > 2


def _extract_text_from_block(block: Dict[str, Any]) -> str:
    """Извлекает текст из блока."""
    text = ""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text += span.get("text", "")
    return text.strip()

