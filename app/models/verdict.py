from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Verdict(Base):
    """One Arbiter decision: the reasoning, the scored options, and the ticket."""

    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    round_index: Mapped[int] = mapped_column(Integer)
    headline: Mapped[str] = mapped_column(Text)
    # SET NULL rather than CASCADE: deleting the ticket should not erase the
    # reasoning that produced it.
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("tickets.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    options: Mapped[list["VerdictOption"]] = relationship(
        back_populates="verdict",
        cascade="all, delete-orphan",
        order_by="VerdictOption.display_order",
    )


class VerdictOption(Base):
    __tablename__ = "verdict_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    verdict_id: Mapped[int] = mapped_column(
        ForeignKey("verdicts.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(200))
    percentage: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text)
    display_order: Mapped[int] = mapped_column(Integer)

    verdict: Mapped[Verdict] = relationship(back_populates="options")
