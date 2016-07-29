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

from invenio_db import db
from invenio_webhooks.models import Receiver

from .models import Release, Repository
from .tasks import process_release


class GitHubReceiver(Receiver):
    """Handle incoming notification from GitHub on a new release."""

    verify_sender = False

    def run(self, event):
        """Process an event.

        We should only do quick and easy things here, since we send the
        rest of the processing to a Celery task. Thus, we should only do stuff
        that doesn't depend on accessing the GitHub API in any way.
        """
        repo_id = event.payload['repository']['id']

        # Ping event - update the ping timestamp of the repository
        if 'hook_id' in event.payload and 'zen' in event.payload:
            Repository.update_ping(repo_id=repo_id)
            return

        # Release event
        if 'release' in event.payload:
            repo = Repository.get(user_id=event.user_id, github_id=repo_id)
            if repo:
                release = Release.create(event)
            else:
                raise Exception('Repository does not exist...')
            repo.releases.append(release)
            db.session.commit()

            # FIXME: If we want to skip the processing, we should do it here
            # (eg. We're in the middle of a migration).
            # if current_app.config['GITHUB_PROCESS_RELEASES']:
            process_release.delay(
                release.release_id,
                verify_sender=self.verify_sender
            )
