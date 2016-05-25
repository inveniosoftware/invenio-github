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

from __future__ import absolute_import

import json
from functools import partial

import httpretty
import six
from invenio_db import db

from . import fixtures


def FIXME_test_handle_payload(app, db, tester_id, remote_token):
    from invenio_webhooks.models import Event

    httpretty.enable()
    extra_data = remote_token.remote_account.extra_data
    assert 'auser/repo-1' in extra_data['repos']
    assert 'auser/repo-2' in extra_data['repos']

    assert len(extra_data['repos']['auser/repo-1']['depositions']) == 0
    assert len(extra_data['repos']['auser/repo-2']['depositions']) == 0

    event = Event(
        receiver_id='github',
        user_id=tester_id,
        payload=fixtures.PAYLOAD('auser', 'repo-1')
    )
    db.session.add(event)
    db.session.commit()

    event.process()

    db.session.expire(remote_token.remote_account)
    extra_data = self.remote_token.remote_account.extra_data
    assert len(extra_data['repos']['auser/repo-1']['depositions']) == 1
    assert len(extra_data['repos']['auser/repo-2']['depositions']) == 0

    dep = extra_data['repos']['auser/repo-1']['depositions'][0]

    assert dep['doi'].endswith(six.text_type(dep['record_id']))
    assert dep['errors'] is None
    assert dep['github_ref'] == "v1.0"


def test_extract_files(app, db, remote_token, request_factory):
    from invenio_github.tasks import extract_files

    httpretty.enable()
    files = extract_files(
        fixtures.PAYLOAD('auser', 'repo-1', tag='v1.0'),
        remote_token.access_token
    )
    assert len(files) == 1

    fileobj, filename = files[0]
    assert filename == "repo-1-v1.0.zip"


def test_extract_metadata(app, db, tester_id, request_factory):
    from invenio_github.tasks import extract_metadata
    from invenio_github.helpers import get_api

    gh = get_api(user_id=tester_id)

    # Mock up responses
    httpretty.enable()
    fixtures.register_endpoint(
        "/repos/auser/repo-2",
        fixtures.REPO('auser', 'repo-2'),
    )
    fixtures.register_endpoint(
        "/repos/auser/repo-2/contents/.zenodo.json",
        fixtures.CONTENT(
            'auser', 'repo-2', '.zenodo.json', 'v1.0',
            json.dumps(dict(
                upload_type='dataset',
                license='mit-license',
                creators=[
                    dict(name='Smith, Joe', affiliation='CERN'),
                    dict(name='Smith, Joe', affiliation='CERN')
                ]
            ))
        )
    )

    metadata = extract_metadata(
        gh,
        fixtures.PAYLOAD('auser', 'repo-2', tag='v1.0'),
    )

    assert metadata['upload_type'] == 'dataset'
