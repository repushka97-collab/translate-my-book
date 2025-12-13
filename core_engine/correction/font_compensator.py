# core_engine/correction/font_compensator.py
"""
[ADVANCED PDF TRANSLATION MODE] Font Metric Compensation System.
Динамическая коррекция кернинга и трекинга для кириллицы.
"""

import os
from typing import Dict, Any, Optional
from pathlib import Path


class FontMetricsCompensator:
    """
    Компенсация метрик шрифта для кириллицы.
    """
    
    def __init__(
        self,
        source_lang: str = "en",
        target_lang: str = "ru",
        max_width_change: float = 1.3
    ):
        """
        Args:
            source_lang: исходный язык
            target_lang: целевой язык
            max_width_change: максимальное увеличение ширины (1.3 = 30%)
        """
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.max_width_change = max_width_change
        
        # Коэффициенты расширения для разных языков
        self.width_factors = {
            ("en", "ru"): 1.25,  # Русский текст примерно на 25% шире английского
            ("en", "de"): 1.15,
            ("en", "fr"): 1.10,
        }
    
    def calculate(
        self,
        original_text: str,
        translated_text: str,
        font_name: str = "Helvetica",
        font_size: float = 12.0
    ) -> Dict[str, Any]:
        """
        Вычисляет компенсацию метрик шрифта.
        
        Args:
            original_text: оригинальный текст
            translated_text: переведенный текст
            font_name: имя шрифта
            font_size: размер шрифта
        
        Returns:
            Словарь с параметрами компенсации:
            {
                "font_size": float,
                "tracking": int,  # в единицах 1/1000 em
                "width_change": float,
                "kerning_adjustment": float
            }
        """
        try:
            # Вычисляем изменение ширины
            width_factor = self.width_factors.get(
                (self.source_lang, self.target_lang),
                1.2  # По умолчанию 20% увеличение
            )
            
            # Упрощенная оценка ширины текста
            # В реальности нужно использовать font metrics
            original_length = len(original_text)
            translated_length = len(translated_text)
            
            # Приблизительное изменение ширины
            length_ratio = translated_length / original_length if original_length > 0 else 1.0
            width_change = length_ratio * width_factor
            
            # Если изменение слишком большое, применяем компенсацию
            compensation = {
                "font_size": font_size,
                "tracking": 0,
                "width_change": width_change,
                "kerning_adjustment": 0.0
            }
            
            if width_change > self.max_width_change:
                # Уменьшаем размер шрифта
                scale_factor = self.max_width_change / width_change
                compensation["font_size"] = font_size * scale_factor
                
                # Применяем отрицательный tracking (сжатие)
                compensation["tracking"] = int((1 - scale_factor) * 100)  # в 1/1000 em
                
                # Корректируем кернинг
                compensation["kerning_adjustment"] = (1 - scale_factor) * 0.1
            
            return compensation
            
        except Exception as e:
            error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write(f"[FontCompensator] Error: {e}\n")
            return {
                "font_size": font_size,
                "tracking": 0,
                "width_change": 1.0,
                "kerning_adjustment": 0.0,
                "error": str(e)
            }

