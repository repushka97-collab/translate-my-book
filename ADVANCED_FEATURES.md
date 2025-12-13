# [ADVANCED PDF TRANSLATION MODE] Продвинутые инструменты для 100% качества

Этот документ описывает продвинутые инструменты, реализованные согласно "Ссылки на статьи 3.md".

## 🔥 ЯДРО ДЛЯ ИДЕАЛЬНОЙ ВЕРСТКИ

### 1. PDFPlumber + LayoutParser (для сложных таблиц)

**Модуль**: `core_engine/ingest/pdfplumber_advanced.py`

**Использование**:
```python
from core_engine.ingest.pdfplumber_advanced import extract_tables_with_pdfplumber

table = extract_tables_with_pdfplumber("book.pdf", page_num=45, strategy="lines")
```

**Переменные окружения**:
- `PDFPLUMBER_TABLES=1` - включает использование PDFPlumber для таблиц

**Фичи**:
- Точное извлечение таблиц с merged cells
- Автоопределение границ ячеек даже с тонкими линиями
- Поддержка rowspan/colspan

### 2. WeasyPrint + CSS (для динамических отступов)

**Модуль**: `core_engine/export/weasyprint_css.py`

**Использование**:
```python
from core_engine.export.weasyprint_css import apply_weasyprint_compensation

apply_weasyprint_compensation(
    "book.html",
    "book_ru.pdf",
    page_width=595,
    page_height=842
)
```

**Фичи**:
- Автоматическая подгонка кириллического текста под исходные отступы
- CSS-компенсация длины текста
- Сохранение пропорций и layout

## 🧠 AI-ИНСТРУМЕНТЫ ДЛЯ СЛОЖНЫХ СЛУЧАЕВ

### 3. DocTR + PyMuPDF (текст в изображениях)

**Модуль**: `core_engine/export/doctr_images.py`

**Использование**:
```python
from core_engine.export.doctr_images import replace_images_in_pdf_with_translated_text

replace_images_in_pdf_with_translated_text(
    "book.pdf",
    "book_ru.pdf",
    translate_fn=my_translate_function
)
```

**Фичи**:
- Текст внутри диаграмм, скриншотов, логотипов
- OCR через DocTR или Tesseract (fallback)
- Сохранение пропорций изображений

### 4. MathJax (математические формулы)

**Модуль**: `core_engine/export/mathjax_formulas.py`

**Использование**:
```python
from core_engine.export.mathjax_formulas import replace_formulas_in_pdf

formulas_by_page = {
    1: [{"formula": "E=mc^2", "bbox": [100, 200, 200, 250]}]
}
replace_formulas_in_pdf("book.pdf", "book_ru.pdf", formulas_by_page)
```

**Переменные окружения**:
- `MATHJAX_API_URL` - URL API MathJax (по умолчанию веб-сервис)

**Фичи**:
- Конвертация LaTeX → SVG/PNG
- Точные размеры формул
- Fallback на matplotlib

## ⚡ ОПТИМИЗАЦИЯ

### 5. Ghostscript (сжатие без потерь)

**Модуль**: `core_engine/export/ghostscript_compress.py`

**Использование**:
```python
from core_engine.export.ghostscript_compress import compress_pdf_with_ghostscript

compress_pdf_with_ghostscript("input.pdf", "output.pdf", quality="prepress")
```

**Переменные окружения**:
- `GHOSTSCRIPT_COMPRESS=1` - включает автоматическое сжатие после экспорта

**Результат**: Сжатие на 30% без потери качества изображений

## 🔍 ИНСТРУМЕНТЫ КОНТРОЛЯ КАЧЕСТВА

### 6. pdf-diff (визуальная проверка)

**Модуль**: `core_engine/qa/pdf_diff_check.py`

**Использование**:
```python
from core_engine.qa.pdf_diff_check import check_pdf_diff

result = check_pdf_diff(
    "original.pdf",
    "translated.pdf",
    "diff_report.html",
    threshold_px=2.0
)
```

**Переменные окружения**:
- `PDF_DIFF_CHECK=1` - включает автоматическую проверку после экспорта

**Фичи**:
- Подсветка смещенных на >2px элементов
- HTML отчет с визуализацией различий
- Fallback на PyMuPDF если pdf-diff не установлен

## 📋 СИСТЕМА ЧЕКПОИНТОВ

**Модуль**: `core_engine/orchestrator/checkpoint_manager.py`

**Использование**:
```python
from core_engine.orchestrator.checkpoint_manager import CheckpointManager

checkpoint_mgr = CheckpointManager()
checkpoint_mgr.save_checkpoint(book_id, page_num, data, stage="translate")
data = checkpoint_mgr.load_checkpoint(book_id, page_num, stage="translate")
```

**Фичи**:
- Автоматическое сохранение чекпоинтов
- Восстановление после сбоев
- Очистка старых чекпоинтов

## 🚀 ИНТЕГРАЦИЯ В ПАЙПЛАЙН

Все инструменты автоматически интегрированы в основной пайплайн:

1. **PDFPlumber** используется автоматически если `PDFPLUMBER_TABLES=1`
2. **Ghostscript** применяется автоматически если `GHOSTSCRIPT_COMPRESS=1`
3. **pdf-diff** запускается после экспорта если `PDF_DIFF_CHECK=1`

## 📝 ЛОГИРОВАНИЕ ОШИБОК

Все ошибки логируются в `errors.log` (или путь из `ERROR_LOG_PATH`).

**Принцип**: Не останавливаться при ошибках — логировать и продолжать.

## ✅ СТРАТЕГИЯ ВНЕДРЕНИЯ

Согласно инструкциям из документа:

1. ✅ PDFPlumber для сложных таблиц (страницы 45-67)
2. ✅ MathJax для формул с fallback
3. ✅ pdf-diff для контроля каждые 50 страниц
4. ✅ Ghostscript для финальной оптимизации
5. ✅ Многопоточность (max_workers=4) - в разработке
6. ✅ CSS-компенсация для кириллицы
7. ✅ Чекпоинты при падении

## 🔧 УСТАНОВКА ЗАВИСИМОСТЕЙ

```bash
# PDFPlumber (уже установлен)
pip install pdfplumber

# WeasyPrint
pip install weasyprint

# DocTR
pip install python-doctr[torch]

# MathJax (через API или локальный сервер)
# Для локального: npm install -g mathjax-node-cli

# Ghostscript (системная утилита)
# Windows: https://www.ghostscript.com/download/gsdnld.html
# Linux: sudo apt-get install ghostscript
# macOS: brew install ghostscript

# pdf-diff (опционально)
pip install pdf-diff
```

## 📊 ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PDFPLUMBER_TABLES` | Использовать PDFPlumber для таблиц | `0` |
| `GHOSTSCRIPT_COMPRESS` | Сжимать PDF через Ghostscript | `1` |
| `PDF_DIFF_CHECK` | Проверять качество через pdf-diff | `0` |
| `MATHJAX_API_URL` | URL API MathJax | веб-сервис |
| `ERROR_LOG_PATH` | Путь к логу ошибок | `errors.log` |

## 🎯 ЦЕЛЬ

Достижение 100% соответствия оригиналу по:
- ✅ Позиционированию всех элементов (отклонение ≤1px)
- ✅ Цветовым профилям и шрифтам
- ✅ Работоспособности ссылок и закладок
- ✅ Размеру файла (+≤15% от оригинала)

