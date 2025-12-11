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
- `dev`  → placeholder, без перевода (CPU)
- `fast` → NLLB 600M, `device: cuda` (по умолчанию)
- `full` → NLLB 1.3B, `device: cpu`

Если CUDA недоступна, `fast` может деградировать на CPU и стать очень медленным; для CPU-режима лучше явно выбрать `--mode full`.

## 3. Быстрый запуск
Скрипт входа: `run_pipeline.py` (требует путь к PDF).
```powershell
# пример
python run_pipeline.py --source path\to\book.pdf --mode fast

# режимы
#   dev  - без перевода, быстрая прогонка контрактов
#   fast - NLLB 600M (CUDA)
#   full - NLLB 1.3B (CPU)
```

## 4. Что создаётся
После успешного прогона в `output/<book_id>/` будут:
- `book.json` — layout-модель (`book_id`, `pages[].blocks[]` с `text`, `translated_text`, `metadata.role`, `bbox`)
- `book_ru.docx` — черновой перевод книги
- `qa_report.json` — базовый QA-отчёт
- `paragraph_stream.json` — построенный поток параграфов (debug)

Параллельно книга регистрируется в `library/<book_id>/` с манифестом и слоями.

## 5. Ограничения текущего ядра
- Языковая пара жёстко EN→RU (NLLB).
- DOCX — черновая верстка без сложных таблиц/картинок.
- Layout роли определяются эвристиками; иерархии глав нет.
- Большие PDF на CPU обрабатываются медленно.

## 6. Быстрая проверка окружения
```powershell
.\.venv\Scripts\Activate.ps1
python - <<EOF
import torch
print("CUDA available:", torch.cuda.is_available())
EOF
```
Если CUDA нет — запускайте с `--mode full` или будьте готовы к долгому времени в `fast`.

