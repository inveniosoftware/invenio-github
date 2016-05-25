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

"""Implement OAuth client handler."""

from __future__ import absolute_import

from flask import current_app, redirect, url_for
from flask_login import current_user
from invenio_oauthclient.errors import OAuthResponseError
from invenio_oauthclient.handlers import authorized_signup_handler, \
    oauth_error_handler
from invenio_oauthclient.models import RemoteToken

from ..tasks import disconnect_github
from ..utils import init_account, init_api


def account_info(remote, resp):
    """Extract account information."""
    gh = init_api(resp['access_token'])
    ghuser = gh.user()
    return dict(email=ghuser.email, nickname=ghuser.login)


def account_setup(remote, token):
    """Setup user account."""
    init_account(token)


@oauth_error_handler
def authorized(resp, remote):
    """Authorized callback handler for GitHub."""
    if resp and 'error' in resp:
        if resp['error'] == 'bad_verification_code':
            # See https://developer.github.com/v3/oauth/#bad-verification-code
            # which recommends starting auth flow again.
            return redirect(url_for('oauthclient.login', remote_app='github'))
        elif resp['error'] in ['incorrect_client_credentials',
                               'redirect_uri_mismatch']:
            raise OAuthResponseError(
                "Application mis-configuration in GitHub", remote, resp
            )

    return authorized_signup_handler(resp, remote)


def disconnect(remote):
    """Disconnect callback handler for GitHub.

    This is a test!
    """
    # User must be authenticated
    if not current_user.is_authenticated():
        return current_app.login_manager.unauthorized()

    token = RemoteToken.get(current_user.get_id(), remote.consumer_key)

    if token:
        disconnect_github.delay(
            remote.name, token.access_token, token.remote_account.extra_data
        )
        token.remote_account.delete()

    return redirect(url_for('oauthclient_settings.index'))


def signup(remote):
    """Signup callback handler for GitHub."""
    pass
