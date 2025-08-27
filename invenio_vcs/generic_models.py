from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from invenio_vcs.models import Repository


@dataclass
class GenericWebhook:
    id: str
    repository_id: str
    url: str


@dataclass
class GenericRepository:
    id: str
    full_name: str
    default_branch: str
    html_url: str
    description: str | None = None
    license_spdx: str | None = None

    @staticmethod
    def from_model(model: Repository):
        return GenericRepository(
            id=model.provider_id,
            full_name=model.name,
            default_branch=model.default_branch,
            html_url=model.html_url,
            description=model.description,
            license_spdx=model.license_spdx,
        )


@dataclass
class GenericRelease:
    id: str
    tag_name: str
    created_at: datetime
    html_url: str
    name: str | None = None
    body: str | None = None
    tarball_url: str | None = None
    zipball_url: str | None = None
    published_at: datetime | None = None


@dataclass
class GenericUser:
    id: str
    username: str
    display_name: str | None = None


class GenericOwnerType(Enum):
    Person = 1
    Organization = 2


@dataclass
class GenericOwner:
    id: str
    path_name: str
    type: GenericOwnerType
    display_name: str | None = None


@dataclass
class GenericContributor:
    id: str
    username: str
    company: str | None = None
    contributions_count: int | None = None
    display_name: str | None = None
