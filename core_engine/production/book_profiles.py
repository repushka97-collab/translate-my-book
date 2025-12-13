# core_engine/production/book_profiles.py
"""
[PRODUCTION MODE] Type-Specific Optimization Profiles.
Готовые профили для разных типов книг.
"""

from typing import Dict, Any, Optional


BOOK_PROFILES = {
    "fiction": {
        "text_overflow_tolerance": 8,  # можно чуть вылезать
        "image_priority": "high",      # картинки критичны
        "font_compensation": 0.92,     # сжатие шрифта на 8%
        "quality_threshold": 0.94,
        "formula_handling": "skip",    # формулы не критичны
        "table_preservation": "flexible"
    },
    "textbook": {
        "text_overflow_tolerance": 2,  # строгое ограничение
        "formula_handling": "mathpix", # приоритет формул
        "table_preservation": "strict",# таблицы должны быть идеальны
        "quality_threshold": 0.97,
        "font_compensation": 0.90,     # более агрессивное сжатие
        "image_priority": "medium"
    },
    "magazine": {
        "color_preservation": True,    # сохранение цветовых профилей
        "image_quality": 0.95,         # качество изображений
        "layout_flexibility": 0.85,    # можно менять отступы
        "quality_threshold": 0.92,
        "text_overflow_tolerance": 5,
        "font_compensation": 0.93
    },
    "technical": {
        "code_preservation": True,     # сохранение форматирования кода
        "diagram_priority": "high",    # схемы важнее текста
        "font_monospace": "FiraCode",  # моноширинный шрифт
        "quality_threshold": 0.95,
        "text_overflow_tolerance": 3,
        "table_preservation": "strict"
    }
}


def detect_book_type(pdf_path: str) -> str:
    """
    Автоматически определяет тип книги по содержимому.
    
    Args:
        pdf_path: путь к PDF файлу
    
    Returns:
        Тип книги: "fiction", "textbook", "magazine", "technical"
    """
    try:
        import fitz
        
        doc = fitz.open(pdf_path)
        
        # Анализируем первые 10 страниц
        text_samples = []
        formula_count = 0
        table_count = 0
        image_count = 0
        
        for page_num in range(min(10, len(doc))):
            page = doc[page_num]
            text = page.get_text()
            text_samples.append(text)
            
            # Подсчитываем формулы (упрощенно - ищем математические символы)
            if any(sym in text for sym in ["∑", "∫", "√", "∂", "∇", "="]):
                formula_count += 1
            
            # Подсчитываем таблицы
            tables = page.find_tables()
            table_count += len(tables)
            
            # Подсчитываем изображения
            images = page.get_images()
            image_count += len(images)
        
        doc.close()
        
        # Эвристики для определения типа
        full_text = " ".join(text_samples).lower()
        
        # Учебник: много формул и таблиц
        if formula_count > 3 or table_count > 5:
            return "textbook"
        
        # Техническая документация: код, схемы
        if any(keyword in full_text for keyword in ["function", "class", "def ", "import ", "api", "endpoint"]):
            return "technical"
        
        # Журнал: много изображений
        if image_count > 20:
            return "magazine"
        
        # Художественная литература: по умолчанию
        return "fiction"
        
    except Exception:
        return "fiction"  # По умолчанию


def get_book_profile(book_type: Optional[str] = None, pdf_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Получает профиль для книги.
    
    Args:
        book_type: тип книги (если известен)
        pdf_path: путь к PDF (для автоматического определения)
    
    Returns:
        Профиль книги
    """
    if not book_type and pdf_path:
        book_type = detect_book_type(pdf_path)
    
    if not book_type:
        book_type = "fiction"  # По умолчанию
    
    return BOOK_PROFILES.get(book_type, BOOK_PROFILES["fiction"])


def apply_profile(book_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Применяет профиль книги к конфигурации.
    
    Args:
        book_type: тип книги
        config: текущая конфигурация
    
    Returns:
        Обновленная конфигурация
    """
    profile = get_book_profile(book_type)
    
    # Обновляем конфигурацию
    updated_config = config.copy()
    
    # Применяем настройки профиля
    if "text_overflow_tolerance" in profile:
        updated_config["max_text_overflow"] = profile["text_overflow_tolerance"]
    
    if "font_compensation" in profile:
        updated_config["font_compensation_factor"] = profile["font_compensation"]
    
    if "quality_threshold" in profile:
        updated_config["quality_threshold"] = profile["quality_threshold"]
    
    if "formula_handling" in profile:
        updated_config["formula_handling"] = profile["formula_handling"]
    
    if "table_preservation" in profile:
        updated_config["table_preservation"] = profile["table_preservation"]
    
    return updated_config

