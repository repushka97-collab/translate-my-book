---
Проверка гихаб

## 1. `requirements.txt`

Создай в корне `translate-my-book` файл `requirements.txt` со следующим содержимым:

```txt
# Core ML + text
torch
transformers
sentencepiece
safetensors
regex
tqdm

# PDF ingest
pymupdf          # fitz
pdfplumber
pypdf

# Export
python-docx
PyYAML
```

Это накрывает все библиотеки, которые мы уже руками доустанавливали под STATE v4.

(Потом мигратор при желании зафиксирует версии, но базовый список уже будет.)

---

## 2. `README.md` для ядра

В том же корне создай `README.md`:

````markdown
# EWB Core Engine (STATE v4, Windows)

Этот репозиторий — рабочее ядро **Translate-My-Book / Education Without Borders**.  
Состояние — STATE v4: однопроходный пайплайн `PDF → JSON layout → DOCX (RU)`.  

---

## 1. Среда

- OS: Windows 11 (x64)
- Python: 3.11.x (официальный инсталлятор)
- Виртуальное окружение: `.venv` в корне проекта

```powershell
cd translate-my-book
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
````

GPU **не используется**, пайп работает на CPU:

```powershell
$env:CUDA_VISIBLE_DEVICES = ""
```

---

## 2. Быстрый запуск пайплайна

Скрипт входа: `run_pipeline.py`.

```powershell
# по умолчанию берёт input.pdf в корне проекта
python run_pipeline.py

# явный путь к PDF
python run_pipeline.py --source path\to\book.pdf
```

После успешного запуска в `output/<book_id>/` появятся:

* `book.json` — структурная модель книги (страницы, блоки, роли)
* `book_ru.docx` — черновой перевод книги на русском
* запись о книге в локальной библиотеке (через `library_manager`)

````

```markdown
---

## 3. Архитектура пайплайна

Пайплайн реализован в `core_engine/orchestrator/pipeline.py` и идёт по шагам:

1. **Ingest**

   - Модуль: `core_engine.ingest.pdf_ingest.ingest_pdf`
   - Вход: путь к PDF
   - Выход: `ingest_result = { book_id, blocks, meta }`

2. **Normalize**

   - Модуль: `core_engine.normalize.text_cleaner.normalize_blocks`
   - Вход: `ingest_result.blocks`
   - Выход: `normalized_blocks` (очищенный текст)

3. **Translate**

   - Модуль: `core_engine.translate.llm_adapter.translate_blocks`
   - Текущая модель: `facebook/nllb-200-distilled-1.3B` через `transformers` на CPU
   - Языковая пара: `en → ru`
   - Выход: `translated_blocks` (в каждом блоке есть `translated_text`)

4. **QA (базовая проверка)**

   - Модуль: `core_engine.qa.integrity_check.qa_check_blocks`
   - Контракт:

     ```python
     qa_report = qa_check_blocks(normalized_blocks, translated_blocks)
     ```

5. **Layout model**

   - Модуль: `core_engine.layout.block_reassemble.build_layout`
   - Вход: `translated_blocks`, `ingest_result.meta`
   - Выход: `layout_model` c полями:

     ```jsonc
     {
       "book_id": "...",
       "pages": [
         {
           "page_num": 1,
           "blocks": [
             {
               "id": "...",
               "page": 1,
               "order": 0,
               "text": "EN",
               "translated_text": "RU",
               "metadata": { "role": "heading|body|caption|other" }
             }
           ]
         }
       ]
     }
     ```

6. **JSON export**

   - Модуль: `core_engine.export.export_json.export_json_bundle`
   - Выход: `output/<book_id>/book.json` и вспомогательные JSON (если есть)

7. **DOCX draft**

   - Модули:
     - `core_engine.layout.layout_reassemble.reassemble_blocks`
     - `core_engine.export.docx_exporter.export_docx`
   - Выход: `output/<book_id>/book_ru.docx`

8. **Регистрация в библиотеке**

   - Модуль: `core_engine.library.library_manager.register_book_in_library`
````

```markdown
---

## 4. Текущее состояние и ограничения (STATE v4)

**Что гарантирует ядро:**

- стабильный формат `book.json` (`book_id`, `pages[]`, `blocks[]` с `text`, `translated_text`, `metadata.role`)
- всегда создаётся `book_ru.docx` с полным текстом книги на русском
- единая точка входа: `python run_pipeline.py --source <pdf>`
- пошаговые логи `[1/8] ... [8/8] ...`

**Ограничения:**

- Перевод: только NLLB-200 1.3B, жёстко зашитая пара `en → ru`.
- DOCX: черновая верстка, без колонок/таблиц/рисунков.
- Структура: нет иерархии “Глава/Подглава”, только роли блоков.
- Производительность: на больших книгах NLLB на CPU может работать медленно.

---

## 5. Дальнейшее развитие (под другие чаты)

Следующие задачи отданы другим мозгам:

- усиление role-классификатора и структуры (`heading`/`section`/`caption` и уровни глав)
- улучшение DOCX-экспортера и полноценный PDF-layout (Layout Engine)
- мульти-LLM режимы `fast / quality / safe` через `configs/llm.yaml` и LLMAdapter
- расширенный QA с сохранением `qa_report.json`

Ядро в STATE v4 считается стабильным для:
- приёма PDF,
- получения `book.json` + `book_ru.docx`,
- использования другими отделами.
```


