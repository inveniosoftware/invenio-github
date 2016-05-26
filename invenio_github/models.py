# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
#
# Invenio is free software; you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Invenio is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston,
# MA 02111-1307, USA.
#
# In applying this license, CERN does not
# waive the privileges and immunities granted to it by virtue of its status
# as an Intergovernmental Organization or submit itself to any jurisdiction.

"""Models for GitHub integration."""

from __future__ import absolute_import

import uuid

from flask import abort
from invenio_accounts.models import User
from invenio_db import db
from invenio_records.models import RecordMetadata
from invenio_webhooks.models import Event
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import UUIDType


class Repository(db.Model, Timestamp):
    """Information about a GitHub repository."""

    __tablename__ = 'github_repositories'

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Repository identifier."""

    # TODO shall we use Text instead?
    name = db.Column(db.String(255), unique=True, index=True, nullable=False)
    """Fully qualified name of the repository including user/organization."""

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)
    """Reference user that can manage this repository."""

    enabled = db.Column(db.Boolean, default=False)
    """Mark if a webhook enabled for this repository."""

    ping = db.Column(db.DateTime, nullable=True)
    """Last ping of the repository."""

    hook = db.Column(db.Text)
    """Hook identifier."""

    @classmethod
    def get(cls, name, user_id):
        """Return a repository."""
        repo = cls.query.filter_by(name=name).first()
        if repo and repo.user_id and str(repo.user_id) != str(user_id):
            abort(403)
        return repo

    @classmethod
    def _change_state(cls, name, user_id, enabled=True):
        """Create repository if need be and change its state."""
        repo = cls.get(name, user_id) or Repository(name=name)
        repo.enabled = enabled
        repo.user_id = user_id if enabled else None
        db.session.add(repo)
        return repo

    @classmethod
    def enable(cls, name, user_id):
        """Enable webhooks for a repository.

        If the repository does not exits it will create one. Raises 403
        exception if it tries to enable hook for repository created by
        other user.

        :param name: Fully qualified name of the repository.
        :param user_id: User identifier.
        """
        return cls._change_state(name, user_id, enabled=True)

    @classmethod
    def disable(cls, name, user_id):
        """Disable webhooks for a repository."""
        return cls._change_state(name, user_id, enabled=False)


class Release(db.Model, Timestamp):
    """Information about a GitHub release."""

    __tablename__ = 'github_releases'

    name = db.Column(db.String(255), unique=True, primary_key=True)
    """Release name."""

    repository_id = db.Column(
        UUIDType,
        db.ForeignKey(Repository.id),
        primary_key=True,
    )
    """Repository identifier."""

    event_id = db.Column(
        UUIDType,
        db.ForeignKey(Event.id),
    )
    """Incomming webhook event identifier."""

    record_id = db.Column(
        UUIDType,
        db.ForeignKey(RecordMetadata.id),
        nullable=True,
    )
    """Record identifier."""

    repository = db.relationship(Repository, backref='releases')
    record = db.relationship(RecordMetadata)
    event = db.relationship(Event)
