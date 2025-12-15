"""
Модуль для человеческих метрик качества.
Оценка "как человек" вместо "как машина".
"""

from typing import Dict, Any, List, Optional
import fitz  # PyMuPDF
from pathlib import Path
import json


class HumanLikeQualityAssessor:
    """Оценка качества перевода как человек."""
    
    def __init__(self, user_preferences: Optional[Dict[str, Any]] = None):
        self.user_preferences = user_preferences or {}
        self.perceptual_models = self._load_perceptual_models()
    
    def _load_perceptual_models(self) -> Dict[str, Any]:
        """Загружает обученные модели восприятия."""
        # Пока заглушка, позже загрузим реальные модели
        return {
            "visual_harmony": None,
            "text_flow": None,
            "element_balance": None,
            "semantic_coherence": None
        }
    
    def assess_page(
        self,
        original_page: fitz.Page,
        translated_page: fitz.Page
    ) -> Dict[str, Any]:
        """
        Оценка страницы "как человек".
        
        Args:
            original_page: оригинальная страница PyMuPDF
            translated_page: переведенная страница PyMuPDF
        
        Returns:
            Словарь с оценками
        """
        scores = {
            "visual_harmony": self.assess_visual_harmony(original_page, translated_page),
            "text_flow_naturalness": self.assess_text_flow(translated_page),
            "element_balance": self.assess_element_balance(translated_page),
            "semantic_coherence": self.assess_semantic_coherence(translated_page)
        }
        
        # Комплексная оценка (как у человека)
        overall_score = self._human_decision_model(scores)
        
        return {
            "overall_score": overall_score,
            "detailed_scores": scores,
            "human_like_recommendation": self.generate_recommendation(overall_score)
        }
    
    def assess_visual_harmony(
        self,
        original_page: fitz.Page,
        translated_page: fitz.Page
    ) -> float:
        """Оценивает визуальную гармонию (0.0-1.0)."""
        try:
            # Упрощенная оценка: сравниваем общую структуру
            orig_blocks = original_page.get_text("dict").get("blocks", [])
            trans_blocks = translated_page.get_text("dict").get("blocks", [])
            
            # Проверяем сохранение пропорций
            orig_ratio = len(orig_blocks) / max(1, len(trans_blocks))
            if 0.7 <= orig_ratio <= 1.3:
                harmony_score = 0.8
            elif 0.5 <= orig_ratio <= 1.5:
                harmony_score = 0.6
            else:
                harmony_score = 0.4
            
            return harmony_score
        except Exception:
            return 0.5
    
    def assess_text_flow(self, translated_page: fitz.Page) -> float:
        """Оценивает естественность текстового потока (0.0-1.0)."""
        try:
            text = translated_page.get_text()
            
            # Проверяем наличие разрывов строк в неподходящих местах
            bad_breaks = text.count("-\n")  # Переносы с дефисом
            total_lines = text.count("\n")
            
            if total_lines == 0:
                return 1.0
            
            break_ratio = bad_breaks / total_lines
            if break_ratio < 0.05:
                return 0.9
            elif break_ratio < 0.1:
                return 0.7
            else:
                return 0.5
        except Exception:
            return 0.5
    
    def assess_element_balance(self, translated_page: fitz.Page) -> float:
        """Оценивает баланс элементов (0.0-1.0)."""
        try:
            blocks = translated_page.get_text("dict").get("blocks", [])
            if not blocks:
                return 0.5
            
            # Проверяем распределение элементов по странице
            y_positions = []
            for block in blocks:
                bbox = block.get("bbox", [0, 0, 0, 0])
                y_positions.append((bbox[1] + bbox[3]) / 2)
            
            if not y_positions:
                return 0.5
            
            # Проверяем равномерность распределения
            y_positions.sort()
            gaps = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions)-1)]
            
            if not gaps:
                return 0.8
            
            avg_gap = sum(gaps) / len(gaps)
            max_gap = max(gaps)
            
            # Если есть очень большие пробелы - плохой баланс
            if max_gap > avg_gap * 3:
                return 0.4
            elif max_gap > avg_gap * 2:
                return 0.6
            else:
                return 0.8
        except Exception:
            return 0.5
    
    def assess_semantic_coherence(self, translated_page: fitz.Page) -> float:
        """Оценивает семантическую связность (0.0-1.0)."""
        try:
            text = translated_page.get_text()
            
            # Проверяем наличие заголовков и параграфов
            # Упрощенная проверка: ищем короткие строки (возможные заголовки)
            lines = text.split("\n")
            short_lines = [l for l in lines if 5 <= len(l.strip()) <= 80]
            
            # Если есть заголовки и параграфы - хорошая связность
            if len(short_lines) > 0 and len(lines) > len(short_lines):
                return 0.8
            elif len(lines) > 5:
                return 0.6
            else:
                return 0.4
        except Exception:
            return 0.5
    
    def _human_decision_model(self, scores: Dict[str, float]) -> float:
        """
        Принимает решение как человек на основе детальных оценок.
        
        Args:
            scores: словарь с детальными оценками
        
        Returns:
            Общая оценка от 0.0 до 10.0
        """
        # Взвешенная сумма (как человек оценивает)
        weights = {
            "visual_harmony": 0.3,
            "text_flow_naturalness": 0.3,
            "element_balance": 0.2,
            "semantic_coherence": 0.2
        }
        
        overall = sum(scores.get(key, 0.5) * weight for key, weight in weights.items())
        
        # Преобразуем в шкалу 0-10
        return overall * 10.0
    
    def generate_recommendation(self, score: float) -> str:
        """
        Генерирует рекомендацию на основе оценки.
        
        Args:
            score: общая оценка от 0.0 до 10.0
        
        Returns:
            Текстовая рекомендация
        """
        if score >= 9.0:
            return "✅ Идеально - можно публиковать"
        elif score >= 7.5:
            return "🟡 Хорошо - небольшие правки для 10% страниц"
        elif score >= 6.0:
            return "🟠 Удовлетворительно - требуется ручная правка 30% страниц"
        else:
            return "🔴 Плохо - переделать с другим алгоритмом"
    
    def calibrate_to_user(self, user_preferences: Dict[str, Any]) -> None:
        """
        Калибрует модель под предпочтения пользователя.
        
        Args:
            user_preferences: словарь с предпочтениями пользователя
        """
        self.user_preferences = user_preferences
        # Здесь можно загрузить обученную модель для конкретного пользователя

