# core_engine/production/security_compliance.py
"""
[PRODUCTION MODE] Security & Compliance Module.
Защита конфиденциальных данных и соответствие GDPR/CCPA.
"""

import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
import fitz
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


# Паттерны для обнаружения конфиденциальных данных
CONFIDENTIAL_PATTERNS = [
    (r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "credit_card"),  # кредитные карты
    (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "email"),        # email
    (r"\b\d{3}[-\.\s]??\d{3}[-\.\s]??\d{4}\b", "phone"),            # телефоны
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn"),                               # SSN (US)
    (r"\b[A-Z]{2}\d{6,9}\b", "passport"),                            # паспортные номера
]


def sanitize_pdf(input_pdf: str, output_pdf: str) -> Dict[str, Any]:
    """
    Удаление метаданных и конфиденциальной информации из PDF.
    
    Args:
        input_pdf: путь к исходному PDF
        output_pdf: путь для сохранения очищенного PDF
    
    Returns:
        Словарь с результатами очистки
    """
    try:
        doc = fitz.open(input_pdf)
        
        # Удаление метаданных
        doc.set_metadata({})
        
        redacted_count = 0
        found_patterns = {}
        
        # Поиск и замена конфиденциальных данных
        for page in doc:
            for pattern, pattern_type in CONFIDENTIAL_PATTERNS:
                text_instances = page.search_for(pattern, flags=fitz.TEXT_PRESERVE_WHITESPACE)
                
                if text_instances:
                    if pattern_type not in found_patterns:
                        found_patterns[pattern_type] = 0
                    
                    for inst in text_instances:
                        # Затирание белым цветом
                        page.add_redact_annot(inst, fill=(1, 1, 1))
                        redacted_count += 1
                        found_patterns[pattern_type] += 1
            
            # Применяем затирания
            page.apply_redactions()
        
        # Удаление embedded files
        embedded_files_count = len(doc.embfile_names)
        for i in range(embedded_files_count):
            try:
                doc.delete_embedded_file(i)
            except Exception:
                pass
        
        # Сохранение очищенного PDF
        doc.save(output_pdf, garbage=4, deflate=True)
        doc.close()
        
        return {
            "success": True,
            "redacted_count": redacted_count,
            "found_patterns": found_patterns,
            "embedded_files_removed": embedded_files_count,
            "output_path": output_pdf
        }
        
    except Exception as e:
        logger.error(f"Error sanitizing PDF: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def detect_personal_data(pdf_path: str) -> Dict[str, Any]:
    """
    Обнаруживает персональные данные в PDF.
    
    Args:
        pdf_path: путь к PDF файлу
    
    Returns:
        Словарь с обнаруженными персональными данными
    """
    try:
        doc = fitz.open(pdf_path)
        
        detected_data = {
            "credit_cards": [],
            "emails": [],
            "phones": [],
            "ssns": [],
            "passports": []
        }
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            # Поиск по паттернам
            for pattern, pattern_type in CONFIDENTIAL_PATTERNS:
                matches = re.findall(pattern, text, re.IGNORECASE)
                
                if matches:
                    if pattern_type == "credit_card":
                        detected_data["credit_cards"].extend(matches)
                    elif pattern_type == "email":
                        detected_data["emails"].extend(matches)
                    elif pattern_type == "phone":
                        detected_data["phones"].extend(matches)
                    elif pattern_type == "ssn":
                        detected_data["ssns"].extend(matches)
                    elif pattern_type == "passport":
                        detected_data["passports"].extend(matches)
        
        doc.close()
        
        # Удаляем дубликаты
        for key in detected_data:
            detected_data[key] = list(set(detected_data[key]))
        
        return detected_data
        
    except Exception as e:
        logger.error(f"Error detecting personal data: {e}")
        return {}


def audit_operation(
    operation_type: str,
    document_id: str,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> None:
    """
    Аудит всех операций с документами (GDPR/CCPA compliance).
    
    Args:
        operation_type: тип операции (upload, translate, delete, etc.)
        document_id: ID документа
        user_id: ID пользователя (опционально)
        details: дополнительные детали (опционально)
    """
    audit_log_path = Path(os.getenv("AUDIT_LOG_PATH", "audit.log"))
    
    audit_entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation_type,
        "document_id": document_id,
        "user_id": user_id,
        "details": details or {}
    }
    
    try:
        with open(audit_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Error writing audit log: {e}")


def should_delete_data(document_id: str, retention_days: int = 30) -> bool:
    """
    Определяет, нужно ли удалить данные по истечении срока хранения.
    
    Args:
        document_id: ID документа
        retention_days: срок хранения в днях (по умолчанию 30)
    
    Returns:
        True если данные нужно удалить
    """
    # В реальной реализации здесь будет проверка даты создания документа
    # Для примера возвращаем False
    return False


def auto_delete_expired_data(data_dir: str, retention_days: int = 30) -> Dict[str, Any]:
    """
    Автоматическое удаление данных после истечения срока хранения.
    
    Args:
        data_dir: директория с данными
        retention_days: срок хранения в днях
    
    Returns:
        Результат удаления
    """
    try:
        data_path = Path(data_dir)
        if not data_path.exists():
            return {"success": False, "error": "Data directory not found"}
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        
        # Удаляем файлы старше retention_days
        for file_path in data_path.rglob("*"):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted expired file: {file_path}")
        
        return {
            "success": True,
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error auto-deleting expired data: {e}")
        return {
            "success": False,
            "error": str(e)
        }

