# SPDX-FileCopyrightText: 2023 CERN.
# SPDX-License-Identifier: MIT

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


class GitHubReceiver(Receiver):
    """Handle incoming notification from GitHub on a new release."""

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

        except (ReleaseAlreadyReceivedError, RepositoryDisabledError) as e:
            event.response_code = 409
            event.response = dict(message=str(e), status=409)
        except (RepositoryAccessError, InvalidSenderError) as e:
            event.response_code = 403
            event.response = dict(message=str(e), status=403)
        except RepositoryNotFoundError as e:
            event.response_code = 404
            event.response = dict(message=str(e), status=404)
