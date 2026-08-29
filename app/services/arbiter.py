import json
import logging
import re

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import MessageAuthorKind, PersonaRole, TicketStatus
from app.core.personas import CAST, ROOM_CONTEXT
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.persona import Persona
from app.models.ticket import Ticket
from app.models.verdict import Verdict, VerdictOption
from app.schemas.verdict import ArbiterVerdict
from app.services.ai.base import AIProvider, AIProviderError
from app.services.discussion import build_provider_messages, window

logger = logging.getLogger(__name__)

_OUTPUT_INSTRUCTION = """\
Answer with a single JSON object and nothing else. No prose before or after, no code fence.

{
  "headline": "one sentence naming what you decided and why",
  "options": [
    {"label": "short name of the option", "percentage": 60, "rationale": "why it scored this"}
  ],
  "ticket": {"title": "imperative title, at most 200 characters", "body": "a Markdown planning \
document with ## Context, ## Goal, ## Approach and ## Risks / Trade-offs sections"}
}

Score only options that were actually proposed in the discussion. The percentages are your
confidence that each option is the right one to build, and they must add up to 100. The ticket
describes the winning option — the one you scored highest."""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)
_SUM_TOLERANCE = 5


def parse_verdict(raw: str) -> ArbiterVerdict:
    """Turn the Arbiter's reply into a validated verdict, or refuse it.

    Models wrap JSON in prose and code fences even when told not to, so the object is
    extracted rather than assumed to be the whole reply. Everything after that is a
    typed check: this is the boundary where model output stops being text.
    """
    match = _JSON_OBJECT.search(raw)
    if match is None:
        raise AIProviderError("The Arbiter did not return a JSON object", safe_to_display=True)

    try:
        payload = json.loads(match.group())
    except json.JSONDecodeError as exc:
        raise AIProviderError(
            f"The Arbiter's JSON could not be parsed: {exc.msg}", safe_to_display=True
        ) from exc

    try:
        verdict = ArbiterVerdict.model_validate(payload)
    except ValidationError as exc:
        raise AIProviderError(
            f"The Arbiter's verdict failed validation: {exc.error_count()} problem(s)",
            safe_to_display=True,
        ) from exc

    total = sum(option.percentage for option in verdict.options)
    if abs(total - 100) > _SUM_TOLERANCE:
        raise AIProviderError(
            f"The Arbiter's percentages sum to {total:.0f}, not 100", safe_to_display=True
        )

    # Within tolerance the split is sound and the drift is rounding, so normalise it
    # rather than discard an otherwise good verdict over a percentage point.
    for option in verdict.options:
        option.percentage = option.percentage * 100 / total

    return verdict


def _record(
    db: Session, conversation: Conversation, arbiter: Persona, round_index: int, verdict: ArbiterVerdict
) -> tuple[Verdict, Message]:
    ticket = Ticket(
        title=verdict.ticket.title,
        body=verdict.ticket.body,
        # Never read from the model. The drag gate (CLAUDE.md section 0, point 3) says
        # only the user may put work into In Progress; this line is that rule in code.
        status=TicketStatus.BACKLOG,
    )
    db.add(ticket)
    db.flush()

    record = Verdict(
        conversation_id=conversation.id,
        round_index=round_index,
        headline=verdict.headline,
        ticket_id=ticket.id,
        options=[
            VerdictOption(
                label=option.label,
                percentage=round(option.percentage),
                rationale=option.rationale,
                display_order=order,
            )
            for order, option in enumerate(verdict.options)
        ],
    )
    db.add(record)

    # The Arbiter also speaks in the room. Without this the chart appears with no
    # turn in the transcript explaining it, and the discussion reads as if it stopped.
    spoken = Message(
        conversation_id=conversation.id,
        author_kind=MessageAuthorKind.PERSONA,
        persona_id=arbiter.id,
        content=f"{verdict.headline}\n\nTicket created: **{verdict.ticket.title}**",
        round_index=round_index,
    )
    db.add(spoken)

    db.commit()
    db.refresh(record)
    db.refresh(spoken)
    return record, spoken


async def run_verdict(
    db: Session, conversation: Conversation, provider: AIProvider, round_index: int
) -> tuple[Verdict, Message]:
    personas = {persona.id: persona for persona in db.scalars(select(Persona))}
    arbiter = next(p for p in personas.values() if p.role is PersonaRole.ARBITER)

    history = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id)
        )
    )
    provider_messages = build_provider_messages(
        window(history, get_settings().chat_history_char_budget), arbiter, personas
    )

    reply = await provider.chat(
        provider_messages,
        system=(
            f"{ROOM_CONTEXT}\n\n{CAST[PersonaRole.ARBITER].system_prompt}"
            f"\n\n{_OUTPUT_INSTRUCTION}"
        ),
    )

    verdict = parse_verdict(reply)
    record, spoken = _record(db, conversation, arbiter, round_index, verdict)

    logger.info(
        "verdict recorded conversation=%s round=%s options=%s ticket=%s",
        conversation.id,
        round_index,
        len(record.options),
        record.ticket_id,
    )
    return record, spoken
