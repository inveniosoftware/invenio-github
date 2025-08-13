# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
#
# Invenio is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Invenio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Invenio. If not, see <http://www.gnu.org/licenses/>.
#
# In applying this licence, CERN does not waive the privileges and immunities
# granted to it by virtue of its status as an Intergovernmental Organization
# or submit itself to any jurisdiction.

"""Task for managing GitHub integration."""

from invenio_db import db
from invenio_webhooks.models import Receiver

from invenio_vcs.models import Release, ReleaseStatus, Repository
from invenio_vcs.providers import get_provider_by_id
from invenio_vcs.tasks import process_release

from .errors import (
    InvalidSenderError,
    ReleaseAlreadyReceivedError,
    RepositoryAccessError,
    RepositoryDisabledError,
    RepositoryNotFoundError,
)


class VCSReceiver(Receiver):
    """Handle incoming notification from GitHub on a new release."""

    def __init__(self, receiver_id):
        super().__init__(receiver_id)
        self.provider_factory = get_provider_by_id(receiver_id)

    def run(self, event):
        """Process an event.

        .. note::

            We should only do basic server side operation here, since we send
            the rest of the processing to a Celery task which will be mainly
            accessing the GitHub API.
        """
        self._handle_event(event)

    def _handle_event(self, event):
        """Handles an incoming github event."""
        is_create_release_event = self.provider_factory.webhook_is_create_release_event(
            event.payload
        )

        if is_create_release_event:
            self._handle_create_release(event)

    def _handle_create_release(self, event):
        """Creates a release in invenio."""
        try:
            generic_release, generic_repo = (
                self.provider_factory.webhook_event_to_generic(event.payload)
            )

            # Check if the release already exists
            existing_release = Release.query.filter_by(
                provider_id=generic_release.id,
            ).first()

            if existing_release:
                raise ReleaseAlreadyReceivedError(release=existing_release)

            # Create the Release
            repo = Repository.get(generic_repo.id, generic_repo.full_name)
            if not repo:
                raise RepositoryNotFoundError(generic_repo.full_name)

            if repo.enabled:
                release = Release(
                    provider_id=generic_release.id,
                    tag=generic_release.tag_name,
                    repository=repo,
                    event=event,
                    status=ReleaseStatus.RECEIVED,
                )
                db.session.add(release)
            else:
                raise RepositoryDisabledError(repo=repo)

            # Process the release
            # Since 'process_release' is executed asynchronously, we commit the current state of session
            db.session.commit()
            process_release.delay(release.provider_id)

        except (ReleaseAlreadyReceivedError, RepositoryDisabledError) as e:
            event.response_code = 409
            event.response = dict(message=str(e), status=409)
        except (RepositoryAccessError, InvalidSenderError) as e:
            event.response_code = 403
            event.response = dict(message=str(e), status=403)
        except RepositoryNotFoundError as e:
            event.response_code = 404
            event.response = dict(message=str(e), status=404)
