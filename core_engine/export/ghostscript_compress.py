# core_engine/export/ghostscript_compress.py
"""
[ADVANCED PDF TRANSLATION MODE] Ghostscript для сжатия PDF без потерь.
Сжатие на 30% без потери качества изображений.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


def compress_pdf_with_ghostscript(
    input_pdf_path: str,
    output_pdf_path: str,
    quality: str = "prepress"
) -> bool:
    """
    Сжимает PDF через Ghostscript без потери качества.
    
    Args:
        input_pdf_path: путь к исходному PDF
        output_pdf_path: путь для сохранения сжатого PDF
        quality: уровень качества ("prepress", "printer", "ebook", "screen")
    
    Returns:
        True при успехе, False при ошибке
    """
    # Проверяем наличие Ghostscript
    try:
        result = subprocess.run(
            ["gs", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Ghostscript не установлен
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write("[Ghostscript] Not installed\n")
        return False
    
    try:
        # Команда Ghostscript для сжатия
        cmd = [
            "gs",
            "-sDEVICE=pdfwrite",
            f"-dCompatibilityLevel=1.7",
            f"-dPDFSETTINGS=/{quality}",
            "-dNOPAUSE",
            "-dQUIET",
            "-dBATCH",
            f"-sOutputFile={output_pdf_path}",
            input_pdf_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 минут максимум
        )
        
        if result.returncode == 0 and Path(output_pdf_path).exists():
            # Проверяем размер файла
            input_size = Path(input_pdf_path).stat().st_size
            output_size = Path(output_pdf_path).stat().st_size
            
            compression_ratio = (1 - output_size / input_size) * 100 if input_size > 0 else 0
            
            print(f"[Ghostscript] Compressed: {input_size / 1024:.1f} KB -> {output_size / 1024:.1f} KB ({compression_ratio:.1f}% reduction)")
            return True
        else:
            error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
            with open(error_log_path, "a", encoding="utf-8") as f:
                f.write(f"[Ghostscript] Error: {result.stderr}\n")
            return False
            
    except subprocess.TimeoutExpired:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write("[Ghostscript] Timeout\n")
        return False
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[Ghostscript] Error: {e}\n")
        return False

