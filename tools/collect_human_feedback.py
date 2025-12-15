#!/usr/bin/env python3
"""
CLI скрипт для сбора человеческой обратной связи.
Альтернатива веб-интерфейсу.
"""

import sys
import argparse
from pathlib import Path

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent))

from core_engine.learning.human_feedback_collector import HumanFeedbackCollector


def main():
    parser = argparse.ArgumentParser(
        description="Собрать человеческую обратную связь для страниц PDF"
    )
    parser.add_argument(
        "--book",
        type=str,
        required=True,
        help="Путь к переведенному PDF"
    )
    parser.add_argument(
        "--original",
        type=str,
        help="Путь к оригинальному PDF (если отличается)"
    )
    parser.add_argument(
        "--pages",
        type=str,
        required=True,
        help="Номера страниц через запятую (например: 1,5,10,15,20)"
    )
    parser.add_argument(
        "--user",
        type=str,
        default="default",
        help="Имя пользователя"
    )
    
    args = parser.parse_args()
    
    # Парсим страницы
    try:
        page_numbers = [int(p.strip()) for p in args.pages.split(",")]
    except ValueError:
        print("[ERROR] Неверный формат страниц. Используйте: 1,5,10,15,20")
        return 1
    
    collector = HumanFeedbackCollector()
    
    print(f"[INFO] Сбор обратной связи для {len(page_numbers)} страниц")
    print(f"       Книга: {args.book}")
    print(f"       Пользователь: {args.user}")
    print()
    
    for page_num in page_numbers:
        print(f"[PAGE {page_num}]")
        
        # Получаем изображения
        try:
            images = collector.get_page_images(
                args.original or args.book,
                args.book,
                page_num
            )
            
            if not images.get("original") or not images.get("translated"):
                print(f"  [WARN] Не удалось загрузить изображения страницы {page_num}")
                continue
            
            # Сохраняем изображения для просмотра
            import base64
            import os
            temp_dir = Path("temp_feedback_images")
            temp_dir.mkdir(exist_ok=True)
            
            orig_img_path = temp_dir / f"page_{page_num}_original.png"
            trans_img_path = temp_dir / f"page_{page_num}_translated.png"
            
            # Декодируем base64 и сохраняем
            orig_data = images["original"].split(",")[1]
            trans_data = images["translated"].split(",")[1]
            
            with open(orig_img_path, "wb") as f:
                f.write(base64.b64decode(orig_data))
            with open(trans_img_path, "wb") as f:
                f.write(base64.b64decode(trans_data))
            
            print(f"  [OK] Изображения сохранены:")
            print(f"       Оригинал: {orig_img_path}")
            print(f"       Перевод: {trans_img_path}")
            print(f"  [INFO] Откройте изображения и оцените качество")
            
            # Запрашиваем оценку
            while True:
                try:
                    score_input = input(f"  Оценка (1-10, или 'skip' для пропуска): ").strip()
                    if score_input.lower() == 'skip':
                        print(f"  [SKIP] Страница {page_num} пропущена")
                        break
                    
                    score = float(score_input)
                    if 1 <= score <= 10:
                        break
                    else:
                        print("  [ERROR] Оценка должна быть от 1 до 10")
                except ValueError:
                    print("  [ERROR] Введите число от 1 до 10 или 'skip'")
            
            if score_input.lower() == 'skip':
                continue
            
            # Запрашиваем комментарий
            comment = input(f"  Комментарий (Enter для пропуска): ").strip()
            
            # Собираем обратную связь
            feedback = collector.collect_feedback(
                original_pdf=args.original or args.book,
                translated_pdf=args.book,
                page_num=page_num,
                user_name=args.user,
                visual_score=int(score),
                comment=comment if comment else None
            )
            
            print(f"  [SUCCESS] Обратная связь сохранена: {feedback}")
            print()
        
        except Exception as e:
            print(f"  [ERROR] Ошибка при обработке страницы {page_num}: {e}")
            continue
    
    print(f"[DONE] Сбор обратной связи завершен")
    print(f"       Для обучения модели запустите:")
    print(f"       python tools/train_human_like_model.py --user {args.user}")
    
    return 0


if __name__ == "__main__":
    # Исправление кодировки для Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    
    sys.exit(main())

