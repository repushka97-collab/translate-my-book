from typing import Any, Dict


class LLMAdapter:
    """
    Базовый интерфейс для всех LLM-провайдеров.
    Пайплайн знает только про эти методы.
    """

    def translate(self, text: str, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError

    def qa(
        self,
        en_text: str,
        ru_text: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Возвращает произвольный dict с результатами сравнения.
        Например: {"semantic_score": 0.93, "issues": [...]}
        """
        raise NotImplementedError

    def ocr(self, image_bytes: bytes, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError

