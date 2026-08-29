import logging

import anthropic
import groq
import openai
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decrypt, get_ai_config_key
from app.models.ai_provider_config import AiProviderConfig
from app.services.ai.base import AIProvider, AIProviderError

logger = logging.getLogger(__name__)


class AnthropicProvider(AIProvider):
    async def chat(self, messages: list[dict], system: str | None = None) -> str:
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        # `effort` and `thinking` are deliberately not sent: the model is free text
        # chosen by the user, and those parameters are rejected by some of the models
        # this field accepts. A persona writes a few paragraphs; it needs neither.
        kwargs: dict = {
            "model": self.model,
            "max_tokens": get_settings().persona_max_tokens,
            "messages": messages,
        }
        if system is not None:
            kwargs["system"] = system

        try:
            response = await client.messages.create(**kwargs)
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
            raise AIProviderError(str(exc), getattr(exc, "status_code", None)) from exc

        for block in response.content:
            if block.type == "text":
                return block.text

        raise AIProviderError(
            f"The model returned no text (stop_reason={response.stop_reason})",
            safe_to_display=True,
        )


class GeminiProvider(AIProvider):
    async def chat(self, messages: list[dict], system: str | None = None) -> str:
        client = genai.Client(api_key=self.api_key)
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in messages
        ]
        config = (
            genai_types.GenerateContentConfig(system_instruction=system)
            if system is not None
            else None
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except genai_errors.APIError as exc:
            raise AIProviderError(str(exc), exc.code) from exc

        if not response.text:
            finish_reason = response.candidates[0].finish_reason if response.candidates else None
            raise AIProviderError(
                f"The model returned no text (finish_reason={finish_reason})", safe_to_display=True
            )

        return response.text


class _OpenAICompatibleProvider(AIProvider):
    """Groq and OpenRouter both speak the OpenAI chat-completions shape.

    They differ only in the client class and the base URL, so the request building
    and the response unwrapping live here rather than being written twice.
    """

    def _client(self):
        raise NotImplementedError

    async def chat(self, messages: list[dict], system: str | None = None) -> str:
        payload = messages if system is None else [{"role": "system", "content": system}, *messages]

        try:
            response = await self._client().chat.completions.create(
                model=self.model,
                messages=payload,
                max_tokens=get_settings().persona_max_tokens,
            )
        except (groq.APIError, openai.APIError) as exc:
            raise AIProviderError(str(exc), getattr(exc, "status_code", None)) from exc

        choice = response.choices[0]
        if not choice.message.content:
            raise AIProviderError(
                f"The model returned no text (finish_reason={choice.finish_reason})",
                safe_to_display=True,
            )

        return choice.message.content


class GroqProvider(_OpenAICompatibleProvider):
    def _client(self):
        return groq.AsyncGroq(api_key=self.api_key)


class OpenRouterProvider(_OpenAICompatibleProvider):
    def _client(self):
        return openai.AsyncOpenAI(
            api_key=self.api_key, base_url="https://openrouter.ai/api/v1"
        )


_PROVIDER_CLASSES: dict[str, type[AIProvider]] = {
    "anthropic": AnthropicProvider,
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
}


def get_provider(db: Session) -> AIProvider:
    config = db.scalars(
        select(AiProviderConfig).where(AiProviderConfig.is_active.is_(True))
    ).one_or_none()
    if config is None:
        raise AIProviderError("No active AI provider is configured", safe_to_display=True)

    provider_class = _PROVIDER_CLASSES.get(config.provider)
    if provider_class is None:
        raise AIProviderError(
            f"Unknown AI provider: {config.provider!r}", safe_to_display=True
        )

    logger.info(
        "Using AI provider config id=%s provider=%s model=%s",
        config.id,
        config.provider,
        config.model,
    )

    return provider_class(
        model=config.model, api_key=decrypt(config.api_key, get_ai_config_key())
    )
