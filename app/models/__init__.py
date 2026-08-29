# Every model must be imported here. Alembic autogenerate compares the database
# against Base.metadata, and a model that was never imported is absent from it —
# so autogenerate would emit a migration dropping its table.
from app.models.ticket import Ticket

__all__ = ["Ticket"]
