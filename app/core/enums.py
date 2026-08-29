from enum import Enum


class TicketStatus(str, Enum):
    """The board's columns, in order.

    Adding a value here is a product decision and requires a migration —
    the database column is a native Postgres enum, not free text.
    """

    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"


class PersonaRole(str, Enum):
    """The four characters in a discussion room.

    Same rule as TicketStatus: a native Postgres enum, so a fifth character is a
    migration and a product decision.
    """

    ARCHITECT = "architect"
    RESEARCHER = "researcher"
    CHALLENGER = "challenger"
    ARBITER = "arbiter"


class MessageAuthorKind(str, Enum):
    """Who put a message in the room.

    DOCUMENT is text the user uploaded rather than typed; it is kept distinct
    from USER so the room can show its provenance.
    """

    USER = "user"
    PERSONA = "persona"
    DOCUMENT = "document"
