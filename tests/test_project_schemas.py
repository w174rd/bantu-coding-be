import pytest
from pydantic import ValidationError

from app.schemas.conversation import ConversationCreate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.ticket import TicketCreate


def test_create_requires_a_non_empty_name():
    with pytest.raises(ValidationError):
        ProjectCreate(name="")


def test_a_name_is_enough():
    project = ProjectCreate(name="Bantu Coding")

    assert project.repo_url is None
    assert project.default_branch is None


def test_repo_url_accepts_an_https_url():
    assert ProjectCreate(name="p", repo_url="https://example.com/owner/repo").repo_url


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/owner/repo",
        "ssh://git@example.com/owner/repo",
        "git@example.com:owner/repo.git",
        "file:///etc/passwd",
        "/etc/passwd",
    ],
)
def test_repo_url_rejects_anything_but_https(url):
    # A run's target comes from a typed column (CLAUDE.md section 6.4). A column that
    # also accepts a local path or an arbitrary scheme is not that guarantee.
    with pytest.raises(ValidationError):
        ProjectCreate(name="p", repo_url=url)


def test_update_distinguishes_omitted_from_explicit_null():
    omitted = ProjectUpdate().model_dump(exclude_unset=True)
    explicit = ProjectUpdate(repo_url=None).model_dump(exclude_unset=True)

    assert omitted == {}
    assert explicit == {"repo_url": None}


def test_update_still_refuses_a_bad_repo_url():
    with pytest.raises(ValidationError):
        ProjectUpdate(repo_url="http://example.com/owner/repo")


def test_a_ticket_cannot_be_created_without_a_project():
    with pytest.raises(ValidationError):
        TicketCreate(title="Add a login form")


def test_a_conversation_cannot_be_created_without_a_project():
    with pytest.raises(ValidationError):
        ConversationCreate(title="Rate limiting")
