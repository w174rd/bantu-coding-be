import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import MessageAuthorKind
from app.db.session import SessionLocal, get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.verdict import Verdict
from app.schemas.conversation import ConversationCreate, ConversationRead
from app.schemas.events import MessageAdded, RoundError, RoundEvent, VerdictReached
from app.schemas.message import MessageCreate, MessageRead
from app.schemas.verdict import VerdictRead
from app.services.ai.base import AIProviderError
from app.services.ai.provider import get_provider
from app.services.arbiter import run_verdict
from app.services.discussion import cadence, run_round
from app.services.documents import extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])

# One round at a time per room. Two open tabs would otherwise interleave two rounds
# into the same transcript and bill twice for it. Per process, not per deployment —
# adequate while the app is single-user on localhost.
_round_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def _get_or_404(conversation_id: int, db: Session) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


@router.get("", response_model=list[ConversationRead])
def list_conversations(db: Session = Depends(get_db)) -> list[Conversation]:
    return list(db.scalars(select(Conversation).order_by(Conversation.id.desc())))


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate, db: Session = Depends(get_db)
) -> Conversation:
    conversation = Conversation(**payload.model_dump())
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationRead)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)) -> Conversation:
    return _get_or_404(conversation_id, db)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_or_404(conversation_id, db))
    db.commit()


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages(conversation_id: int, db: Session = Depends(get_db)) -> list[Message]:
    _get_or_404(conversation_id, db)
    # Ordered by id, not created_at: messages written in one transaction share an
    # identical now() and would come back in an arbitrary order.
    return list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        )
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    conversation_id: int, payload: MessageCreate, db: Session = Depends(get_db)
) -> Message:
    _get_or_404(conversation_id, db)
    message = Message(
        conversation_id=conversation_id,
        author_kind=MessageAuthorKind.USER,
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.post(
    "/{conversation_id}/documents",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    conversation_id: int, file: UploadFile, db: Session = Depends(get_db)
) -> Message:
    _get_or_404(conversation_id, db)

    max_bytes = get_settings().document_max_bytes
    # One byte past the limit is enough to know it was exceeded, and stops an
    # oversized upload from being read into memory in full.
    raw = await file.read(max_bytes + 1)
    try:
        text = extract_text(file.filename, raw, max_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    message = Message(
        conversation_id=conversation_id,
        author_kind=MessageAuthorKind.DOCUMENT,
        content=text,
        source_name=file.filename,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{conversation_id}/verdicts", response_model=list[VerdictRead])
def list_verdicts(conversation_id: int, db: Session = Depends(get_db)) -> list[Verdict]:
    _get_or_404(conversation_id, db)
    return list(
        db.scalars(
            select(Verdict)
            .where(Verdict.conversation_id == conversation_id)
            .order_by(Verdict.round_index)
        )
    )


def _sse(event: RoundEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


async def _run(conversation_id: int, db: Session) -> AsyncIterator[str]:
    conversation = db.get(Conversation, conversation_id)
    provider = get_provider(db)
    round_index = 0

    async for event in run_round(db, conversation, provider):
        round_index = getattr(event, "round_index", round_index)
        yield _sse(event)

    if round_index % cadence(conversation) == 0:
        verdict, spoken = await run_verdict(db, conversation, provider, round_index)
        yield _sse(MessageAdded(message=MessageRead.model_validate(spoken)))
        yield _sse(VerdictReached(verdict=VerdictRead.model_validate(verdict)))


@router.get("/{conversation_id}/stream")
async def stream_round(
    conversation_id: int, db: Session = Depends(get_db)
) -> StreamingResponse:
    """Run the next discussion round, streaming each persona as it finishes.

    Deliberately non-idempotent: opening this stream is what makes the personas
    speak. The lock below is what stops a second reader from starting a duplicate
    round rather than joining this one.
    """
    _get_or_404(conversation_id, db)

    lock = _round_locks[conversation_id]
    if lock.locked():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A round is already running for this conversation",
        )

    async def events() -> AsyncIterator[str]:
        # A session of its own, not the request-scoped one: this generator runs while
        # the response streams, and tying its lifetime to the dependency's teardown
        # would make correctness depend on when FastAPI closes it.
        stream_db = SessionLocal()
        async with lock:
            try:
                async for chunk in _run(conversation_id, stream_db):
                    yield chunk
            except AIProviderError as exc:
                logger.warning("round failed conversation=%s error=%s", conversation_id, exc)
                # A vendor SDK's message can echo the request it came from, and the API
                # key travels in that request. Only messages this codebase wrote are sent.
                yield _sse(
                    RoundError(
                        detail=str(exc)
                        if exc.safe_to_display
                        else "The AI provider rejected the request. See the server log."
                    )
                )
            except Exception:
                logger.exception("round crashed conversation=%s", conversation_id)
                yield _sse(RoundError(detail="The discussion round failed unexpectedly"))
            finally:
                stream_db.close()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
