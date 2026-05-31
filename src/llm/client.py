"""
OpenAI API client wrapper with retry logic and structured output helpers.
"""

import logging
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import RateLimitError, APITimeoutError, APIConnectionError

logger = logging.getLogger("oss-maintainer-bot.llm")


class LLMClient:
    """Wrapper around the OpenAI client with retry logic."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = OpenAI(api_key=api_key)
        self.model = model
        logger.info("LLM client initialized with model: %s", model)

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def complete(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.3, max_tokens: int = 1024) -> str:
        """Send a chat completion request and return the response text."""
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        logger.debug("LLM response (%d tokens): %s...",
                     response.usage.total_tokens, content[:100])
        return content.strip()

    def complete_json(self, system_prompt: str, user_prompt: str,
                      temperature: float = 0.2) -> dict:
        """Request JSON output and parse it safely."""
        import json
        system_with_json = system_prompt + "\n\nIMPORTANT: Respond ONLY with valid JSON. No markdown, no explanation."
        raw = self.complete(system_with_json, user_prompt,
                            temperature=temperature, max_tokens=512)
        # Strip accidental markdown code fences
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse LLM JSON response: %s\nRaw: %s", exc, raw)
            return {}
