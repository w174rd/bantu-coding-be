from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.project import Project
from app.models.ticket import Ticket
from app.schemas.conversation import ConversationRead
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.ticket import TicketRead

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _get_or_404(project_id: int, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _reject_duplicate_name(name: str, db: Session) -> None:
    if db.scalar(select(Project.id).where(Project.name == name)) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A project with that name exists"
        )


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)) -> list[Project]:
    return list(db.scalars(select(Project).order_by(Project.id)))


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    _reject_duplicate_name(payload.name, db)
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    return _get_or_404(project_id, db)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db)
) -> Project:
    project = _get_or_404(project_id, db)
    fields = payload.model_dump(exclude_unset=True)
    if "name" in fields and fields["name"] != project.name:
        _reject_duplicate_name(fields["name"], db)
    for field, value in fields.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: int, db: Session = Depends(get_db)) -> None:
    db.delete(_get_or_404(project_id, db))
    db.commit()


@router.get("/{project_id}/tickets", response_model=list[TicketRead])
def list_project_tickets(project_id: int, db: Session = Depends(get_db)) -> list[Ticket]:
    _get_or_404(project_id, db)
    return list(
        db.scalars(select(Ticket).where(Ticket.project_id == project_id).order_by(Ticket.id))
    )


@router.get("/{project_id}/conversations", response_model=list[ConversationRead])
def list_project_conversations(
    project_id: int, db: Session = Depends(get_db)
) -> list[Conversation]:
    _get_or_404(project_id, db)
    return list(
        db.scalars(
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.id.desc())
        )
    )
