# CI/CD Пайплайн для массовой обработки книг

Этот документ описывает настройку CI/CD для автоматической обработки PDF.

## 🚀 GitHub Actions Workflow

**Файл**: `.github/workflows/pdf-translation.yml`

Автоматически запускается при:
- Push PDF файлов в `books/`
- Ручной триггер через `workflow_dispatch`

**Этапы**:
1. Установка зависимостей
2. Перевод PDF с автоматической коррекцией
3. Проверка качества
4. Загрузка артефактов

## 🐳 Docker Image

**Файл**: `Dockerfile`

**Использование**:
```bash
# Сборка образа
docker build -t pdf-translation:latest .

# Запуск контейнера
docker run -v /path/to/input:/input -v /path/to/output:/output pdf-translation:latest
```

**Включенные инструменты**:
- Poppler (PDF utilities)
- Tesseract OCR
- Ghostscript (сжатие)
- Python 3.11 + все зависимости

## 📊 Мониторинг

### Prometheus Metrics

Метрики для мониторинга:
- `pdf_translation_attempts_total` - общее количество попыток
- `pdf_translation_failures_total` - количество ошибок
- `pdf_quality_score_avg` - средний score качества
- `pdf_processing_backlog_size` - размер очереди

### Алерты

Настроены алерты на:
- Высокий процент ошибок (>20%)
- Падение качества (<92%)
- Рост очереди обработки (>100 файлов)

## 🔄 Интеграция

Все модули автоматического исправления интегрированы:
- `AUTO_CORRECTION=1` - автоматическое исправление верстки
- `USE_OVERFLOW_PREDICTOR=1` - предсказание рисков
- `USE_VECTOR_REPAIR=1` - исправление векторной графики
- `USE_FONT_COMPENSATION=1` - компенсация метрик шрифта

## 📝 Использование

### Локально

```bash
# С включенной автоматической коррекцией
AUTO_CORRECTION=1 USE_OVERFLOW_PREDICTOR=1 python run_pipeline.py --source book.pdf
```

### В Docker

```bash
docker run -e AUTO_CORRECTION=1 -e USE_OVERFLOW_PREDICTOR=1 \
  -v $(pwd)/books:/input -v $(pwd)/output:/output \
  pdf-translation:latest
```

### В GitHub Actions

Workflow автоматически использует все улучшения при обработке PDF.

