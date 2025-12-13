# core_engine/production/disaster_recovery.py
"""
[PRODUCTION MODE] Disaster Recovery & Rollback System.
Система аварийного восстановления при критических ошибках.
"""

import os
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def try_adobe_recovery(original_pdf: str, failed_pdf: str, error_log: str) -> Optional[Dict[str, Any]]:
    """
    Попытка восстановления через Adobe PDF Library SDK.
    (Заглушка - в реальности нужен платный SDK)
    
    Args:
        original_pdf: путь к оригинальному PDF
        failed_pdf: путь к неудачно переведенному PDF
        error_log: путь к логу ошибок
    
    Returns:
        Результат восстановления или None
    """
    # В реальной реализации здесь будет интеграция с Adobe SDK
    logger.warning("Adobe SDK recovery not implemented (requires paid license)")
    return None


def generate_manual_tasks(original_pdf: str, failed_pdf: str, error_log: str) -> Dict[str, Any]:
    """
    Генерирует задачи для ручного исправления.
    
    Args:
        original_pdf: путь к оригинальному PDF
        failed_pdf: путь к неудачно переведенному PDF
        error_log: путь к логу ошибок
    
    Returns:
        Словарь с задачами для человека
    """
    try:
        import fitz
        
        tasks = []
        
        doc_orig = fitz.open(original_pdf)
        doc_failed = fitz.open(failed_pdf)
        
        max_pages = min(len(doc_orig), len(doc_failed))
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_failed = doc_failed[page_num]
            
            # Упрощенная проверка ошибок
            text_orig = page_orig.get_text()
            text_failed = page_failed.get_text()
            
            if len(text_failed) < len(text_orig) * 0.5:  # Потеряно более 50% текста
                task = {
                    "page_number": page_num + 1,
                    "priority": "high",
                    "issue": "significant_text_loss",
                    "original_length": len(text_orig),
                    "translated_length": len(text_failed),
                    "loss_percentage": (1 - len(text_failed) / len(text_orig)) * 100
                }
                tasks.append(task)
        
        doc_orig.close()
        doc_failed.close()
        
        return {
            "success": True,
            "tasks": tasks,
            "total_tasks": len(tasks),
            "output_format": "manual_review_required"
        }
        
    except Exception as e:
        logger.error(f"Error generating manual tasks: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def extract_text_only(original_pdf: str, failed_pdf: str, error_log: str) -> Dict[str, Any]:
    """
    Экстренный режим: извлечение только текста без верстки.
    
    Args:
        original_pdf: путь к оригинальному PDF
        failed_pdf: путь к неудачно переведенному PDF
        error_log: путь к логу ошибок
    
    Returns:
        Результат экстренного режима
    """
    try:
        import fitz
        
        doc_orig = fitz.open(original_pdf)
        
        # Создаем простой текстовый файл с переводом
        output_text_path = Path(failed_pdf).with_suffix(".txt")
        
        with open(output_text_path, "w", encoding="utf-8") as f:
            for page_num in range(len(doc_orig)):
                page = doc_orig[page_num]
                text = page.get_text()
                f.write(f"\n--- Page {page_num + 1} ---\n")
                f.write(text)
                f.write("\n")
        
        doc_orig.close()
        
        return {
            "success": True,
            "output_path": str(output_text_path),
            "mode": "text_only",
            "note": "Layout not preserved - text only extraction"
        }
        
    except Exception as e:
        logger.error(f"Error in text-only extraction: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def validate_recovery(result: Dict[str, Any]) -> bool:
    """
    Проверяет валидность результата восстановления.
    
    Args:
        result: результат восстановления
    
    Returns:
        True если результат валиден
    """
    if not result.get("success"):
        return False
    
    # Дополнительные проверки в зависимости от режима
    if result.get("mode") == "text_only":
        return Path(result.get("output_path", "")).exists()
    
    return True


def disaster_recovery(
    original_pdf: str,
    failed_translated_pdf: str,
    error_log: str
) -> Dict[str, Any]:
    """
    Система аварийного восстановления при критических ошибках.
    
    Args:
        original_pdf: путь к оригинальному PDF
        failed_translated_pdf: путь к неудачно переведенному PDF
        error_log: путь к логу ошибок
    
    Returns:
        Результат восстановления
    """
    recovery_strategies: List[tuple] = [
        ("adobe_sdk", try_adobe_recovery),
        ("manual_fallback", generate_manual_tasks),
        ("text_only", extract_text_only)
    ]
    
    for strategy_name, strategy_func in recovery_strategies:
        try:
            logger.info(f"Attempting recovery via {strategy_name}")
            result = strategy_func(original_pdf, failed_translated_pdf, error_log)
            
            if validate_recovery(result):
                logger.info(f"Recovery via {strategy_name} successful!")
                return {
                    "success": True,
                    "strategy": strategy_name,
                    "result": result
                }
        
        except Exception as e:
            logger.error(f"Strategy {strategy_name} failed: {e}")
            continue
    
    # Если все стратегии провалились
    raise RuntimeError("All recovery strategies exhausted. Manual intervention required.")


class CriticalRecoveryFailure(Exception):
    """Исключение при полном провале восстановления."""
    pass

