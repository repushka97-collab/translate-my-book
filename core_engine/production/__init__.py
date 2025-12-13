# core_engine/production/__init__.py
"""
[PRODUCTION MODE] Production-ready modules for PDF translation.
"""

from core_engine.production.performance_config import get_performance_config, apply_performance_config
from core_engine.production.book_profiles import (
    BOOK_PROFILES,
    detect_book_type,
    get_book_profile,
    apply_profile
)
from core_engine.production.disaster_recovery import disaster_recovery, CriticalRecoveryFailure
from core_engine.production.cost_optimizer import (
    select_provider,
    estimate_cost,
    get_cost_optimization_recommendations
)
from core_engine.production.human_review import (
    generate_human_tasks,
    should_trigger_human_review
)
from core_engine.production.monitoring import (
    MetricsCollector,
    get_metrics_collector,
    generate_grafana_queries,
    generate_alert_rules
)
from core_engine.production.continuous_learning import continuous_learning_pipeline
from core_engine.production.security_compliance import (
    sanitize_pdf,
    detect_personal_data,
    audit_operation,
    auto_delete_expired_data
)

__all__ = [
    "get_performance_config",
    "apply_performance_config",
    "BOOK_PROFILES",
    "detect_book_type",
    "get_book_profile",
    "apply_profile",
    "disaster_recovery",
    "CriticalRecoveryFailure",
    "select_provider",
    "estimate_cost",
    "get_cost_optimization_recommendations",
    "generate_human_tasks",
    "should_trigger_human_review",
    "MetricsCollector",
    "get_metrics_collector",
    "generate_grafana_queries",
    "generate_alert_rules",
    "continuous_learning_pipeline",
    "sanitize_pdf",
    "detect_personal_data",
    "audit_operation",
    "auto_delete_expired_data"
]

