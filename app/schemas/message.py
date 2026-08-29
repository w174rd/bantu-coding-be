from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import MessageAuthorKind


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    author_kind: MessageAuthorKind
    persona_id: int | None
    content: str
    round_index: int
    source_name: str | None
    created_at: datetime
