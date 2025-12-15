# 🔧 Инструкции по доустановке недостающих библиотек

## 1. pdf-diff (требует компилятор C++)

### Вариант A: Установить Microsoft C++ Build Tools (рекомендуется)

1. **Скачать Microsoft C++ Build Tools:**
   - Перейти: https://visualstudio.microsoft.com/visual-cpp-build-tools/
   - Скачать "Build Tools for Visual Studio"
   - Установить с компонентом "C++ build tools"

2. **После установки:**
   ```bash
   pip install pdf-diff
   ```

### Вариант B: Использовать предкомпилированный wheel (если доступен)

```bash
# Попробовать установить через conda (если установлен)
conda install -c conda-forge pdf-diff

# Или найти предкомпилированный wheel на GitHub
```

### Вариант C: Использовать альтернативу

Вместо `pdf-diff` можно использовать:
- `pymupdf` (fitz) для сравнения PDF
- Наш собственный модуль `core_engine/qa/pixel_perfect_diff.py`

---

## 2. mathpix (недоступен через pip)

### Вариант A: Установить mpxpy (официальный клиент)

```bash
pip install mpxpy
```

**Получить API ключ:**
- Зарегистрироваться на https://mathpix.com/
- Получить `app_id` и `app_key`

### Вариант B: Использовать альтернативу (уже есть в проекте)

Вместо Mathpix можно использовать:
- ✅ Наш модуль `core_engine/export/mathjax_formulas.py` (уже работает)
- `pymupdf` для извлечения формул
- `latex2mathml` для конвертации LaTeX

---

## 3. perceptualdiff (недоступен для Windows)

### Вариант A: Использовать WSL (Windows Subsystem for Linux)

1. **Установить WSL:**
   ```powershell
   wsl --install
   ```

2. **В WSL:**
   ```bash
   sudo apt-get install perceptualdiff
   pip install perceptualdiff
   ```

### Вариант B: Использовать альтернативу

Вместо `perceptualdiff` можно использовать:
- `opencv-python` для сравнения изображений
- `scikit-image` для метрик схожести
- Наш модуль `core_engine/qa/pixel_perfect_diff.py`

---

## 4. structural-similarity (недоступен через pip)

### ✅ Уже доступно!

`scikit-image` уже установлен и содержит функцию `structural_similarity`:

```python
from skimage.metrics import structural_similarity as ssim
```

Также используем наш модуль `core_engine/qa/layout_similarity.py` который уже реализован.

---

## 5. weasyprint (требует системные библиотеки)

### Для Windows:

1. **Установить GTK+ Runtime:**
   - Скачать: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer
   - Или использовать MSYS2: https://www.msys2.org/

2. **Или использовать альтернативу:**
   - `playwright` (уже используется в проекте)
   - `pdfkit` + `wkhtmltopdf`

### Для Linux:

```bash
sudo apt-get install python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0
```

---

## 🚀 Быстрая установка

### Автоматическая установка:

```bash
python install_remaining.py
```

### Ручная установка:

```bash
# 1. Установить альтернативы (если нужно):
pip install mpxpy  # для mathpix
pip install diff-match-patch  # альтернатива diff-match-patch-python

# 2. Установить C++ Build Tools (для pdf-diff):
# Скачать: https://visualstudio.microsoft.com/visual-cpp-build-tools/
# После установки:
pip install pdf-diff

# 3. Остальное уже доступно:
# - structural_similarity → scikit-image (уже установлен)
# - perceptualdiff → opencv-python (уже установлен)
# - mathpix → mathjax_formulas.py (уже в проекте)
```

---

## ✅ Рекомендации

**Для большинства задач достаточно уже установленных библиотек:**

1. ✅ **pdf-diff** → используем `core_engine/qa/pixel_perfect_diff.py`
2. ✅ **mathpix** → используем `core_engine/export/mathjax_formulas.py`
3. ✅ **perceptualdiff** → используем `opencv-python` и `scikit-image`
4. ✅ **structural-similarity** → используем `scikit-image.metrics.structural_similarity`
5. ⚠️ **weasyprint** → используем `playwright` (уже работает)

**Вывод:** Все функциональные аналоги уже есть в проекте! Дополнительная установка не критична.

