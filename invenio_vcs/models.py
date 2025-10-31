# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Models for the VCS integration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from invenio_accounts.models import User
from invenio_db import db
from invenio_i18n import lazy_gettext as _
from invenio_webhooks.models import Event
from sqlalchemy import UniqueConstraint, delete, insert, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import ChoiceType, JSONType, UUIDType


class ReleaseStatus(Enum):
    """Constants for possible status of a Release."""

    __order__ = "RECEIVED PROCESSING PUBLISHED FAILED DELETED"

    RECEIVED = "R"
    """Release has been received and is pending processing."""

    PROCESSING = "P"
    """Release is still being processed."""

    PUBLISHED = "D"
    """Release was successfully processed and published."""

    FAILED = "F"
    """Release processing has failed."""

    DELETED = "E"
    """Release has been deleted."""

    def __init__(self, value):
        """Hack."""

    def __eq__(self, other):
        """Equality test."""
        return self.value == other

    def __str__(self):
        """Return its value."""
        return self.value


repository_user_association = db.Table(
    "vcs_repository_users",
    db.Model.metadata,
    db.Column(
        "repository_id",
        UUIDType,
        db.ForeignKey("vcs_repositories.id"),
        primary_key=True,
    ),
    db.Column(
        "user_id", db.Integer, db.ForeignKey("accounts_user.id"), primary_key=True
    ),
    db.Column("created", db.DateTime, nullable=False),
    db.Column("updated", db.DateTime, nullable=False),
)


class Repository(db.Model, Timestamp):
    """Information about a vcs repository."""

    __tablename__ = "vcs_repositories"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_id",
            name="uq_vcs_repositories_provider_provider_id",
        ),
        # Index("ix_vcs_repositories_provider_provider_id", "provider", "provider_id"),
    )

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Repository identifier."""

    provider_id = db.Column(
        db.String(255),
        nullable=False,
    )
    """Unique VCS provider identifier for a repository.

    .. note::

        Past implementations of GitHub for Invenio, used the repository name
        (eg. 'inveniosoftware/invenio-github') in order to track repositories.
        This however leads to problems, since repository names can change and
        thus render the stored repository name useless. In order to tackle this
        issue, the `provider_id` should be used to track repositories, which is a
        unique identifier that GitHub uses for each repository and doesn't
        change on renames/transfers.

        In order to be able to keep deleted repositories with releases that
        have been published, it is possible to keep an entry without a
        `provider_id`, that only has a `name`. This only applies to the default
        `github` provider on migrated pre-VCS instances.
    """

    provider = db.Column(db.String(255), nullable=False)
    """Which VCS provider the repository is hosted by (and therefore the context in which to consider the provider_id)"""

    description = db.Column(db.String(10000), nullable=True)
    license_spdx = db.Column(db.String(255), nullable=True)
    default_branch = db.Column(db.String(255), nullable=False)

    full_name = db.Column("name", db.String(255), nullable=False)
    """Fully qualified name of the repository including user/organization."""

    hook = db.Column(db.String(255), nullable=True)
    """Hook identifier."""

    enabled_by_user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)

    #
    # Relationships
    #
    users = db.relationship(User, secondary=repository_user_association)
    enabled_by_user = db.relationship(User, foreign_keys=[enabled_by_user_id])

    @classmethod
    def create(
        cls,
        provider,
        provider_id,
        default_branch,
        full_name=None,
        description=None,
        license_spdx=None,
        **kwargs,
    ):
        """Create the repository."""
        obj = cls(
            provider=provider,
            provider_id=provider_id,
            full_name=full_name,
            default_branch=default_branch,
            description=description,
            license_spdx=license_spdx,
            **kwargs,
        )
        db.session.add(obj)
        return obj

    def add_user(self, user_id: int):
        """Add permission for a user to access the repository."""
        now = datetime.now(tz=timezone.utc)
        stmt = insert(repository_user_association).values(
            repository_id=self.id, user_id=user_id, created=now, updated=now
        )
        db.session.execute(stmt)

    def remove_user(self, user_id: int):
        """Remove permission for a user to access the repository."""
        stmt = delete(repository_user_association).filter_by(
            repository_id=self.id, user_id=user_id
        )
        db.session.execute(stmt)

    def list_users(self):
        """Return a list of users with access to the repository."""
        return db.session.execute(
            select(repository_user_association).filter_by(repository_id=self.id)
        )

    @classmethod
    def get(cls, provider: str, provider_id: str) -> Repository | None:
        """Return a repository given its provider ID.

        :param str provider: Registered ID of the VCS provider.
        :param str provider_id: VCS provider repository identifier.
        :returns: The repository object or None if one with the given ID and provider doesn't exist.
        """
        return cls.query.filter(
            Repository.provider_id == provider_id, Repository.provider == provider
        ).one_or_none()

    @property
    def enabled(self):
        """Return if the repository has webhooks enabled."""
        return bool(self.hook)

    def latest_release(self, status=None):
        """Chronologically latest published release of the repository."""
        # Bail out fast if object (Repository) not in DB session.
        if self not in db.session:
            return None

        q = self.releases if status is None else self.releases.filter_by(status=status)
        return q.order_by(db.desc(Release.created)).first()

    def __repr__(self):
        """Get repository representation."""
        return "<Repository {self.full_name}:{self.provider_id}>".format(self=self)


class Release(db.Model, Timestamp):
    """Information about a VCS release."""

    __tablename__ = "vcs_releases"

    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "provider",
            name="uq_vcs_releases_provider_id_provider",
        ),
    )

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Release identifier."""

    provider_id = db.Column(db.String(255), nullable=True)
    """Unique VCS provider release identifier."""

    provider = db.Column(db.String(255), nullable=False)
    """Which VCS provider the release is hosted by (and therefore the context in which to consider the provider_id)"""

    tag = db.Column(db.String(255))
    """Release tag."""

    errors = db.Column(
        MutableDict.as_mutable(
            db.JSON()
            .with_variant(postgresql.JSONB(), "postgresql")
            .with_variant(JSONType(), "sqlite")
            .with_variant(JSONType(), "mysql")
        ),
        nullable=True,
    )
    """Release processing errors."""

    repository_id = db.Column(UUIDType, db.ForeignKey(Repository.id))
    """Repository identifier."""

    event_id = db.Column(UUIDType, db.ForeignKey(Event.id), nullable=True)
    """Incoming webhook event identifier."""

    record_id = db.Column(
        UUIDType,
        index=True,
        nullable=True,
    )
    """Weak reference to a record identifier."""

    status = db.Column(
        ChoiceType(ReleaseStatus, impl=db.CHAR(1)),
        nullable=False,
    )
    """Status of the release, e.g. 'processing', 'published', 'failed', etc."""

    repository = db.relationship(
        Repository, backref=db.backref("releases", lazy="dynamic")
    )

    event = db.relationship(Event)

    def __repr__(self):
        """Get release representation."""
        return f"<Release {self.tag}:{self.provider_id} ({self.status.title})>"
