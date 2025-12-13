# [PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

Полный список внедренных техник из "Ссылки на статьи2.md.txt"

## ✅ Внедренные техники

### 1. ✅ PyMuPDF Deep Layout Manipulation
**Модуль**: `core_engine/export/pdf_rebuilder.py`

**Что делает**:
- Точная замена текста с сохранением шрифтов, размеров и позиций
- Использует `page.add_redact_annot()` и `page.apply_redactions()`
- Точная вставка через `page.insert_text()` с сохранением fontsize и fontname

**Использование**:
```bash
$env:PDF_REBUILD="1"
python run_pipeline.py --source "book.pdf" --mode fast
```

**Ключевые функции**:
- `rebuild_pdf_with_translations()` - основной метод пересборки PDF
- `adjust_fontsize_for_overflow()` - автоматическое сжатие шрифта при переполнении
- `calculate_text_width()` - вычисление ширины текста

---

### 2. ✅ pdf2docx интеграция
**Модуль**: `core_engine/export/pdf2docx_bridge.py`

**Что делает**:
- Идеальное сохранение таблиц при PDF→DOCX→PDF
- Автоопределение merged cells
- Сохранение стилей таблиц

**Использование**:
```python
from core_engine.export.pdf2docx_bridge import convert_pdf_to_docx_via_pdf2docx
convert_pdf_to_docx_via_pdf2docx("input.pdf", "output.docx", start_page=1, end_page=100)
```

**Требования**: `pip install pdf2docx`

---

### 3. ✅ Обработка длинного русского текста
**Модуль**: `core_engine/export/pdf_rebuilder.py` (функция `adjust_fontsize_for_overflow`)

**Что делает**:
- Автоматическое сжатие шрифта при переполнении без сдвига верстки
- Формула: `scale = rect.width / new_text_width`
- Минимальный размер шрифта: 6pt

**Алгоритм**:
```python
if new_text_width > rect.width:
    scale = rect.width / new_text_width
    fontsize *= scale
```

---

### 4. ✅ LaTeX в PDF: Mathpix + PyMuPDF
**Модуль**: `core_engine/export/latex_formulas.py`

**Что делает**:
- Рендеринг LaTeX формул в изображения
- Вставка в исходные координаты PDF
- Fallback на локальный рендерер (matplotlib)

**Использование**:
```python
from core_engine.export.latex_formulas import render_latex_to_image, insert_formula_image_in_pdf

# Рендерим формулу
formula_image = render_latex_to_image("E = mc^2", dpi=200)

# Вставляем в PDF
insert_formula_image_in_pdf(page, rect, formula_image)
```

**Требования**: 
- Mathpix API (опционально): `MATHPIX_APP_ID`, `MATHPIX_APP_KEY`
- matplotlib для fallback: `pip install matplotlib`

---

### 5. ✅ Пакетная обработка с чекпоинтами
**Модуль**: `core_engine/export/parallel_pdf_processor.py`

**Что делает**:
- Многопоточная обработка страниц (ThreadPoolExecutor)
- Автосохранение каждые 10 страниц
- Восстановление после падения

**Использование**:
```python
from core_engine.export.parallel_pdf_processor import process_pages_parallel
from pathlib import Path

def process_page(page_num):
    # Ваша логика обработки страницы
    return {"page": page_num, "result": "..."}

results = process_pages_parallel(
    total_pages=300,
    process_page_fn=process_page,
    book_id="book123",
    checkpoint_dir=Path("checkpoints"),
    max_workers=4,
    checkpoint_interval=10
)
```

---

### 6. ✅ Сжатие PDF после перевода
**Модуль**: `core_engine/export/pdf_rebuilder.py` (функция `compress_pdf`)

**Что делает**:
- Сжатие без потерь: `garbage=4, deflate=True, clean=True`
- Критично для русского текста (увеличивает размер на 25-40%)

**Использование**:
```python
from core_engine.export.pdf_rebuilder import compress_pdf
compress_pdf("input.pdf", "output_compressed.pdf")
```

**Автоматически**: включается при `PDF_REBUILD=1` и `PDF_COMPRESS=1`

---

### 7. ✅ OCR для картинок с текстом
**Модуль**: `core_engine/export/ocr_images.py`

**Что делает**:
- Извлечение всех изображений из PDF
- OCR через Tesseract с русской моделью
- Возврат текста с координатами для замены

**Использование**:
```python
from core_engine.export.ocr_images import extract_and_ocr_images_from_pdf

results = extract_and_ocr_images_from_pdf("book.pdf", page_num=5, languages="eng+rus")
for result in results:
    print(f"Text at {result['bbox']}: {result['ocr_text']}")
```

