#!/usr/bin/env python3
"""
Инструмент для ручного сравнения оригинальных и переведенных PDF.
Открывает оба PDF рядом для визуального сравнения.
"""

import sys
import os
from pathlib import Path
import subprocess
import webbrowser
import tempfile

# Исправление кодировки для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


def find_pdf_pairs():
    """Находит пары оригинал-перевод в output/."""
    pairs = []
    output_dir = Path("output")
    
    if not output_dir.exists():
        return pairs
    
    for book_dir in output_dir.iterdir():
        if not book_dir.is_dir():
            continue
        
        translated_pdf = book_dir / "book_ru.pdf"
        if not translated_pdf.exists():
            continue
        
        # Ищем оригинал
        original_pdf = None
        # В library
        library_dir = Path("library") / book_dir.name
        if library_dir.exists():
            orig = library_dir / "original.pdf"
            if orig.exists():
                original_pdf = orig
        
        # В исходных директориях
        if not original_pdf:
            for search_dir in [Path("For test"), Path("ingest")]:
                for pdf_file in search_dir.glob("*.pdf"):
                    # Проверяем по размеру или имени
                    if pdf_file.stat().st_size > 0:
                        original_pdf = pdf_file
                        break
                if original_pdf:
                    break
        
        if original_pdf:
            pairs.append({
                "book_id": book_dir.name,
                "original": str(original_pdf),
                "translated": str(translated_pdf),
                "name": book_dir.name
            })
    
    return pairs


def open_pdfs_side_by_side(original_pdf, translated_pdf):
    """Открывает два PDF рядом для сравнения."""
    original_path = Path(original_pdf)
    translated_path = Path(translated_pdf)
    
    if not original_path.exists():
        print(f"❌ Оригинал не найден: {original_path}")
        return False
    
    if not translated_path.exists():
        print(f"❌ Перевод не найден: {translated_path}")
        return False
    
    print(f"📄 Оригинал: {original_path}")
    print(f"📄 Перевод: {translated_path}")
    print()
    
    # Windows: открываем в двух окнах
    if sys.platform == "win32":
        try:
            # Открываем оригинал
            os.startfile(str(original_path))
            print("✅ Оригинал открыт")
            
            # Небольшая задержка
            import time
            time.sleep(1)
            
            # Открываем перевод
            os.startfile(str(translated_path))
            print("✅ Перевод открыт")
            print()
            print("💡 Расположите окна рядом для сравнения")
            return True
        except Exception as e:
            print(f"❌ Ошибка открытия: {e}")
            return False
    
    # Linux/Mac: используем системные команды
    else:
        try:
            # Пробуем разные команды
            commands = [
                ["xdg-open", str(original_path)],  # Linux
                ["open", str(original_path)],       # Mac
            ]
            
            for cmd in commands:
                try:
                    subprocess.Popen(cmd)
                    import time
                    time.sleep(1)
                    break
                except FileNotFoundError:
                    continue
            
            # Открываем перевод
            for cmd in commands:
                try:
                    subprocess.Popen(cmd)
                    break
                except FileNotFoundError:
                    continue
            
            print("✅ PDF открыты")
            return True
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False


