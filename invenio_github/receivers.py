# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2014, 2015, 2016 CERN.
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

from __future__ import absolute_import

from datetime import datetime

from invenio_db import db
from invenio_webhooks.models import Receiver

from .errors import ReleaseAlreadyReceivedError, RepositoryAccessError, \
    RepositoryDisabledError
from .models import Release, Repository
from .tasks import process_release


class GitHubReceiver(Receiver):
    """Handle incoming notification from GitHub on a new release."""

    verify_sender = False

    def run(self, event):
        """Process an event.

        .. note::

            We should only do basic server side operation here, since we send
            the rest of the processing to a Celery task which will be mainly
            accessing the GitHub API.
        """
        repo_id = event.payload['repository']['id']

        # Ping event - update the ping timestamp of the repository
        if 'hook_id' in event.payload and 'zen' in event.payload:
            repository = Repository.query.filter_by(
                github_id=repo_id
            ).one()
            repository.ping = datetime.utcnow()
            db.session.commit()
            return

        # Release event
        if 'release' in event.payload:
            try:
                release = Release.create(event)
                db.session.commit()

                # FIXME: If we want to skip the processing, we should do it
                # here (eg. We're in the middle of a migration).
                # if current_app.config['GITHUB_PROCESS_RELEASES']:
                process_release.delay(
                    release.release_id,
                    verify_sender=self.verify_sender
                )
            except (ReleaseAlreadyReceivedError, RepositoryDisabledError) as e:
                event.response_code = 409
                event.response = dict(message=str(e), status=409)
            except RepositoryAccessError as e:
                event.response = 403
                event.response = dict(message=str(e), status=403)
