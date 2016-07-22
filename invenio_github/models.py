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
from datetime import datetime

from enum import Enum
from invenio_accounts.models import User
from invenio_db import db
from invenio_records.models import RecordMetadata
from invenio_webhooks.models import Event
from sqlalchemy.dialects import postgresql
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import ChoiceType, JSONType, UUIDType


def _(text):
    """Identity function for `gettext`."""
    # FIXME: Replace with `speaklater.make_lazy_gettext`
    return text


RELEASE_STATUS_TITLES = {
    'RECEIVED': _('Received'),
    'PROCESSING': _('Processing'),
    'PUBLISHED': _('Published'),
    'FAILED': _('Failed'),
}

RELEASE_STATUS_ICON = {
    'RECEIVED': 'fa-inbox',
    'PROCESSING': 'fa-cog',
    'PUBLISHED': 'fa-check',
    'FAILED': 'fa-times',
}

RELEASE_STATUS_COLOR = {
    'RECEIVED': 'info',
    'PROCESSING': 'warning',
    'PUBLISHED': 'success',
    'FAILED': 'danger',
}


class ReleaseStatus(Enum):
    """Constants for possible status of a Release."""

    __order__ = 'RECEIVED PROCESSING PUBLISHED FAILED'

    RECEIVED = 'R'
    """Release has been received and is pending processing."""

    PROCESSING = 'P'
    """Release is still being processed."""

    PUBLISHED = 'D'
    """Release was successfully processed and published."""

    FAILED = 'F'
    """Release processing has failed."""

    def __init__(self, value):
        """Hack."""

    def __eq__(self, other):
        """Equality test."""
        return self.value == other

    def __str__(self):
        """Return its value."""
        return self.value

    @property
    def title(self):
        """Return human readable title."""
        return RELEASE_STATUS_TITLES[self.name]

    @property
    def icon(self):
        """Font Awesome status icon."""
        return RELEASE_STATUS_ICON[self.name]

    @property
    def color(self):
        """UI status color."""
        return RELEASE_STATUS_COLOR[self.name]


