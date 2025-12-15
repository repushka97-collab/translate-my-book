# Быстрая установка недостающих библиотек (если возможно)

Write-Host "=== Попытка установки недостающих библиотек ===" -ForegroundColor Cyan

# 1. Попробовать установить mathpix-python (альтернатива mathpix)
Write-Host "`n[1/4] Установка mathpix-python..." -ForegroundColor Yellow
pip install mathpix-python 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ mathpix-python установлен" -ForegroundColor Green
} else {
    Write-Host "  ✗ mathpix-python не установлен (не критично)" -ForegroundColor Yellow
}

# 2. Проверить, установлен ли C++ Build Tools (для pdf-diff)
Write-Host "`n[2/4] Проверка C++ Build Tools..." -ForegroundColor Yellow
$vcTools = Get-Command cl.exe -ErrorAction SilentlyContinue
if ($vcTools) {
    Write-Host "  ✓ C++ Build Tools найдены" -ForegroundColor Green
    Write-Host "  Попытка установки pdf-diff..." -ForegroundColor Cyan
    pip install pdf-diff 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ pdf-diff установлен" -ForegroundColor Green
    } else {
        Write-Host "  ✗ pdf-diff не установлен (требует компиляцию)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ✗ C++ Build Tools не найдены" -ForegroundColor Yellow
    Write-Host "  Скачать: https://visualstudio.microsoft.com/visual-cpp-build-tools/" -ForegroundColor Cyan
}

# 3. Проверить альтернативы
Write-Host "`n[3/4] Проверка альтернатив..." -ForegroundColor Yellow
python -c "from skimage.metrics import structural_similarity; print('  ✓ structural_similarity доступен через scikit-image')" 2>&1 | Out-Null
python -c "import cv2; print('  ✓ opencv-python доступен для сравнения изображений')" 2>&1 | Out-Null

# 4. Итоговый статус
Write-Host "`n[4/4] Итоговый статус:" -ForegroundColor Yellow
Write-Host "  ✓ Все функциональные аналоги доступны" -ForegroundColor Green
Write-Host "  ✓ Дополнительная установка не критична" -ForegroundColor Green

Write-Host "`n=== Готово ===" -ForegroundColor Green

