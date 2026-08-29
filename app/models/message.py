from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import MessageAuthorKind
from app.db.base import Base


class Message(Base):
    __tablename__ = "messages"

    __table_args__ = (Index("ix_messages_conversation_id_id", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    author_kind: Mapped[MessageAuthorKind] = mapped_column(
        Enum(
            MessageAuthorKind,
            name="message_author_kind",
            values_callable=lambda enum: [member.value for member in enum],
        )
    )
    persona_id: Mapped[int | None] = mapped_column(
        ForeignKey("personas.id"), default=None
    )
    content: Mapped[str] = mapped_column(Text)
    # Which debate round this belongs to. Everything the user or a document puts in
    # before a round has run is 0.
    round_index: Mapped[int] = mapped_column(default=0, server_default="0")
    # Filename of an uploaded document, kept for display. Never used as a path.
    source_name: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
