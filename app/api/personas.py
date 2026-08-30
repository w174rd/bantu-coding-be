from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.ai_provider_config import AiProviderConfig
from app.models.persona import Persona
from app.schemas.persona import PersonaRead, PersonaUpdate

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


@router.get("", response_model=list[PersonaRead])
def list_personas(db: Session = Depends(get_db)) -> list[Persona]:
    return list(db.scalars(select(Persona).order_by(Persona.display_order)))


@router.patch("/{persona_id}", response_model=PersonaRead)
def update_persona(
    persona_id: int, payload: PersonaUpdate, db: Session = Depends(get_db)
) -> Persona:
    persona = db.get(Persona, persona_id)
    if persona is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    # exclude_unset, so "not sent" and "sent as null" stay different: the second
    # clears the preference and sends the persona back to the active config.
    fields = payload.model_dump(exclude_unset=True)
    if "ai_provider_config_id" in fields:
        config_id = fields["ai_provider_config_id"]
        if config_id is not None and db.get(AiProviderConfig, config_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI provider config not found",
            )
        persona.ai_provider_config_id = config_id

    db.commit()
    db.refresh(persona)
    return persona
