# PowerShell скрипт для установки недостающих библиотек
# Запуск: .\install_missing_libraries.ps1

Write-Host "📦 Установка недостающих библиотек из install_requirements.sh..." -ForegroundColor Cyan

# Критические библиотеки для PDF
Write-Host "`n[1/4] Установка PDF библиотек..." -ForegroundColor Yellow
pip install --no-cache-dir pdf2docx==0.5.8 ocrmypdf==15.1.0

# Для векторной графики
Write-Host "`n[2/4] Установка библиотек для векторной графики..." -ForegroundColor Yellow
pip install --no-cache-dir opencv-python-headless==4.10.0.84 svgwrite==1.4.3 svgpathtools==1.5.1 scikit-image==0.23.2 weasyprint==61.0

# Для ML/AI
Write-Host "`n[3/4] Установка ML/AI библиотек..." -ForegroundColor Yellow
pip install --no-cache-dir layoutparser[all]==0.3.4 doctr==0.10.0 torchvision==0.19.0

# Специализированные
Write-Host "`n[4/4] Установка специализированных библиотек..." -ForegroundColor Yellow
pip install --no-cache-dir mathpix==1.0.0 tabula-py==2.10.0 "camelot-py[cv]==0.11.0" fonttools==4.53.1 colour-science==0.4.8

# Для оптимизации
Write-Host "`n[5/5] Установка библиотек для оптимизации..." -ForegroundColor Yellow
pip install --no-cache-dir dask==2024.8.0 joblib==1.4.2 memory-profiler==0.61.0 pdf-diff==2.0.0 perceptualdiff==1.0.1 structural-similarity==0.2.5

Write-Host "`n✅ Все библиотеки установлены!" -ForegroundColor Green
Write-Host "`nПроверка установки..." -ForegroundColor Cyan
python -c "import sys; libs = ['pdf2docx', 'ocrmypdf', 'cv2', 'svgwrite', 'skimage', 'weasyprint', 'layoutparser', 'doctr', 'mathpix', 'tabula', 'camelot', 'fonttools', 'dask', 'joblib', 'memory_profiler', 'pdf_diff', 'perceptualdiff']; installed = []; [installed.append(l) if (lambda: __import__('cv2' if l == 'cv2' else 'skimage' if l == 'skimage' else l)())() else None for l in libs]; print(f'Установлено: {len(installed)}/{len(libs)}'); [print(f'  + {l}') for l in sorted(installed)]"

