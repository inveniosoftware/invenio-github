# -*- coding: utf-8 -*-
# This file is part of Invenio.
# Copyright (C) 2025 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Task for managing vcs integration."""

from invenio_db import db
from invenio_webhooks.models import Receiver

from invenio_vcs.config import get_provider_by_id
from invenio_vcs.models import Release, ReleaseStatus, Repository
from invenio_vcs.tasks import process_release

from .errors import (
    InvalidSenderError,
    ReleaseAlreadyReceivedError,
    RepositoryAccessError,
    RepositoryDisabledError,
    RepositoryNotFoundError,
)


class VCSReceiver(Receiver):
    """Handle incoming notification from vcs on a new release."""

    def __init__(self, receiver_id):
        """Constructor."""
        super().__init__(receiver_id)
        self.provider_factory = get_provider_by_id(receiver_id)

    def run(self, event):
        """Process an event.

        .. note::

            We should only do basic server side operation here, since we send
            the rest of the processing to a Celery task which will be mainly
            accessing the vcs API.
        """
        self._handle_event(event)

    def _handle_event(self, event):
        """Handles an incoming vcs event."""
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
                provider=self.provider_factory.id,
            ).first()

            if existing_release:
                raise ReleaseAlreadyReceivedError(release=existing_release)

            # Create the Release
            repo = Repository.get(
                self.provider_factory.id,
                provider_id=generic_repo.id,
            )
            if not repo:
                raise RepositoryNotFoundError(generic_repo.full_name)

            if repo.enabled:
                release = Release(
                    provider_id=generic_release.id,
                    provider=self.provider_factory.id,
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
            process_release.delay(self.provider_factory.id, release.provider_id)

        except (ReleaseAlreadyReceivedError, RepositoryDisabledError) as e:
            event.response_code = 409
            event.response = dict(message=str(e), status=409)
        except (RepositoryAccessError, InvalidSenderError) as e:
            event.response_code = 403
            event.response = dict(message=str(e), status=403)
        except RepositoryNotFoundError as e:
            event.response_code = 404
            event.response = dict(message=str(e), status=404)
