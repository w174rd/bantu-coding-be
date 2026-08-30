from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VerdictOptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str
    percentage: int
    rationale: str
    display_order: int


class VerdictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    round_index: int
    headline: str
    ticket_ids: list[int]
    created_at: datetime
    options: list[VerdictOptionRead]


class ArbiterOption(BaseModel):
    """One scored option as the Arbiter proposed it, before it is trusted."""

    label: str = Field(min_length=1, max_length=200)
    percentage: float = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)


class ArbiterTicket(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


MAX_TICKETS_PER_VERDICT = 8


class ArbiterVerdict(BaseModel):
    """The typed gate every Arbiter response must pass before anything is written.

    Model output is data, not a command (CLAUDE.md 6.4). Note what is absent: no
    ticket status, no ticket id, no conversation id. Those are decided by code, so
    no phrasing in a discussion can reach them.
    """

    headline: str = Field(min_length=1)
    options: list[ArbiterOption] = Field(min_length=1)
    # Capped because every entry becomes a row this code writes on the model's say-so.
    # A confused Arbiter must not be able to flood the board in a single verdict.
    tickets: list[ArbiterTicket] = Field(min_length=1, max_length=MAX_TICKETS_PER_VERDICT)
