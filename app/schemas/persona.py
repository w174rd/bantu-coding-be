from pydantic import BaseModel, ConfigDict

from app.core.enums import PersonaRole


class PersonaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: PersonaRole
    name: str
    avatar: str
    accent_color: str
    tagline: str
    display_order: int
