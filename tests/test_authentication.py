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

from urlparse import parse_qs, urlparse

import httpretty
from flask import url_for
from invenio_db import db
from mock import MagicMock

from . import fixtures


def get_state(url):
    return parse_qs(urlparse(url).query)['state'][0]


def test_bad_verification_code(app, db):
    with app.test_request_context():
        # Test redirect
        client = app.test_client()
        resp = client.get(
            url_for('invenio_oauthclient.login', remote_app='github')
        )
        assert resp.status_code == 302
        assert resp.location.startswith(
            'https://github.com/login/oauth/authorize'
        )
        state = get_state(resp.location)

        httpretty.enable()
        fixtures.register_github_api()

        # Test restart of auth flow when getting a bad_verification_code
        resp = client.get(
            url_for(
                'invenio_oauthclient.authorized',
                remote_app='github',
                code='bad_verification_code',
                state=state,
            )
        )

        assert resp.status_code == 302
        # assert resp.location.endswith(
        #     url_for('invenio_oauthclient.login', remote_app='github')
        # )

    httpretty.disable()
    httpretty.reset()


def test_no_public_email(app, db):
    # Test redirect
    with app.test_request_context():
        client = app.test_client()
        resp = client.get(
            url_for('invenio_oauthclient.login', remote_app='github',
                    next='/mytest/')
        )
        assert resp.status_code == 302
        assert resp.location.startswith(
            'https://github.com/login/oauth/authorize'
        )
        state = get_state(resp.location)

        httpretty.enable()
        fixtures.register_oauth_flow()
        fixtures.register_endpoint(
            '/user',
            fixtures.USER('noemailuser', bio=False)
        )
        fixtures.register_endpoint(
            '/user/emails?per_page=1',
            [
                {
                    'email': None,
                    'verified': True,
                    'primary': True
                }
            ]
        )

        # Assert user is redirect to page requesting email address
        resp = client.get(
            url_for(
                'invenio_oauthclient.authorized',
                remote_app='github',
                code='test_no_email',
                state=state,
            )
        )
        assert resp.location == url_for(
            'invenio_oauthclient.signup', remote_app='github', _external=True
        )

        # Mock account setup to prevent GitHub queries
        from invenio_oauthclient.proxies import current_oauthclient
        current_oauthclient.signup_handlers['github']['setup'] = MagicMock()

        resp = client.post(
            url_for(
                'invenio_oauthclient.signup',
                remote_app='github',
            ),
            data={'email': 'noemailuser@inveniosoftware.org'}
        )
        assert resp.location.endswith('/mytest/')

        from invenio_accounts.models import User
        assert User.query.filter_by(
            email='noemailuser@inveniosoftware.org'
        ).count() == 1

    httpretty.disable()
    httpretty.reset()
