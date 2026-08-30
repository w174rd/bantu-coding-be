import pytest
from pydantic import ValidationError

from app.core.enums import TicketStatus
from app.schemas.ticket import TicketCreate, TicketUpdate


def test_board_columns_are_exactly_these_four_in_order():
    assert [status.value for status in TicketStatus] == [
        "backlog",
        "in_progress",
        "in_review",
        "done",
    ]


def test_create_requires_a_non_empty_title():
    with pytest.raises(ValidationError):
        TicketCreate(project_id=1, title="")


def test_create_defaults_body_to_none():
    assert TicketCreate(project_id=1, title="Add a login form").body is None


def test_update_cannot_move_a_ticket_between_projects():
    # Reassigning a ticket is a different feature; PATCH silently ignoring the field
    # would look like it worked.
    assert "project_id" not in TicketUpdate.model_fields


def test_update_distinguishes_omitted_from_explicit_null():
    omitted = TicketUpdate().model_dump(exclude_unset=True)
    explicit = TicketUpdate(body=None).model_dump(exclude_unset=True)

    assert omitted == {}
    assert explicit == {"body": None}


def test_update_rejects_a_status_outside_the_board():
    with pytest.raises(ValidationError):
        TicketUpdate(status="archived")


def test_update_accepts_each_board_column():
    for status in TicketStatus:
        assert TicketUpdate(status=status.value).status is status
