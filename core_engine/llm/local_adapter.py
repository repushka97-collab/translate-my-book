"""
Local / offline LLMAdapter for EWB Core Engine.

Цели:
- обеспечить рабочий адаптер без API-ключей;
- дать крюк для подключения оффлайн-переводчиков (Argos, локальные модели)
  без изменения остального пайплайна;
- по умолчанию вести себя как «умный echo», не ломая структуру.
"""

from __future__ import annotations

from typing import Any, Dict

from core_engine.llm.llm_adapter import LLMAdapter  # type: ignore


try:
    # Опционально: если когда-нибудь установим Argos Translate — можно
    # использовать его как реальный оффлайн-переводчик.
    import argostranslate.translate  # type: ignore
    HAS_ARGOS = True
except Exception:  # pragma: no cover
    HAS_ARGOS = False


class LocalAdapter(LLMAdapter):
    """
    Локальный адаптер.

    model_name может использоваться, например:
      - "local:echo"   — всегда возвращать исходный текст;
      - "local:argos"  — попытаться использовать Argos Translate (если установлен).
    """

    def __init__(self, model_name: str = "local:echo", **kwargs: Any) -> None:
        # На случай разных сигнатур базового класса — вызываем осторожно.
        try:
            super().__init__(model_name=model_name, **kwargs)  # type: ignore[arg-type]
        except TypeError:
            try:
                super().__init__()  # type: ignore[misc]
            except Exception:
                # Ничего страшного, базовый init может быть пустым.
                pass

        self.model_name = model_name

    # --- Основной контракт ---------------------------------------------------

    def translate(self, text: str, context: Dict[str, Any] | None = None) -> str:
        """
        Локальный перевод.

        По умолчанию:
        - режим "local:echo" — отдаём исходный текст, не трогая структуру;
        - режим "local:argos" — если установлен Argos и есть языковые пакеты,
          пытаемся перевести (ещё не настраиваем, только задел).
        """
        if not text:
            return ""

        if self.model_name.endswith("argos") and HAS_ARGOS:
            # TODO: здесь можно будет выбрать нужные языковые пары,
            # когда захотим заморочиться с установкой пакетов Argos.
            try:
                return argostranslate.translate.translate(text, "en", "ru")  # type: ignore[arg-type]
            except Exception:
                return text

        # Дефолт: echo без изменений.
        return text

    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> str:
        return "local-analyze-not-implemented"

    def qa(
        self,
        en_text: str,
        ru_text: str,
        context: Dict[str, Any] | None = None,
    ) -> str:
        return "local-qa-not-implemented"

    def ocr(self, image_bytes: bytes, context: Dict[str, Any] | None = None) -> str:
        return ""

