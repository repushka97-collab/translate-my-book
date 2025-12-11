from typing import Any, Dict

from core_engine.llm.llm_adapter import LLMAdapter


class OpenAIAdapter(LLMAdapter):
    """
    Адаптер для OpenAI Chat Completions.
    Ожидает переменную окружения OPENAI_API_KEY.
    """

    def __init__(self, model_name: str):
        # формат ожидаем: "openai:gpt-4o-mini"
        # храним только часть после провайдера
        parts = model_name.split(":", 1)
        self.model = parts[1] if len(parts) > 1 else model_name

    def _client(self):
        # ленивый импорт, чтобы не ронять систему, если openai не установлен
        from openai import OpenAI  # type: ignore
        return OpenAI()

    def translate(self, text: str, context: Dict[str, Any] | None = None) -> str:
        if not text.strip():
            return text

        client = self._client()
        system_msg = (
            "Ты профессиональный технический переводчик. "
            "Переводи аккуратно, сохраняя структуру, формулы, ссылки, DOI, FIG/TABLE токены."
        )

        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    def analyze(self, text: str, context: Dict[str, Any] | None = None) -> str:
        client = self._client()
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты аналитик текста."},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content.strip()

    def qa(
        self,
        en_text: str,
        ru_text: str,
        context: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        client = self._client()
        prompt = (
            "Сравни оригинальный английский текст и русский перевод. "
            "Оцени семантическое соответствие по шкале 0..1 и перечисли ключевые проблемы.\n\n"
            f"EN:\n{en_text}\n\nRU:\n{ru_text}"
        )
        resp = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "Ты QA-ассистент перевода."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
        )
        content = resp.choices[0].message.content.strip()
        # пока возвращаем как есть, без парсинга
        return {"provider": "openai", "raw": content}

    def ocr(self, image_bytes: bytes, context: Dict[str, Any] | None = None) -> str:
        # сюда позже можно прикрутить vision-модель OpenAI
        return ""

