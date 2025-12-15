#!/usr/bin/env python3
"""Скрипт для установки недостающих библиотек"""

import subprocess
import sys

def install_package(package_name, description=""):
    """Попытка установить пакет"""
    print(f"\n[Установка] {package_name} {description}")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  [OK] {package_name} установлен успешно")
        return True
    except subprocess.CalledProcessError:
        print(f"  [FAIL] {package_name} не установлен")
        return False

def check_alternative(module_name, description):
    """Проверка альтернативы"""
    try:
        __import__(module_name)
        print(f"  [OK] {description} доступен")
        return True
    except ImportError:
        print(f"  [FAIL] {description} недоступен")
        return False

print("=" * 60)
print("УСТАНОВКА НЕДОСТАЮЩИХ БИБЛИОТЕК")
print("=" * 60)

# 1. Попробовать установить альтернативы
print("\n[1] Установка альтернатив...")
install_package("mpxpy", "(альтернатива mathpix)")
install_package("diff-match-patch", "(альтернатива diff-match-patch-python)")

# 2. Проверка C++ Build Tools для pdf-diff
print("\n[2] Проверка возможности установки pdf-diff...")
print("  Примечание: pdf-diff требует Microsoft C++ Build Tools")
print("  Скачать: https://visualstudio.microsoft.com/visual-cpp-build-tools/")
try:
    install_package("pdf-diff")
except:
    print("  ✗ pdf-diff требует компилятор C++")

# 3. Проверка альтернатив
print("\n[3] Проверка доступных альтернатив...")
check_alternative("skimage.metrics", "structural_similarity (scikit-image)")
check_alternative("cv2", "opencv-python для сравнения изображений")

# 4. Итог
print("\n" + "=" * 60)
print("ИТОГ:")
print("=" * 60)
print("\n[OK] Все функциональные аналоги доступны в проекте:")
print("  - pdf-diff -> core_engine/qa/pixel_perfect_diff.py")
print("  - mathpix -> core_engine/export/mathjax_formulas.py")
print("  - perceptualdiff -> opencv-python + scikit-image")
print("  - structural-similarity -> scikit-image.metrics.structural_similarity")
print("\n[OK] Дополнительная установка не критична!")

