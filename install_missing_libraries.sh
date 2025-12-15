#!/bin/bash
# Bash скрипт для установки недостающих библиотек
# Запуск: bash install_missing_libraries.sh

echo "📦 Установка недостающих библиотек из install_requirements.sh..."

# Критические библиотеки для PDF
echo ""
echo "[1/4] Установка PDF библиотек..."
pip install --no-cache-dir pdf2docx==0.5.8 ocrmypdf==15.1.0

# Для векторной графики
echo ""
echo "[2/4] Установка библиотек для векторной графики..."
pip install --no-cache-dir opencv-python-headless==4.10.0.84 svgwrite==1.4.3 svgpathtools==1.5.1 scikit-image==0.23.2 weasyprint==61.0

# Для ML/AI
echo ""
echo "[3/4] Установка ML/AI библиотек..."
pip install --no-cache-dir "layoutparser[all]==0.3.4" doctr==0.10.0 torchvision==0.19.0

# Специализированные
echo ""
echo "[4/4] Установка специализированных библиотек..."
pip install --no-cache-dir mathpix==1.0.0 tabula-py==2.10.0 "camelot-py[cv]==0.11.0" fonttools==4.53.1 colour-science==0.4.8

# Для оптимизации
echo ""
echo "[5/5] Установка библиотек для оптимизации..."
pip install --no-cache-dir dask==2024.8.0 joblib==1.4.2 memory-profiler==0.61.0 pdf-diff==2.0.0 perceptualdiff==1.0.1 structural-similarity==0.2.5

echo ""
echo "✅ Все библиотеки установлены!"
echo ""
echo "Проверка установки..."
python3 -c "
import sys
libs = ['pdf2docx', 'ocrmypdf', 'cv2', 'svgwrite', 'skimage', 'weasyprint', 'layoutparser', 'doctr', 'mathpix', 'tabula', 'camelot', 'fonttools', 'dask', 'joblib', 'memory_profiler', 'pdf_diff', 'perceptualdiff']
installed = []
for l in libs:
    try:
        if l == 'cv2':
            import cv2
        elif l == 'skimage':
            import skimage
        else:
            __import__(l)
        installed.append(l)
    except ImportError:
        pass
print(f'Установлено: {len(installed)}/{len(libs)}')
for l in sorted(installed):
    print(f'  + {l}')
"

