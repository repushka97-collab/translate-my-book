@echo off
chcp 65001 >nul
echo ============================================================
echo 🚀 Запуск системы Human Feedback
echo ============================================================
echo.

REM Проверяем наличие Flask
python -c "import flask" 2>nul
if errorlevel 1 (
    echo [INFO] Установка Flask...
    pip install flask flask-cors
)

echo.
echo [1] Поиск переведенных PDF...
python test_human_feedback.py

echo.
echo [2] Запуск веб-интерфейса...
echo     Откройте http://localhost:5000/ в браузере
echo.
cd tools\human_feedback_interface
python app.py