**Требования**: 
- Tesseract OCR: `pip install pytesseract`
- Tesseract binary: https://github.com/tesseract-ocr/tesseract

**Параметры OCR**:
- `--oem 1` - LSTM только
- `--psm 6` - единый блок текста
- `-l eng+rus` - смешанные языки

---

### 8. ✅ Векторная графика с текстом
**Модуль**: `core_engine/export/vector_graphics.py`

**Что делает**:
- Извлечение векторных объектов (SVG-диаграммы)
- Замена текста в путях без изменения геометрии
- Сохранение структуры векторной графики

**Использование**:
```python
from core_engine.export.vector_graphics import extract_vector_graphics_with_text, translate_vector_graphics

# Извлекаем векторные объекты
vector_objs = extract_vector_graphics_with_text(page)

# Переводим текст
translated = translate_vector_graphics(vector_objs, translate_fn=lambda t: translate(t))
```

---

### 9. ✅ PDFMathTranslate Full Workflow
**Интегрировано в пайплайн**:
- Автоопределение формул (уже реализовано)
- Сохранение формул без перевода (уже реализовано)
- Восстановление layout через Layout API (уже реализовано)

**Дополнительно**: можно использовать LaTeX рендеринг через `latex_formulas.py`

---

### 10. ✅ Nayana Foundation: Multilingual Typesetting
**Модуль**: `core_engine/export/nayana_kerning.py`

**Что делает**:
- Алгоритм перерасчёта кернинга для кириллицы
- Автоматическая коррекция размера шрифта
- Учет разницы в ширине символов (английский vs кириллица)

**Использование**:
```python
from core_engine.export.nayana_kerning import adjust_kerning, calculate_text_position_adjustment

# Корректируем кернинг
adjusted_font_size, width_ratio = adjust_kerning(
    "English text",
    "Русский текст",
    original_font_size=12.0
)

# Полная коррекция позиции
adjustment = calculate_text_position_adjustment(
    original_rect_width=100.0,
    original_text="English",
    translated_text="Русский",
    font_size=12.0
)
```

**Интегрировано**: автоматически используется в `pdf_rebuilder.py`

---

## 🚀 Переменные окружения для Expert Mode

```bash
# PyMuPDF Deep Layout Manipulation
$env:PDF_REBUILD="1"              # Использовать точную замену текста
$env:PDF_COMPRESS="1"             # Сжимать PDF после перевода

# Параллельная обработка
$env:PARALLEL_PROCESSING="1"      # Включить параллельную обработку
$env:MAX_WORKERS="4"              # Количество потоков
$env:CHECKPOINT_INTERVAL="10"     # Сохранять чекпоинт каждые N страниц

# OCR для изображений
$env:OCR_IMAGES="1"               # OCR текста на изображениях
$env:OCR_LANGUAGES="eng+rus"      # Языки для OCR

# LaTeX формулы
$env:MATHPIX_APP_ID="your_id"     # Mathpix API (опционально)
$env:MATHPIX_APP_KEY="your_key"   # Mathpix API key

# Векторная графика
$env:PROCESS_VECTOR_GRAPHICS="1"  # Обрабатывать векторную графику
```

---

## 📊 Примеры использования

### Базовый Expert Mode
```bash
$env:PDF_REBUILD="1"
$env:PDF_COMPRESS="1"
python run_pipeline.py --source "book.pdf" --mode fast
```

### С параллельной обработкой
```bash
$env:PDF_REBUILD="1"
$env:PARALLEL_PROCESSING="1"
$env:MAX_WORKERS="4"
python run_pipeline.py --source "large_book.pdf" --mode fast
```

### С OCR для изображений
```bash
$env:PDF_REBUILD="1"
$env:OCR_IMAGES="1"
$env:OCR_LANGUAGES="eng+rus"
python run_pipeline.py --source "book_with_images.pdf" --mode fast
```

---

## 🎯 Итоговый статус

**Все 10 техник из "Ссылки на статьи2.md.txt" внедрены и готовы к использованию!**

- ✅ PyMuPDF Deep Layout Manipulation
- ✅ pdf2docx интеграция
- ✅ Обработка длинного русского текста
- ✅ LaTeX в PDF (Mathpix + PyMuPDF)
- ✅ Пакетная обработка с чекпоинтами
- ✅ Сжатие PDF после перевода
- ✅ OCR для картинок с текстом
- ✅ Векторная графика с текстом
- ✅ PDFMathTranslate workflow (интегрировано)
- ✅ Nayana Foundation: Multilingual Typesetting

**Пайплайн готов к production использованию на финальной стадии!**

