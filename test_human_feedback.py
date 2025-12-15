#!/usr/bin/env python3
"""
Скрипт для быстрого тестирования системы Human Feedback.
Находит переведенные PDF и запускает веб-интерфейс.
"""

import sys
from pathlib import Path

# Исправление кодировки для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def find_translated_pdfs():
    """Находит переведенные PDF в проекте."""
    pdfs = []
    
    # Ищем в output/
    output_dir = Path("output")
    if output_dir.exists():
        for book_dir in output_dir.iterdir():
            if book_dir.is_dir():
                pdf_path = book_dir / "book_ru.pdf"
                if pdf_path.exists():
                    # Ищем оригинал
                    original = None
                    for orig_file in ["book.pdf", "book_en.pdf", "original.pdf"]:
                        orig_path = book_dir / orig_file
                        if orig_path.exists():
                            original = str(orig_path)
                            break
                    
                    pdfs.append({
                        "translated": str(pdf_path),
                        "original": original,
                        "book_id": book_dir.name
                    })
    
    return pdfs


def main():
    print("=" * 60)
    print("🔍 Поиск переведенных PDF для тестирования")
    print("=" * 60)
    print()
    
    pdfs = find_translated_pdfs()
    
    if not pdfs:
        print("❌ Не найдено переведенных PDF в output/")
        print()
        print("💡 Сначала запустите перевод:")
        print("   python run_pipeline.py --source test_pdfs/Book1.pdf --mode fast")
        print()
        return 1
    
    print(f"✅ Найдено {len(pdfs)} переведенных PDF:")
    print()
    
    for i, pdf_info in enumerate(pdfs, 1):
        print(f"{i}. {pdf_info['book_id']}")
        print(f"   Перевод: {pdf_info['translated']}")
        if pdf_info['original']:
            print(f"   Оригинал: {pdf_info['original']}")
        print()
    
    # Выбираем первый PDF для тестирования
    if pdfs:
        test_pdf = pdfs[0]
        print("=" * 60)
        print("🚀 Запуск веб-интерфейса для тестирования")
        print("=" * 60)
        print()
        print(f"📄 Тестируем: {test_pdf['book_id']}")
        print()
        print("1. Запустите веб-интерфейс:")
        print("   cd tools/human_feedback_interface")
        print("   python app.py")
        print()
        print("2. Откройте в браузере:")
        # Используем прямые слеши для URL
        translated_url = test_pdf['translated'].replace('\\', '/')
        if test_pdf['original']:
            original_url = test_pdf['original'].replace('\\', '/')
            print(f"   http://localhost:5000/feedback?book={translated_url}&page=1&original={original_url}")
        else:
            print(f"   http://localhost:5000/feedback?book={translated_url}&page=1")
        print()
        print("3. Оцените несколько страниц (минимум 3-5 для теста)")
        print()
        print("4. После оценки запустите обучение:")
        print("   python tools/train_human_like_model.py --user test_user")
        print()
        print("5. Используйте в пайплайне:")
        print("   $env:USE_HUMAN_LIKE_EVALUATION='1'")
        print("   $env:HUMAN_MODEL_USER='test_user'")
        print("   python run_pipeline.py --source test_pdfs/Book1.pdf --mode fast")
        print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

