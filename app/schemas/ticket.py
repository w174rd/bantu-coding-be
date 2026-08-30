from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import TicketStatus


class TicketCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None
    status: TicketStatus | None = None


class TicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str | None
    status: TicketStatus
    verdict_id: int | None
    created_at: datetime
    updated_at: datetime
