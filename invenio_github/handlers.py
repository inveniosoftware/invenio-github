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

import github3
from flask import current_app, redirect, url_for
from flask_login import current_user
from invenio_oauthclient.models import RemoteToken
from invenio_oauthclient.signals import account_setup_received

from .api import GitHubAPI
from .tasks import disconnect_github


def account_setup(remote, token=None, response=None,
                  account_setup=None):
    """Setup user account."""
    GitHubAPI(user_id=token.remote_account.user_id).init_account()


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
