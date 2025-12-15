"""
Модуль для обучения модели качества на основе человеческой обратной связи.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
import pickle


class QualityModelTrainer:
    """Обучает модель качества на основе обратной связи пользователя."""
    
    def __init__(self, models_dir: str = "models/quality"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
    
    def train_user_model(
        self,
        user_name: str,
        feedback_data: List[Dict[str, Any]],
        model_type: str = "simple_regression"
    ) -> str:
        """
        Обучает модель для конкретного пользователя.
        
        Args:
            user_name: имя пользователя
            feedback_data: список обратных связей
            model_type: тип модели ("simple_regression", "neural_network", etc.)
        
        Returns:
            Путь к сохраненной модели
        """
        if not feedback_data:
            raise ValueError(f"No feedback data for user {user_name}")
        
        # Извлекаем признаки из обратной связи
        features = []
        labels = []
        
        for feedback in feedback_data:
            # Признаки: метрики страницы
            feature_vector = self._extract_features(feedback)
            features.append(feature_vector)
            
            # Метка: оценка пользователя
            label = feedback.get("visual_score", 5.0)
            labels.append(label)
        
        # Обучаем модель (упрощенная версия)
        if model_type == "simple_regression":
            model = self._train_simple_regression(features, labels)
        else:
            raise ValueError(f"Unknown model type: {model_type}")
        
        # Сохраняем модель
        model_path = self.models_dir / f"{user_name}_quality_model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
        
        print(f"[QualityModel] Trained model for {user_name}: {model_path}")
        return str(model_path)
    
    def _extract_features(self, feedback: Dict[str, Any]) -> List[float]:
        """
        Извлекает признаки из обратной связи.
        
        Args:
            feedback: словарь с обратной связью
        
        Returns:
            Вектор признаков
        """
        # Упрощенные признаки (можно расширить)
        features = [
            len(feedback.get("problem_areas", [])),  # Количество проблемных областей
            len(feedback.get("semantic_issues", [])),  # Количество семантических проблем
            len(feedback.get("comment", "")),  # Длина комментария (индикатор проблем)
        ]
        
        # Добавляем признаки из problem_areas
        problem_areas = feedback.get("problem_areas", [])
        if problem_areas:
            # Средняя серьезность проблем
            severities = {"low": 1, "medium": 2, "high": 3}
            avg_severity = sum(severities.get(area.get("severity", "medium"), 2) 
                             for area in problem_areas) / len(problem_areas)
            features.append(avg_severity)
        else:
            features.append(0.0)
        
        return features
    
    def _train_simple_regression(
        self,
        features: List[List[float]],
        labels: List[float]
    ) -> Dict[str, Any]:
        """
        Обучает простую модель регрессии.
        
        Args:
            features: список векторов признаков
            labels: список меток (оценок)
        
        Returns:
            Обученная модель (словарь с коэффициентами)
        """
        # Упрощенная линейная регрессия
        # В реальности можно использовать sklearn, torch, etc.
        
        # Простое среднее взвешенное
        if not features or not labels:
            return {"type": "constant", "value": 5.0}
        
        # Вычисляем средние веса для каждого признака
        num_features = len(features[0])
        weights = [0.0] * num_features
        
        # Упрощенный алгоритм: корреляция признаков с метками
        for i in range(num_features):
            feature_values = [f[i] for f in features]
            # Простая корреляция
            if len(set(feature_values)) > 1:
                # Нормализуем
                max_val = max(feature_values)
                min_val = min(feature_values)
                if max_val > min_val:
                    normalized = [(v - min_val) / (max_val - min_val) for v in feature_values]
                    # Корреляция с метками
                    correlation = sum(n * l for n, l in zip(normalized, labels)) / len(labels)
                    weights[i] = correlation / 10.0  # Нормализуем к шкале 0-1
                else:
                    weights[i] = 0.0
            else:
                weights[i] = 0.0
        
        # Базовое значение
        bias = (sum(labels) / len(labels)) / 10.0
        
        return {
            "type": "linear_regression",
            "weights": weights,
            "bias": bias,
            "num_features": num_features
        }
    
    def predict(
        self,
        model_path: str,
        features: List[float]
    ) -> float:
        """
        Предсказывает оценку на основе признаков.
        
        Args:
            model_path: путь к модели
            features: вектор признаков
        
        Returns:
            Предсказанная оценка от 0.0 до 10.0
        """
        with open(model_path, "rb") as f:
            model = pickle.load(f)
        
        if model["type"] == "constant":
            return model["value"]
        elif model["type"] == "linear_regression":
            # Линейная комбинация
            prediction = model["bias"]
            for i, weight in enumerate(model["weights"]):
                if i < len(features):
                    prediction += weight * features[i]
            
            # Ограничиваем диапазон 0-10
            return max(0.0, min(10.0, prediction * 10.0))
        else:
            raise ValueError(f"Unknown model type: {model['type']}")


def load_user_model(user_name: str, models_dir: str = "models/quality") -> Optional[str]:
    """
    Загружает модель пользователя.
    
    Args:
        user_name: имя пользователя
        models_dir: директория с моделями
    
    Returns:
        Путь к модели или None если не найдена
    """
    model_path = Path(models_dir) / f"{user_name}_quality_model.pkl"
    if model_path.exists():
        return str(model_path)
    return None

