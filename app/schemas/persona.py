from pydantic import BaseModel, ConfigDict

from app.core.enums import PersonaRole


class PersonaUpdate(BaseModel):
    # The only mutable field. Role, name, avatar and colour are seeded identity
    # rather than user settings, so they are deliberately absent.
    ai_provider_config_id: int | None = None


class PersonaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: PersonaRole
    name: str
    avatar: str
    accent_color: str
    tagline: str
    display_order: int
    ai_provider_config_id: int | None
