from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import PersonaRole
from app.db.base import Base


class Persona(Base):
    """One of the four characters in the discussion room.

    Display data only. The system prompt that gives a persona its personality
    lives in app/core/personas.py and is never served over the API.
    """

    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[PersonaRole] = mapped_column(
        Enum(
            PersonaRole,
            name="persona_role",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(50))
    avatar: Mapped[str] = mapped_column(String(8))
    accent_color: Mapped[str] = mapped_column(String(7))
    tagline: Mapped[str] = mapped_column(String(120))
    display_order: Mapped[int]
    # Null means "use whichever config is_active", which is what all four personas
    # did before this column existed. SET NULL on delete, never CASCADE: there are
    # exactly four personas and they are seeded — losing a model configuration must
    # drop the preference, not the character.
    ai_provider_config_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_provider_configs.id", ondelete="SET NULL"), default=None
    )
