from typing import Any, Dict

from core_engine.llm.llm_adapter import LLMAdapter


class OllamaAdapter(LLMAdapter):
    """
    Заглушка под локальный Ollama сервер.
    """

    def __init__(self, model_name: str):
        # формат: "ollama:llama3" и т.п.
        parts = model_name.split(":", 1)
        self.model = parts[1] if len(parts) > 1 else model_name

    def translate(self, text: str, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("OllamaAdapter.translate not implemented yet")

    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("OllamaAdapter.analyze not implemented yet")

    def qa(
        self,
        en_text: str,
        ru_text: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("OllamaAdapter.qa not implemented yet")

    def ocr(self, image_bytes: bytes, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("OllamaAdapter.ocr not implemented yet")

