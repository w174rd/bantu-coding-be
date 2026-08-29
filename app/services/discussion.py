import logging
import time
from collections.abc import AsyncIterator

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import MessageAuthorKind, PersonaRole
from app.core.personas import CAST, ROOM_CONTEXT
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.persona import Persona
from app.schemas.events import (
    MessageAdded,
    PersonaThinking,
    RoundCompleted,
    RoundEvent,
    RoundStarted,
)
from app.schemas.message import MessageRead
from app.services.ai.base import AIProvider

logger = logging.getLogger(__name__)

ROUND_ORDER = (PersonaRole.ARCHITECT, PersonaRole.RESEARCHER, PersonaRole.CHALLENGER)


def _speaker(message: Message, personas: dict[int, Persona]) -> str:
    if message.author_kind is MessageAuthorKind.USER:
        return "You"
    if message.author_kind is MessageAuthorKind.DOCUMENT:
        return f"Document ({message.source_name})" if message.source_name else "Document"
    persona = personas.get(message.persona_id) if message.persona_id else None
    return persona.name if persona else "Unknown"


def window(messages: list[Message], budget: int) -> list[Message]:
    """Keep the newest messages that fit the character budget, oldest dropped first."""
    if not messages:
        return []

    kept = [messages[-1]]
    used = len(messages[-1].content)

    for message in reversed(messages[:-1]):
        used += len(message.content)
        if used > budget:
            break
        kept.append(message)

    kept.reverse()
    return kept


def build_provider_messages(
    messages: list[Message], speaking_as: Persona, personas: dict[int, Persona]
) -> list[dict]:
    """Flatten a five-party room into the two-role shape every provider accepts.

    The speaking persona's own lines become `assistant`; everyone else's — the human,
    documents, and the other three personas — become `user`, each labelled with who
    said it. Without the label the model cannot tell an ally's argument from an
    opponent's. Consecutive `user` entries are merged because several providers
    reject two in a row.
    """
    flattened: list[dict] = []

    for message in messages:
        if message.persona_id == speaking_as.id:
            flattened.append({"role": "assistant", "content": message.content})
            continue

        labelled = f"{_speaker(message, personas)}: {message.content}"
        if flattened and flattened[-1]["role"] == "user":
            flattened[-1]["content"] += f"\n\n{labelled}"
        else:
            flattened.append({"role": "user", "content": labelled})

    # Providers reject a conversation that opens on an assistant turn.
    while flattened and flattened[0]["role"] != "user":
        flattened.pop(0)

    return flattened


def cadence(conversation: Conversation) -> int:
    return conversation.arbiter_every_n_rounds or get_settings().arbiter_every_n_rounds


async def run_round(
    db: Session, conversation: Conversation, provider: AIProvider
) -> AsyncIterator[RoundEvent]:
    """Run one Architect → Researcher → Challenger round, emitting events as it goes.

    Each message is committed the moment it is produced. A round that dies halfway
    leaves behind the contributions that did land, because they are real.
    """
    personas = {persona.id: persona for persona in db.scalars(select(Persona))}
    by_role = {persona.role: persona for persona in personas.values()}

    last_round = db.scalar(
        select(Message.round_index)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.round_index.desc())
        .limit(1)
    )
    round_index = (last_round or 0) + 1

    yield RoundStarted(round_index=round_index)

    for role in ROUND_ORDER:
        persona = by_role[role]
        yield PersonaThinking(
            round_index=round_index, persona_id=persona.id, role=role
        )

        history = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.id)
            )
        )
        provider_messages = build_provider_messages(
            window(history, get_settings().chat_history_char_budget), persona, personas
        )

        started = time.monotonic()
        reply = await provider.chat(
            provider_messages,
            system=f"{ROOM_CONTEXT}\n\n{CAST[role].system_prompt}",
        )
        # Metadata only — never the prompt, never the reply (CLAUDE.md 6.4).
        logger.info(
            "persona spoke conversation=%s round=%s role=%s chars=%s duration=%.1fs",
            conversation.id,
            round_index,
            role.value,
            len(reply),
            time.monotonic() - started,
        )

        message = Message(
            conversation_id=conversation.id,
            author_kind=MessageAuthorKind.PERSONA,
            persona_id=persona.id,
            content=reply,
            round_index=round_index,
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        yield MessageAdded(message=MessageRead.model_validate(message))

    yield RoundCompleted(round_index=round_index)
