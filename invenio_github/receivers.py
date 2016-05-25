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

import sys

import requests
import six
from invenio_db import db
from invenio_oauth2server.models import Token as ProviderToken
from invenio_webhooks.models import CeleryReceiver

from .helpers import get_account, get_api
from .upload import upload
from .utils import get_contributors, get_extra_metadata, get_owner, init_api, \
    is_valid_sender, remove_hook, revoke_token, submitted_deposition


class GitHubReceiver(CeleryReceiver):
    """Handle incomming notification from GitHub on a new release."""

    verify_sender = True

    def run(self, event):
        """Process an event."""
        # Ping event
        if 'hook_id' in event.payload and 'zen' in event.payload:
            # TODO: record we sucessfully received ping event
            return

        # Get account and internal access token
        account = get_account(user_id=event.user_id)
        gh = get_api(user_id=event.user_id)
        access_token = ProviderToken.query.filter_by(
            id=account.extra_data['tokens']['internal']
        ).first().access_token

        # Validate payload sender
        if self.verify_sender and \
                not is_valid_sender(account.extra_data, event.payload):
            raise Exception('Invalid sender for payload %s for user %s' % (
                event.payload, event.user_id
            ))

        try:
            # Extra metadata from .zenodo.json and github repository
            metadata = extract_metadata(gh, event.payload)

            # Extract zip snapshot from github
            files = extract_files(event.payload,
                                  account.tokens[0].access_token)

            # Upload into Zenodo
            deposition = upload(access_token, metadata, files, publish=True)

            # TODO: Add step to update metadata of all previous records
            submitted_deposition(
                account.extra_data, event.payload['repository']['full_name'],
                deposition, event.payload['release']['tag_name']
            )
            account.extra_data.changed()
            db.session.commit()
            # Send email to user that release was included.
        except Exception as e:
            # Handle errors and possibly send user an email
            # Send email to user
            current_app.logger.exception('Failed handling GitHub payload')
            db.session.commit()
            six.reraise(*sys.exc_info())
