# core_engine/correction/overflow_predictor.py
"""
[ADVANCED PDF TRANSLATION MODE] ML-Based Overflow Predictor.
Предсказывает проблемные места ДО перевода и корректирует параметры.
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import fitz  # PyMuPDF


class OverflowPredictor:
    """
    Предсказатель переполнений текста на основе анализа страницы.
    """
    
    def __init__(self, confidence_threshold: float = 0.85):
        """
        Args:
            confidence_threshold: порог уверенности для предсказаний
        """
        self.confidence_threshold = confidence_threshold
    
    def predict_overflow_risks(
        self,
        page,
        source_lang: str = "en",
        target_lang: str = "ru",
        confidence_threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Предсказывает риски переполнения для страницы.
        
        Args:
            page: страница PDF (fitz.Page)
            source_lang: исходный язык
            target_lang: целевой язык
            confidence_threshold: порог уверенности (опционально)
        
        Returns:
            Словарь с предсказаниями рисков
        """
        if confidence_threshold is None:
            confidence_threshold = self.confidence_threshold
        
        try:
            blocks = page.get_text("dict").get("blocks", [])
            
            risks = {
                "tables": False,
                "headers": False,
                "narrow_columns": False,
                "small_fonts": False,
                "risk_score": 0.0,
                "recommendations": []
            }
            
            # Анализируем блоки на предмет рисков
            for block in blocks:
                if block.get("type") != 0:  # Только текстовые блоки
                    continue
                
                bbox = block.get("bbox", [0, 0, 0, 0])
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                
                text = self._extract_text_from_block(block)
                
                # Проверка на узкие колонки
                if width < 100:  # Очень узкий блок
                    risks["narrow_columns"] = True
                    risks["risk_score"] += 0.2
                    risks["recommendations"].append("Узкая колонка обнаружена - требуется уменьшение размера шрифта")
                
                # Проверка на маленькие шрифты
                spans = []
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        spans.append(span)
                
                if spans:
                    avg_font_size = sum(s.get("size", 12) for s in spans) / len(spans)
                    if avg_font_size < 9:  # Очень маленький шрифт
                        risks["small_fonts"] = True
                        risks["risk_score"] += 0.15
                
                # Проверка на заголовки
                if self._is_heading(text):
                    risks["headers"] = True
                    risks["risk_score"] += 0.1
                    risks["recommendations"].append("Заголовок обнаружен - рекомендуется компенсация")
                
                # Проверка на таблицы (упрощенная)
                if self._looks_like_table(text):
                    risks["tables"] = True
                    risks["risk_score"] += 0.3
                    risks["recommendations"].append("Таблица обнаружена - требуется масштабирование текста в таблицах")
            
            # Нормализуем risk_score
            risks["risk_score"] = min(1.0, risks["risk_score"])
            
            # Определяем, превышен ли порог
            risks["high_risk"] = risks["risk_score"] >= confidence_threshold
            
            return risks
            
        except Exception as e:
            error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write(f"[OverflowPredictor] Error: {e}\n")
            return {
                "tables": False,
                "headers": False,
                "narrow_columns": False,
                "small_fonts": False,
                "risk_score": 0.0,
                "recommendations": [],
                "error": str(e)
            }
    
    def _extract_text_from_block(self, block: Dict[str, Any]) -> str:
        """Извлекает текст из блока."""
        text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text += span.get("text", "")
        return text.strip()
    
    def _is_heading(self, text: str) -> bool:
        """Определяет, является ли текст заголовком."""
        if not text:
            return False
        text_clean = text.strip()
        if len(text_clean) < 100 and (text_clean.isupper() or 
                                       text_clean.startswith(("Chapter", "Part", "Section"))):
            return True
        return False
    
    def _looks_like_table(self, text: str) -> bool:
        """Определяет, похож ли текст на таблицу."""
        if not text:
            return False
        # Много табуляций или разделителей
        return text.count("\t") > 2 or text.count("|") > 2


def adjust_translation_params(
    risk_areas: Dict[str, Any],
    base_params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Корректирует параметры перевода на основе предсказанных рисков.
    
    Args:
        risk_areas: результаты predict_overflow_risks
        base_params: базовые параметры перевода
    
    Returns:
        Скорректированные параметры
    """
    adjusted = base_params.copy()
    
    if risk_areas.get("tables"):
        adjusted["table_scaling"] = 0.95  # Уменьшить размер текста в таблицах на 5%
    
    if risk_areas.get("headers"):
        adjusted["header_compensation"] = True
    
    if risk_areas.get("narrow_columns"):
        adjusted["font_size_reduction"] = 0.9  # Уменьшить размер шрифта на 10%
    
    if risk_areas.get("small_fonts"):
        adjusted["min_font_size"] = 8  # Минимальный размер шрифта
    
    return adjusted

