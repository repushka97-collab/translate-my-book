#!/usr/bin/env python3
"""
Скрипт для обучения персональной модели качества на основе обратной связи пользователя.
"""

import sys
import argparse
from pathlib import Path

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

from core_engine.learning.human_feedback_collector import HumanFeedbackCollector
from core_engine.learning.quality_model_trainer import QualityModelTrainer


def main():
    parser = argparse.ArgumentParser(
        description="Обучить персональную модель качества на основе обратной связи"
    )
    parser.add_argument(
        "--user",
        type=str,
        required=True,
        help="Имя пользователя"
    )
    parser.add_argument(
        "--feedback-dir",
        type=str,
        default="human_feedback",
        help="Директория с обратной связью"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="models/quality",
        help="Директория для сохранения модели"
    )
    parser.add_argument(
        "--model-type",
        type=str,
        default="simple_regression",
        choices=["simple_regression"],
        help="Тип модели"
    )
    
    args = parser.parse_args()
    
    # Загружаем обратную связь пользователя
    collector = HumanFeedbackCollector(feedback_dir=args.feedback_dir)
    feedback_data = collector.load_user_feedback(args.user)
    
    if not feedback_data:
        print(f"[ERROR] Нет данных обратной связи для пользователя '{args.user}'")
        print(f"       Сначала соберите обратную связь через интерфейс:")
        print(f"       python tools/human_feedback_interface/app.py")
        return 1
    
    print(f"[INFO] Загружено {len(feedback_data)} примеров обратной связи для '{args.user}'")
    
    # Обучаем модель
    trainer = QualityModelTrainer(models_dir=args.output)
    
    try:
        model_path = trainer.train_user_model(
            user_name=args.user,
            feedback_data=feedback_data,
            model_type=args.model_type
        )
        
        print(f"[SUCCESS] Модель обучена и сохранена: {model_path}")
        print(f"         Теперь можно использовать в пайплайне:")
        print(f"         USE_HUMAN_LIKE_EVALUATION=1")
        print(f"         HUMAN_MODEL_USER={args.user}")
        
        return 0
    except Exception as e:
        print(f"[ERROR] Ошибка при обучении модели: {e}")
        return 1


if __name__ == "__main__":
    # Исправление кодировки для Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    
    sys.exit(main())

