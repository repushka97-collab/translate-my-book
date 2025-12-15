# 🚀 Быстрый старт: Система обучения "глазами человека"

## ✅ Что реализовано

Полная система для сбора человеческой обратной связи и обучения персональной модели качества.

---

## 📋 Шаг 1: Запустить веб-интерфейс

```bash
cd tools/human_feedback_interface
pip install -r requirements.txt
python app.py
```

Откройте в браузере:
```
http://localhost:5000/
```

---

## 📋 Шаг 2: Оценить страницы

1. Введите путь к переведенному PDF
2. Выберите номер страницы
3. Оцените качество от 1 до 10
4. Выделите проблемные области мышью
5. Добавьте комментарии
6. Сохраните оценку

**Минимум:** 10 страниц для базовой модели  
**Рекомендуется:** 20-50 страниц для хорошей точности

---

## 📋 Шаг 3: Обучить модель

```bash
python tools/train_human_like_model.py --user your_name
```

Модель сохранится в `models/quality/your_name_quality_model.pkl`

---

## 📋 Шаг 4: Использовать в пайплайне

```bash
$env:USE_HUMAN_LIKE_EVALUATION="1"
$env:HUMAN_MODEL_USER="your_name"
python run_pipeline.py --source new_book.pdf --mode fast
```

Система автоматически:
- ✅ Оценит качество "как вы"
- ✅ Применит коррекцию если оценка < 7.0
- ✅ Покажет рекомендации

---

## 🎯 Альтернатива: CLI интерфейс

Если не хотите использовать веб-интерфейс:

```bash
python tools/collect_human_feedback.py \
    --book output/book_id/book_ru.pdf \
    --pages 1,5,10,15,20 \
    --user your_name
```

---

## 📊 Структура данных

### Обратная связь:
```
human_feedback/
└── your_name/
    ├── book1_page1_feedback.json
    └── book1_page5_feedback.json
```

### Модели:
```
models/quality/
└── your_name_quality_model.pkl
```

---

## 💡 Пример полного цикла

```bash
# 1. Собрать обратную связь (веб-интерфейс)
cd tools/human_feedback_interface
python app.py
# Откройте http://localhost:5000/ и оцените 20 страниц

# 2. Обучить модель
python tools/train_human_like_model.py --user your_name

# 3. Использовать в пайплайне
$env:USE_HUMAN_LIKE_EVALUATION="1"
$env:HUMAN_MODEL_USER="your_name"
python run_pipeline.py --source new_book.pdf --mode fast
```

---

## ✅ Готово!

Система обучения "глазами человека" полностью интегрирована и готова к использованию!

