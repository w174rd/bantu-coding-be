from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import MessageAuthorKind
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationCreate, ConversationRead
from app.schemas.message import MessageCreate, MessageRead
from app.services.documents import extract_text

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


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
