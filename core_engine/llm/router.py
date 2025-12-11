"""
LLMRouter for EWB Core Engine.

Задачи:
- читать config/llm.yaml;
- для каждой задачи (translation/qa/research/ocr) выбирать нужный адаптер;
- не привязывать пайплайн к конкретному провайдеру (OpenAI, DeepSeek, локальные).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Tuple, Type

import yaml  # type: ignore

from core_engine.llm.llm_adapter import LLMAdapter  # type: ignore
from core_engine.llm.dummy_adapter import DummyAdapter  # type: ignore
from core_engine.llm.openai_adapter import OpenAIAdapter  # type: ignore
from core_engine.llm.deepseek_adapter import DeepSeekAdapter  # type: ignore
from core_engine.llm.gemini_adapter import GeminiAdapter  # type: ignore
from core_engine.llm.hf_adapter import HFAdapter  # type: ignore
from core_engine.llm.ollama_adapter import OllamaAdapter  # type: ignore
from core_engine.llm.local_adapter import LocalAdapter  # type: ignore


logger = logging.getLogger(__name__)


# Карта префикс → класс адаптера
ADAPTERS: Dict[str, Type[LLMAdapter]] = {
    "dummy": DummyAdapter,
    "openai": OpenAIAdapter,
    "deepseek": DeepSeekAdapter,
    "gemini": GeminiAdapter,
    "hf": HFAdapter,
    "ollama": OllamaAdapter,
    "local": LocalAdapter,
}


DEFAULT_CONFIG = {
    "translation_model": "dummy:echo",
    "qa_model": "dummy:echo",
    "research_model": "dummy:echo",
    "ocr_model": "dummy:echo",
    "local_fallback": "local:echo",
}


def _parse_model_spec(spec: str) -> Tuple[str, str]:
    """
    Парсит строки вида "openai:gpt-4o-mini" или "dummy:echo".

    Возвращает (provider, model_name).
    """
    if not spec:
        return "dummy", "echo"

    if ":" not in spec:
        return spec, ""

    provider, model_name = spec.split(":", 1)
    provider = provider.strip()
    model_name = model_name.strip()
    if not provider:
        provider = "dummy"
    return provider, model_name


class LLMRouter:
    """
    Центральная точка выбора LLMAdapter по задаче.

    Использование:
        router = LLMRouter(config_path="core_engine/config/llm.yaml")
        adapter = router.get_translation_adapter()
        text = adapter.translate("...", context={...})
    """

    def __init__(self, config_path: str | None = None) -> None:
        if config_path is None:
            # По умолчанию ожидаем конфиг рядом с core_engine/.
            base = Path(__file__).resolve().parents[1]
            config_path = base / "config" / "llm.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = Path(config_path)
        self.config: Dict[str, str] = self._load_config()

    # --------------------------------------------------------------------- load

    def _load_config(self) -> Dict[str, str]:
        if not self.config_path.exists():
            logger.warning("LLM config not found at %s, using defaults", self.config_path)
            return dict(DEFAULT_CONFIG)

        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to read llm.yaml: %s", exc)
            return dict(DEFAULT_CONFIG)

        # Плоская нормализация: только нужные ключи, с дефолтами.
        cfg: Dict[str, str] = {}
        for key, default in DEFAULT_CONFIG.items():
            value = data.get(key, default)
            if not isinstance(value, str):
                value = default
            cfg[key] = value

        return cfg

    # ---------------------------------------------------------------- provider

    def _get_adapter_for_spec(self, spec: str) -> LLMAdapter:
        provider, model_name = _parse_model_spec(spec)
        adapter_cls = ADAPTERS.get(provider)

        if adapter_cls is None:
            logger.warning(
                "Unknown LLM provider '%s' in spec '%s', falling back to DummyAdapter",
                provider,
                spec,
            )
            adapter_cls = DummyAdapter

        try:
            return adapter_cls(model_name=model_name)  # type: ignore[arg-type]
        except TypeError:
            # На случай странных сигнатур — пробуем без имени модели.
            return adapter_cls()  # type: ignore[call-arg]

    # ----------------------------------------------------------------- helpers

    def get_translation_adapter(self) -> LLMAdapter:
        spec = self.config.get("translation_model", DEFAULT_CONFIG["translation_model"])
        return self._get_adapter_for_spec(spec)

    def get_qa_adapter(self) -> LLMAdapter:
        spec = self.config.get("qa_model", DEFAULT_CONFIG["qa_model"])
        return self._get_adapter_for_spec(spec)

    def get_research_adapter(self) -> LLMAdapter:
        spec = self.config.get("research_model", DEFAULT_CONFIG["research_model"])
        return self._get_adapter_for_spec(spec)

    def get_ocr_adapter(self) -> LLMAdapter:
        spec = self.config.get("ocr_model", DEFAULT_CONFIG["ocr_model"])
        return self._get_adapter_for_spec(spec)

    # На будущее: можно добавить метод fallback-логики, если основной провайдер
    # недоступен — подхватить local_fallback/ollama и т.п.

