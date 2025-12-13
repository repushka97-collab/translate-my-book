# core_engine/production/cost_optimizer.py
"""
[PRODUCTION MODE] Cost Optimization for Cloud Deployment.
Оптимизация стоимости обработки.
"""

from typing import Dict, Any, Optional


PROVIDERS = {
    "aws": {
        "cost": 0.12,
        "max_quality": 0.94,
        "gpu_available": True,
        "name": "AWS Lambda"
    },
    "gcp": {
        "cost": 0.08,
        "max_quality": 0.96,
        "gpu_available": True,
        "name": "Google Cloud Run"
    },
    "hetzner": {
        "cost": 0.03,
        "max_quality": 0.97,
        "gpu_available": False,
        "name": "Self-hosted (Hetzner)"
    },
    "hybrid": {
        "cost": 0.05,
        "max_quality": 0.95,
        "gpu_available": True,
        "name": "Hybrid (cloud + local)"
    }
}


def needs_gpu(book_profile: Dict[str, Any]) -> bool:
    """
    Определяет, нужен ли GPU для обработки книги.
    
    Args:
        book_profile: профиль книги
    
    Returns:
        True если нужен GPU
    """
    # GPU нужен для:
    # - Учебников с формулами (MathJax/Mathpix)
    # - Книг с большим количеством изображений (DocTR)
    # - Технической документации с диаграммами
    
    if book_profile.get("formula_handling") == "mathpix":
        return True
    
    if book_profile.get("diagram_priority") == "high":
        return True
    
    return False


def select_provider(
    book_profile: Dict[str, Any],
    quality_requirements: float,
    budget: Optional[float] = None
) -> str:
    """
    Умный выбор провайдера в зависимости от требований.
    
    Args:
        book_profile: профиль книги
        quality_requirements: требуемое качество (0.0-1.0)
        budget: бюджет на обработку (опционально)
    
    Returns:
        Имя провайдера
    """
    requires_gpu = needs_gpu(book_profile)
    
    # Выбор по приоритетам
    if quality_requirements > 0.96:
        # Высокое качество - используем hetzner если не нужен GPU
        if not requires_gpu:
            return "hetzner"
        else:
            return "hybrid"
    
    elif budget and budget < 50:
        # Низкий бюджет - hetzner
        return "hetzner"
    
    elif requires_gpu:
        # Нужен GPU - GCP лучшее соотношение цена/качество
        return "gcp"
    
    else:
        # По умолчанию - hybrid
        return "hybrid"


def estimate_cost(
    provider: str,
    page_count: int,
    requires_gpu: bool = False
) -> float:
    """
    Оценивает стоимость обработки.
    
    Args:
        provider: имя провайдера
        page_count: количество страниц
        requires_gpu: требуется ли GPU
    
    Returns:
        Ориентировочная стоимость
    """
    provider_info = PROVIDERS.get(provider, PROVIDERS["hybrid"])
    
    # Базовая стоимость
    base_cost = provider_info["cost"]
    
    # Если нужен GPU и провайдер его поддерживает
    if requires_gpu and provider_info["gpu_available"]:
        base_cost *= 2.5  # GPU дороже
    
    return base_cost * page_count


def get_cost_optimization_recommendations(
    current_provider: str,
    book_profile: Dict[str, Any],
    page_count: int
) -> Dict[str, Any]:
    """
    Получает рекомендации по оптимизации стоимости.
    
    Args:
        current_provider: текущий провайдер
        book_profile: профиль книги
        page_count: количество страниц
    
    Returns:
        Рекомендации по оптимизации
    """
    requires_gpu = needs_gpu(book_profile)
    current_cost = estimate_cost(current_provider, page_count, requires_gpu)
    
    recommendations = []
    
    # Проверяем альтернативные провайдеры
    for provider_name, provider_info in PROVIDERS.items():
        if provider_name == current_provider:
            continue
        
        # Пропускаем если нужен GPU, а провайдер его не поддерживает
        if requires_gpu and not provider_info["gpu_available"]:
            continue
        
        alt_cost = estimate_cost(provider_name, page_count, requires_gpu)
        savings = current_cost - alt_cost
        
        if savings > 0:
            recommendations.append({
                "provider": provider_name,
                "provider_name": provider_info["name"],
                "estimated_cost": alt_cost,
                "savings": savings,
                "savings_percent": (savings / current_cost) * 100
            })
    
    # Сортируем по экономии
    recommendations.sort(key=lambda x: x["savings"], reverse=True)
    
    return {
        "current_provider": current_provider,
        "current_cost": current_cost,
        "recommendations": recommendations[:3]  # Топ-3 рекомендации
    }

