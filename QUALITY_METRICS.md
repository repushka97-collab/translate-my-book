# [QUALITY VERIFICATION MODE] Метрики качества для финального контроля

Этот документ описывает все метрики качества, реализованные согласно "метрики качества.md".

## 📏 АВТОМАТИЧЕСКИЕ МЕТРИКИ КАЧЕСТВА

### 1. Pixel Perfect Comparison

**Модуль**: `core_engine/qa/pixel_perfect_diff.py`

**Использование**:
```python
from core_engine.qa.pixel_perfect_diff import compare_pdfs_pixel_perfect

metrics = compare_pdfs_pixel_perfect(
    "original.pdf",
    "translated.pdf",
    max_shift=1.0,
    max_displacement=2.0
)

# Результат:
# {
#   "shift_score": 0.98,  # идеал = 1.0
#   "element_loss": 0.0,  # потерянных элементов нет
#   "text_overflow": 0.02,  # 2% текста вылезло за границы
#   "overall_score": 0.97
# }
```

**Метрики**:
- `shift_score`: точность позиционирования (0.0-1.0)
- `element_loss`: процент потерянных элементов
- `text_overflow`: процент текста, вылезшего за границы
- `displacements`: список смещенных элементов

### 2. Layout Similarity

**Модуль**: `core_engine/qa/layout_similarity.py`

**Использование**:
```python
from core_engine.qa.layout_similarity import calculate_layout_similarity

metrics = calculate_layout_similarity(
    "original.pdf",
    "translated.pdf",
    method="jaccard",  # или "euclidean"
    threshold=0.95
)

# Результат: 0.97 (отличное соответствие)
```

**Метрики**:
- `similarity`: структурное сходство (0.0-1.0)
- `structure_match`: соответствие структуры
- `element_types_match`: соответствие типов элементов
- `hierarchy_preserved`: сохранение иерархии

### 3. Text Flow Analysis

**Модуль**: `core_engine/qa/text_flow_analysis.py`

**Использование**:
```python
from core_engine.qa.text_flow_analysis import analyze_text_flow

metrics = analyze_text_flow("original.pdf", "translated.pdf")

# Результат:
# {
#   "flow_score": 0.95,  # TextFlowScore (0.0-1.0)
#   "hyphenation_errors": 2,
#   "text_overflow_count": 5,
#   "reading_order_preserved": True
# }
```

**Проверки**:
- Порядок чтения (LTR/RTL)
- Разрывы строк в середине слов
- Смещение текста из-за увеличения длины

## 🎨 ВИЗУАЛЬНАЯ ВЕРИФИКАЦИЯ

### 4. Color-Coded Difference Maps (Heatmaps)

**Модуль**: `core_engine/qa/heatmap_diff.py`

**Использование**:
```python
from core_engine.qa.heatmap_diff import generate_heatmap_diff

result = generate_heatmap_diff(
    "original.pdf",
    "translated.pdf",
    "output/heatmaps",
    threshold_green=2.0,  # зеленый (0-2px)
    threshold_yellow=5.0  # желтый (2-5px)
)
```

**Цветовая схема**:
- 🟢 Зеленый (0-2px): Незначительные смещения (OK)
- 🟡 Желтый (2-5px): Требует проверки
- 🔴 Красный (>5px): Критическая ошибка верстки

**Требования**: `pip install opencv-python`

## 📊 КОЛИЧЕСТВЕННЫЕ МЕТРИКИ

### 5. PDF Quality Scorecard

**Модуль**: `core_engine/qa/quality_scorecard.py`

**Использование**:
```python
from core_engine.qa.quality_scorecard import generate_quality_scorecard, print_scorecard

scorecard = generate_quality_scorecard(
    "original.pdf",
    "translated.pdf",
    "output/quality_scorecard.json"
)

print_scorecard(scorecard)
```

**Пример вывода**:
```
Quality Scorecard
==================================================
Overall Score: 95.3/100
Layout Preservation: 97.2% (±1.3px)
Text Overflow Rate: 1.8% (должно быть <3%)
Image Position Drift: 0.05px avg
Font Consistency: 100%
Table Integrity: 96.5%
Page Count Match: ✅
File Size Ratio: 1.12x (допустимо до 1.25x)
--------------------------------------------------
Recommendations:
  • ✅ Отличное качество: результат готов к использованию
==================================================
```

**Метрики**:
- `overall_score`: общая оценка (0-100)
- `layout_preservation`: сохранение верстки (%)
- `text_overflow_rate`: процент переполнения
- `image_position_drift`: среднее смещение изображений (px)
- `font_consistency`: соответствие шрифтов (%)
- `table_integrity`: целостность таблиц (%)
- `page_count_match`: совпадение количества страниц
- `file_size_ratio`: отношение размеров файлов

## 🔄 ИНТЕГРАЦИЯ В ПАЙПЛАЙН

Все метрики автоматически интегрированы в основной пайплайн:

1. **Quality Scorecard** запускается автоматически после экспорта PDF (если `QUALITY_CHECK=1`)
2. **Heatmaps** генерируются опционально (если `GENERATE_HEATMAPS=1`)
3. **pdf-diff** используется для дополнительной визуализации (если `PDF_DIFF_CHECK=1`)

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `QUALITY_CHECK` | Включить проверку качества | `1` |
| `GENERATE_HEATMAPS` | Генерировать тепловые карты | `0` |
| `PDF_DIFF_CHECK` | Использовать pdf-diff | `0` |

### Стратегия оценки

Согласно инструкциям из документа:

1. ✅ **Автоматическая оценка** для всех страниц:
   - Pixel Perfect Comparison (макс. смещение 2px)
   - Layout Similarity (мин. 0.93)
   - Text Flow Analysis

2. ✅ **Quality Scorecard**:
   - Если OVERALL SCORE ≥ 95 → принять результат
   - Если 90 ≤ SCORE < 95 → пометить 10% страниц для ручной проверки
   - Если SCORE < 90 → запустить корректирующий пайплайн

3. ✅ **Heatmaps** для визуализации проблемных страниц

4. ✅ **Отчеты сохраняются** в `output/{book_id}/quality_reports/`

## 📁 Структура отчетов

```
output/{book_id}/
├── book_ru.pdf
├── quality_reports/
│   ├── quality_scorecard.json      # Полный отчет с метриками
│   ├── pdf_diff_report.html         # Визуальный отчет pdf-diff
│   └── heatmaps/                    # Тепловые карты
│       ├── heatmap_page_0001.png
│       ├── heatmap_page_0002.png
│       └── ...
```

## 🎯 Цель

Обеспечить объективную оценку качества перевода с фокусом на:
- ✅ Пиксельную точность позиционирования (±1px допуск)
- ✅ Сохранение логической структуры документа
- ✅ Отсутствие текстовых переполнений
- ✅ Идентичность визуального восприятия

## 📝 Рекомендации

- **Для учебников/научной литературы**: применять повышенные требования (макс. смещение 1px)
- **При обнаружении системной ошибки**: остановить процесс и проанализировать причину
- **Сохранять все отчеты**: для анализа и улучшения алгоритмов

