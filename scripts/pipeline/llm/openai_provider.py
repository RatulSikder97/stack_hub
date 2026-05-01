"""OpenAI provider — wraps the Responses API."""

from __future__ import annotations

from pipeline.llm.base import GenerationRequest, LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, *, api_key: str, model: str, base_url: str | None = None) -> None:
        super().__init__(api_key=api_key, model=model)
        self._base_url = base_url or None

    def _generate(self, request: GenerationRequest) -> str:
        from openai import OpenAI

        kwargs: dict[str, object] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        client = OpenAI(**kwargs)  # type: ignore[arg-type]
        response = client.responses.create(
            model=self._model,
            input=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            max_output_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        return response.output_text or ""
