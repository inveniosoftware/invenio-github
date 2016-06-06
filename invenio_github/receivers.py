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

from .api import GitHubRelease


class GitHubReceiver(Receiver):
    """Handle incomming notification from GitHub on a new release."""

    verify_sender = False

    def run(self, event):
        """Process an event."""
        release = GitHubRelease(event)
        # Ping event
        if 'hook_id' in event.payload and 'zen' in event.payload:
            release.repository_model.ping = datetime.now()
            db.session.commit()
            return

        # Validate payload sender
        if self.verify_sender and not release.verify_sender():
            raise Exception('Invalid sender for payload %s for user %s' % (
                event.payload, event.user_id
            ))

        release.publish()
        db.session.commit()
