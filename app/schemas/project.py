from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _https_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value)
    # Not cosmetic. CLAUDE.md section 6.4 requires a run's target to come from a typed
    # column; a column that also accepts file:// or ssh:// is not the guarantee it looks
    # like, so the schema is where the scheme is pinned.
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("repo_url must be an https:// URL")
    return value


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    repo_url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, max_length=100)

    _validate_repo_url = field_validator("repo_url")(_https_url)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    repo_url: str | None = Field(default=None, max_length=500)
    default_branch: str | None = Field(default=None, max_length=100)

    _validate_repo_url = field_validator("repo_url")(_https_url)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    repo_url: str | None
    default_branch: str | None
    created_at: datetime
    updated_at: datetime
