# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2016 CERN.
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

"""Test GitHub hook."""

from __future__ import absolute_import

import json

import httpretty
from flask import url_for
from invenio_db import db
from invenio_webhooks.models import Event
from mock import MagicMock, patch

from invenio_github.models import Repository


def test_webhook_post(app, db, tester_id, location, remote_token,
                      request_factory):
    """Test payload parsing on webhook."""
    from . import fixtures
    httpretty.enable()
    httpretty.register_uri(
        httpretty.HEAD,
        'https://api.github.com/repos/tester/arepo/zipball/v1.0',
        status=302,
    )
    httpretty.register_uri(
        httpretty.GET,
        'https://api.github.com/repos/tester/arepo/zipball/v1.0',
        body=fixtures.ZIPBALL(stream=True),
        streaming=True,
    )

    with patch('invenio_deposit.api.Deposit.indexer') as fun:
        # Enable repository webhook.
        db.session.add(Repository(name='arepo', enabled=True))
        db.session.commit()

        # JSON payload parsing.
        payload = json.dumps(fixtures.PAYLOAD('tester', 'arepo'))
        headers = [('Content-Type', 'application/json')]
        with app.test_request_context(headers=headers, data=payload):
            event = Event.create(receiver_id='github', user_id=tester_id)
            db.session.commit()
            event.process()
            db.session.commit()

        from invenio_records.models import RecordMetadata
        assert RecordMetadata.query.count() == 2

    httpretty.disable()
