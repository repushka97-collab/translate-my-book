# [ADVANCED PDF TRANSLATION MODE] Система автоматического исправления ошибок верстки

Этот документ описывает все модули автоматического исправления, реализованные согласно "префинальная обработка.md.txt".

## 🛠️ МОДУЛИ АВТОМАТИЧЕСКОГО ИСПРАВЛЕНИЯ

### 1. Dynamic Layout Correction Engine

**Модуль**: `core_engine/correction/layout_fixer.py`

**Использование**:
```python
from core_engine.correction.layout_fixer import apply_layout_correction

result = apply_layout_correction(
    "original.pdf",
    "translated.pdf",
    "corrected.pdf",
    target_language="ru"
)

# Результат:
# {
#   "success": True,
#   "pages_processed": 350,
#   "issues_found": 42,
#   "output_path": "corrected.pdf"
# }
```

**Возможности**:
- Автоматическое обнаружение переполнений текста
- Исправление смещения изображений
- Коррекция таблиц
- Адаптивное масштабирование шрифтов

**Переменная окружения**: `AUTO_CORRECTION=1`

### 2. ML-Based Overflow Predictor

**Модуль**: `core_engine/correction/overflow_predictor.py`

**Использование**:
```python
from core_engine.correction.overflow_predictor import OverflowPredictor, adjust_translation_params

predictor = OverflowPredictor(confidence_threshold=0.85)

risks = predictor.predict_overflow_risks(
    page=original_page,
    source_lang="en",
    target_lang="ru"
)

# Результат:
# {
#   "tables": True,
#   "headers": False,
#   "narrow_columns": True,
#   "risk_score": 0.75,
#   "recommendations": [...]
# }

# Корректируем параметры перевода
params = adjust_translation_params(risks, base_params)
```

**Возможности**:
- Предсказание рисков переполнения ДО перевода
- Автоматическая корректировка параметров перевода
- Обнаружение проблемных зон (таблицы, заголовки, узкие колонки)

**Переменная окружения**: `USE_OVERFLOW_PREDICTOR=1`

### 3. Font Metric Compensation System

**Модуль**: `core_engine/correction/font_compensator.py`

**Использование**:
```python
from core_engine.correction.font_compensator import FontMetricsCompensator

compensator = FontMetricsCompensator(
    source_lang="en",
    target_lang="ru",
    max_width_change=1.3
)

compensation = compensator.calculate(
    original_text="Introduction to Algorithms",
    translated_text="Введение в алгоритмы",
    font_name="Helvetica",
    font_size=12
)

# Результат:
# {
#   "font_size": 11.5,
#   "tracking": -15,
#   "width_change": 1.25,
#   "kerning_adjustment": 0.1
# }
```

**Возможности**:
- Динамическая коррекция кернинга и трекинга
- Компенсация увеличения ширины текста для кириллицы
- Автоматическое уменьшение размера шрифта при переполнении

### 4. Batch Correction Framework

**Модуль**: `core_engine/correction/batch_corrector.py`

**Использование**:
```python
from core_engine.correction.batch_corrector import BatchCorrector

corrector = BatchCorrector(
    input_dir="translated_books/",
    output_dir="corrected_books/",
    workers=8,
    quality_threshold=0.95
)

results = corrector.run(
    quality_check=True,
    checkpoint_interval=10
)

# Результат:
# {
#   "success_count": 95,
#   "total_count": 100,
#   "avg_quality_improvement": 12.5,
#   "errors": []
# }
```

**Возможности**:
- Массовое исправление переведенных PDF
- Многопоточная обработка
- Автоматический контроль качества
- Сохранение чекпоинтов

## 🔄 ИНТЕГРАЦИЯ В ПАЙПЛАЙН

Все модули автоматически интегрированы в основной пайплайн:

1. **Overflow Predictor** запускается перед переводом (если `USE_OVERFLOW_PREDICTOR=1`)
2. **Layout Fixer** применяется после экспорта PDF (если `AUTO_CORRECTION=1`)
3. **Font Compensator** используется в процессе перевода для коррекции метрик шрифта

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `USE_OVERFLOW_PREDICTOR` | Включить предсказание рисков | `0` |
| `AUTO_CORRECTION` | Включить автоматическое исправление | `0` |

### Workflow

1. **Перед переводом**: Overflow Predictor анализирует страницы и корректирует параметры
2. **Во время перевода**: Font Compensator применяет компенсацию метрик шрифта
3. **После перевода**: Layout Fixer исправляет обнаруженные ошибки верстки
4. **Проверка качества**: Quality Scorecard оценивает результат

## 📊 МЕТРИКИ

Согласно документации:
- **Text overflow elimination**: 92%
- **Table structure preservation**: 98%
- **Image drift correction**: ±0.5px
- **Точность предсказаний**: 89%

## 🎯 ЦЕЛЬ

Создать self-healing систему, которая:
- Автоматически исправляет 95% ошибок верстки без человека
- Предсказывает проблемные места ДО перевода
- Обрабатывает 100+ книг в сутки с гарантией качества

