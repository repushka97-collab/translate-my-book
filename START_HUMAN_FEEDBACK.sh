#!/bin/bash

echo "============================================================"
echo "🚀 Запуск системы Human Feedback"
echo "============================================================"
echo ""

# Проверяем наличие Flask
if ! python -c "import flask" 2>/dev/null; then
    echo "[INFO] Установка Flask..."
    pip install flask flask-cors
fi

echo ""
echo "[1] Поиск переведенных PDF..."
python test_human_feedback.py

echo ""
echo "[2] Запуск веб-интерфейса..."
echo "    Откройте http://localhost:5000/ в браузере"
echo ""
cd tools/human_feedback_interface
python app.py

