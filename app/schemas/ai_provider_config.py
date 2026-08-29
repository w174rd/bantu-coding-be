from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["anthropic", "gemini", "groq", "openrouter"]


class AiProviderConfigCreate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    provider: Provider
    model: str = Field(min_length=1, max_length=100)
    api_key: str = Field(min_length=1)
    is_active: bool = False


class AiProviderConfigUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    provider: Provider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=100)
    api_key: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class AiProviderConfigRead(BaseModel):
    """Note the absence of api_key: a stored secret is never returned to a client
    (CLAUDE.md section 7). Only enough of it to tell two keys apart.
    """

    id: int
    title: str | None
    provider: str
    model: str
    api_key_preview: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
