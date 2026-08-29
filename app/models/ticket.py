from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TicketStatus
from app.db.base import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
