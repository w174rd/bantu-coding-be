from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TicketStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.project import Project
    from app.models.verdict import Verdict


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Every ticket belongs to a project. CASCADE because a project is the container:
    # deleting it and leaving its board behind would orphan rows under a NOT NULL column.
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[TicketStatus] = mapped_column(
        # values_callable stores the lowercase values ("in_progress"); without it
        # SQLAlchemy persists the member *names* ("IN_PROGRESS") instead.
        Enum(
            TicketStatus,
            name="ticket_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=TicketStatus.BACKLOG,
        server_default=TicketStatus.BACKLOG.value,
    )
    # Null for every ticket written by hand on the board, which is the normal case.
    # SET NULL on delete: losing the verdict must not delete the work it proposed.
    verdict_id: Mapped[int | None] = mapped_column(
        ForeignKey("verdicts.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(back_populates="tickets")
    verdict: Mapped["Verdict | None"] = relationship(back_populates="tickets")
