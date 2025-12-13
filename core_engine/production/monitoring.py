# core_engine/production/monitoring.py
"""
[PRODUCTION MODE] Production Monitoring Dashboard.
Мониторинг системы перевода PDF.
"""

import os
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from datetime import datetime


class MetricsCollector:
    """Сборщик метрик для мониторинга."""
    
    def __init__(self, metrics_file: str = "metrics.json"):
        """
        Args:
            metrics_file: путь к файлу метрик
        """
        self.metrics_file = Path(metrics_file)
        self.metrics = {
            "system_health": {},
            "quality_metrics": {},
            "business_metrics": {}
        }
    
    def record_processing_time(self, book_id: str, processing_time: float) -> None:
        """Записывает время обработки книги."""
        if "processing_times" not in self.metrics["business_metrics"]:
            self.metrics["business_metrics"]["processing_times"] = []
        
        self.metrics["business_metrics"]["processing_times"].append({
            "book_id": book_id,
            "time": processing_time,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_quality_score(self, book_id: str, quality_score: float) -> None:
        """Записывает оценку качества."""
        if "quality_scores" not in self.metrics["quality_metrics"]:
            self.metrics["quality_metrics"]["quality_scores"] = []
        
        self.metrics["quality_metrics"]["quality_scores"].append({
            "book_id": book_id,
            "score": quality_score,
            "timestamp": datetime.now().isoformat()
        })
    
    def record_error(self, error_type: str, error_message: str) -> None:
        """Записывает ошибку."""
        if "errors" not in self.metrics["system_health"]:
            self.metrics["system_health"]["errors"] = []
        
        self.metrics["system_health"]["errors"].append({
            "type": error_type,
            "message": error_message,
            "timestamp": datetime.now().isoformat()
        })
    
    def save_metrics(self) -> None:
        """Сохраняет метрики в файл."""
        try:
            with open(self.metrics_file, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving metrics: {e}")
    
    def get_avg_quality_score(self) -> float:
        """Возвращает среднюю оценку качества."""
        scores = self.metrics["quality_metrics"].get("quality_scores", [])
        if not scores:
            return 0.0
        
        return sum(s["score"] for s in scores) / len(scores)
    
    def get_avg_processing_time(self) -> float:
        """Возвращает среднее время обработки."""
        times = self.metrics["business_metrics"].get("processing_times", [])
        if not times:
            return 0.0
        
        return sum(t["time"] for t in times) / len(times)
    
    def get_error_rate(self, time_window_minutes: int = 5) -> float:
        """Возвращает частоту ошибок за последние N минут."""
        errors = self.metrics["system_health"].get("errors", [])
        if not errors:
            return 0.0
        
        # Фильтруем ошибки за последние N минут
        cutoff_time = time.time() - (time_window_minutes * 60)
        recent_errors = [
            e for e in errors
            if datetime.fromisoformat(e["timestamp"]).timestamp() > cutoff_time
        ]
        
        return len(recent_errors) / time_window_minutes  # ошибок в минуту


# Глобальный экземпляр сборщика метрик
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Получает глобальный экземпляр сборщика метрик."""
    global _metrics_collector
    if _metrics_collector is None:
        metrics_file = os.getenv("METRICS_FILE", "metrics.json")
        _metrics_collector = MetricsCollector(metrics_file)
    return _metrics_collector


def generate_grafana_queries() -> Dict[str, Any]:
    """
    Генерирует запросы для Grafana dashboard.
    
    Returns:
        Словарь с запросами для Grafana
    """
    return {
        "system_health": {
            "cpu_usage": "avg(pdf_translation_cpu_usage{service='worker'})",
            "memory_usage": "avg(pdf_translation_memory_usage{service='worker'})",
            "queue_backlog": "sum(pdf_translation_queue_length)",
            "error_rate": "rate(pdf_translation_errors_total[5m])"
        },
        "quality_metrics": {
            "avg_quality_score": "avg(pdf_quality_score)",
            "pages_below_threshold": "count(pdf_quality_score < 0.90)",
            "worst_performing_book": "bottomk(1, pdf_quality_score{book=~'.*'})"
        },
        "business_metrics": {
            "books_processed_24h": "increase(pdf_books_processed_total[24h])",
            "avg_processing_time": "avg(pdf_processing_time_seconds)",
            "cost_per_book": "avg(pdf_cost_per_book)"
        }
    }


def generate_alert_rules() -> List[Dict[str, Any]]:
    """
    Генерирует правила алертов для мониторинга.
    
    Returns:
        Список правил алертов
    """
    return [
        {
            "name": "CRITICAL_QUALITY_DROP",
            "condition": "avg(pdf_quality_score) < 0.85",
            "duration": "5m",
            "channels": ["@admin", "#pdf-team"],
            "message": "CRITICAL: Quality dropped below 85% across all books!"
        },
        {
            "name": "QUEUE_BACKLOG_CRITICAL",
            "condition": "pdf_translation_queue_length > 200",
            "duration": "10m",
            "channels": ["@devops"],
            "message": "ALERT: Processing queue exceeded 200 books. Scaling required!"
        },
        {
            "name": "COST_SPIKE",
            "condition": "increase(pdf_cost_per_book[1h]) > 0.5",
            "duration": "15m",
            "channels": ["@finance", "@admin"],
            "message": "WARNING: Cost per book increased by 50% in the last hour!"
        }
    ]

