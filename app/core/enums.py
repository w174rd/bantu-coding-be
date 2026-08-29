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
