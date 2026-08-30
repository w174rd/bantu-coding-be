# Every model must be imported here. Alembic autogenerate compares the database
# against Base.metadata, and a model that was never imported is absent from it —
# so autogenerate would emit a migration dropping its table.
from app.models.ai_provider_config import AiProviderConfig
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.persona import Persona
from app.models.project import Project
from app.models.ticket import Ticket
from app.models.verdict import Verdict, VerdictOption

__all__ = [
    "AiProviderConfig",
    "Conversation",
    "Message",
    "Persona",
    "Project",
    "Ticket",
    "Verdict",
    "VerdictOption",
]
