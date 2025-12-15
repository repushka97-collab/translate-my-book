#!/usr/bin/env python3
"""Скрипт для исправления кодировки во всех Python файлах"""

import sys
import os
from pathlib import Path

# Исправление кодировки для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def add_encoding_fix_to_file(file_path: Path) -> bool:
    """Добавляет исправление кодировки в начало файла если его там нет."""
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Проверяем, есть ли уже исправление
        if 'sys.stdout.reconfigure' in content or 'sys.stderr.reconfigure' in content:
            return False  # Уже есть
        
        # Проверяем, есть ли import sys
        if 'import sys' not in content:
            return False  # Нет sys, пропускаем
        
        # Находим место после import sys
        lines = content.split('\n')
        new_lines = []
        sys_import_found = False
        encoding_fix_added = False
        
        for i, line in enumerate(lines):
            new_lines.append(line)
            
            # Ищем import sys
            if 'import sys' in line and not sys_import_found:
                sys_import_found = True
                # Добавляем исправление кодировки после import sys
                if i + 1 < len(lines) and lines[i + 1].strip() == '':
                    # Если следующая строка пустая, добавляем туда
                    continue
                else:
                    # Добавляем после текущей строки
                    new_lines.append('')
                    new_lines.append('# Исправление кодировки для Windows')
                    new_lines.append('if sys.platform == "win32":')
                    new_lines.append('    try:')
                    new_lines.append('        sys.stdout.reconfigure(encoding=\'utf-8\')')
                    new_lines.append('        sys.stderr.reconfigure(encoding=\'utf-8\')')
                    new_lines.append('    except Exception:')
                    new_lines.append('        pass  # Если не поддерживается, игнорируем')
                    encoding_fix_added = True
        
        if encoding_fix_added:
            file_path.write_text('\n'.join(new_lines), encoding='utf-8')
            return True
        
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

# Основные скрипты для исправления
main_scripts = [
    "run_pipeline.py",
    "run_all_pdfs.py",
]

for script in main_scripts:
    script_path = Path(script)
    if script_path.exists():
        if add_encoding_fix_to_file(script_path):
            print(f"Fixed encoding in {script}")
        else:
            print(f"Encoding fix already present or not needed in {script}")

print("Encoding fixes applied!")

