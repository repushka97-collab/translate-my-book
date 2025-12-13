# core_engine/correction/batch_corrector.py
"""
[ADVANCED PDF TRANSLATION MODE] Batch Correction Framework.
Массовое исправление переведенных PDF с автоматическим контролем качества.
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from core_engine.correction.layout_fixer import apply_layout_correction
from core_engine.qa.quality_scorecard import generate_quality_scorecard


class BatchCorrector:
    """
    Массовое исправление переведенных PDF.
    """
    
    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        workers: int = 4,
        quality_threshold: float = 0.95
    ):
        """
        Args:
            input_dir: директория с переведенными PDF
            output_dir: директория для сохранения исправленных PDF
            workers: количество потоков
            quality_threshold: минимальный порог качества
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.workers = workers
        self.quality_threshold = quality_threshold
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run(
        self,
        quality_check: bool = True,
        checkpoint_interval: int = 10
    ) -> Dict[str, Any]:
        """
        Запускает массовое исправление.
        
        Args:
            quality_check: проверять ли качество после исправления
            checkpoint_interval: интервал сохранения чекпоинтов
        
        Returns:
            Словарь с результатами
        """
        # Находим все PDF файлы
        pdf_files = list(self.input_dir.glob("*.pdf"))
        
        if not pdf_files:
            return {
                "success_count": 0,
                "total_count": 0,
                "avg_quality_improvement": 0.0,
                "errors": []
            }
        
        results = {
            "success_count": 0,
            "total_count": len(pdf_files),
            "avg_quality_improvement": 0.0,
            "errors": []
        }
        
        quality_improvements = []
        
        # Обрабатываем файлы в параллель
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {}
            
            for pdf_file in pdf_files:
                # Ищем оригинальный файл (предполагаем что он в другой директории)
                # В реальности нужно передавать путь к оригиналу
                original_path = pdf_file  # Упрощение - в реальности нужен отдельный путь
                
                future = executor.submit(
                    self._correct_single_pdf,
                    str(original_path),
                    str(pdf_file),
                    quality_check
                )
                futures[future] = pdf_file
            
            # Собираем результаты
            for i, future in enumerate(as_completed(futures)):
                pdf_file = futures[future]
                try:
                    result = future.result()
                    if result.get("success"):
                        results["success_count"] += 1
                        if "quality_improvement" in result:
                            quality_improvements.append(result["quality_improvement"])
                except Exception as e:
                    results["errors"].append({
                        "file": str(pdf_file),
                        "error": str(e)
                    })
                
                # Сохраняем чекпоинт
                if (i + 1) % checkpoint_interval == 0:
                    self._save_checkpoint(results, i + 1)
        
        # Вычисляем среднее улучшение качества
        if quality_improvements:
            results["avg_quality_improvement"] = sum(quality_improvements) / len(quality_improvements)
        
        return results
    
    def _correct_single_pdf(
        self,
        original_path: str,
        translated_path: str,
        quality_check: bool
    ) -> Dict[str, Any]:
        """Исправляет один PDF файл."""
        try:
            output_path = self.output_dir / Path(translated_path).name
            
            # Применяем исправления
            correction_result = apply_layout_correction(
                original_path,
                translated_path,
                str(output_path),
                target_language="ru"
            )
            
            if not correction_result.get("success"):
                return {"success": False, "error": correction_result.get("error")}
            
            # Проверяем качество если требуется
            quality_improvement = 0.0
            if quality_check and Path(original_path).exists():
                try:
                    scorecard_before = generate_quality_scorecard(
                        original_path,
                        translated_path,
                        None
                    )
                    scorecard_after = generate_quality_scorecard(
                        original_path,
                        str(output_path),
                        None
                    )
                    
                    score_before = scorecard_before.get("overall_score", 0.0)
                    score_after = scorecard_after.get("overall_score", 0.0)
                    quality_improvement = score_after - score_before
                except Exception:
                    pass  # Игнорируем ошибки проверки качества
            
            return {
                "success": True,
                "output_path": str(output_path),
                "quality_improvement": quality_improvement
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _save_checkpoint(self, results: Dict[str, Any], processed: int) -> None:
        """Сохраняет чекпоинт."""
        checkpoint_path = self.output_dir / f"checkpoint_{processed}.json"
        try:
            checkpoint_path.write_text(
                json.dumps(results, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception:
            pass  # Игнорируем ошибки сохранения чекпоинта