def create_comparison_html(original_pdf, translated_pdf, output_html):
    """Создает HTML страницу для сравнения PDF."""
    import fitz  # PyMuPDF
    import base64
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Сравнение PDF</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #f5f5f5;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .comparison {
            display: flex;
            gap: 20px;
            justify-content: center;
        }
        .pdf-container {
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .pdf-container h3 {
            margin-top: 0;
            color: #333;
        }
        .pdf-container img {
            max-width: 100%;
            height: auto;
            border: 1px solid #ddd;
            margin: 10px 0;
        }
        .controls {
            text-align: center;
            margin-top: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            margin: 0 5px;
        }
        button:hover {
            background: #45a049;
        }
        input[type="number"] {
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 60px;
            font-size: 16px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Сравнение PDF: Оригинал vs Перевод</h1>
        <p>Используйте кнопки для навигации по страницам</p>
    </div>
    
    <div class="comparison">
        <div class="pdf-container">
            <h3>Оригинал</h3>
            <div id="original-pages"></div>
        </div>
        <div class="pdf-container">
            <h3>Перевод</h3>
            <div id="translated-pages"></div>
        </div>
    </div>
    
    <div class="controls">
        <button onclick="prevPage()">◀ Предыдущая</button>
        <label>
            Страница: 
            <input type="number" id="page-num" value="1" min="1" onchange="goToPage()">
            <span id="total-pages">/ 1</span>
        </label>
        <button onclick="nextPage()">Следующая ▶</button>
    </div>
    
    <script>
        let currentPage = 1;
        let totalPages = 1;
        let originalPages = [];
        let translatedPages = [];
        
        // Загружаем страницы
        function loadPages() {
            // Здесь будут данные из Python
            originalPages = ORIGINAL_PAGES_DATA;
            translatedPages = TRANSLATED_PAGES_DATA;
            totalPages = Math.max(originalPages.length, translatedPages.length);
            document.getElementById('total-pages').textContent = '/ ' + totalPages;
            showPage(1);
        }
        
        function showPage(pageNum) {
            currentPage = Math.max(1, Math.min(pageNum, totalPages));
            document.getElementById('page-num').value = currentPage;
            
            const origDiv = document.getElementById('original-pages');
            const transDiv = document.getElementById('translated-pages');
            
            if (currentPage <= originalPages.length) {
                origDiv.innerHTML = `<img src="${originalPages[currentPage - 1]}" alt="Page ${currentPage}">`;
            } else {
                origDiv.innerHTML = '<p>Страница не найдена</p>';
            }
            
            if (currentPage <= translatedPages.length) {
                transDiv.innerHTML = `<img src="${translatedPages[currentPage - 1]}" alt="Page ${currentPage}">`;
            } else {
                transDiv.innerHTML = '<p>Страница не найдена</p>';
            }
        }
        
        function prevPage() {
            showPage(currentPage - 1);
        }
        
        function nextPage() {
            showPage(currentPage + 1);
        }
        
        function goToPage() {
            const pageNum = parseInt(document.getElementById('page-num').value);
            showPage(pageNum);
        }
        
        // Загружаем при старте
        loadPages();
    </script>
</body>
</html>"""
    
    # Извлекаем страницы из PDF
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        original_pages_data = []
        translated_pages_data = []
        
        max_pages = min(len(doc_orig), len(doc_trans), 10)  # Первые 10 страниц
        
        for page_num in range(max_pages):
            # Оригинал
            page_orig = doc_orig[page_num]
            pix_orig = page_orig.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes_orig = pix_orig.tobytes("png")
            original_pages_data.append(f"data:image/png;base64,{base64.b64encode(img_bytes_orig).decode('utf-8')}")
            
            # Перевод
            page_trans = doc_trans[page_num]
            pix_trans = page_trans.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes_trans = pix_trans.tobytes("png")
            translated_pages_data.append(f"data:image/png;base64,{base64.b64encode(img_bytes_trans).decode('utf-8')}")
        
        doc_orig.close()
        doc_trans.close()
        
        # Заменяем плейсхолдеры
        html_content = html_content.replace(
            "ORIGINAL_PAGES_DATA",
            str(original_pages_data).replace("'", '"')
        )
        html_content = html_content.replace(
            "TRANSLATED_PAGES_DATA",
            str(translated_pages_data).replace("'", '"')
        )
        
        # Сохраняем HTML
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания HTML: {e}")
        return False


def main():
    print("=" * 80)
    print("📊 ИНСТРУМЕНТ ДЛЯ РУЧНОГО СРАВНЕНИЯ PDF")
    print("=" * 80)
    print()
    
    # Находим пары PDF
    pairs = find_pdf_pairs()
    
    if not pairs:
        print("❌ Не найдено переведенных PDF в output/")
        print()
        print("💡 Сначала запустите перевод:")
        print("   python run_full_test_with_integrations.py")
        return 1
    
    print(f"✅ Найдено {len(pairs)} переведенных PDF:")
    print()
    for i, pair in enumerate(pairs, 1):
        print(f"{i}. {pair['name']}")
        print(f"   Оригинал: {pair['original']}")
        print(f"   Перевод: {pair['translated']}")
    print()
    
    # Выбираем PDF для сравнения
    if len(pairs) == 1:
        selected = pairs[0]
        print(f"📄 Выбран: {selected['name']}")
    else:
        try:
            choice = input(f"Выберите PDF для сравнения (1-{len(pairs)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(pairs):
                selected = pairs[idx]
            else:
                print("❌ Неверный выбор")
                return 1
        except (ValueError, KeyboardInterrupt):
            print("❌ Отменено")
            return 1
    
    print()
    print("=" * 80)
    print("🔍 ВАРИАНТЫ СРАВНЕНИЯ")
    print("=" * 80)
    print()
    print("1. Открыть PDF в двух окнах (Windows)")
    print("2. Создать HTML страницу для сравнения в браузере")
    print()
    
    try:
        choice = input("Выберите вариант (1 или 2): ").strip()
        
        if choice == "1":
            print()
            print("🔄 Открываю PDF...")
            if open_pdfs_side_by_side(selected['original'], selected['translated']):
                print("✅ PDF открыты! Расположите окна рядом для сравнения")
            else:
                print("❌ Не удалось открыть PDF")
                return 1
        
        elif choice == "2":
            print()
            print("🔄 Создаю HTML страницу...")
            output_html = Path("comparison") / f"{selected['name']}_comparison.html"
            output_html.parent.mkdir(exist_ok=True)
            
            if create_comparison_html(selected['original'], selected['translated'], output_html):
                print(f"✅ HTML создан: {output_html}")
                print("🔄 Открываю в браузере...")
                webbrowser.open(f"file://{output_html.resolve()}")
                print("✅ Открыто в браузере!")
            else:
                print("❌ Не удалось создать HTML")
                return 1
        
        else:
            print("❌ Неверный выбор")
            return 1
    
    except KeyboardInterrupt:
        print("\n❌ Отменено")
        return 1
    
    print()
    print("=" * 80)
    print("✅ ГОТОВО")
    print("=" * 80)
    print()
    print("💡 Для оценки качества используйте веб-интерфейс:")
    print("   cd tools/human_feedback_interface")
    print("   python app.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

