"""Novita provider — uses the OpenAI-compatible Chat Completions endpoint."""

from __future__ import annotations

from pipeline.llm.base import GenerationRequest, LLMProvider


class NovitaProvider(LLMProvider):
    """Novita exposes an OpenAI-compatible API at `/v3/openai`.

    We use the `openai` SDK pointed at the Novita base URL. This means the
    same well-tested HTTP client supports both providers without a separate
    Novita SDK dependency.
    """

    name = "novita"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.novita.ai/v3/openai",
    ) -> None:
        super().__init__(api_key=api_key, model=model)
        self._base_url = base_url

    def _generate(self, request: GenerationRequest) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        # Novita supports chat.completions, not the newer responses API.
        completion = client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        if not completion.choices:
            return ""
        return completion.choices[0].message.content or ""
