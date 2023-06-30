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

from invenio_github.models import Release, ReleaseStatus, Repository
from invenio_github.tasks import process_release

from .errors import (
    InvalidSenderError,
    ReleaseAlreadyReceivedError,
    RepositoryAccessError,
    RepositoryDisabledError,
    RepositoryNotFoundError,
)

state = {}


class GitHubReceiver(Receiver):
    """Handle incoming notification from GitHub on a new release."""

    def run(self, event):
        """Process an event.

        .. note::

            We should only do basic server side operation here, since we send
            the rest of the processing to a Celery task which will be mainly
            accessing the GitHub API.
        """
        try:
            self._handle_event(event)
        except Exception as e:
            # Event failed to be processed and error was not handled yet
            if not event.response or event.response_code < 400:
                event.response = {"status": 500, "message": str(e)}
                event.response_code = 500
            # Other cases were already handled (e.g. response/response_code were set by the event handler)

    def _handle_event(self, event):
        """Handles an incoming github event."""
        action = event.payload.get("action")
        is_draft_release = event.payload.get("release", {}).get("draft")

        # Draft releases do not create releases on invenio
        is_create_release_event = (
            action in ("published", "released", "created") and not is_draft_release
        )

        if is_create_release_event:
            self._handle_create_release(event)
        else:
            pass

    def _handle_create_release(self, event):
        """Creates a release in invenio."""
        try:
            release_id = event.payload["release"]["id"]
            if release_id in state:
                raise ReleaseAlreadyReceivedError()

            # Lock event release to avoid concurrent processing
            state.update({release_id: event})

            # Check if the release already exists
            existing_release = Release.query.filter_by(
                release_id=release_id,
            ).first()

            if existing_release:
                raise ReleaseAlreadyReceivedError(release=existing_release)

            # Create the Release
            repo_id = event.payload["repository"]["id"]
            repo_name = event.payload["repository"]["name"]
            repo = Repository.get(repo_id, repo_name)
            if not repo:
                raise RepositoryNotFoundError(repo_name)

            if repo.enabled:
                release = Release(
                    release_id=release_id,
                    tag=event.payload["release"]["tag_name"],
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
            process_release.delay(release.release_id)

            # Unlock the event release
            del state[release_id]
        except (ReleaseAlreadyReceivedError, RepositoryDisabledError) as e:
            event.response_code = 409
            event.response = dict(message=str(e), status=409)
        except (RepositoryAccessError, InvalidSenderError) as e:
            event.response_code = 403
            event.response = dict(message=str(e), status=403)
        except RepositoryNotFoundError as e:
            event.response_code = 404
            event.response = dict(message=str(e), status=404)
