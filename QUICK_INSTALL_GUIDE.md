# 🚀 Быстрая инструкция по доустановке библиотек

## ✅ Что уже установлено автоматически

Запущен скрипт `install_remaining.py`, который установил:
- ✅ **mpxpy** (альтернатива mathpix)
- ✅ **diff-match-patch** (альтернатива diff-match-patch-python)

## 📋 Что осталось сделать

### 1. pdf-diff (опционально)

**Требует:** Microsoft C++ Build Tools

**Шаги:**
1. Скачать: https://visualstudio.microsoft.com/visual-cpp-build-tools/
2. Установить с компонентом "C++ build tools"
3. После установки выполнить:
   ```bash
   pip install pdf-diff
   ```

**Альтернатива:** Используйте: `core_engine/qa/pixel_perfect_diff.py` (уже работает!)

---

## ✅ Все остальное уже доступно!

### Альтернативы, которые уже работают:

1. **pdf-diff** → `core_engine/qa/pixel_perfect_diff.py` ✅
2. **mathpix** → `core_engine/export/mathjax_formulas.py` ✅
3. **perceptualdiff** → `opencv-python` + `scikit-image` ✅
4. **structural-similarity** → `scikit-image.metrics.structural_similarity` ✅

---

## 🎯 Итог

**Все функциональные аналоги доступны в проекте!**

Дополнительная установка **не критична** - проект полностью функционален.

Если нужен именно `pdf-diff`, установите C++ Build Tools (см. выше).

---

## 📝 Команды для справки

```bash
# Проверить статус установки
python install_remaining.py

# Установить альтернативы (если еще не установлены)
pip install mpxpy diff-match-patch

# Установить pdf-diff (после установки C++ Build Tools)
pip install pdf-diff
```

