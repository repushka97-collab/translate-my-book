from typing import Any, Dict

from core_engine.llm.llm_adapter import LLMAdapter


class HFAdapter(LLMAdapter):
    """
    Заглушка под HuggingFace Inference / локальные модели.
    """

    def __init__(self, model_name: str):
        self.model_name = model_name

    def translate(self, text: str, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("HFAdapter.translate not implemented yet")

    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("HFAdapter.analyze not implemented yet")

    def qa(
        self,
        en_text: str,
        ru_text: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError("HFAdapter.qa not implemented yet")

    def ocr(self, image_bytes: bytes, context: Dict[str, Any] | None = None) -> str:
        raise NotImplementedError("HFAdapter.ocr not implemented yet")

