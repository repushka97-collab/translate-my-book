# core_engine/qa/heatmap_diff.py
"""
[QUALITY VERIFICATION MODE] Color-Coded Difference Maps.
Генерация тепловых карт различий через OpenCV.
"""

import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import fitz  # PyMuPDF


def generate_heatmap_diff(
    original_pdf: str,
    translated_pdf: str,
    output_dir: str,
    threshold_green: float = 2.0,
    threshold_yellow: float = 5.0
) -> Dict[str, Any]:
    """
    Генерирует тепловые карты различий между оригиналом и переводом.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
        output_dir: директория для сохранения heatmaps
        threshold_green: порог для зеленого (0-2px)
        threshold_yellow: порог для желтого (2-5px)
    
    Returns:
        Словарь с результатами:
        {
            "heatmaps_generated": int,
            "severity_scores": List[float],
            "critical_pages": List[int],
            "output_dir": str
        }
    """
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write("[HeatmapDiff] OpenCV not installed\n")
        return {
            "heatmaps_generated": 0,
            "severity_scores": [],
            "critical_pages": [],
            "output_dir": output_dir,
            "error": "OpenCV not installed"
        }
    
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        max_pages = min(len(doc_orig), len(doc_trans))
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        heatmaps_generated = 0
        severity_scores = []
        critical_pages = []
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_trans = doc_trans[page_num]
            
            # Рендерим страницы в изображения
            mat_orig = page_orig.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x для лучшего качества
            mat_trans = page_trans.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            # Конвертируем в numpy массивы
            img_orig = np.frombuffer(mat_orig.samples, dtype=np.uint8).reshape(
                mat_orig.height, mat_orig.width, mat_orig.n
            )
            img_trans = np.frombuffer(mat_trans.samples, dtype=np.uint8).reshape(
                mat_trans.height, mat_trans.width, mat_trans.n
            )
            
            # Приводим к одинаковому размеру
            if img_orig.shape != img_trans.shape:
                # Изменяем размер меньшего изображения
                if img_orig.shape[0] * img_orig.shape[1] < img_trans.shape[0] * img_trans.shape[1]:
                    img_orig = cv2.resize(img_orig, (img_trans.shape[1], img_trans.shape[0]))
                else:
                    img_trans = cv2.resize(img_trans, (img_orig.shape[1], img_orig.shape[0]))
            
            # Конвертируем в grayscale для сравнения
            if len(img_orig.shape) == 3:
                gray_orig = cv2.cvtColor(img_orig, cv2.COLOR_RGB2GRAY)
            else:
                gray_orig = img_orig
            
            if len(img_trans.shape) == 3:
                gray_trans = cv2.cvtColor(img_trans, cv2.COLOR_RGB2GRAY)
            else:
                gray_trans = img_trans
            
            # Вычисляем разницу
            diff = cv2.absdiff(gray_orig, gray_trans)
            
            # Создаем цветовую карту
            # Нормализуем разницу для визуализации
            diff_normalized = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
            
            # Применяем цветовую карту (JET для тепловой карты)
            heatmap = cv2.applyColorMap(diff_normalized, cv2.COLORMAP_JET)
            
            # Вычисляем severity score
            severity_score = _calculate_severity_score(diff, threshold_green, threshold_yellow)
            severity_scores.append(severity_score)
            
            if severity_score < 0.7:  # Критическая страница
                critical_pages.append(page_num + 1)
            
            # Сохраняем heatmap
            heatmap_path = output_path / f"heatmap_page_{page_num + 1:04d}.png"
            cv2.imwrite(str(heatmap_path), heatmap)
            heatmaps_generated += 1
        
        doc_orig.close()
        doc_trans.close()
        
        return {
            "heatmaps_generated": heatmaps_generated,
            "severity_scores": severity_scores,
            "critical_pages": critical_pages,
            "output_dir": str(output_path),
            "avg_severity": sum(severity_scores) / len(severity_scores) if severity_scores else 0.0
        }
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[HeatmapDiff] Error: {e}\n")
        return {
            "heatmaps_generated": 0,
            "severity_scores": [],
            "critical_pages": [],
            "output_dir": output_dir,
            "error": str(e)
        }


def _calculate_severity_score(
    diff_image,
    threshold_green: float,
    threshold_yellow: float
) -> float:
    """Вычисляет severity score на основе разницы (0.0-1.0)."""
    try:
        import cv2  # type: ignore
        import numpy as np  # type: ignore
        
        # Вычисляем статистику разницы
        mean_diff = np.mean(diff_image)
        max_diff = np.max(diff_image)
        
        # Нормализуем (0-255 -> 0-1)
        mean_normalized = mean_diff / 255.0
        max_normalized = max_diff / 255.0
        
        # Вычисляем score (чем меньше разница, тем выше score)
        score = 1.0 - (mean_normalized * 0.7 + max_normalized * 0.3)
        
        return max(0.0, min(1.0, score))
        
    except Exception:
        return 0.5  # Fallback

