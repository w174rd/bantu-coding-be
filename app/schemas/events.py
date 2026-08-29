from typing import Literal

from pydantic import BaseModel

from app.core.enums import PersonaRole
from app.schemas.message import MessageRead
from app.schemas.verdict import VerdictRead


class RoundStarted(BaseModel):
    type: Literal["round_started"] = "round_started"
    round_index: int


class PersonaThinking(BaseModel):
    type: Literal["persona_thinking"] = "persona_thinking"
    round_index: int
    persona_id: int
    role: PersonaRole


class MessageAdded(BaseModel):
    type: Literal["message"] = "message"
    message: MessageRead


class VerdictReached(BaseModel):
    type: Literal["verdict"] = "verdict"
    verdict: VerdictRead


class RoundCompleted(BaseModel):
    type: Literal["round_completed"] = "round_completed"
    round_index: int


class RoundError(BaseModel):
    type: Literal["error"] = "error"
    detail: str


RoundEvent = (
    RoundStarted | PersonaThinking | MessageAdded | VerdictReached | RoundCompleted | RoundError
)
