# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
"""
Generic dataclass models to represent the bare minimum necessary data from VCS providers.

These are essentially the "lowest common factor" of
the otherwise large, complex, and heterogenous responses returned by APIs.

These are used by higher-level calls to have a common set of data to
operate on. Provider implementations are responsible for converting API
responses into these generic classes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum

from invenio_vcs.models import Repository


@dataclass
class GenericWebhook:
    """Generic webhook representation."""

    id: str
    repository_id: str
    url: str


@dataclass
class GenericRepository:
    """Generic repository representation."""

    id: str
    full_name: str
    default_branch: str
    description: str | None = None
    license_spdx: str | None = None

    @staticmethod
    def from_model(model: Repository):
        """Create a GenericRepository from a Repository model."""
        return GenericRepository(
            id=model.provider_id,
            full_name=model.full_name,
            default_branch=model.default_branch,
            description=model.description,
            license_spdx=model.license_spdx,
        )

    def to_model(self, model: Repository):
        """Update a Repository model with this generic repository's data."""
        for key, value in asdict(self).items():
            if key in ["id"]:
                continue

            db_value = getattr(model, key)
            if db_value != value:
                setattr(model, key, value)


@dataclass
class GenericRelease:
    """Generic release representation."""

    id: str
    tag_name: str
    created_at: datetime
    name: str | None = None
    body: str | None = None
    tarball_url: str | None = None
    zipball_url: str | None = None
    published_at: datetime | None = None
    """Releases may be published at a different time than when they're created.

    For example, the publication to a package repository (e.g. NPM) may have taken place
    a few minutes before the maintainers published the release on the VCS. The date may
    even be in the future if a release is pre-scheduled (quite common on GitLab).
    """


@dataclass
class GenericUser:
    """Generic user representation."""

    id: str
    username: str
    display_name: str | None = None


class GenericOwnerType(Enum):
    """Types of repository owners."""

    Person = 1
    Organization = 2


@dataclass
class GenericOwner:
    """Generic repository owner representation."""

    id: str
    path_name: str
    type: GenericOwnerType
    display_name: str | None = None


@dataclass
class GenericContributor:
    """Generic contributor representation."""

    id: str
    username: str
    company: str | None = None
    contributions_count: int | None = None
    display_name: str | None = None