class Repository(db.Model, Timestamp):
    """Information about a GitHub repository."""

    __tablename__ = 'github_repositories'

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Repository identifier."""

    github_id = db.Column(
        db.Integer,
        unique=True,
        index=True,
        nullable=True,
    )
    """Unique GitHub identifier for a repository.

    Note: Past implementations of GitHub for Invenio, used the repository name
    (eg. 'inveniosoftware/invenio-github') in order to track repositories. This
    however leads to problems, since repository names can change and thus
    render the stored repository name useless. In order to tackle this issue,
    the `github_id` should be used to track repositories, which is a unique
    identifier that GitHub uses for each repository and doesn't change on
    renames/transfers.

    In order to be able to keep deleted repositories with releases that have
    been published, it is possible to keep an entry without a `github_id`,
    that only has a `name`.
    """

    # TODO shall we use Text instead?
    name = db.Column(db.String(255), unique=True, index=True, nullable=False)
    """Fully qualified name of the repository including user/organization."""

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)
    """Reference user that can manage this repository."""

    # FIXME: Remove `enabled` and add as property that checks the `hook` field?
    enabled = db.Column(db.Boolean, default=False)
    """Mark if a webhook is enabled for this repository."""

    ping = db.Column(db.DateTime, nullable=True)
    """Last ping of the repository."""

    hook = db.Column(db.Integer)
    """Hook identifier."""

    #
    # Relationships
    #
    user = db.relationship(User)

    @classmethod
    def get_or_create(cls, user_id, github_id=None, name=None, **kwargs):
        """Get or create the repository."""
        obj = cls.get(user_id, github_id=github_id, name=name)
        if not obj:
            obj = cls.create(user_id, github_id=github_id, name=name, **kwargs)
        return obj

    @classmethod
    def create(cls, user_id, github_id=None, name=None, **kwargs):
        """Create the repository."""
        with db.session.begin_nested():
            obj = cls(user_id=user_id, github_id=github_id, name=name,
                      **kwargs)
            db.session.add(obj)
        return obj

    @classmethod
    def get(cls, user_id, github_id=None, name=None):
        """Return a repository."""
        repo = cls.query.filter((Repository.github_id == github_id) |
                                (Repository.name == name)).first()
        if repo and repo.user_id and str(repo.user_id) != str(user_id):
            raise Exception('Access forbidden for this repository.')
        return repo

    @classmethod
    def enable(cls, user_id, github_id, name):
        """Enable webhooks for a repository.

        If the repository does not exist it will create one. Raises 403
        exception if it tries to enable hook for repository created by
        other user.

        :param user_id: User identifier.
        :param repo_id: GitHub id of the repository.
        :param name: Fully qualified name of the repository.
        """
        repo = cls.get_or_create(user_id, github_id=github_id, name=name)
        repo.enabled = True
        repo.user_id = user_id
        db.session.add(repo)
        return repo

    @classmethod
    def disable(cls, user_id, github_id, name):
        """Disable webhooks for a repository.

        Disables the webhook from a repository if its exists in the DB.

        :param user_id: User identifier.
        :param repo_id: GitHub id of the repository.
        :param name: Fully qualified name of the repository.
        """
        repo = cls.get(user_id, github_id=github_id, name=name)
        if repo:
            repo.enabled = False
            repo.user_id = None
            repo.hook = None
            db.session.add(repo)
        return repo

    @classmethod
    def update_ping(cls, repo_id):
        """Update ping to current time."""
        repository = cls.query.filter_by(
            github_id=repo_id,
            enabled=True,
        ).one()
        repository.ping = datetime.utcnow()
        db.session.commit()

    @property
    def latest_release(self):
        """Chronologically latest published release of the repository."""
        return self.releases.filter_by(
            status=ReleaseStatus.PUBLISHED).order_by('created desc').first()


class Release(db.Model, Timestamp):
    """Information about a GitHub release."""

    __tablename__ = 'github_releases'

    id = db.Column(
        UUIDType,
        primary_key=True,
        default=uuid.uuid4,
    )
    """Release identifier."""

    release_id = db.Column(db.Integer, unique=True, nullable=True)
    """Unique GitHub release identifier."""

    tag = db.Column(db.String(255))
    """Release tag."""

    errors = db.Column(
        JSONType().with_variant(
            postgresql.JSON(none_as_null=True),
            'postgresql',
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
        db.ForeignKey(RecordMetadata.id),
        nullable=True,
    )
    """Record identifier."""

    status = db.Column(
        ChoiceType(ReleaseStatus, impl=db.CHAR(1)),
        nullable=False,
    )
    """Status of the release, e.g. 'processing', 'published', 'failed', etc."""

    repository = db.relationship(
        Repository,
        backref=db.backref('releases', lazy='dynamic')
    )
    record = db.relationship(RecordMetadata)
    event = db.relationship(Event)

    @classmethod
    def create(cls, event):
        """Create a new Release model."""
        release_id = event.payload['release']['id']

        # Check if the release has already been received
        existing_release = Release.query.filter_by(
            release_id=release_id,
        ).first()
        if existing_release:
            msg = ('Release [{tag}:{release_id}] has already been received '
                   'with status {status}.')
            raise Exception(msg.format(tag=existing_release.tag,
                                       release_id=release_id,
                                       status=existing_release.status.title))

        # Check if the release corresponds to a repository in our database
        repo_id = event.payload['repository']['id']
        repository = Repository.get(user_id=event.user_id, github_id=repo_id)
        if repository:
            # Create the Release
            with db.session.begin_nested():
                release = cls(
                    release_id=release_id,
                    tag=event.payload['release']['tag_name'],
                    repository=repository,
                    event=event,
                    status=ReleaseStatus.RECEIVED,
                )
                db.session.add(release)
            return release
        else:
            msg = 'Repository [{repo_name}:{repo_id}] is not enabled.'
            raise Exception(
                msg.format(repo_name=event.payload['repository']['full_name'],
                           repo_id=repo_id))

    @property
    def doi(self):
        """Get DOI of Release from record metadata."""
        if self.record:
            return self.record.json.get('doi')
