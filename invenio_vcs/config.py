# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2023 CERN.
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

from datetime import timedelta
from typing import TYPE_CHECKING

from flask import current_app

if TYPE_CHECKING:
    from invenio_vcs.providers import RepositoryServiceProviderFactory

VCS_PROVIDERS = []

# GITHUB_WEBHOOK_RECEIVER_URL = None
"""URL format to be used when creating a webhook on GitHub.

This configuration variable must be set explicitly. Example::

    http://localhost:5000/api/receivers/github/events/?access_token={token}

.. note::

    This config variable is used because using `url_for` to get and external
    url of an `invenio_base.api_bluebrint`, while inside the regular app
    context, doesn't work as expected.
"""

# GITHUB_SHARED_SECRET = "CHANGEME"
"""Shared secret between you and GitHub.

Used to make GitHub sign webhook requests with HMAC.

See http://developer.github.com/v3/repos/hooks/#example
"""

# GITHUB_INSECURE_SSL = False
"""Determine if the GitHub webhook request will check the SSL certificate.

Never set to True in a production environment, but can be useful for
development and integration servers.
"""

GITHUB_REFRESH_TIMEDELTA = timedelta(days=1)
"""Time period after which a GitHub account sync should be initiated."""

VCS_RELEASE_CLASS = "invenio_vcs.service:VCSRelease"
"""GitHubRelease class to be used for release handling."""

VCS_TEMPLATE_INDEX = "invenio_vcs/settings/index.html"
"""Repositories list template."""

VCS_TEMPLATE_VIEW = "invenio_vcs/settings/view.html"
"""Repository detail view template."""

GITHUB_ERROR_HANDLERS = None
"""Definition of the way specific exceptions are handled."""

VCS_MAX_CONTRIBUTORS_NUMBER = 30
"""Max number of contributors of a release to be retrieved from Github."""

VCS_INTEGRATION_ENABLED = False
"""Enables the github integration."""

VCS_CITATION_FILE = None
"""Citation file name."""

VCS_CITATION_METADATA_SCHEMA = None
"""Citation metadata schema."""

VCS_ZIPBALL_TIMEOUT = 300
"""Timeout for the zipball download, in seconds."""


def get_provider_list(app=current_app) -> list["RepositoryServiceProviderFactory"]:
    return app.config["VCS_PROVIDERS"]


def get_provider_by_id(id: str) -> "RepositoryServiceProviderFactory":
    providers = get_provider_list()
    for provider in providers:
        if id == provider.id:
            return provider
    raise Exception(f"VCS provider with ID {id} not registered")
