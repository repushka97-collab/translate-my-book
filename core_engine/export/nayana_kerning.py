"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

Nayana Foundation: Multilingual Typesetting - алгоритм перерасчёта кернинга для кириллицы.
Основано на: https://github.com/pymupdf/Nayana/blob/main/nayana/typesetter.py
"""

from __future__ import annotations

from typing import Tuple


def adjust_kerning(
    original_text: str,
    translated_text: str,
    original_font_size: float
) -> Tuple[float, float]:
    """
    Алгоритм перерасчёта кернинга для кириллицы.
    
    Возвращает скорректированные отступы для точного позиционирования.
    
    Args:
        original_text: оригинальный текст (английский)
        translated_text: переведенный текст (русский)
        original_font_size: оригинальный размер шрифта
    
    Returns:
        Tuple[adjusted_font_size, width_scale_factor]
    """
    # Эмпирические коэффициенты для кириллицы
    # Русский текст в среднем на 20-30% длиннее английского
    # Но кириллические символы могут быть шире
    
    # Средняя ширина символа (относительно font_size)
    avg_char_width_en = 0.6  # английский
    avg_char_width_ru = 0.65  # кириллица (немного шире)
    
    # Вычисляем ожидаемую ширину
    original_width = len(original_text) * original_font_size * avg_char_width_en
    translated_width = len(translated_text) * original_font_size * avg_char_width_ru
    
    # Коэффициент масштабирования
    if original_width > 0:
        width_ratio = translated_width / original_width
    else:
        width_ratio = 1.0
    
    # Если текст стал длиннее - уменьшаем шрифт
    if width_ratio > 1.0:
        # Ограничиваем уменьшение до 70% от оригинала
        scale_factor = min(1.0 / width_ratio, 0.7)
        adjusted_font_size = original_font_size * scale_factor
    else:
        adjusted_font_size = original_font_size
    
    return adjusted_font_size, width_ratio


def calculate_text_position_adjustment(
    original_rect_width: float,
    original_text: str,
    translated_text: str,
    font_size: float
) -> dict:
    """
    Вычисляет корректировки позиции и размера для переведенного текста.
    
    Returns:
        {
            "adjusted_font_size": float,
            "width_scale": float,
            "needs_wrap": bool,
            "line_count": int (если нужен перенос)
        }
    """
    adjusted_font_size, width_ratio = adjust_kerning(original_text, translated_text, font_size)
    
    # Проверяем, нужен ли перенос строк
    char_width = adjusted_font_size * 0.65  # для кириллицы
    text_width = len(translated_text) * char_width
    needs_wrap = text_width > original_rect_width
    
    line_count = 1
    if needs_wrap:
        # Оцениваем количество строк
        line_count = max(1, int(text_width / original_rect_width) + 1)
    
    return {
        "adjusted_font_size": adjusted_font_size,
        "width_scale": width_ratio,
        "needs_wrap": needs_wrap,
        "line_count": line_count,
    }

