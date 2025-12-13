# core_engine/qa/pdf_diff_check.py
"""
[ADVANCED PDF TRANSLATION MODE] pdf-diff для визуальной проверки качества.
Автоматическая проверка смещения элементов после перевода.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any


def check_pdf_diff(
    original_pdf: str,
    translated_pdf: str,
    output_html: str,
    threshold_px: float = 2.0
) -> Optional[Dict[str, Any]]:
    """
    Проверяет различия между оригинальным и переведенным PDF.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
        output_html: путь для сохранения HTML отчета
        threshold_px: порог смещения в пикселях (по умолчанию 2px)
    
    Returns:
        Словарь с результатами проверки или None при ошибке
    """
    # Проверяем наличие pdf-diff
    try:
        result = subprocess.run(
            ["pdf-diff", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # pdf-diff не установлен, используем fallback через PyMuPDF
        return _check_pdf_diff_pymupdf(original_pdf, translated_pdf, output_html, threshold_px)
    
    try:
        cmd = [
            "pdf-diff",
            original_pdf,
            translated_pdf,
            "--output", output_html,
            "--threshold", str(threshold_px)
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            # Парсим результаты (упрощенная версия)
            report = {
                "status": "success",
                "report_path": output_html,
                "threshold_px": threshold_px
            }
            return report
        else:
            # Fallback на PyMuPDF
            return _check_pdf_diff_pymupdf(original_pdf, translated_pdf, output_html, threshold_px)
            
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[pdf-diff] Error: {e}\n")
        return _check_pdf_diff_pymupdf(original_pdf, translated_pdf, output_html, threshold_px)


def _check_pdf_diff_pymupdf(
    original_pdf: str,
    translated_pdf: str,
    output_html: str,
    threshold_px: float
) -> Optional[Dict[str, Any]]:
    """Fallback проверка через PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        from pathlib import Path
        
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        differences = []
        max_pages = min(len(doc_orig), len(doc_trans))
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_trans = doc_trans[page_num]
            
            # Получаем текст и bbox для обеих страниц
            blocks_orig = page_orig.get_text("dict").get("blocks", [])
            blocks_trans = page_trans.get_text("dict").get("blocks", [])
            
            # Упрощенное сравнение: проверяем количество блоков и их позиции
            if len(blocks_orig) != len(blocks_trans):
                differences.append({
                    "page": page_num + 1,
                    "type": "block_count_mismatch",
                    "original_count": len(blocks_orig),
                    "translated_count": len(blocks_trans)
                })
            
            # Проверяем смещения блоков
            min_blocks = min(len(blocks_orig), len(blocks_trans))
            for i in range(min_blocks):
                bbox_orig = blocks_orig[i].get("bbox", [0, 0, 0, 0])
                bbox_trans = blocks_trans[i].get("bbox", [0, 0, 0, 0])
                
                if len(bbox_orig) >= 4 and len(bbox_trans) >= 4:
                    dx = abs(bbox_trans[0] - bbox_orig[0])
                    dy = abs(bbox_trans[1] - bbox_orig[1])
                    
                    if dx > threshold_px or dy > threshold_px:
                        differences.append({
                            "page": page_num + 1,
                            "type": "position_shift",
                            "block_index": i,
                            "dx": dx,
                            "dy": dy,
                            "threshold": threshold_px
                        })
        
        doc_orig.close()
        doc_trans.close()
        
        # Генерируем HTML отчет
        html_content = _generate_diff_html_report(differences, threshold_px)
        Path(output_html).write_text(html_content, encoding="utf-8")
        
        return {
            "status": "success",
            "report_path": output_html,
            "differences_count": len(differences),
            "differences": differences[:10],  # Первые 10 для примера
            "threshold_px": threshold_px
        }
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[pdf-diff] PyMuPDF fallback error: {e}\n")
        return None


def _generate_diff_html_report(differences: list, threshold_px: float) -> str:
    """Генерирует HTML отчет о различиях."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>PDF Diff Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .difference {{ 
                border: 1px solid #ddd; 
                padding: 10px; 
                margin: 10px 0; 
                background: #f9f9f9;
            }}
            .warning {{ color: #ff6600; }}
            .error {{ color: #cc0000; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background: #f0f0f0; }}
        </style>
    </head>
    <body>
        <h1>PDF Diff Report</h1>
        <p>Threshold: {threshold_px}px</p>
        <p>Total differences: {len(differences)}</p>
        
        <table>
            <tr>
                <th>Page</th>
                <th>Type</th>
                <th>Details</th>
            </tr>
    """
    
    for diff in differences:
        html += f"""
            <tr>
                <td>{diff.get('page', 'N/A')}</td>
                <td>{diff.get('type', 'unknown')}</td>
                <td>{str(diff)}</td>
            </tr>
        """
    
    html += """
        </table>
    </body>
    </html>
    """
    
    return html

