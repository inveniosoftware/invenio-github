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
from enum import Enum

from flask import current_app
from flask_babelex import lazy_gettext as _
from invenio_accounts.models import User
from invenio_db import db
from invenio_records.api import Record
from invenio_records.models import RecordMetadata
from invenio_webhooks.models import Event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy_utils.models import Timestamp
from sqlalchemy_utils.types import ChoiceType, JSONType, UUIDType

from .errors import ReleaseAlreadyReceivedError, RepositoryAccessError, \
    RepositoryDisabledError

RELEASE_STATUS_TITLES = {
    'RECEIVED': _('Received'),
    'PROCESSING': _('Processing'),
    'PUBLISHED': _('Published'),
    'FAILED': _('Failed'),
}

RELEASE_STATUS_ICON = {
    'RECEIVED': 'fa-spinner',
    'PROCESSING': 'fa-spinner',
    'PUBLISHED': 'fa-check',
    'FAILED': 'fa-times',
}

RELEASE_STATUS_COLOR = {
    'RECEIVED': 'default',
    'PROCESSING': 'default',
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

    .. note::

        Past implementations of GitHub for Invenio, used the repository name
        (eg. 'inveniosoftware/invenio-github') in order to track repositories.
        This however leads to problems, since repository names can change and
        thus render the stored repository name useless. In order to tackle this
        issue, the `github_id` should be used to track repositories, which is a
        unique identifier that GitHub uses for each repository and doesn't
        change on renames/transfers.

        In order to be able to keep deleted repositories with releases that
        have been published, it is possible to keep an entry without a
        `github_id`, that only has a `name`.
    """

    name = db.Column(db.String(255), unique=True, index=True, nullable=False)
    """Fully qualified name of the repository including user/organization."""

    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=True)
    """Reference user that can manage this repository."""

    ping = db.Column(db.DateTime, nullable=True)
    """Last ping of the repository."""

    hook = db.Column(db.Integer)
    """Hook identifier."""

    #
    # Relationships
    #
    user = db.relationship(User)

    @classmethod
    def create(cls, user_id, github_id=None, name=None, **kwargs):
        """Create the repository."""
        with db.session.begin_nested():
            obj = cls(user_id=user_id, github_id=github_id, name=name,
                      **kwargs)
            db.session.add(obj)
        return obj

    @classmethod
    def get(cls, user_id, github_id=None, name=None, check_owner=True):
        """Return a repository.

        :param integer user_id: User identifier.
        :param integer github_id: GitHub repository identifier.
        :param str name: GitHub repository full name.
        :returns: The repository object.
        :raises: :py:exc:`~sqlalchemy.orm.exc.NoResultFound`: if the repository
                 doesn't exist.
        :raises: :py:exc:`~sqlalchemy.orm.exc.MultipleResultsFound`: if
                 multiple repositories with the specified GitHub id and/or name
                 exist.
        :raises: :py:exc:`RepositoryAccessError`: if the user is not the owner
                 of the repository.
        """
        repo = cls.query.filter((Repository.github_id == github_id) |
                                (Repository.name == name)).one()
        if check_owner and repo and repo.user_id and repo.user_id != user_id:
            raise RepositoryAccessError(
                'User {user} cannot access repository {repo}({repo_id}).'
                .format(user=user_id, repo=name, repo_id=github_id)
            )
        return repo

    @classmethod
    def enable(cls, user_id, github_id, name, hook):
        """Enable webhooks for a repository.

        If the repository does not exist it will create one.

        :param user_id: User identifier.
        :param repo_id: GitHub repository identifier.
        :param name: Fully qualified name of the repository.
        :param hook: GitHub hook identifier.
        """
        try:
            repo = cls.get(user_id, github_id=github_id, name=name)
        except NoResultFound:
            repo = cls.create(user_id=user_id, github_id=github_id, name=name)
        repo.hook = hook
        repo.user_id = user_id
        return repo

    @classmethod
    def disable(cls, user_id, github_id, name):
        """Disable webhooks for a repository.

        Disables the webhook from a repository if it exists in the DB.

        :param user_id: User identifier.
        :param repo_id: GitHub id of the repository.
        :param name: Fully qualified name of the repository.
        """
        repo = cls.get(user_id, github_id=github_id, name=name)
        repo.hook = None
        repo.user_id = None
        return repo

    @property
    def enabled(self):
        """Return if the repository has webhooks enabled."""
        return bool(self.hook)

    def latest_release(self, status=None):
        """Chronologically latest published release of the repository."""
        # Bail out fast if object not in DB session.
        if self not in db.session:
            return None
        q = self.releases if status is None else self.releases.filter_by(
            status=status)
        return q.order_by(db.desc(Release.created)).first()

    def __repr__(self):
        """Get repository representation."""
        return '<Repository {self.name}:{self.github_id}>'.format(self=self)


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

    recordmetadata = db.relationship(RecordMetadata)
    event = db.relationship(Event)

    @classmethod
    def create(cls, event):
        """Create a new Release model."""
        # Check if the release has already been received
        release_id = event.payload['release']['id']
        existing_release = Release.query.filter_by(
            release_id=release_id,
        ).first()
        if existing_release:
            raise ReleaseAlreadyReceivedError(
                '{release} has already been received.'
                .format(release=existing_release)
            )

        # Create the Release
        repo_id = event.payload['repository']['id']
        repo = Repository.get(user_id=event.user_id, github_id=repo_id)
        if repo.enabled:
            with db.session.begin_nested():
                release = cls(
                    release_id=release_id,
                    tag=event.payload['release']['tag_name'],
                    repository=repo,
                    event=event,
                    status=ReleaseStatus.RECEIVED,
                )
                db.session.add(release)
            return release
        else:
            current_app.logger.warning(
                'Release creation attempt on disabled {repo}.'
                .format(repo=repo)
            )
            raise RepositoryDisabledError(
                '{repo} is not enabled for webhooks.'.format(repo=repo)
            )

    @property
    def record(self):
        """Get Record object."""
        if self.recordmetadata:
            return Record(self.recordmetadata.json, model=self.recordmetadata)
        else:
            return None

    @property
    def deposit_id(self):
        """Get deposit identifier."""
        if self.record and '_deposit' in self.record:
            return self.record['_deposit']['id']
        else:
            return None

    def __repr__(self):
        """Get release representation."""
        return ('<Release {self.tag}:{self.release_id} ({self.status.title})>'
                .format(self=self))
