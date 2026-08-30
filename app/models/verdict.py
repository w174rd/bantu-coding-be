from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Verdict(Base):
    """One Arbiter decision: the reasoning, the scored options, and its tickets.

    A verdict may produce several tickets — the Arbiter splits work that has
    independently shippable parts — so the foreign key lives on `tickets`, not here.
    """

    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    round_index: Mapped[int] = mapped_column(Integer)
    headline: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    options: Mapped[list["VerdictOption"]] = relationship(
        back_populates="verdict",
        cascade="all, delete-orphan",
        order_by="VerdictOption.display_order",
    )
    # Ordered by id, which is insertion order: the Arbiter returns its tickets with
    # dependencies first, and they are written in that order.
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="verdict", order_by="Ticket.id"
    )

    @property
    def ticket_ids(self) -> list[int]:
        return [ticket.id for ticket in self.tickets]


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
