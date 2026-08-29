from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiProviderConfig(Base):
    """Which model, from which vendor, the personas speak through.

    Stored in the database rather than in .env so the provider and model can be
    switched at runtime. This is the *app's* credential — CLAUDE.md 6.3 item 2
    keeps it separate from the credentials an agent run is given.
    """

    __tablename__ = "ai_provider_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str | None] = mapped_column(String(100), default=None)
    # Free text, not a native enum like PersonaRole: which vendors are supported is
    # decided by the adapters in code, so adding one must not need a migration.
    provider: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(100))
    api_key: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
