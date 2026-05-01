from __future__ import annotations

import os

from dotenv import load_dotenv

from common import ROOT


def get_provider() -> str:
    load_dotenv(ROOT / ".env")
    return os.getenv("LLM_PROVIDER", "openai").strip().lower()


def has_provider_key(provider: str) -> bool:
    key_name = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
    }.get(provider)
    return bool(key_name and os.getenv(key_name))


def generate_text(system_prompt: str, user_prompt: str, max_tokens: int = 1200) -> str:
    provider = get_provider()

    if provider == "openai":
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing OPENAI_API_KEY")
        client = OpenAI(api_key=api_key)
        resp = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4.1"),
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_output_tokens=max_tokens,
        )
        return (resp.output_text or "").strip()

    if provider == "gemini":
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Missing GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        combined = (
            f"System instructions:\n{system_prompt}\n\n"
            f"User request:\n{user_prompt}"
        )
        resp = client.models.generate_content(model=model, contents=combined)
        return (resp.text or "").strip()

    if provider == "anthropic":
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY")
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.getenv("ANTHROPIC_MODEL", "claude-opus-4-7"),
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(
            block.text
            for block in response.content
            if getattr(block, "type", "") == "text"
        ).strip()

    raise RuntimeError(
        "Unsupported LLM_PROVIDER. "
        "Use openai, gemini, or anthropic."
    )
