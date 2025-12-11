from typing import Any, Dict

from core_engine.llm.llm_adapter import LLMAdapter


class DummyAdapter(LLMAdapter):
    """
    Тестовый адаптер: ничего не вызывает, просто эхо/заглушки.
    Используем по умолчанию, чтобы пайплайн был независим от API.
    """

    def __init__(self, model_name: str = "dummy:echo"):
        self.model_name = model_name

    def translate(self, text: str, context: Dict[str, Any] | None = None) -> str:
        # Прозрачное эхо — удобно для отладки
        return text

    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> str:
        return "dummy-analysis"

    def qa(
        self,
        en_text: str,
        ru_text: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return {
            "provider": "dummy",
            "semantic_score": 1.0 if en_text == ru_text else 0.5,
            "issues": [],
        }

    def ocr(self, image_bytes: bytes, context: Dict[str, Any] | None = None) -> str:
        return ""

