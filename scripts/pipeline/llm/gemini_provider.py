"""Google Gemini provider — wraps `google-genai`."""

from __future__ import annotations

from pipeline.llm.base import GenerationRequest, LLMProvider


class GeminiProvider(LLMProvider):
    name = "gemini"

    def _generate(self, request: GenerationRequest) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self._api_key)
        config = types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            temperature=request.temperature,
            max_output_tokens=request.max_tokens,
        )
        response = client.models.generate_content(
            model=self._model,
            contents=request.user_prompt,
            config=config,
        )
        return response.text or ""
