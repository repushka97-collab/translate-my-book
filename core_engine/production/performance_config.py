# core_engine/production/performance_config.py
"""
[PRODUCTION MODE] Performance Tuning Configuration.
Оптимизация производительности для продакшена.
"""

import os
from typing import Dict, Any, Optional


def get_performance_config() -> Dict[str, Any]:
    """
    Возвращает оптимальную конфигурацию производительности.
    
    Returns:
        Словарь с настройками производительности
    """
    # Определяем доступную память
    try:
        import psutil
        total_memory_gb = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        total_memory_gb = 16  # По умолчанию
    
    # Настройки в зависимости от доступной памяти
    if total_memory_gb >= 64:
        max_workers = 16
        memory_limit = "48GB"
    elif total_memory_gb >= 32:
        max_workers = 8
        memory_limit = "24GB"
    elif total_memory_gb >= 16:
        max_workers = 4
        memory_limit = "12GB"
    else:
        max_workers = 2
        memory_limit = "8GB"
    
    # Проверяем наличие GPU
    gpu_available = False
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        pass
    
    config = {
        "max_workers": int(os.getenv("MAX_WORKERS", max_workers)),
        "chunk_size": int(os.getenv("CHUNK_SIZE", 50)),
        "ocr_cache": os.getenv("OCR_CACHE", "1") == "1",
        "font_substitution": {
            "Helvetica": "DejaVuSans",
            "Times-Roman": "LiberationSerif",
            "Courier": "LiberationMono"
        },
        "memory_limit": os.getenv("MEMORY_LIMIT", memory_limit),
        "gpu_acceleration": gpu_available and os.getenv("GPU_ACCELERATION", "1") == "1"
    }
    
    return config


def apply_performance_config(config: Dict[str, Any]) -> None:
    """
    Применяет конфигурацию производительности к системе.
    
    Args:
        config: конфигурация производительности
    """
    # Устанавливаем переменные окружения
    os.environ["MAX_WORKERS"] = str(config["max_workers"])
    os.environ["CHUNK_SIZE"] = str(config["chunk_size"])
    os.environ["OCR_CACHE"] = "1" if config["ocr_cache"] else "0"
    os.environ["MEMORY_LIMIT"] = config["memory_limit"]
    os.environ["GPU_ACCELERATION"] = "1" if config["gpu_acceleration"] else "0"
    
    # Логируем конфигурацию
    print(f"      Performance Config:")
    print(f"        Max Workers: {config['max_workers']}")
    print(f"        Chunk Size: {config['chunk_size']}")
    print(f"        Memory Limit: {config['memory_limit']}")
    print(f"        GPU Acceleration: {config['gpu_acceleration']}")

