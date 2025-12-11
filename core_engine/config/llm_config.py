from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


# ============================
#  ДЕФОЛТНЫЙ КОНФИГ (FALLBACK)
# ============================

# Если configs/llm.yaml не найден или битый — ядро возьмёт ЭТОТ конфиг.
# Здесь сразу заданы три профиля:
#   - dev   → placeholder (без перевода)
#   - fast  → NLLB 600M (обычно CUDA)
#   - full  → NLLB 1.3B (CPU/GPU, как зададим)
_FALLBACK_CONFIG: Dict[str, Any] = {
    "default_profile": "fast",
    "profiles": {
        "dev": {
            "backend": "placeholder",
            "device": "cpu",
        },
        "fast": {
            "backend": "nllb",
            "model_name": "facebook/nllb-200-distilled-600M",
            "device": "cuda",
            "batch_size": 8,
            "max_length": 640,
            "source_lang": "en",
            "target_lang": "ru",
        },
        "full": {
            "backend": "nllb",
            "model_name": "facebook/nllb-200-distilled-1.3B",
            "device": "cpu",
            "batch_size": 4,
            "max_length": 640,
            "source_lang": "en",
            "target_lang": "ru",
        },
    },
}


# Возможные пути к внешнему YAML-конфигу
_CONFIG_CANDIDATES = [
    Path("configs") / "llm.yaml",
    Path("config") / "llm.yaml",  # альтернативный путь
]


def _load_raw_config() -> Dict[str, Any]:
    """
    Пытаемся загрузить configs/llm.yaml.
    Если не нашли или YAML сломан — возвращаем _FALLBACK_CONFIG.
    """
    for cfg_path in _CONFIG_CANDIDATES:
        if cfg_path.exists():
            try:
                with cfg_path.open("r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    return data
            except Exception:
                # Ядро не должно падать из-за кривого конфига.
                break
    return dict(_FALLBACK_CONFIG)


def get_llm_config() -> Dict[str, Any]:
    """Полный конфиг LLM (со всеми профилями)."""
    return _load_raw_config()


def get_llm_profile(mode: str | None = None) -> Dict[str, Any]:
    """
    Возвращает словарь с настройками конкретного профиля (dev / fast / full).

    Логика выбора:
      - если mode None → берём default_profile из конфига;
      - если mode задан и есть в profiles → берём его;
      - если mode неизвестен → fallback на default_profile;
      - если и default_profile нет в profiles → fallback на fast.
    """
    cfg = _load_raw_config()
    profiles = cfg.get("profiles") or {}
    default_name = cfg.get("default_profile", "fast")

    normalized_mode = (mode or "").strip().lower() if mode else None

    if normalized_mode and normalized_mode in profiles:
        profile_name = normalized_mode
    else:
        profile_name = default_name if default_name in profiles else "fast"

    profile = dict(profiles.get(profile_name, {}))

    # Дефолты, если чего-то нет в yaml
    profile.setdefault("backend", "nllb")
    profile.setdefault("model_name", "facebook/nllb-200-distilled-600M")
    profile.setdefault("device", "cpu")
    profile.setdefault("batch_size", 8)
    profile.setdefault("max_length", 640)
    profile.setdefault("source_lang", "en")
    profile.setdefault("target_lang", "ru")

    profile["profile_name"] = profile_name
    return profile
