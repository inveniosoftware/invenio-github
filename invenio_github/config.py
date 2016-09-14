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

"""Configuration for GitHub module."""

from copy import deepcopy
from datetime import timedelta

from invenio_oauthclient.contrib.github import REMOTE_APP

GITHUB_WEBHOOK_RECEIVER_ID = 'github'
"""Local name of webhook receiver."""

GITHUB_WEBHOOK_RECEIVER_URL = None
"""URL format to be used when creating a webhook on GitHub.

This configuration variable must be set explicitly. Example::

    http://localhost:5000/api/receivers/github/events/?access_token={token}

.. note::

    This config variable is used because using `url_for` to get and external
    url of an `invenio_base.api_bluebrint`, while inside the regular app
    context, doesn't work as expected.
"""

GITHUB_SHARED_SECRET = 'CHANGEME'
"""Shared secret between you and GitHub.

Used to make GitHub sign webhook requests with HMAC.

See http://developer.github.com/v3/repos/hooks/#example
"""

GITHUB_INSECURE_SSL = False
"""Determine if the GitHub webhook request will check the SSL certificate.

Never set to True in a production environment, but can be useful for
development and integration servers.
"""

GITHUB_REFRESH_TIMEDELTA = timedelta(days=1)
"""Time period after which a GitHub account sync should be initiated."""

GITHUB_RELEASE_CLASS = 'invenio_github.api:GitHubRelease'
"""GitHubRelease class to be used for release handling."""

GITHUB_METADATA_FILE = '.invenio.json'
"""File with extra metadata stored in GitHub repository."""

GITHUB_DEPOSIT_CLASS = 'invenio_deposit.api:Deposit'
"""Deposit class that implements a `publish` method."""

GITHUB_RECORD_SERIALIZER = None
"""Serializer to use to display record metadata."""

GITHUB_PID_FETCHER = 'recid'
"""PID Fetcher for Release records."""

GITHUB_TEMPLATE_INDEX = 'invenio_github/settings/index.html'
"""Repositories list template."""

GITHUB_TEMPLATE_VIEW = 'invenio_github/settings/view.html'
"""Repository detail view template."""

# Copy the default GitHub OAuth application configuration, and update
# handlers and scope.
GITHUB_REMOTE_APP = deepcopy(REMOTE_APP)
"""OAuth Client configuration."""
GITHUB_REMOTE_APP['disconnect_handler'] = 'invenio_github.handlers:disconnect'
GITHUB_REMOTE_APP['signup_handler']['setup'] = \
    'invenio_github.handlers:account_setup'
GITHUB_REMOTE_APP['params']['request_token_params']['scope'] = \
    'user,admin:repo_hook,read:org'
