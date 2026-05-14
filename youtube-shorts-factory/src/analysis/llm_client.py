"""Multi-provider LLM client with automatic failover.

Order is configurable via `LLM_PROVIDER_ORDER`. Groq is recommended as
the primary provider because it's fast and inexpensive — perfect for
the high-volume creative tasks (viral analysis, translation, copy).

All providers are called through the OpenAI-compatible chat API where
possible; Anthropic uses its native SDK.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import Secrets

log = logging.getLogger("shorts_factory.llm")


class LLMClient:
    """Thin failover wrapper over Groq / OpenAI / Anthropic."""

    def __init__(self, secrets: Secrets):
        self.secrets = secrets
        self._openai = None
        self._groq = None
        self._anthropic = None

    # ─── Lazy clients ─────────────────────────────────────────────────────
    def _get_groq(self):
        if self._groq is None and self.secrets.groq_api_key:
            from openai import OpenAI

            self._groq = OpenAI(
                api_key=self.secrets.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
            )
        return self._groq

    def _get_openai(self):
        if self._openai is None and self.secrets.openai_api_key:
            from openai import OpenAI

            self._openai = OpenAI(api_key=self.secrets.openai_api_key)
        return self._openai

    def _get_anthropic(self):
        if self._anthropic is None and self.secrets.anthropic_api_key:
            from anthropic import Anthropic

            self._anthropic = Anthropic(api_key=self.secrets.anthropic_api_key)
        return self._anthropic

    # ─── Public API ───────────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, max=20))
    def chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """Send a prompt and return the assistant's text reply.

        If `json_mode=True`, ensures the response is valid JSON (parses
        & re-serialises to guarantee shape).
        """
        last_error: Optional[Exception] = None
        for provider in self.secrets.llm_provider_order:
            try:
                if provider == "groq" and self._get_groq():
                    return self._chat_openai_compat(
                        self._get_groq(),
                        self.secrets.groq_model,
                        system,
                        user,
                        json_mode=json_mode,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                if provider == "openai" and self._get_openai():
                    return self._chat_openai_compat(
                        self._get_openai(),
                        self.secrets.openai_model,
                        system,
                        user,
                        json_mode=json_mode,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                if provider == "anthropic" and self._get_anthropic():
                    return self._chat_anthropic(
                        system,
                        user,
                        json_mode=json_mode,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
            except Exception as e:  # noqa: BLE001
                log.warning("LLM provider %s failed: %s", provider, e)
                last_error = e
                continue
        raise RuntimeError(f"All LLM providers failed: {last_error!r}")

    # ─── Internals ────────────────────────────────────────────────────────
    def _chat_openai_compat(
        self,
        client,
        model: str,
        system: str,
        user: str,
        *,
        json_mode: bool,
        max_tokens: int,
        temperature: float,
    ) -> str:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        if json_mode:
            return json.dumps(json.loads(text))
        return text

    def _chat_anthropic(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool,
        max_tokens: int,
        temperature: float,
    ) -> str:
        client = self._get_anthropic()
        if json_mode:
            user = user + "\n\nReturn ONLY valid JSON. No prose."
        resp = client.messages.create(
            model=self.secrets.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        if json_mode:
            # tolerate code fences
            text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            return json.dumps(json.loads(text))
        return text


# ─── Convenience helpers for typed JSON returns ──────────────────────────
def parse_json_reply(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # tolerate stray prose around JSON
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
        raise
