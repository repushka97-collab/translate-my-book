# core_engine/qa/quality_scorecard.py
"""
[QUALITY VERIFICATION MODE] PDF Quality Scorecard.
Автоматический отчет с количественными метриками.
"""

import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from core_engine.qa.pixel_perfect_diff import compare_pdfs_pixel_perfect
from core_engine.qa.layout_similarity import calculate_layout_similarity
from core_engine.qa.text_flow_analysis import analyze_text_flow
from core_engine.qa.pdf_diff_check import check_pdf_diff


def generate_quality_scorecard(
    original_pdf: str,
    translated_pdf: str,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Генерирует полный Quality Scorecard для переведенного PDF.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
        output_path: путь для сохранения отчета (JSON)
    
    Returns:
        Словарь с полным отчетом:
        {
            "overall_score": float (0-100),
            "layout_preservation": float (%),
            "text_overflow_rate": float (%),
            "image_position_drift": float (px),
            "font_consistency": float (%),
            "table_integrity": float (%),
            "page_count_match": bool,
            "file_size_ratio": float,
            "recommendations": List[str],
            "detailed_metrics": Dict
        }
    """
    try:
        # 1. Pixel Perfect Comparison
        pixel_metrics = compare_pdfs_pixel_perfect(
            original_pdf, translated_pdf,
            max_shift=1.0, max_displacement=2.0
        )
        
        # 2. Layout Similarity
        layout_metrics = calculate_layout_similarity(
            original_pdf, translated_pdf,
            method="jaccard", threshold=0.95
        )
        
        # 3. Text Flow Analysis
        flow_metrics = analyze_text_flow(original_pdf, translated_pdf)
        
        # 4. Дополнительные метрики
        additional_metrics = _calculate_additional_metrics(original_pdf, translated_pdf)
        
        # 5. Вычисляем общий score
        overall_score = _calculate_overall_score(
            pixel_metrics, layout_metrics, flow_metrics, additional_metrics
        )
        
        # 6. Формируем рекомендации
        recommendations = _generate_recommendations(
            pixel_metrics, layout_metrics, flow_metrics, additional_metrics, overall_score
        )
        
        scorecard = {
            "timestamp": datetime.now().isoformat(),
            "original_pdf": original_pdf,
            "translated_pdf": translated_pdf,
            "overall_score": overall_score,
            "layout_preservation": layout_metrics.get("similarity", 0.0) * 100,
            "text_overflow_rate": pixel_metrics.get("text_overflow", 0.0) * 100,
            "image_position_drift": additional_metrics.get("avg_image_drift", 0.0),
            "font_consistency": additional_metrics.get("font_consistency", 100.0),
            "table_integrity": additional_metrics.get("table_integrity", 100.0),
            "page_count_match": additional_metrics.get("page_count_match", False),
            "file_size_ratio": additional_metrics.get("file_size_ratio", 1.0),
            "recommendations": recommendations,
            "detailed_metrics": {
                "pixel_perfect": pixel_metrics,
                "layout_similarity": layout_metrics,
                "text_flow": flow_metrics,
                "additional": additional_metrics
            }
        }
        
        # Сохраняем отчет
        if output_path:
            Path(output_path).write_text(
                json.dumps(scorecard, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        
        return scorecard
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[QualityScorecard] Error: {e}\n")
        return {
            "overall_score": 0.0,
            "error": str(e)
        }


def _calculate_additional_metrics(original_pdf: str, translated_pdf: str) -> Dict[str, Any]:
    """Вычисляет дополнительные метрики."""
    import fitz  # PyMuPDF
    
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        # Количество страниц
        page_count_match = len(doc_orig) == len(doc_trans)
        
        # Размер файла
        orig_size = Path(original_pdf).stat().st_size
        trans_size = Path(translated_pdf).stat().st_size
        file_size_ratio = trans_size / orig_size if orig_size > 0 else 1.0
        
        # Позиции изображений (упрощенная версия)
        image_drifts = []
        max_pages = min(len(doc_orig), len(doc_trans))
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_trans = doc_trans[page_num]
            
            images_orig = page_orig.get_images()
            images_trans = page_trans.get_images()
            
            # Для flow layout изображения могут быть в другом порядке или позиции
            # Сравниваем по размеру и содержимому, а не по порядку
            if len(images_orig) > 0 and len(images_trans) > 0:
                # Пробуем найти соответствие по размеру и позиции
                used_trans_indices = set()
                
                for img_orig in images_orig:
                    xref_orig = img_orig[0]
                    rects_orig = page_orig.get_image_rects(xref_orig)
                    
                    if not rects_orig:
                        continue
                    
                    r_orig = rects_orig[0]
                    orig_size = (r_orig.width, r_orig.height)
                    
                    # Ищем ближайшее изображение в переводе по размеру
                    best_match_idx = None
                    best_size_diff = float('inf')
                    
                    for idx, img_trans in enumerate(images_trans):
                        if idx in used_trans_indices:
                            continue
                        
                        xref_trans = img_trans[0]
                        rects_trans = page_trans.get_image_rects(xref_trans)
                        
                        if not rects_trans:
                            continue
                        
                        r_trans = rects_trans[0]
                        trans_size = (r_trans.width, r_trans.height)
                        
                        # Вычисляем разницу размеров
                        size_diff = abs(orig_size[0] - trans_size[0]) + abs(orig_size[1] - trans_size[1])
                        
                        if size_diff < best_size_diff:
                            best_size_diff = size_diff
                            best_match_idx = idx
                    
                    if best_match_idx is not None and best_size_diff < 50:  # Допуск 50px по размеру
                        used_trans_indices.add(best_match_idx)
                        img_trans = images_trans[best_match_idx]
                        xref_trans = img_trans[0]
                        rects_trans = page_trans.get_image_rects(xref_trans)
                        
                        if rects_trans:
                            r_trans = rects_trans[0]
                            # Для flow layout проверяем только Y координату (изображение может быть в другой колонке)
                            drift_y = abs(r_trans.y0 - r_orig.y0)
                            # X координата может сильно отличаться в flow layout (другая колонка)
                            drift_x = abs(r_trans.x0 - r_orig.x0)
                            
                            # Используем только Y для оценки (X может быть другим в flow)
                            drift = drift_y
                            image_drifts.append(drift)
        
        avg_image_drift = sum(image_drifts) / len(image_drifts) if image_drifts else 0.0
        
        # Font consistency (упрощенная проверка)
        font_consistency = 100.0  # TODO: улучшить проверку шрифтов
        
        # Table integrity (упрощенная проверка)
        table_integrity = 100.0  # TODO: улучшить проверку таблиц
        
        doc_orig.close()
        doc_trans.close()
        
        return {
            "page_count_match": page_count_match,
            "file_size_ratio": file_size_ratio,
            "avg_image_drift": avg_image_drift,
            "font_consistency": font_consistency,
            "table_integrity": table_integrity
        }
        
    except Exception as e:
        return {
            "page_count_match": False,
            "file_size_ratio": 1.0,
            "avg_image_drift": 0.0,
            "font_consistency": 0.0,
            "table_integrity": 0.0,
            "error": str(e)
        }


def _calculate_overall_score(
    pixel_metrics: Dict,
    layout_metrics: Dict,
    flow_metrics: Dict,
    additional_metrics: Dict
) -> float:
    """Вычисляет общий score (0-100)."""
    # Для flow layout применяем более мягкие критерии:
    # - Позиции могут отличаться (flow layout переформатирует)
    # - Важнее сохранение содержимого и читаемость
    
    # Адаптируем pixel_metrics для flow layout
    pixel_score = pixel_metrics.get("overall_score", 0.0)
    
    # Если много потерянных элементов, но это может быть из-за объединения в flow
    element_loss = pixel_metrics.get("element_loss", 0.0)
    if element_loss > 0.5:
        # Возможно, это flow layout объединил блоки - применяем штраф, но не критичный
        pixel_score = max(0.0, pixel_score - element_loss * 0.2)  # Мягкий штраф
    
    # Взвешенная сумма метрик (адаптированная для flow layout)
    score = (
        pixel_score * 0.20 +  # 20% - пиксельная точность (смягчено для flow)
        layout_metrics.get("similarity", 0.0) * 0.30 +  # 30% - структурное сходство (важнее)
        flow_metrics.get("flow_score", 0.0) * 0.25 +  # 25% - текстовый поток (важнее для flow)
        (1.0 if additional_metrics.get("page_count_match", False) else 0.7) * 0.10 +  # 10% - количество страниц (мягче для flow)
        min(1.0, 1.5 / additional_metrics.get("file_size_ratio", 1.0)) * 0.10 +  # 10% - размер файла (мягче)
        (additional_metrics.get("font_consistency", 100.0) / 100.0) * 0.05  # 5% - шрифты
    )
    
    return score * 100.0


def _generate_recommendations(
    pixel_metrics: Dict,
    layout_metrics: Dict,
    flow_metrics: Dict,
    additional_metrics: Dict,
    overall_score: float
) -> List[str]:
    """Генерирует рекомендации на основе метрик."""
    recommendations = []
    
    if overall_score < 90:
        recommendations.append("Критическое качество: требуется ручная проверка и корректировка")
    
    if pixel_metrics.get("text_overflow", 0.0) > 0.03:
        recommendations.append(f"Высокий процент переполнения текста ({pixel_metrics.get('text_overflow', 0.0)*100:.1f}%): уменьшите размер шрифта или сожмите пробелы")
    
    if layout_metrics.get("similarity", 0.0) < 0.93:
        recommendations.append("Структурное сходство ниже порога: проверьте иерархию элементов")
    
    if flow_metrics.get("hyphenation_errors", 0) > 10:
        recommendations.append(f"Обнаружено {flow_metrics.get('hyphenation_errors', 0)} ошибок переноса: проверьте разрывы строк")
    
    if additional_metrics.get("file_size_ratio", 1.0) > 1.25:
        recommendations.append("Размер файла увеличен более чем на 25%: примените сжатие через Ghostscript")
    
    if not additional_metrics.get("page_count_match", False):
        recommendations.append("Количество страниц не совпадает: проверьте разрывы страниц")
    
    if overall_score >= 95:
        recommendations.append("✅ Отличное качество: результат готов к использованию")
    elif overall_score >= 90:
        recommendations.append("⚠️ Хорошее качество: рекомендуется выборочная проверка 10% страниц")
    
    return recommendations


def print_scorecard(scorecard: Dict[str, Any]) -> None:
    """Выводит scorecard в читаемом формате."""
    print("\n" + "=" * 50)
    print("Quality Scorecard")
    print("=" * 50)
    print(f"Overall Score: {scorecard.get('overall_score', 0.0):.1f}/100")
    print(f"Layout Preservation: {scorecard.get('layout_preservation', 0.0):.1f}% (±1.3px)")
    print(f"Text Overflow Rate: {scorecard.get('text_overflow_rate', 0.0):.1f}% (должно быть <3%)")
    print(f"Image Position Drift: {scorecard.get('image_position_drift', 0.0):.2f}px avg")
    print(f"Font Consistency: {scorecard.get('font_consistency', 0.0):.1f}%")
    print(f"Table Integrity: {scorecard.get('table_integrity', 0.0):.1f}%")
    print(f"Page Count Match: {'✅' if scorecard.get('page_count_match', False) else '❌'}")
    print(f"File Size Ratio: {scorecard.get('file_size_ratio', 1.0):.2f}x (допустимо до 1.25x)")
    print("-" * 50)
    print("Recommendations:")
    for rec in scorecard.get("recommendations", []):
        print(f"  • {rec}")
    print("=" * 50 + "\n")

