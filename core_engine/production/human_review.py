# core_engine/production/human_review.py
"""
[PRODUCTION MODE] Human-in-the-Loop Workflow for Critical Cases.
Система для ручной проверки критических случаев.
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
import fitz


def calculate_priority(page_errors: Dict[str, Any]) -> str:
    """
    Вычисляет приоритет задачи для человека.
    
    Args:
        page_errors: словарь с ошибками страницы
    
    Returns:
        Приоритет: "critical", "high", "medium", "low"
    """
    error_count = len(page_errors.get("errors", []))
    quality_score = page_errors.get("quality_score", 1.0)
    
    if quality_score < 0.70 or error_count > 10:
        return "critical"
    elif quality_score < 0.85 or error_count > 5:
        return "high"
    elif quality_score < 0.90 or error_count > 2:
        return "medium"
    else:
        return "low"


def extract_page_image(pdf_path: str, page_num: int, output_path: Optional[str] = None) -> str:
    """
    Извлекает изображение страницы.
    
    Args:
        pdf_path: путь к PDF
        page_num: номер страницы (0-based)
        output_path: путь для сохранения (опционально)
    
    Returns:
        Путь к сохраненному изображению
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    
    if not output_path:
        output_path = f"page_{page_num + 1}.png"
    
    # Рендерим страницу в изображение
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x увеличение
    pix.save(output_path)
    
    doc.close()
    return output_path


def generate_diff_map(original_pdf: str, translated_pdf: str, page_num: int) -> Dict[str, Any]:
    """
    Генерирует карту различий между оригиналом и переводом.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
        page_num: номер страницы
    
    Returns:
        Словарь с информацией о различиях
    """
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        page_orig = doc_orig[page_num]
        page_trans = doc_trans[page_num]
        
        text_orig = page_orig.get_text()
        text_trans = page_trans.get_text()
        
        # Упрощенный анализ различий
        diff_info = {
            "text_length_orig": len(text_orig),
            "text_length_trans": len(text_trans),
            "length_ratio": len(text_trans) / len(text_orig) if len(text_orig) > 0 else 0,
            "blocks_orig": len(page_orig.get_text("dict").get("blocks", [])),
            "blocks_trans": len(page_trans.get_text("dict").get("blocks", []))
        }
        
        doc_orig.close()
        doc_trans.close()
        
        return diff_info
        
    except Exception as e:
        return {"error": str(e)}


def ai_suggest_fixes(page_errors: Dict[str, Any]) -> List[str]:
    """
    Генерирует предложения по исправлению на основе ошибок.
    
    Args:
        page_errors: словарь с ошибками страницы
    
    Returns:
        Список предложений
    """
    suggestions = []
    
    errors = page_errors.get("errors", [])
    
    for error in errors:
        error_type = error.get("type", "")
        
        if error_type == "text_overflow":
            suggestions.append("Уменьшить размер шрифта или применить font compensation")
        elif error_type == "image_drift":
            suggestions.append("Скорректировать позицию изображения")
        elif error_type == "table_break":
            suggestions.append("Проверить структуру таблицы и применить table preservation")
        elif error_type == "formula_error":
            suggestions.append("Проверить обработку формул через MathJax/Mathpix")
    
    return suggestions


def generate_human_tasks(
    failed_pages: Dict[int, Dict[str, Any]],
    original_pdf: str,
    failed_pdf: str,
    output_dir: str
) -> List[Dict[str, Any]]:
    """
    Генерирует задачи для человека с контекстом.
    
    Args:
        failed_pages: словарь {page_num: page_errors}
        original_pdf: путь к оригинальному PDF
        failed_pdf: путь к неудачно переведенному PDF
        output_dir: директория для сохранения задач
    
    Returns:
        Список задач для человека
    """
    tasks = []
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for page_num, page_errors in failed_pages.items():
        # Извлекаем изображения страниц
        orig_image_path = output_path / f"page_{page_num + 1}_original.png"
        trans_image_path = output_path / f"page_{page_num + 1}_translated.png"
        
        extract_page_image(original_pdf, page_num, str(orig_image_path))
        extract_page_image(failed_pdf, page_num, str(trans_image_path))
        
        # Генерируем карту различий
        diff_map = generate_diff_map(original_pdf, failed_pdf, page_num)
        
        # Генерируем предложения по исправлению
        suggested_fixes = ai_suggest_fixes(page_errors)
        
        task = {
            "page_number": page_num + 1,
            "priority": calculate_priority(page_errors),
            "context": {
                "original_image": str(orig_image_path),
                "translated_image": str(trans_image_path),
                "diff_map": diff_map,
                "error_details": page_errors,
                "suggested_fixes": suggested_fixes
            },
            "tools_provided": [
                "zoom_tool",
                "text_replacement_tool",
                "image_position_tool",
                "font_selector"
            ]
        }
        tasks.append(task)
    
    # Сортировка по приоритету
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(key=lambda x: priority_order.get(x["priority"], 4))
    
    # Сохраняем задачи в JSON
    tasks_file = output_path / "human_tasks.json"
    with open(tasks_file, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)
    
    return tasks


def should_trigger_human_review(
    quality_score: float,
    auto_attempts: int,
    book_type: str
) -> bool:
    """
    Определяет, нужно ли привлекать человека для проверки.
    
    Args:
        quality_score: оценка качества (0.0-1.0)
        auto_attempts: количество автоматических попыток
        book_type: тип книги
    
    Returns:
        True если нужна ручная проверка
    """
    # Критерии для ручной проверки:
    # 1. Качество < 90% после 3 автоматических попыток
    if quality_score < 0.90 and auto_attempts >= 3:
        return True
    
    # 2. Уникальные случаи (юридические документы, художественные книги)
    if book_type in ["legal", "artistic"]:
        if quality_score < 0.95:
            return True
    
    # 3. Критически низкое качество
    if quality_score < 0.70:
        return True
    
    return False

