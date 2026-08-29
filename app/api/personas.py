from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.persona import Persona
from app.schemas.persona import PersonaRead

router = APIRouter(prefix="/api/v1/personas", tags=["personas"])


@router.get("", response_model=list[PersonaRead])
def list_personas(db: Session = Depends(get_db)) -> list[Persona]:
    return list(db.scalars(select(Persona).order_by(Persona.display_order)))
