# EWB Core Engine (STATE v7.1, Windows)

Рабочее ядро **Translate-My-Book / Education Without Borders**: однопроходный пайплайн `PDF → JSON layout → DOCX (RU)` с регистрацией в локальной библиотеке.

## 1. Среда

- OS: Windows 11 (x64)
- Python: 3.11.x
- Виртуальное окружение: `.venv` в корне

Установка зависимостей:

```powershell
cd translate-my-book
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Профили LLM (configs/llm.yaml)

- `dev`  → placeholder, без перевода (CPU) - для быстрой проверки контрактов
- `fast` → NLLB 600M, `device: cuda` (по умолчанию) - быстрый перевод с кэшированием
- `full` → NLLB 1.3B, `device: cpu` - более качественный перевод на CPU
- `hybrid` → NLLB baseline + LLM refine (Ollama) - максимальное качество

Если CUDA недоступна, `fast` может деградировать на CPU и стать очень медленным; для CPU-режима лучше явно выбрать `--mode full`.

**Новые возможности:**
- **Кэширование переводов**: автоматически включено в режиме `fast`, ускоряет повторные запуски
- **Гибридный перевод**: режим `hybrid` использует NLLB для базового перевода, затем улучшает важные блоки через LLM (требует Ollama)

## 3. Быстрый запуск

Скрипт входа: `run_pipeline.py` (требует путь к PDF).

```powershell
# пример
python run_pipeline.py --source path\to\book.pdf --mode fast

# режимы
#   dev    - без перевода, быстрая прогонка контрактов
#   fast   - NLLB 600M (CUDA) с кэшированием
#   full   - NLLB 1.3B (CPU)
#   hybrid - NLLB baseline + LLM refine (требует Ollama)
```

### Проверка GPU / CPU

```powershell
.\.venv\Scripts\Activate.ps1
python - <<EOF
import torch
print("CUDA available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("Device:", torch.cuda.get_device_name(0))
EOF
```

Если CUDA нет — используйте `--mode full` (CPU). В режиме `fast` без CUDA перевод будет медленным.

## 4. Что создаётся

После успешного прогона в `output/<book_id>/` будут:

- `book.json` — layout-модель (`book_id`, `pages[].blocks[]` с `text`, `translated_text`, `metadata.role`, `bbox`)
- `book_ru.docx` — черновой перевод книги
- `qa_report.json` — базовый QA-отчёт
- `paragraph_stream.json` — построенный поток параграфов (debug)

Параллельно книга регистрируется в `library/<book_id>/` с манифестом и слоями.

## 5. Возможности ядра

### Качество перевода
- **Гибридный перевод**: NLLB baseline + LLM refine для важных блоков
- **Post-processing**: автоматическое исправление артефактов NLLB
- **Терминологическая нормализация**: сохранение медицинских/технических терминов
- **Улучшенное слияние предложений**: автоматическое объединение разорванных фрагментов

### Верстка и структура
- **Детекция глав**: автоматическое определение Part → Chapter → Section
- **Двухколоночная верстка**: правильный порядок чтения для двухколоночных документов
- **Изображения**: автоматическая вставка изображений из PDF в DOCX
- **Таблицы**: улучшенное распознавание и рендеринг таблиц
- **Сноски и формулы**: автоматическая детекция и стилизация

### Производительность
- **Кэширование переводов**: ускорение повторных запусков
- **GPU оптимизация**: оптимизировано для RTX 5080 (batch_size=32)
- **Инкрементальная обработка**: пропуск уже переведенных блоков

### Ограничения
- Языковая пара жёстко EN→RU (NLLB).
- DOCX — черновая верстка, сложные таблицы могут требовать ручной доработки.
- Layout роли определяются эвристиками.
- Большие PDF на CPU обрабатываются медленно (рекомендуется GPU).

## 6. Быстрая проверка окружения

```powershell
.\.venv\Scripts\Activate.ps1
python - <<EOF
import torch
print("CUDA available:", torch.cuda.is_available())
EOF
```

Если CUDA нет — запускайте с `--mode full` или будьте готовы к долгому времени в `fast`.
