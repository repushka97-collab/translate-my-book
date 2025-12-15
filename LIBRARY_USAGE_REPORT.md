# 📊 Отчет об использовании библиотек в коде

## ✅ Используемые библиотеки

### 1. pdf-diff

**Использование:**
- ✅ **Используется** в `core_engine/qa/pdf_diff_check.py`
- ✅ **Имеет fallback** на PyMuPDF (работает без установки pdf-diff)
- ✅ **Вызывается** из `core_engine/orchestrator/pipeline.py` (опционально, через `PDF_DIFF_CHECK=1`)

**Статус:** 
- ⚠️ **Не критично** - есть полноценный fallback через PyMuPDF
- ✅ **Работает** даже без установки pdf-diff

**Код:**
```python
# core_engine/qa/pdf_diff_check.py
def check_pdf_diff(...):
    try:
        # Пробует использовать pdf-diff
        subprocess.run(["pdf-diff", "--version"], ...)
    except FileNotFoundError:
        # Fallback на PyMuPDF (работает всегда!)
        return _check_pdf_diff_pymupdf(...)
```

---

### 2. mathpix

**Использование:**
- ✅ **Используется** в `core_engine/export/latex_formulas.py` (опционально)
- ✅ **Имеет fallback** на MathJax (работает без установки mathpix)
- ✅ **Упоминается** в `core_engine/production/book_profiles.py` и `cost_optimizer.py`

**Статус:**
- ⚠️ **Не критично** - есть fallback на MathJax
- ✅ **Работает** через MathJax API без установки mathpix

**Код:**
```python
# core_engine/export/latex_formulas.py
mathpix_app_id = os.getenv("MATHPIX_APP_ID")
if mathpix_app_id and mathpix_app_key:
    # Использует Mathpix API (если настроен)
    ...
else:
    # Fallback на MathJax (работает всегда!)
    ...
```

**Альтернатива:**
- ✅ `core_engine/export/mathjax_formulas.py` - работает без установки

---

### 3. perceptualdiff

**Использование:**
- ❌ **НЕ используется** напрямую в коде
- ✅ **Альтернатива:** `opencv-python` используется в `core_engine/qa/heatmap_diff.py`

**Статус:**
- ✅ **Не нужен** - используется opencv-python для сравнения изображений

**Код:**
```python
# core_engine/qa/heatmap_diff.py использует cv2 (opencv-python)
import cv2
# Сравнение изображений через OpenCV
```

---

### 4. structural-similarity

**Использование:**
- ❌ **НЕ используется** напрямую в коде
- ✅ **Альтернатива:** `scikit-image.metrics.structural_similarity` доступен, но не используется
- ✅ **Альтернатива:** `core_engine/qa/layout_similarity.py` использует собственные метрики

**Статус:**
- ✅ **Не нужен** - используется собственная реализация в `layout_similarity.py`

**Код:**
```python
# core_engine/qa/layout_similarity.py
# Использует собственные метрики Jaccard и Euclidean
# Не требует structural-similarity библиотеку
```

---

## 📋 Итоговая таблица

| Библиотека | Используется? | Критично? | Fallback | Статус |
|------------|---------------|-----------|----------|--------|
| **pdf-diff** | ✅ Да (опционально) | ❌ Нет | ✅ PyMuPDF | ✅ Работает |
| **mathpix** | ✅ Да (опционально) | ❌ Нет | ✅ MathJax | ✅ Работает |
| **perceptualdiff** | ❌ Нет | ❌ Нет | ✅ OpenCV | ✅ Не нужен |
| **structural-similarity** | ❌ Нет | ❌ Нет | ✅ Собственная реализация | ✅ Не нужен |

---

## ✅ Вывод

### Все библиотеки имеют альтернативы или fallback!

1. **pdf-diff** → ✅ Fallback на PyMuPDF (работает)
2. **mathpix** → ✅ Fallback на MathJax (работает)
3. **perceptualdiff** → ✅ Используется OpenCV (установлен)
4. **structural-similarity** → ✅ Собственная реализация (работает)

### Рекомендация

**Установка этих библиотек НЕ критична!**

Проект полностью функционален без них благодаря:
- ✅ Fallback механизмам
- ✅ Альтернативным реализациям
- ✅ Использованию установленных библиотек (OpenCV, scikit-image)

**Можно использовать проект как есть!** 🚀

