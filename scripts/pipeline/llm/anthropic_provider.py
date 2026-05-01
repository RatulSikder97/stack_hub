"""Anthropic provider — wraps the Messages API."""

from __future__ import annotations

from pipeline.llm.base import GenerationRequest, LLMProvider


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def _generate(self, request: GenerationRequest) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=self._api_key)
        response = client.messages.create(
            model=self._model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system_prompt,
            messages=[{"role": "user", "content": request.user_prompt}],
        )
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        )
